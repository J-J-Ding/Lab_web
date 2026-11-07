"""V10 direct saves: authorization, complete immutable snapshots and one atomic pointer update."""
from django.db import transaction
from django.db.models import Max, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.exceptions import ValidationError as ModelError
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.accounts.services import locked_users
from apps.accounts.permissions import is_manager
from apps.assets.models import AssetFile
from apps.members.models import MemberProfile
from apps.members.services import VersionConflict
from apps.workflow.audit import record
from apps.workflow.models import ContentEditGrant, RevisionEditEvent
from .models import ContentItem, ContentRevision, DETAIL_MODELS, Contributor, RevisionContribution, RevisionAsset, ContentProjectLink, ContentIdentifier
from .serializers import validate_detail
from .services import locked_editor, normalize_identifier
from .types import CONTRIBUTION_ROLES


def team(user):
    return bool(user.is_authenticated and user.is_active and (user.is_superuser or user.role in ('ADMIN','TEACHER','STUDENT')))


def editable(user, item):
    return team(user) and (is_manager(user) or item.created_by_id == user.pk or ContentEditGrant.objects.filter(item=item,user=user,can_edit=True,revoked_at__isnull=True).exists())


def readable(user, deleted=False):
    if not team(user):return ContentItem.objects.none()
    qs=ContentItem.objects.filter(deleted_at__isnull=not deleted)
    if deleted and not is_manager(user):
        grants=ContentEditGrant.objects.filter(user=user,can_edit=True,revoked_at__isnull=True).values("item_id")
        return qs.filter(Q(created_by=user)|Q(pk__in=grants))
    if is_manager(user):return qs
    grants=ContentEditGrant.objects.filter(user=user,revoked_at__isnull=True).values('item_id')
    return qs.filter(Q(published_revision__isnull=False)|Q(created_by=user)|Q(pk__in=grants))


def name_for(profile):
    revision = profile.published_revision or profile.draft_revision
    return revision.display_name.strip() if revision else ''


def avatar_for(profile):
    revision=profile.published_revision or profile.draft_revision
    asset=revision.avatar_asset if revision and revision.avatar_asset_id else None
    if not asset or asset.purpose!='avatar' or asset.scan_status!='CLEAN' or asset.deletion_requested_at:return None
    return f'/api/assets/{asset.pk}/download/'


def directory():
    return MemberProfile.objects.filter(user__is_active=True,user__role__in=['TEACHER','STUDENT'],merged_into__isnull=True).select_related('user','published_revision__avatar_asset','draft_revision__avatar_asset').order_by('user_id')


def asset_check(actor, ids, previous=()):
    if len(ids) != len(set(ids)):
        raise ValidationError({'assets':'Duplicate attachment.'})
    assets=list(AssetFile.objects.select_for_update().filter(pk__in=ids,scan_status='CLEAN',purpose__in=['image','attachment'],deletion_requested_at__isnull=True).filter(Q(owner=actor)|Q(pk__in=previous)).filter(Q(expires_at__isnull=True)|Q(expires_at__gt=timezone.now())))
    if len(assets)!=len(ids):raise ValidationError({'assets':'File unavailable or not owned by you.'})
    return {a.pk:a for a in assets}


