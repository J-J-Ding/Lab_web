from django.db import transaction,IntegrityError
from django.db.models import Max,Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError,PermissionDenied,NotFound,Throttled
from apps.accounts.models import User
from apps.accounts.permissions import is_manager
from apps.content import services as content_services
from apps.content.models import (ContentItem,ContentRevision,ContentIdentifier,DETAIL_MODELS,Contributor,RevisionContribution,ContentProjectLink,RevisionAsset)
from apps.content.serializers import validate_detail
from apps.content.types import CONTRIBUTION_ROLES
from apps.members.services import VersionConflict
from .permissions import actor_for,locked_item,locked_revision,selectable_contributors
from .models import RevisionEditEvent,RevisionSubmission,ReviewDecision,ContributionConfirmation,ContentEditGrant,CorrectionRequest,ContentModerationEvent
from .audit import record


def check_version(item,version):
    if item.lock_version!=version:raise VersionConflict()


def bump(item,actor,edited=False):
    item.lock_version+=1
    if edited:item.last_edited_by=actor
    item.save(update_fields=['lock_version','last_edited_by','working_revision','published_revision','visibility_gate','archived_at','updated_at'])


def track_edit(actor,revision):
    RevisionEditEvent.objects.get_or_create(content_revision=revision,editor_snapshot=actor.pk,defaults={'editor':actor})


def check_editable(item,revision):
    if item.archived_at or revision.state!='DRAFT' or item.working_revision_id!=revision.pk:
        raise VersionConflict('Only the active draft of an unarchived item may be edited.')


def validate_ready(item,revision):
    if not revision.title.strip():raise ValidationError({'title':'Title required.'})
    detail=DETAIL_MODELS[item.kind].objects.get(revision=revision)
    fields={'PAPER':['venue','publication_date'],'PROJECT':['funder','start_date'],
            'AWARD':['event_name','award_name','award_date'],'ACTIVITY':['starts_at','body'],
            'NEWS':['body'],'BLOG':['body'],'PUBLICATION':['publisher','publication_date'],
            'LAB_PAGE':['page_key','body']}[item.kind]
    if any(not getattr(detail,f) for f in fields):raise ValidationError({'detail':'Complete the required publication fields: '+', '.join(fields)})
    links=list(revision.contributions.all())
    if item.kind in ('PAPER','PROJECT','AWARD','PUBLICATION') and not links:
        raise ValidationError({'contributions':'At least one contributor is required.'})
    for link in links:
        event=link.confirmations.order_by('-created_at','-pk').first()
        if event is None or event.decision!='CONFIRMED':
            raise ValidationError({'contributions':'Every listed contribution must be confirmed without an active dispute.'})


def reserve_identifier(item,data):
    mapping={'PAPER':('DOI','doi'),'PROJECT':('PROJECT','project_number'),'PUBLICATION':('ISBN','isbn'),'LAB_PAGE':('PAGE','page_key')}
    if item.kind not in mapping:return
    scheme,field=mapping[item.kind]
    if not data.get(field):return
    value=content_services.normalize_identifier(scheme,data[field]);data[field]=value
    existing=ContentIdentifier.objects.filter(scheme=scheme,value=value).first()
    if existing and existing.item_id!=item.pk:raise ValidationError({field:'Identifier already belongs to another item.'})
    if not existing:
        # A new identifier is reserved as a pending alias; only approval promotes it.
        ContentIdentifier.objects.create(item=item,scheme=scheme,value=value,is_current=False)


def replace_contributions(actor,item,revision,links):
    # Confirmation records remain attached to historical drafts; only replace a draft's
    # rows when no confirmation references them, otherwise require a fresh draft version.
    old=list(revision.contributions.all())
    signature=lambda e:(str(e['contributor']),e['contribution_role'],e['position'],e['is_corresponding'])
    current=[(str(c.contributor_id),c.contribution_role,c.position,c.is_corresponding) for c in old]
    if sorted(current)==sorted(signature(e) for e in links):return
    if old and any(c.confirmations.exists() for c in old):
        raise VersionConflict('Confirmed authorship cannot be replaced in place. Withdraw/clone a fresh draft.')
    seen=set();positions=set()
    for entry in links:
        key=(entry['contributor'],entry['contribution_role'])
        if key in seen:raise ValidationError({'contributions':'Duplicate contributor and role.'})
        seen.add(key)
        if entry['contribution_role'] not in CONTRIBUTION_ROLES[item.kind]:raise ValidationError({'contributions':'Invalid role for content type.'})
        if entry['contribution_role']=='AUTHOR':
            if entry['position'] in positions:raise ValidationError({'contributions':'Author positions must be unique.'})
            positions.add(entry['position'])
        if entry['is_corresponding'] and entry['contribution_role']!='AUTHOR':raise ValidationError({'contributions':'Only authors can be corresponding.'})
    # No private profile fields are loaded or disclosed by contributor selection.
    contributors={c.pk:c for c in selectable_contributors(actor).filter(pk__in=[e['contributor'] for e in links])}
    if len(contributors)!=len({e['contributor'] for e in links}):raise ValidationError({'contributions':'Contributor unavailable.'})
    revision.contributions.all().delete()
    for entry in links:
        contributor=contributors[entry['contributor']]
        RevisionContribution.objects.create(revision=revision,contributor=contributor,
            contribution_role=entry['contribution_role'],position=entry['position'],is_corresponding=entry['is_corresponding'],
            approved_display_name=contributor.safe_name,approved_affiliation=contributor.safe_affiliation)


