"""Unified business profiles and private resumes; account security is never writable here."""
from django.db import transaction
from django.db.models import Max
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from apps.accounts.services import locked_users
from apps.accounts.serializers import StrictSerializer, StrictString, StrictBoolean
from apps.assets.models import AssetFile
from apps.workflow.audit import record
from apps.workflow.models import RevisionEditEvent
from .models import MemberProfile,MemberRevision,MemberSlug,MemberPrivateData,EducationEntry,ResearchArea,MemberResearchArea,AlumniDestination,Resume
from .serializers import DraftInput, StrictInteger, draft_data
from .services import VersionConflict
from .permissions import require_management


class ProfileInput(DraftInput):
    public_visible=StrictBoolean(required=False)
    contact_visible=StrictBoolean(required=False)
    education_visible=StrictBoolean(required=False)
    alumni_visible=StrictBoolean(required=False)
    phone=StrictString(max_length=40,allow_blank=True,required=False)
    internal_contact=StrictString(max_length=254,allow_blank=True,required=False)


class ResumeInput(StrictSerializer):
    lock_version=StrictInteger(min_value=0,required=False)
    title=StrictString(max_length=200,required=False)
    intention=StrictString(max_length=300,allow_blank=True,required=False)
    introduction=StrictString(max_length=10000,allow_blank=True,required=False)
    asset=serializers.UUIDField(allow_null=True,required=False)


def profile_data(profile,actor,revision=None):
    revision=revision or profile.published_revision or profile.draft_revision
    data=draft_data(profile,revision) if revision else {'lock_version':profile.lock_version,'display_name':'','education':[],'research_areas':[]}
    data.update(id=str(profile.pk),user_id=profile.user_id,**{key:getattr(profile,key) for key in ('public_visible','contact_visible','education_visible','alumni_visible')})
    if profile.user_id==actor.pk or actor.is_superuser:
        private=getattr(profile,'private_data',None)
        data.update(phone=private.phone if private else '',internal_contact=private.internal_contact if private else '')
    return data


@transaction.atomic
def get_profile(request,pk=None):
    actor,_=locked_users(request)
    if pk:
        profile=get_object_or_404(MemberProfile.objects.select_for_update(),pk=pk,merged_into__isnull=True)
        require_management(actor,profile)
    else:
        profile,_=MemberProfile.objects.get_or_create(user=actor,defaults={'created_by':actor,'updated_by':actor})
        profile=MemberProfile.objects.select_for_update().get(pk=profile.pk)
    return actor,profile