@transaction.atomic
def save(request, data, pk=None, source_id=None):
    actor,_=locked_users(request);actor=locked_editor(actor)
    item=get_object_or_404(ContentItem.objects.select_for_update(),pk=pk) if pk else None
    if item and not editable(actor,item):raise PermissionDenied()
    if item and item.lock_version!=data.get('lock_version'):raise VersionConflict()
    if item and item.deleted_at:raise VersionConflict("Restore deleted content before editing.")
    if item and item.archived_at:raise VersionConflict('Unarchive before editing.')
    source=None
    if item:
        source=get_object_or_404(ContentRevision,item=item,pk=source_id) if source_id else (item.published_revision or item.working_revision)
    kind=item.kind if item else data['kind']
    if kind=='LAB_PAGE' and not is_manager(actor):raise PermissionDenied()
    if kind=='LAB_PAGE' and data.get('detail',{}).get('page_key')=='home':raise ValidationError({'detail':'Homepage layout is controlled by the website template.'})
    if 'featured' in data and not is_manager(actor):raise PermissionDenied('Only teachers can select featured content.')
    title=data.get('title',source.title if source else '').strip()
    if not title:raise ValidationError({'title':'Title required.'})
    detail={f.name:getattr(getattr(source,DETAIL_MODELS[kind]._meta.get_field('revision').remote_field.related_name),f.name) for f in DETAIL_MODELS[kind]._meta.fields if f.name!='revision'} if source else {}
    detail.update(data.get('detail',{}));detail=validate_detail(kind,detail)
    if kind=='LAB_PAGE' and detail.get('page_key')=='home':raise ValidationError({'detail':'Use the fixed homepage instead.'})
    if not item:item=ContentItem.objects.create(kind=kind,created_by=actor,last_edited_by=actor)
    # Old unprocessed work remains historical; no automatic publication of its content.
    if item.working_revision_id:
        old=item.working_revision
        if old.state=='DRAFT':old.state='WITHDRAWN';old.save(update_fields=['state'])
        elif old.state=='SUBMITTED':old.state='WITHDRAWN';old.save(update_fields=['state'])
        # Legacy APPROVED is retained; the partial working constraint requires settling it.
        elif old.state=='APPROVED':old.state='WITHDRAWN';old.save(update_fields=['state'])
        item.working_revision=None
    from .rich_content import validate_document,image_ids
    rich_body=validate_document(data.get('rich_body',source.rich_body if source else None))
    revision=ContentRevision.objects.create(rich_body=rich_body,item=item,number=(item.revisions.aggregate(n=Max('number'))['n'] or 0)+1,title=title,summary=data.get('summary',source.summary if source else ''),edited_by=actor,base_published_revision=item.published_revision)
    mapping={'PAPER':('DOI','doi'),'PROJECT':('PROJECT','project_number'),'PUBLICATION':('ISBN','isbn'),'LAB_PAGE':('PAGE','page_key')}
    if kind in mapping:
        scheme,field=mapping[kind];value=detail.get(field)
        ContentIdentifier.objects.filter(item=item,scheme=scheme,is_current=True).update(is_current=False)
        if value:
            value=normalize_identifier(scheme,value);detail[field]=value
            conflict=ContentIdentifier.objects.filter(scheme=scheme,value=value).exclude(item=item).exists()
            if conflict:raise ValidationError({field:'Identifier already belongs to another record.'})
            ContentIdentifier.objects.update_or_create(item=item,scheme=scheme,value=value,defaults={'is_current':True})
    instance=DETAIL_MODELS[kind](revision=revision,**detail)
    try:instance.full_clean();instance.save()
    except ModelError as exc:raise ValidationError(exc.message_dict) from None
    if 'authors' in data:
        ids=data['authors']
        if ids and not CONTRIBUTION_ROLES[kind]:raise ValidationError({'authors':'This page does not accept authors.'})
        if len(ids)!=len(set(ids)):raise ValidationError({'authors':'Duplicate member.'})
        if not data.get('authors_ordered',True):
            previous=list(source.contributions.filter(contributor__member_profile__user_id__in=ids).order_by('position','id').values_list('contributor__member_profile__user_id',flat=True)) if source else []
            ids=list(dict.fromkeys(previous))+sorted(set(ids)-set(previous))
        from apps.accounts.models import User
        list(User.objects.select_for_update().filter(pk__in=ids).order_by('pk'))
        profiles={p.user_id:p for p in directory().select_for_update(of=('self',)).filter(user_id__in=ids)}
        if len(profiles)!=len(ids) or any(not name_for(p) for p in profiles.values()):raise ValidationError({'authors':'Select registered active Teacher/Student members with completed names.'})
        for position,uid in enumerate(ids,1):
            profile=profiles[uid];contributor,_=Contributor.objects.get_or_create(member_profile=profile,defaults={'display_name':name_for(profile),'created_by':actor})
            role='AUTHOR' if 'AUTHOR' in CONTRIBUTION_ROLES[kind] else CONTRIBUTION_ROLES[kind][0]
            RevisionContribution.objects.create(revision=revision,contributor=contributor,contribution_role=role,position=position,approved_display_name=name_for(profile))
        # Immutable external historical signatures are retained, never added through user input.
        legacy=source.contributions.filter(Q(contributor__member_profile__isnull=True)|Q(contributor__member_profile__user__isnull=True)) if source else []
        for position,link in enumerate(legacy,len(ids)+1):
            RevisionContribution.objects.create(revision=revision,contributor=link.contributor,contribution_role=link.contribution_role,position=position,approved_display_name=link.approved_display_name,approved_affiliation=link.approved_affiliation,is_corresponding=link.is_corresponding)
    elif source:
        if source_id and source.contributions.filter(contributor__member_profile__user__isnull=False).exclude(contributor__member_profile__user__is_active=True,contributor__member_profile__user__role__in=['TEACHER','STUDENT']).exists():
            raise VersionConflict('Historical author is no longer an active team member. Load the content in the editor and select valid authors instead.')
        for link in source.contributions.all():
            RevisionContribution.objects.create(revision=revision,**{f:getattr(link,f) for f in ('contributor_id','contribution_role','position','is_corresponding','approved_display_name','approved_affiliation')})
    previous=list(source.assets.values_list('asset_id',flat=True)) if source else []
    ids=list(data.get('assets',previous))
    for aid in sorted(image_ids(rich_body)):
        from uuid import UUID
        if UUID(aid) not in ids:ids.append(UUID(aid))
    if len(ids)>60:raise ValidationError({'assets':'正文图片与附件总数不能超过60。'})
    assets=asset_check(actor,ids,previous)
    if any(not assets[aid].mime_type.startswith('image/') for aid in assets if str(aid) in image_ids(rich_body)):
        raise ValidationError({'rich_body':'正文只能插入图片资产。'})
    from .public_serializers import cover_for_revision
    previous_cover=cover_for_revision(source) if source else None
    cover=data.get('cover_asset',previous_cover.pk if previous_cover else None)
    if cover is not None and (cover not in assets or not assets[cover].mime_type.startswith('image/')):
        raise ValidationError({'cover_asset':'Select an uploaded image attached to this record.'})
    # New records without an explicit selection use their first image; explicit null clears it.
    if not source and 'cover_asset' not in data:cover=next((aid for aid in ids if assets[aid].mime_type.startswith('image/')),None)
    for position,aid in enumerate(ids,1):
        asset=assets[aid]
        from .public_selectors import published_items_base
        other_public=published_items_base().exclude(pk=item.pk).filter(published_revision__assets__asset=asset).exists()
        asset.visibility='PUBLIC' if data.get('visibility_scope',item.visibility_scope)=='PUBLIC' or other_public else 'PRIVATE'
        asset.expires_at=None;asset.save(update_fields=['visibility','expires_at'])
        RevisionAsset.objects.create(revision=revision,asset=asset,purpose='cover' if aid==cover else 'body' if str(aid) in image_ids(rich_body) else 'gallery' if asset.mime_type.startswith('image/') else asset.purpose,position=position)
    projects=data.get('project_links',list(source.project_links.values_list('target_project_id',flat=True)) if source else [])
    if len(projects)!=len(set(projects)) or ContentItem.objects.filter(pk__in=projects,kind='PROJECT',deleted_at__isnull=True).exclude(pk=item.pk).count()!=len(projects):raise ValidationError({'project_links':'Select existing projects.'})
    for project in projects:ContentProjectLink.objects.create(source_revision=revision,target_project_id=project)
    revision.state='PUBLISHED';revision.save(update_fields=['state'])
    item.published_revision=revision;item.visibility_scope=data.get('visibility_scope',item.visibility_scope);item.visibility_gate=True;item.featured=data.get('featured',item.featured);item.last_edited_by=actor;item.lock_version+=1;item.save()
    RevisionEditEvent.objects.create(content_revision=revision,editor=actor,editor_snapshot=actor.pk)
    record(actor,item,'content.restore' if source_id else 'content.saved',tuple(data),revision)
    return item


@transaction.atomic
def set_deleted(request,pk,version,deleted):
    actor,_=locked_users(request);actor=locked_editor(actor)
    item=get_object_or_404(ContentItem.objects.select_for_update(),pk=pk)
    if not editable(actor,item):raise PermissionDenied()
    if item.lock_version!=version:raise VersionConflict()
    if bool(item.deleted_at)==deleted:raise VersionConflict('Content already deleted.' if deleted else 'Content already restored.')
    item.deleted_at=timezone.now() if deleted else None
    item.deleted_by=actor if deleted else None
    item.visibility_gate=False
    item.lock_version+=1;item.last_edited_by=actor
    item.save(update_fields=['deleted_at','deleted_by','visibility_gate','lock_version','last_edited_by','updated_at'])
    record(actor,item,'content.deleted' if deleted else 'content.undeleted',('deleted_at','visibility_gate'))
    return item