@transaction.atomic
def create(request,data):
    actor=actor_for(request,editor=True)
    try:
        with transaction.atomic():
            item=content_services.create_content(actor,data['kind'],data['title'],data['detail'],data['summary'])
            replace_contributions(actor,item,item.working_revision,data['contributions'])
    except IntegrityError:
        raise ValidationError({'detail':'A normalized identifier or author position is already in use.'}) from None
    return item


@transaction.atomic
def edit(request,revision_id,data):
    actor=actor_for(request,editor=True);item,revision=locked_revision(actor,revision_id,True)
    check_version(item,data['lock_version']);check_editable(item,revision)
    if 'title' in data:revision.title=data['title']
    if 'summary' in data:revision.summary=data['summary']
    if 'detail' in data:
        detail=DETAIL_MODELS[item.kind].objects.get(revision=revision)
        current={f.name:getattr(detail,f.name) for f in detail._meta.fields if f.name!='revision'}
        current.update(data['detail']);values=validate_detail(item.kind,current)
        try:
            with transaction.atomic():
                reserve_identifier(item,values)
                for field,value in values.items():setattr(detail,field,value)
                detail.full_clean();detail.save()
        except DjangoValidationError as exc:raise ValidationError(exc.message_dict) from None
        except IntegrityError:raise ValidationError({'detail':'Identifier already reserved.'}) from None
    if 'contributions' in data:replace_contributions(actor,item,revision,data['contributions'])
    if 'assets' in data:
        from apps.assets.models import AssetFile
        from django.utils import timezone
        ids=set(data['assets'])
        existing=set(revision.assets.values_list('asset_id',flat=True))
        assets=list(AssetFile.objects.select_for_update().filter(pk__in=ids,scan_status='CLEAN',purpose__in=['image','attachment'],deletion_requested_at__isnull=True).filter(Q(owner=actor)|Q(pk__in=existing)).filter(Q(expires_at__isnull=True)|Q(expires_at__gt=timezone.now())).order_by('pk'))
        if len(assets)!=len(ids):raise ValidationError({'assets':'Asset unavailable.'})
        revision.assets.all().delete()
        for pos,asset in enumerate(assets,1):RevisionAsset.objects.create(revision=revision,asset=asset,purpose=asset.purpose,position=pos)
    if 'project_links' in data:
        ids=set(data['project_links'])
        # Only publicly known projects or projects already privately visible to this actor.
        from .permissions import visible_items
        allowed=ContentItem.objects.filter(kind='PROJECT',deleted_at__isnull=True).filter(Q(published_revision__state='PUBLISHED',visibility_gate=True)|Q(pk__in=visible_items(actor).values('pk')))
        existing=set(revision.project_links.values_list('target_project_id',flat=True))
        new_ids=ids-existing
        if len(new_ids)!=allowed.filter(pk__in=new_ids).exclude(pk=item.pk).count():raise ValidationError({'project_links':'Project unavailable.'})
        revision.project_links.all().delete()
        for pk in ids:ContentProjectLink.objects.create(source_revision=revision,target_project_id=pk)
    revision.edited_by=actor;revision.save();track_edit(actor,revision);bump(item,actor,edited=True)
    record(actor,item,'content.draft.update',set(data)-{'lock_version'},revision)
    return item


