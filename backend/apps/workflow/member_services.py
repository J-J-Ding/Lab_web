from django.db import transaction,IntegrityError
from django.db.models import Max
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError,PermissionDenied,NotFound
from apps.accounts.models import User
from apps.accounts.permissions import can_manage
from apps.accounts.services import audit as account_audit
from apps.members.models import MemberProfile,MemberRevision,MembershipApplication,MemberSlug,MemberPrivateData
from apps.members import services as member_services
from apps.members.services import VersionConflict
from apps.content.models import Contributor
from apps.assets.models import AssetFile
from .permissions import actor_for
from .models import RevisionSubmission,RevisionEditEvent,ReviewDecision,MemberPublicationConsent
from .audit import record


def protect_target(actor,target):
    if target is None or not can_manage(actor,target):raise NotFound()


@transaction.atomic
def apply(request,data):
    actor=actor_for(request)
    if MembershipApplication.objects.filter(applicant=actor,state__in=['DRAFT','SUBMITTED']).exists():raise VersionConflict('An application is already pending.')
    if data.get('target_profile'):
        target=get_object_or_404(MemberProfile,pk=data['target_profile'],user__isnull=True,merged_into__isnull=True)
    else:target=None
    proof=None
    if data.get('proof_asset'):
        proof=AssetFile.objects.filter(pk=data['proof_asset'],owner=actor,scan_status='CLEAN',mime_type='application/pdf',expires_at__gt=timezone.now()).first()
        if proof is None:raise ValidationError({'proof_asset':'Proof unavailable.'})
    result=MembershipApplication.objects.create(applicant=actor,target_profile=target,application_kind=data['application_kind'],statement=data['statement'],proof_asset=proof,state='SUBMITTED')
    record(actor,result,'member.application.submit',('application_kind','proof_asset'))
    return result


@transaction.atomic
def decide_application(request,application_id,data):
    # Lock users in PK order like V2, then application, then profiles in UUID order.
    initial=get_object_or_404(MembershipApplication.objects.only('applicant_id'),pk=application_id)
    from apps.accounts.services import locked_users
    actor,target=locked_users(request,initial.applicant_id)
    protect_target(actor,target)
    if not target.is_active:raise VersionConflict("The applicant account is disabled.")
    application=get_object_or_404(MembershipApplication.objects.select_for_update(),pk=application_id)
    if actor.pk==target.pk:raise PermissionDenied('You cannot review your own application.')
    if application.state!='SUBMITTED' or application.lock_version!=data['lock_version']:raise VersionConflict()
    if data['decision']=='APPROVE':
        own=MemberProfile.objects.filter(user=target).first()
        ids=[p for p in (own.pk if own else None,application.target_profile_id) if p]
        profiles={p.pk:p for p in MemberProfile.objects.select_for_update().filter(pk__in=ids).order_by('pk')}
        own=profiles.get(own.pk) if own else None
        profile=profiles.get(application.target_profile_id) if application.target_profile_id else own
        if profile is None:
            profile=MemberProfile.objects.create(user=target,created_by=actor,updated_by=actor)
            MemberPrivateData.objects.create(profile=profile)
        if profile.merged_into_id or (profile.user_id is not None and profile.user_id!=target.pk):raise VersionConflict('The target profile is already claimed.')
        original_draft=own.draft_revision if own and own.pk!=profile.pk else None
        if own and own.pk!=profile.pk:
            if own.published_revision_id or Contributor.objects.filter(member_profile=own).exists() or own.membership_status!='PENDING' or own.revisions.exclude(state='DRAFT').exists():
                raise VersionConflict('Existing achievements or reviewed identity require an explicit manual merge.')
            # Preserve original drafts and application evidence under merged_into; no
            # transfer of authorship or silent overwrite of target's reviewed fields.
            own.user=None;own.merged_into=profile;own.public_visible=False;own.save(update_fields=['user','merged_into','public_visible','updated_at'])
            record(actor,own,'member.profile.merge',('user','merged_into'))
        if profile.published_revision and profile.published_revision.member_kind!=application.application_kind:
            raise ValidationError({'application_kind':'The requested identity differs from the existing approved profile.'})
        profile.user=target;profile.membership_status='ACTIVE';profile.updated_by=actor;profile.lock_version+=1
        profile.save(update_fields=['user','membership_status','updated_by','lock_version','updated_at'])
        if profile.draft_revision is None:
            revision=member_services.clone_revision(profile,target)
        else:revision=profile.draft_revision
        if revision.state!='DRAFT':raise VersionConflict('Resolve the existing pending profile revision before approving identity.')
        if original_draft and data.get('use_applicant_fields'):
            from apps.members.serializers import draft_data
            source=draft_data(own,original_draft)
            allowed=('display_name','slug','bio','public_contact_email','public_contact_enabled','education','research_areas','alumni','avatar_asset')
            merge={key:source[key] for key in allowed}
            if merge['avatar_asset']:
                import uuid
                merge['avatar_asset']=uuid.UUID(merge['avatar_asset'])
            merge['lock_version']=profile.lock_version
            profile,revision=member_services.update_draft(target,merge)
        revision.member_kind=application.application_kind;revision.save(update_fields=['member_kind'])
        RevisionEditEvent.objects.get_or_create(member_revision=revision,editor_snapshot=actor.pk,defaults={'editor':actor})
        if not Contributor.objects.filter(member_profile=profile).exists():
            Contributor.objects.create(member_profile=profile,display_name=(profile.published_revision.display_name if profile.published_revision else revision.display_name) or target.username)
        if target.role=='CUSTOMER':
            target.role='STUDENT';target.save(update_fields=['role'])
            account_audit('user.updated',actor=actor,target=target,request=request,fields=['role'],changes={'role':{'before':'CUSTOMER','after':'STUDENT'}})
        application.target_profile=profile;application.state='APPROVED'
    else:application.state='REJECTED'
    application.reviewed_by=actor;application.reviewed_at=timezone.now();application.review_note=data['reason'];application.lock_version+=1
    application.save()
    ReviewDecision.objects.create(application=application,reviewer=actor,reviewer_snapshot=actor.pk,decision=data['decision'],reason=data['reason'])
    record(actor,application,'member.application.'+data['decision'].lower(),('state','target_profile'))
    return application


