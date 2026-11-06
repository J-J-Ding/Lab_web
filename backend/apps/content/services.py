import re
from difflib import SequenceMatcher
from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import PermissionDenied,ValidationError
from apps.accounts.models import User
from apps.accounts.permissions import is_manager
from apps.workflow.audit import record
from .models import ContentItem,ContentRevision,ContentIdentifier,DETAIL_MODELS,Contributor,RevisionContribution
from .types import CONTRIBUTION_ROLES
from .serializers import validate_detail


def normalize_identifier(scheme, value):
    if not isinstance(value,str):
        raise ValidationError({'identifier':'Expected text.'})
    value=value.strip()
    if scheme=='DOI':
        value=re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)','',value,flags=re.I)
        value=re.sub(r'\s+','',value).lower()
        if not re.fullmatch(r'10\.\d{4,9}/\S+',value):
            raise ValidationError({'doi':'Invalid DOI.'})
    elif scheme=='ISBN':
        value=re.sub(r'[-\s]','',value).upper()
        if len(value)==13 and value.isdigit():
            valid=sum(int(c)*(1 if i%2==0 else 3) for i,c in enumerate(value))%10==0
        elif len(value)==10 and value[:9].isdigit() and (value[-1].isdigit() or value[-1]=='X'):
            valid=sum((10-i)*(10 if c=='X' else int(c)) for i,c in enumerate(value))%11==0
        else:
            valid=False
        if not valid:
            raise ValidationError({'isbn':'Invalid ISBN checksum.'})
    elif scheme=='PROJECT':
        value=re.sub(r'\s+','',value).upper()
    elif scheme=='PAGE' and value not in ('home','about','contact'):
        raise ValidationError({'page_key':'Invalid page key.'})
    if not value or len(value)>255:
        raise ValidationError({'identifier':'Invalid identifier length.'})
    return value


def locked_editor(actor):
    user=User.objects.select_for_update().get(pk=actor.pk)
    if not user.is_active:
        raise PermissionDenied()
    if is_manager(user):
        return user
    if user.role=='STUDENT':
        return user
    raise PermissionDenied('An active membership is required.')


@transaction.atomic
def create_content(actor, kind, title, detail, summary=''):
    actor=locked_editor(actor)
    if kind not in DETAIL_MODELS:
        raise ValidationError({'kind':'Unsupported content kind.'})
    if not isinstance(title,str) or not title.strip() or len(title)>500:
        raise ValidationError({'title':'A title of 1–500 characters is required.'})
    if not isinstance(summary,str) or len(summary)>10000:
        raise ValidationError({'summary':'Invalid summary.'})
    data=validate_detail(kind,detail)
    scheme_field={'PAPER':('DOI','doi'),'PROJECT':('PROJECT','project_number'),'PUBLICATION':('ISBN','isbn'),'LAB_PAGE':('PAGE','page_key')}.get(kind)
    identifier=None
    if scheme_field:
        scheme,field=scheme_field
        if data.get(field):
            data[field]=normalize_identifier(scheme,data[field]);identifier=(scheme,data[field])
    item=ContentItem.objects.create(kind=kind,created_by=actor,last_edited_by=actor)
    revision=ContentRevision.objects.create(item=item,number=1,title=title.strip(),summary=summary,edited_by=actor)
    instance=DETAIL_MODELS[kind](revision=revision,**data)
    try:
        instance.full_clean()
    except DjangoValidationError as exc:
        raise ValidationError(exc.message_dict) from None
    instance.save()
    if identifier:
        ContentIdentifier.objects.create(item=item,scheme=identifier[0],value=identifier[1])
    item.working_revision=revision
    item.save(update_fields=['working_revision','updated_at'])
    from apps.workflow.models import RevisionEditEvent
    RevisionEditEvent.objects.get_or_create(content_revision=revision,editor_snapshot=actor.pk,defaults={"editor":actor})
    record(actor,item,'content.draft.create',('kind','title'),revision)
    return item


@transaction.atomic
def add_contribution(actor, revision_id, contributor_id, role, position, is_corresponding=False):
    actor=locked_editor(actor)
    # Lock order is actor, stable item, revision for all future editing services.
    ref=ContentRevision.objects.get(pk=revision_id)
    item=ContentItem.objects.select_for_update().get(pk=ref.item_id)
    revision=ContentRevision.objects.select_for_update().get(pk=revision_id)
    if not is_manager(actor) and item.created_by_id!=actor.pk:
        raise PermissionDenied()
    if revision.state!='DRAFT':
        raise ValidationError({'revision':'Only drafts may be edited.'})
    if role not in CONTRIBUTION_ROLES[item.kind]:
        raise ValidationError({'contribution_role':'Invalid role for this kind.'})
    if isinstance(position,bool) or not isinstance(position,int) or position<1:
        raise ValidationError({'position':'Positive integer required.'})
    if not isinstance(is_corresponding,bool) or (is_corresponding and role!='AUTHOR'):
        raise ValidationError({'is_corresponding':'Only authors may be corresponding.'})
    contributor=Contributor.objects.get(pk=contributor_id)
    link=RevisionContribution.objects.create(revision=revision,contributor=contributor,
        contribution_role=role,position=position,is_corresponding=is_corresponding,
        approved_display_name=contributor.display_name,approved_affiliation=contributor.external_affiliation)
    from apps.workflow.models import RevisionEditEvent
    RevisionEditEvent.objects.get_or_create(content_revision=revision,editor_snapshot=actor.pk,defaults={"editor":actor})
    revision.edited_by=actor;revision.save(update_fields=['edited_by'])
    item.last_edited_by=actor;item.lock_version+=1;item.save(update_fields=['last_edited_by','lock_version','updated_at'])
    record(actor,item,'content.contributor.add',('contributions',),revision)
    return link


def possible_duplicates(item):
    """Private editor hint, never an automatic merge or anonymous search."""
    revision=item.working_revision or item.published_revision
    if not revision:
        return []
    candidates=ContentItem.objects.filter(kind=item.kind).exclude(pk=item.pk).select_related('working_revision','published_revision')
    result=[]
    for candidate in candidates:
        other=candidate.working_revision or candidate.published_revision
        if other and SequenceMatcher(None,revision.title.casefold(),other.title.casefold()).ratio()>=0.85:
            result.append(candidate.pk)
    return result
