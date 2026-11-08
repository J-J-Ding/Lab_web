import uuid
from django.conf import settings
from django.db import models
from django.db.models import F,Q
from apps.workflow.models import RevisionState


class MemberProfile(models.Model):
    class Status(models.TextChoices):
        PENDING='PENDING'
        ACTIVE='ACTIVE'
        ALUMNI='ALUMNI'
        LEFT='LEFT'
    id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user=models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='member_profile')
    membership_status=models.CharField(max_length=8,choices=Status,default=Status.PENDING)
    # Immediate deny gates are separate from immutable approved snapshots.
    public_visible=models.BooleanField(default=False)
    contact_visible=models.BooleanField(default=False)
    education_visible=models.BooleanField(default=False)
    alumni_visible=models.BooleanField(default=False)
    merged_into=models.ForeignKey('self',null=True,blank=True,on_delete=models.PROTECT)
    draft_revision=models.OneToOneField('MemberRevision',null=True,blank=True,on_delete=models.SET_NULL,related_name='+')
    published_revision=models.OneToOneField('MemberRevision',null=True,blank=True,on_delete=models.PROTECT,related_name='+')
    lock_version=models.PositiveBigIntegerField(default=0)
    privacy_version=models.PositiveBigIntegerField(default=0)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL,related_name='+')
    updated_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL,related_name='+')
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=Q(membership_status__in=['PENDING','ACTIVE','ALUMNI','LEFT']),name='member_status_valid'),models.CheckConstraint(condition=~Q(merged_into=F('id')),name='member_no_self_merge')]


class MemberRevision(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    profile=models.ForeignKey(MemberProfile,on_delete=models.CASCADE,related_name='revisions')
    number=models.PositiveIntegerField()
    base_published_revision=models.ForeignKey("self",null=True,blank=True,on_delete=models.PROTECT,related_name="+")
    member_kind=models.CharField(max_length=8,choices=[('STUDENT','STUDENT'),('TEACHER','TEACHER'),('CUSTOMER','CUSTOMER')],default='STUDENT')
    public_member_status=models.CharField(max_length=8,choices=[('ACTIVE','ACTIVE'),('ALUMNI','ALUMNI'),('LEFT','LEFT')],default='ACTIVE')
    display_name=models.CharField(max_length=150,blank=True)
    slug=models.SlugField(max_length=160,blank=True,allow_unicode=True)
    highest_education=models.CharField(max_length=32,blank=True)
    enrollment_year=models.PositiveIntegerField(null=True,blank=True)
    bio=models.TextField(blank=True,max_length=10000)
    public_contact_email=models.EmailField(blank=True)
    public_contact_enabled=models.BooleanField(default=False)
    avatar_asset=models.ForeignKey('assets.AssetFile',null=True,blank=True,on_delete=models.PROTECT)
    state=models.CharField(max_length=12,choices=RevisionState,default=RevisionState.DRAFT)
    edited_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['profile','number'],name='member_revision_number_unique'),models.UniqueConstraint(fields=['profile'],condition=Q(state__in=['DRAFT','SUBMITTED','APPROVED']),name='member_one_working_revision'),models.CheckConstraint(condition=Q(number__gt=0),name='member_revision_positive'),models.CheckConstraint(condition=Q(state__in=RevisionState.values),name='member_revision_state_valid'),models.CheckConstraint(condition=Q(member_kind__in=['STUDENT','TEACHER','CUSTOMER']),name='member_kind_valid'),models.CheckConstraint(condition=Q(public_member_status__in=['ACTIVE','ALUMNI','LEFT']),name='member_public_status_valid'),models.CheckConstraint(condition=Q(public_contact_enabled=False)|~Q(public_contact_email=''),name='member_public_contact_required')]


class MemberSlug(models.Model):
    slug=models.SlugField(max_length=160,unique=True,allow_unicode=True)
    profile=models.ForeignKey(MemberProfile,on_delete=models.PROTECT,related_name='slugs')


class MemberPrivateData(models.Model):
    profile=models.OneToOneField(MemberProfile,on_delete=models.CASCADE,related_name='private_data')
    phone=models.CharField(max_length=40,blank=True)
    internal_contact=models.CharField(max_length=254,blank=True)
    cv_data=models.JSONField(default=dict,blank=True)
    management_note=models.TextField(blank=True,max_length=5000)


class EducationEntry(models.Model):
    revision=models.ForeignKey(MemberRevision,on_delete=models.CASCADE,related_name='education')
    school=models.CharField(max_length=200)
    education_level=models.CharField(max_length=32,blank=True)
    major=models.CharField(max_length=200,blank=True)
    degree=models.CharField(max_length=100,blank=True)
    start_date=models.DateField(null=True,blank=True)
    end_date=models.DateField(null=True,blank=True)
    is_public=models.BooleanField(default=False)
    position=models.PositiveIntegerField()
    class Meta:
        ordering=['position','pk']
        constraints=[models.UniqueConstraint(fields=['revision','position'],name='education_position_unique'),models.CheckConstraint(condition=Q(position__gt=0),name='education_position_positive'),models.CheckConstraint(condition=Q(start_date__isnull=True)|Q(end_date__isnull=True)|Q(end_date__gte=F('start_date')),name='education_date_order')]


