from django.db import transaction
from django.db.models import Max
from rest_framework.exceptions import APIException,ValidationError,NotFound
from apps.assets.models import AssetFile
from apps.workflow.audit import record
from .models import (MemberProfile,MemberRevision,MemberPrivateData,EducationEntry,ResearchArea,
                     MemberResearchArea,AlumniDestination,MemberRevisionAsset)
from .permissions import lock_actor,require_management


class VersionConflict(APIException):
    status_code=409
    default_detail='The draft has changed. Reload before saving.'
    default_code='version_conflict'


def clone_revision(profile, actor):
    original=profile.revisions.filter(state__in=["PUBLISHED","REJECTED","WITHDRAWN"]).order_by("-number").first()
    fields=('member_kind','public_member_status','display_name','slug','bio','enrollment_year','public_contact_email','public_contact_enabled','avatar_asset_id')
    data={f:getattr(original,f) for f in fields} if original else {}
    if not original:
        data['display_name']=' '.join(v for v in (actor.first_name,actor.last_name) if v)
    number=(profile.revisions.aggregate(n=Max('number'))['n'] or 0)+1
    rev=MemberRevision.objects.create(profile=profile,number=number,edited_by=actor,base_published_revision=profile.published_revision,**data)
    if original:
        for entry in original.education.all():
            values={f:getattr(entry,f) for f in ('school','education_level','major','degree','start_date','end_date','is_public','position')}
            EducationEntry.objects.create(revision=rev,**values)
        for link in original.research_links.all():
            MemberResearchArea.objects.create(revision=rev,area=link.area,position=link.position)
        old=AlumniDestination.objects.filter(revision=original).first()
        if old:
            AlumniDestination.objects.create(revision=rev,**{f:getattr(old,f) for f in ('graduation_year','degree','destination_type','organization','is_public')})
        for asset in original.assets.all():
            MemberRevisionAsset.objects.create(revision=rev,asset=asset.asset,purpose=asset.purpose,position=asset.position)
    profile.draft_revision=rev
    profile.updated_by=actor
    profile.save(update_fields=['draft_revision','updated_by','updated_at'])
    return rev


@transaction.atomic
def initialize_draft(actor):
    actor=lock_actor(actor)
    profile=MemberProfile.objects.select_for_update().filter(user=actor).first()
    if profile is None:
        profile=MemberProfile.objects.create(user=actor,created_by=actor,updated_by=actor)
        MemberPrivateData.objects.create(profile=profile)
    if profile.merged_into_id:
        raise NotFound()
    if profile.draft_revision_id:
        if profile.draft_revision.state!='DRAFT':
            raise VersionConflict('An existing revision is already under review.')
        return profile,profile.draft_revision,False
    rev=clone_revision(profile,actor)
    from apps.workflow.models import RevisionEditEvent
    RevisionEditEvent.objects.get_or_create(member_revision=rev,editor_snapshot=actor.pk,defaults={"editor":actor})
    record(actor,profile,'member.draft.create',('draft_revision',),rev)
    return profile,rev,True


@transaction.atomic
def update_draft(actor,data):
    actor=lock_actor(actor)
    profile=MemberProfile.objects.select_for_update().filter(user=actor,merged_into__isnull=True).first()
    if profile is None or not profile.draft_revision_id:
        raise NotFound('Initialize a draft first.')
    rev=MemberRevision.objects.select_for_update().get(pk=profile.draft_revision_id)
    if rev.state!='DRAFT' or profile.lock_version!=data['lock_version']:
        raise VersionConflict()
    values={k:v for k,v in data.items() if k not in ('lock_version','education','research_areas','alumni','avatar_asset')}
    enabled=values.get('public_contact_enabled',rev.public_contact_enabled)
    email=values.get('public_contact_email',rev.public_contact_email)
    if enabled and not email:
        raise ValidationError({'public_contact_email':'An explicit public email is required.'})
    if 'avatar_asset' in data:
        asset=None
        if data['avatar_asset']:
            asset=AssetFile.objects.filter(pk=data['avatar_asset'],owner=actor,scan_status='CLEAN',mime_type__in=['image/jpeg','image/png','image/webp']).first()
            if asset is not None and asset.expires_at is not None:
                from django.utils import timezone
                if asset.expires_at <= timezone.now(): asset=None
            if asset is None:
                raise ValidationError({'avatar_asset':'Asset unavailable.'})
        values['avatar_asset']=asset
    for key,value in values.items():
        setattr(rev,key,value)
    rev.edited_by=actor
    rev.save()
    if 'education' in data:
        rev.education.all().delete()
        EducationEntry.objects.bulk_create([EducationEntry(revision=rev,**entry) for entry in data['education']])
    if 'research_areas' in data:
        rev.research_links.all().delete()
        for i,name in enumerate(data['research_areas'],1):
            area,_=ResearchArea.objects.get_or_create(name=name)
            MemberResearchArea.objects.create(revision=rev,area=area,position=i)
    if 'alumni' in data:
        AlumniDestination.objects.filter(revision=rev).delete()
        if data['alumni'] is not None:
            AlumniDestination.objects.create(revision=rev,**data['alumni'])
    profile.lock_version+=1
    profile.updated_by=actor
    profile.save(update_fields=['lock_version','updated_by','updated_at'])
    from apps.workflow.models import RevisionEditEvent
    RevisionEditEvent.objects.get_or_create(member_revision=rev,editor_snapshot=actor.pk,defaults={"editor":actor})
    record(actor,profile,'member.draft.update',set(data)-{'lock_version'},rev)
    return profile,rev


@transaction.atomic
def create_unbound_profile(actor):
    actor=lock_actor(actor)
    profile=MemberProfile()
    require_management(actor,profile)
    profile.created_by=profile.updated_by=actor
    profile.save()
    MemberPrivateData.objects.create(profile=profile)
    record(actor,profile,'member.profile.create')
    return profile


@transaction.atomic
def bind_profile(actor,profile_id,user_id):
    """Internal management primitive; no V4 endpoint, no role change or name matching."""
    from apps.accounts.models import User
    from apps.accounts.permissions import can_manage
    actor=lock_actor(actor)
    target=User.objects.select_for_update().get(pk=user_id)
    if not can_manage(actor,target):
        raise NotFound()
    profile=MemberProfile.objects.select_for_update().get(pk=profile_id)
    require_management(actor,profile)
    if profile.user_id is not None or profile.merged_into_id or MemberProfile.objects.filter(user=target).exists():
        raise VersionConflict('The account or profile is already bound.')
    profile.user=target
    profile.updated_by=actor
    profile.save(update_fields=['user','updated_by','updated_at'])
    record(actor,profile,'member.profile.bind',('user',))
    return profile