@transaction.atomic
def clone(request,item_id,data):
    actor=actor_for(request,editor=True);item=locked_item(actor,item_id,True)
    check_version(item,data['lock_version'])
    if item.archived_at or item.working_revision_id:raise VersionConflict('An active draft already exists or this item is archived.')
    source_id=data.get('source_revision') or item.revisions.filter(state__in=['PUBLISHED','REJECTED','WITHDRAWN']).order_by('-number').values_list('pk',flat=True).first()
    source=get_object_or_404(ContentRevision,item=item,pk=source_id)
    if source.state not in ('PUBLISHED','REJECTED','WITHDRAWN'):raise VersionConflict('Select a historical revision.')
    number=(item.revisions.aggregate(n=Max('number'))['n'] or 0)+1
    revision=ContentRevision.objects.create(item=item,number=number,title=source.title,summary=source.summary,rich_body=source.rich_body,edited_by=actor,base_published_revision=item.published_revision)
    original=DETAIL_MODELS[item.kind].objects.get(revision=source)
    DETAIL_MODELS[item.kind].objects.create(revision=revision,**{f.name:getattr(original,f.name) for f in original._meta.fields if f.name!='revision'})
    for link in source.contributions.all():
        RevisionContribution.objects.create(revision=revision,**{f:getattr(link,f) for f in ('contributor_id','contribution_role','position','is_corresponding','approved_display_name','approved_affiliation')})
    for link in source.project_links.all():ContentProjectLink.objects.create(source_revision=revision,target_project=link.target_project,relation_type=link.relation_type)
    for link in source.assets.all():RevisionAsset.objects.create(revision=revision,asset=link.asset,purpose=link.purpose,position=link.position)
    # Always reconfirm; this is the conservative allowed behavior in the spec.
    item.working_revision=revision;track_edit(actor,revision);bump(item,actor,edited=True)
    record(actor,item,'content.draft.clone',('working_revision',),revision)
    return item


@transaction.atomic
def submit(request,revision_id,version):
    actor=actor_for(request,editor=True);item,revision=locked_revision(actor,revision_id,True)
    check_version(item,version);check_editable(item,revision);validate_ready(item,revision)
    revision.state='SUBMITTED';revision.submitted_at=timezone.now();revision.save(update_fields=['state','submitted_at'])
    RevisionSubmission.objects.create(content_revision=revision,submitted_by=actor,submitter_snapshot=actor.pk)
    bump(item,actor);record(actor,item,'content.submitted',('state',),revision)
    return item


@transaction.atomic
def withdraw(request,revision_id,version):
    actor=actor_for(request);item,revision=locked_revision(actor,revision_id,True)
    check_version(item,version)
    sub=RevisionSubmission.objects.filter(content_revision=revision).first()
    if revision.state!='SUBMITTED' or not sub:raise VersionConflict('Only pending submissions can be withdrawn.')
    if sub.submitter_snapshot!=actor.pk:raise PermissionDenied('Only the submitter may withdraw.')
    revision.state='WITHDRAWN';revision.save(update_fields=['state']);item.working_revision=None
    bump(item,actor);record(actor,item,'content.withdrawn',('state',),revision)
    return item


@transaction.atomic
def decide(request,revision_id,data):
    actor=actor_for(request,manager=True);item,revision=locked_revision(actor,revision_id)
    check_version(item,data['lock_version'])
    if item.archived_at or revision.state!='SUBMITTED' or item.working_revision_id!=revision.pk:raise VersionConflict('This revision is no longer pending or the item is archived.')
    sub=get_object_or_404(RevisionSubmission,content_revision=revision)
    from .permissions import can_self_review
    if not can_self_review(actor) and (sub.submitter_snapshot==actor.pk or revision.edit_events.filter(editor_snapshot=actor.pk).exists()):raise PermissionDenied('Self review is not permitted for this account.')
    if revision.base_published_revision_id!=item.published_revision_id:raise VersionConflict('Published baseline changed; merge and resubmit.')
    if data['decision']=='APPROVE':
        validate_ready(item,revision)
        revision.state='PUBLISHED';revision.save(update_fields=['state'])
        from apps.assets.models import AssetFile
        from django.utils import timezone
        assets=list(AssetFile.objects.select_for_update().filter(revisionasset__revision=revision))
        for asset in assets:
            if asset.scan_status!='CLEAN' or asset.purpose not in ('image','attachment') or asset.deletion_requested_at or (asset.expires_at and asset.expires_at<=timezone.now()):raise ValidationError({'assets':'Asset unavailable.'})
            asset.visibility='PUBLIC';asset.expires_at=None;asset.save(update_fields=['visibility','expires_at'])
        item.published_revision=revision;item.visibility_gate=True
        detail=DETAIL_MODELS[item.kind].objects.get(revision=revision)
        mapping={'PAPER':('DOI','doi'),'PROJECT':('PROJECT','project_number'),'PUBLICATION':('ISBN','isbn'),'LAB_PAGE':('PAGE','page_key')}
        if item.kind in mapping:
            scheme,field=mapping[item.kind];value=getattr(detail,field)
            ContentIdentifier.objects.filter(item=item,scheme=scheme,is_current=True).update(is_current=False)
            if value:ContentIdentifier.objects.filter(item=item,scheme=scheme,value=value).update(is_current=True)
    else:
        revision.state='REJECTED';revision.save(update_fields=['state'])
    item.working_revision=None
    ReviewDecision.objects.create(content_revision=revision,reviewer=actor,reviewer_snapshot=actor.pk,decision=data['decision'],reason=data['reason'])
    bump(item,actor);record(actor,item,'content.review.'+data['decision'].lower(),('state','published_revision'),revision)
    return item