@transaction.atomic
def save_profile(request,data,pk=None,source_id=None):
    actor,profile=get_profile(request,pk)
    if profile.lock_version!=data['lock_version']:raise VersionConflict()
    owner=profile.user
    if not owner:raise ValidationError('Bind an account through Root before editing.')
    private_allowed=actor.pk==owner.pk or actor.is_superuser
    privacy=('public_visible','contact_visible','education_visible','alumni_visible')
    if not private_allowed:
        if set(data)&{'phone','internal_contact'}:raise PermissionDenied()
        if any(data.get(key,False) and not getattr(profile,key) for key in privacy):raise PermissionDenied('Only the owner or Root may expand visibility.')
        if 'public_contact_email' in data and data['public_contact_email'] != (profile.published_revision.public_contact_email if profile.published_revision else ''):raise PermissionDenied()
        if data.get('public_contact_enabled') and not (profile.published_revision and profile.published_revision.public_contact_enabled):raise PermissionDenied()
    source=get_object_or_404(MemberRevision,pk=source_id,profile=profile) if source_id else (profile.published_revision or profile.draft_revision)
    if profile.draft_revision_id:
        draft=profile.draft_revision
        if draft.state in ('DRAFT','SUBMITTED','APPROVED'):draft.state='WITHDRAWN';draft.save(update_fields=['state'])
        profile.draft_revision=None
    fields=('display_name','slug','bio','public_contact_email','public_contact_enabled','avatar_asset_id')
    values={f:getattr(source,f) for f in fields} if source else {'display_name':' '.join(filter(None,(owner.first_name,owner.last_name)))}
    for key in ('display_name','slug','bio','public_contact_email','public_contact_enabled'):
        if key in data:values[key]=data[key]
    values['slug']=values.get('slug') or 'member-'+str(profile.pk)
    if MemberSlug.objects.filter(slug=values['slug']).exclude(profile=profile).exists():raise ValidationError({'slug':'This public address is already used.'})
    MemberSlug.objects.get_or_create(slug=values['slug'],defaults={'profile':profile})
    is_customer=owner.role=='CUSTOMER' and not owner.is_superuser
    for key in privacy:
        if key in data:setattr(profile,key,data[key])
    if is_customer:
        if any(data.get(key) for key in privacy):raise PermissionDenied('Customer profiles and resumes remain private.')
        for key in privacy:setattr(profile,key,False)
    if profile.public_visible and not values.get('display_name','').strip():raise ValidationError({'display_name':'Name required for public profiles.'})
    if values.get('public_contact_enabled') and not values.get('public_contact_email'):raise ValidationError({'public_contact_email':'Enter the public contact email.'})
    if 'avatar_asset' in data:values['avatar_asset_id']=data['avatar_asset']
    if values.get('avatar_asset_id'):
        image=get_object_or_404(AssetFile.objects.select_for_update(),pk=values['avatar_asset_id'],scan_status='CLEAN',purpose='avatar',deletion_requested_at__isnull=True)
        previous=source.avatar_asset_id if source else None
        if image.owner_id not in (actor.pk,owner.pk) and image.pk!=previous:raise PermissionDenied()
        if image.expires_at and image.expires_at<=timezone.now():raise ValidationError({'avatar_asset':'Image expired; upload again.'})
        image.expires_at=None;image.visibility='PUBLIC' if profile.public_visible else 'PRIVATE';image.save(update_fields=['visibility','expires_at'])
    revision=MemberRevision.objects.create(profile=profile,number=(profile.revisions.aggregate(n=Max('number'))['n'] or 0)+1,base_published_revision=profile.published_revision,member_kind=owner.role if owner.role in ('TEACHER','STUDENT','CUSTOMER') else 'TEACHER',public_member_status=source.public_member_status if source else 'ACTIVE',edited_by=actor,**values)
    education=data.get('education',list(source.education.values('school','major','degree','start_date','end_date','is_public','position')) if source else [])
    if not private_allowed:
        old_public={e['school'] for e in (list(source.education.filter(is_public=True).values('school')) if source else [])}
        if any(e['is_public'] and e['school'] not in old_public for e in education):raise PermissionDenied('Cannot expand another member’s education visibility.')
    EducationEntry.objects.bulk_create([EducationEntry(revision=revision,**entry) for entry in education])
    names=data.get('research_areas',[link.area.name for link in source.research_links.select_related('area')] if source else [])
    for position,name in enumerate(names,1):
        area,_=ResearchArea.objects.get_or_create(name=name);MemberResearchArea.objects.create(revision=revision,area=area,position=position)
    alumni=data.get('alumni',None)
    if 'alumni' not in data and source:
        old=getattr(source,'alumni',None)
        if old:alumni={f:getattr(old,f) for f in ('graduation_year','degree','destination_type','organization','is_public')}
    if alumni:
        if not private_allowed and alumni.get('is_public') and not (source and getattr(source,'alumni',None) and source.alumni.is_public):raise PermissionDenied()
        AlumniDestination.objects.create(revision=revision,**alumni)
    if private_allowed and set(data)&{'phone','internal_contact'}:
        private,_=MemberPrivateData.objects.get_or_create(profile=profile)
        for key in ('phone','internal_contact'):
            if key in data:setattr(private,key,data[key])
        private.save()
    revision.state='PUBLISHED';revision.save(update_fields=['state'])
    profile.published_revision=revision;profile.lock_version+=1;profile.privacy_version+=1;profile.updated_by=actor
    if owner.role in ('TEACHER','STUDENT'):profile.membership_status='ACTIVE' if revision.public_member_status=='ACTIVE' else revision.public_member_status
    profile.save()
    RevisionEditEvent.objects.create(member_revision=revision,editor=actor,editor_snapshot=actor.pk)
    record(actor,profile,'member.restore' if source_id else 'member.saved',tuple(data),revision)
    return profile


def resume_data(resume):
    return {'id':str(resume.pk),'title':resume.title,'intention':resume.intention,'introduction':resume.introduction,'lock_version':resume.lock_version,'asset':str(resume.asset_id) if resume.asset_id else None,'download_url':f'/api/assets/{resume.asset_id}/download/' if resume.asset_id else None,'updated_at':resume.updated_at}


@transaction.atomic
def save_resume(request,data,pk=None,owner=None):
    actor,_=locked_users(request)
    if owner and not actor.is_superuser:raise PermissionDenied()
    resume=get_object_or_404(Resume.objects.select_for_update(),pk=pk) if pk else Resume(owner=owner or actor)
    if resume.owner_id!=actor.pk and not actor.is_superuser:raise NotFound()
    if pk and data.get('lock_version')!=resume.lock_version:raise VersionConflict()
    if 'asset' in data:
        asset=get_object_or_404(AssetFile.objects.select_for_update(),pk=data['asset'],owner__in=[resume.owner,actor],purpose='resume',visibility='PRIVATE',scan_status='CLEAN',deletion_requested_at__isnull=True) if data['asset'] else None
        if asset and asset.expires_at and asset.expires_at<=timezone.now():raise ValidationError({'asset':'Resume file expired.'})
        if asset:asset.expires_at=None;asset.save(update_fields=['expires_at'])
        resume.asset=asset
    for key in ('title','intention','introduction'):
        if key in data:setattr(resume,key,data[key])
    resume.lock_version+=1;resume.save();record(actor,resume,'resume.saved',tuple(data))
    return resume