@transaction.atomic
def withdraw_application(request,application_id,version):
    actor=actor_for(request)
    application=get_object_or_404(MembershipApplication.objects.select_for_update(),pk=application_id,applicant=actor)
    if application.state not in ('DRAFT','SUBMITTED') or application.lock_version!=version:raise VersionConflict()
    application.state='WITHDRAWN';application.lock_version+=1;application.save(update_fields=['state','lock_version'])
    record(actor,application,'member.application.withdraw',('state',))
    return application


@transaction.atomic
def submit_profile(request,data):
    actor=actor_for(request)
    profile=get_object_or_404(MemberProfile.objects.select_for_update(),user=actor,merged_into__isnull=True)
    if profile.membership_status not in ('ACTIVE','ALUMNI'):raise PermissionDenied('Approve membership before publishing a profile.')
    if not profile.draft_revision_id:raise NotFound()
    revision=MemberRevision.objects.select_for_update().get(pk=profile.draft_revision_id)
    if revision.state!='DRAFT' or profile.lock_version!=data['lock_version']:raise VersionConflict()
    if not revision.display_name.strip() or not revision.slug:raise ValidationError({'detail':'Display name and slug are required.'})
    if data['contact_visible'] and not (revision.public_contact_enabled and revision.public_contact_email):raise ValidationError({'public_contact_email':'Explicit public contact consent and address required.'})
    if revision.avatar_asset_id:
        image=revision.avatar_asset
        if image.scan_status!='CLEAN' or image.owner_id!=actor.pk or (image.expires_at and image.expires_at<=timezone.now()):raise ValidationError({'avatar_asset':'Upload a current validated avatar first.'})
    revision.state='SUBMITTED';revision.save(update_fields=['state'])
    RevisionSubmission.objects.create(member_revision=revision,submitted_by=actor,submitter_snapshot=actor.pk)
    MemberPublicationConsent.objects.create(revision=revision,privacy_version=profile.privacy_version,**{k:data[k] for k in ('public_visible','contact_visible','education_visible','alumni_visible')})
    profile.lock_version+=1;profile.save(update_fields=['lock_version','updated_at'])
    record(actor,profile,'member.profile.submit',('state',),revision)
    return profile