@transaction.atomic
def moderate(request,item_id,action,data):
    actor=actor_for(request,manager=True);item=locked_item(actor,item_id)
    check_version(item,data['lock_version'])
    if action=='archive':
        if item.archived_at:raise VersionConflict('Already archived.')
        item.archived_at=timezone.now()
    elif action=='unarchive':
        if not item.archived_at:raise VersionConflict('Not archived.')
        item.archived_at=None
    else:
        if not item.published_revision_id or not item.visibility_gate:raise VersionConflict('No visible publication to unpublish.')
        item.visibility_gate=False
    ContentModerationEvent.objects.create(item=item,actor=actor,actor_snapshot=actor.pk,action=action.upper(),reason=data['reason'])
    bump(item,actor);record(actor,item,'content.'+action,('archived_at' if action!='unpublish' else 'visibility_gate',))
    return item


@transaction.atomic
def grant(request,item_id,data):
    from apps.accounts.services import locked_users
    actor,target=locked_users(request,data['user_id'])
    actor=content_services.locked_editor(actor)
    item=locked_item(actor,item_id)
    check_version(item,data['lock_version'])
    if not (is_manager(actor) or item.created_by_id==actor.pk):raise PermissionDenied()
    if target is None or not target.is_active:raise NotFound()
    if not actor.is_superuser and (target.is_superuser or target.role=='ADMIN'):raise NotFound()
    content_services.locked_editor(target)
    ContentEditGrant.objects.update_or_create(item=item,user=target,defaults={'granted_by':actor,'can_edit':data['can_edit'],'revoked_at':timezone.now() if data['revoke'] else None})
    bump(item,actor);record(actor,item,'content.grant.revoke' if data['revoke'] else 'content.grant.add',('edit_grants',))
    return item


@transaction.atomic
def confirm(request,contribution_id,data,proxy=False):
    actor=actor_for(request,manager=proxy)
    ref=get_object_or_404(RevisionContribution.objects.select_related('revision'),pk=contribution_id)
    item=ContentItem.objects.select_for_update().get(pk=ref.revision.item_id)
    contribution=RevisionContribution.objects.select_for_update(of=('self',)).select_related('contributor__member_profile').get(pk=contribution_id)
    revision=contribution.revision
    if revision.state not in ('DRAFT','SUBMITTED') or item.working_revision_id!=revision.pk:raise VersionConflict('Use a correction request for historical authorship.')
    if data['decision']=='DISPUTED' and not data['reason'].strip():raise ValidationError({'reason':'A dispute reason is required.'})
    if proxy:
        if not data['reason'].strip():raise ValidationError({'reason':'Evidence verification reason required.'})
    elif contribution.contributor.member_profile_id is None or contribution.contributor.member_profile.user_id!=actor.pk:
        raise NotFound()
    ContributionConfirmation.objects.create(contribution=contribution,actor=actor,actor_snapshot=actor.pk,decision=data['decision'],reason=data['reason'],is_proxy=proxy)
    bump(item,actor);record(actor,item,'content.contribution.'+data['decision'].lower(),('confirmation',),revision)
    return {'contribution':str(contribution.pk),'state':data['decision'],'lock_version':item.lock_version}


@transaction.atomic
def correction(request,item_id,reason):
    actor=actor_for(request)
    item=get_object_or_404(ContentItem,pk=item_id,deleted_at__isnull=True,published_revision__state='PUBLISHED',visibility_gate=True)
    from .permissions import can_submit
    if not can_submit(actor) and not item.published_revision.contributions.filter(contributor__member_profile__user=actor).exists():raise PermissionDenied()
    if CorrectionRequest.objects.filter(requester=actor,created_at__gte=timezone.now()-timezone.timedelta(hours=1)).count()>=10:
        raise Throttled(wait=3600)
    result=CorrectionRequest.objects.create(item=item,requester=actor,reason=reason)
    record(actor,item,'content.correction.create',('correction_request',))
    return result


@transaction.atomic
def discard(request,revision_id,version):
    actor=actor_for(request,editor=True);item,revision=locked_revision(actor,revision_id,True)
    check_version(item,version);check_editable(item,revision)
    revision.state='WITHDRAWN';revision.save(update_fields=['state']);item.working_revision=None
    bump(item,actor);record(actor,item,'content.draft.discard',('state',),revision)
    return item


@transaction.atomic
def resolve_correction(request,pk,reply):
    actor=actor_for(request,manager=True)
    result=get_object_or_404(CorrectionRequest.objects.select_for_update(),pk=pk)
    if result.state!='OPEN':raise VersionConflict('Correction already resolved.')
    result.state='RESOLVED';result.reply=reply;result.save(update_fields=['state','reply'])
    record(actor,result.item,'content.correction.resolve',('correction_request',))
    return result