class ResearchArea(models.Model):
    name=models.CharField(max_length=100,unique=True)


class MemberResearchArea(models.Model):
    revision=models.ForeignKey(MemberRevision,on_delete=models.CASCADE,related_name='research_links')
    area=models.ForeignKey(ResearchArea,on_delete=models.PROTECT)
    position=models.PositiveIntegerField()
    class Meta:
        ordering=['position','pk']
        constraints=[models.UniqueConstraint(fields=['revision','area'],name='member_area_unique'),models.UniqueConstraint(fields=['revision','position'],name='member_area_position_unique'),models.CheckConstraint(condition=Q(position__gt=0),name='member_area_position_positive')]


class AlumniDestination(models.Model):
    revision=models.OneToOneField(MemberRevision,on_delete=models.CASCADE,related_name='alumni')
    graduation_year=models.PositiveIntegerField(null=True,blank=True)
    degree=models.CharField(max_length=100,blank=True)
    destination_type=models.CharField(max_length=16,choices=[('WORK','WORK'),('STUDY','STUDY'),('OTHER','OTHER')])
    organization=models.CharField(max_length=200,blank=True)
    is_public=models.BooleanField(default=False)
    class Meta:
        constraints=[models.CheckConstraint(condition=Q(graduation_year__gte=1900)&Q(graduation_year__lte=2200),name='alumni_year_range'),models.CheckConstraint(condition=Q(destination_type__in=['WORK','STUDY','OTHER']),name='alumni_destination_valid')]


class MembershipApplication(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    applicant=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='membership_applications')
    target_profile=models.ForeignKey(MemberProfile,null=True,blank=True,on_delete=models.PROTECT)
    application_kind=models.CharField(max_length=8,choices=[('STUDENT','STUDENT'),('TEACHER','TEACHER')])
    statement=models.CharField(max_length=2000,blank=True)
    review_note=models.CharField(max_length=2000,blank=True)
    lock_version=models.PositiveBigIntegerField(default=0)
    state=models.CharField(max_length=12,default='DRAFT')
    proof_asset=models.ForeignKey('assets.AssetFile',null=True,blank=True,on_delete=models.PROTECT)
    reviewed_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name='+')
    reviewed_at=models.DateTimeField(null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['applicant'],condition=Q(state__in=['DRAFT','SUBMITTED']),name='member_one_active_application'),models.CheckConstraint(condition=Q(state__in=['DRAFT','SUBMITTED','APPROVED','REJECTED','WITHDRAWN']),name='application_state_valid'),models.CheckConstraint(condition=Q(application_kind__in=['STUDENT','TEACHER']),name='application_kind_valid')]


class MemberRevisionAsset(models.Model):
    revision=models.ForeignKey(MemberRevision,on_delete=models.CASCADE,related_name='assets')
    asset=models.ForeignKey('assets.AssetFile',on_delete=models.PROTECT)
    purpose=models.CharField(max_length=32)
    position=models.PositiveIntegerField(default=1)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['revision','asset','purpose'],name='member_asset_unique'),models.CheckConstraint(condition=Q(position__gt=0),name='member_asset_position_positive')]


class Resume(models.Model):
    deleted_at=models.DateTimeField(null=True,blank=True,db_index=True)
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='resumes')
    title=models.CharField(max_length=200,default='我的简历')
    intention=models.CharField(max_length=300,blank=True)
    introduction=models.TextField(blank=True,max_length=10000)
    asset=models.ForeignKey('assets.AssetFile',null=True,blank=True,on_delete=models.PROTECT)
    lock_version=models.PositiveBigIntegerField(default=0)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)


class ResumeSubmission(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='resume_submissions')
    resume=models.ForeignKey(Resume,on_delete=models.PROTECT,related_name='submissions')
    asset=models.ForeignKey('assets.AssetFile',on_delete=models.PROTECT,related_name='resume_submissions')
    resume_version=models.PositiveBigIntegerField()
    profile_snapshot=models.JSONField(default=dict)
    resume_snapshot=models.JSONField(default=dict)
    state=models.CharField(max_length=12,default='SUBMITTED',choices=[('SUBMITTED','已投递'),('WITHDRAWN','已撤回')])
    created_at=models.DateTimeField(auto_now_add=True)
    withdrawn_at=models.DateTimeField(null=True,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['owner','resume'],condition=Q(state='SUBMITTED'),name='one_active_resume_submission'),models.CheckConstraint(condition=Q(state__in=['SUBMITTED','WITHDRAWN']),name='resume_submission_state_valid')]


class SubmissionNotification(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    recipient=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='submission_notifications')
    submission=models.ForeignKey(ResumeSubmission,on_delete=models.PROTECT,related_name='notifications')
    created_at=models.DateTimeField(auto_now_add=True)
    read_at=models.DateTimeField(null=True,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['recipient','submission'],name='submission_notice_recipient_unique')]
        indexes=[models.Index(fields=['recipient','read_at'])]