@transaction.atomic
def decide_profile(request,revision_id,data):
    initial=get_object_or_404(MemberRevision.objects.only('profile_id'),pk=revision_id)
    reference=MemberProfile.objects.only('user_id').get(pk=initial.profile_id)
    from apps.accounts.services import locked_users
    from apps.accounts.permissions import is_manager
    actor,target=locked_users(request,reference.user_id)
    if not is_manager(actor):raise PermissionDenied()
    protect_target(actor,target)
    profile=MemberProfile.objects.select_for_update().get(pk=initial.profile_id)
    if profile.user_id!=target.pk:raise VersionConflict('Profile binding changed.')
    revision=MemberRevision.objects.select_for_update().get(pk=revision_id)
    if profile.lock_version!=data['lock_version'] or revision.state!='SUBMITTED' or profile.draft_revision_id!=revision.pk:raise VersionConflict()
    submission=get_object_or_404(RevisionSubmission,member_revision=revision)
    if submission.submitter_snapshot==actor.pk or revision.edit_events.filter(editor_snapshot=actor.pk).exists():raise PermissionDenied('Reviewing your own changes is not allowed.')
    if revision.base_published_revision_id!=profile.published_revision_id:raise VersionConflict('Published profile baseline changed.')
    if data['decision']=='APPROVE':
        consent=revision.publication_consent
        if consent.privacy_version!=profile.privacy_version:raise VersionConflict('Public consent changed; withdraw and resubmit.')
        if profile.membership_status not in ('ACTIVE','ALUMNI'):raise VersionConflict('Membership is no longer active.')
        existing=MemberSlug.objects.filter(slug=revision.slug).first()
        if existing and existing.profile_id!=profile.pk:raise ValidationError({'slug':'Slug already reserved.'})
        if not existing:MemberSlug.objects.create(profile=profile,slug=revision.slug)
        if revision.avatar_asset_id:
            image=AssetFile.objects.select_for_update().get(pk=revision.avatar_asset_id)
            if image.scan_status!='CLEAN' or image.owner_id!=profile.user_id or (image.expires_at and image.expires_at<=timezone.now()):raise ValidationError({'avatar_asset':'Avatar no longer available.'})
            image.expires_at=None;image.visibility='PUBLIC';image.save(update_fields=['expires_at','visibility'])
        revision.state='PUBLISHED';revision.save(update_fields=['state'])
        profile.published_revision=revision
        for field in ('public_visible','contact_visible','education_visible','alumni_visible'):setattr(profile,field,getattr(consent,field))
    else:
        revision.state='REJECTED';revision.save(update_fields=['state'])
    profile.draft_revision=None;profile.lock_version+=1;profile.save()
    ReviewDecision.objects.create(member_revision=revision,reviewer=actor,reviewer_snapshot=actor.pk,decision=data['decision'],reason=data['reason'])
    record(actor,profile,'member.profile.review.'+data['decision'].lower(),('state','published_revision'),revision)
    return profile


@transaction.atomic
def withdraw_profile(request,version):
    actor=actor_for(request)
    profile=get_object_or_404(MemberProfile.objects.select_for_update(),user=actor)
    if not profile.draft_revision_id or profile.lock_version!=version:raise VersionConflict()
    revision=MemberRevision.objects.select_for_update().get(pk=profile.draft_revision_id)
    if revision.state!='SUBMITTED':raise VersionConflict()
    revision.state='WITHDRAWN';revision.save(update_fields=['state'])
    profile.draft_revision=None;profile.lock_version+=1;profile.save(update_fields=['draft_revision','lock_version','updated_at'])
    record(actor,profile,'member.profile.withdraw',('state',),revision)
    return profile


@transaction.atomic
def restrict_privacy(request,scopes):
    actor=actor_for(request)
    profile=get_object_or_404(MemberProfile.objects.select_for_update(),user=actor)
    fields={'public':'public_visible','contact':'contact_visible','education':'education_visible','alumni':'alumni_visible'}
    for scope in scopes:setattr(profile,fields[scope],False)
    profile.privacy_version+=1;profile.lock_version+=1
    profile.save(update_fields=[fields[s] for s in set(scopes)]+['privacy_version','lock_version','updated_at'])
    record(actor,profile,'member.privacy.restrict',[fields[s] for s in scopes])
    return profile
