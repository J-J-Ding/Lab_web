import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q

ACTIVE_STATES=['QUEUED','EXTRACTING','AWAITING_CONSENT','CALLING','VALIDATING']
class AIImportJob(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='ai_jobs')
    asset=models.ForeignKey('assets.AssetFile',null=True,on_delete=models.SET_NULL,related_name='ai_import_jobs')
    target_type=models.CharField(max_length=12)
    mode=models.CharField(max_length=8,default='IMPORT')
    state=models.CharField(max_length=20,default='QUEUED',db_index=True)
    model_name=models.CharField(max_length=80,default='deepseek-flash')
    prompt_version=models.CharField(max_length=30,default='extract-v1')
    source_pages=models.JSONField(default=list)
    source_preview=models.TextField(blank=True)
    selected_text=models.TextField(blank=True)
    input_digest=models.CharField(max_length=64,blank=True)
    lease_token=models.UUIDField(null=True)
    lease_expires_at=models.DateTimeField(null=True)
    heartbeat_at=models.DateTimeField(null=True)
    attempts=models.PositiveIntegerField(default=0)
    error_code=models.CharField(max_length=60,blank=True)
    lock_version=models.PositiveBigIntegerField(default=0)
    deleted_at=models.DateTimeField(null=True)
    finished_at=models.DateTimeField(null=True)
    created_at=models.DateTimeField(auto_now_add=True)
    expires_at=models.DateTimeField()
    class Meta:
        constraints=[models.UniqueConstraint(fields=['owner'],condition=Q(state__in=ACTIVE_STATES,deleted_at__isnull=True),name='ai_owner_one_active_job'),models.CheckConstraint(condition=Q(state__in=ACTIVE_STATES+['READY','APPLIED','FAILED','CANCELLED','EXPIRED']),name='ai_job_state_valid')]
        indexes=[models.Index(fields=['state','created_at'])]
class AIConsent(models.Model):
    job=models.ForeignKey(AIImportJob,on_delete=models.PROTECT,related_name='consents')
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    version=models.CharField(max_length=30)
    scopes=models.JSONField(default=list)
    text_digest=models.CharField(max_length=64,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    revoked_at=models.DateTimeField(null=True)
class AICandidate(models.Model):
    job=models.OneToOneField(AIImportJob,on_delete=models.PROTECT,primary_key=True,related_name='candidate')
    schema_version=models.PositiveIntegerField(default=1)
    data=models.JSONField(default=dict)
    applied=models.JSONField(default=dict)
    confirmed_at=models.DateTimeField(null=True)
    applied_revision=models.ForeignKey('content.ContentRevision',null=True,on_delete=models.PROTECT,related_name='+')
    applied_member_revision=models.ForeignKey('members.MemberRevision',null=True,on_delete=models.PROTECT,related_name='+')
    expires_at=models.DateTimeField()
class AIUsageLedger(models.Model):
    job=models.OneToOneField(AIImportJob,on_delete=models.PROTECT,related_name='usage')
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    request_digest=models.CharField(max_length=64,unique=True)
    state=models.CharField(max_length=12,default='RESERVED')
    reserved_cny=models.DecimalField(max_digits=12,decimal_places=6)
    actual_cny=models.DecimalField(max_digits=12,decimal_places=6,null=True)
    input_tokens=models.PositiveIntegerField(default=0)
    output_tokens=models.PositiveIntegerField(default=0)
    price_snapshot=models.JSONField(default=dict)
    request_id_digest=models.CharField(max_length=64,blank=True)
    billing_day_utc=models.DateField()
    business_day=models.DateField()
    created_at=models.DateTimeField(auto_now_add=True)
    settled_at=models.DateTimeField(null=True)
    sent_at=models.DateTimeField(null=True)
    reconciliation_reason_digest=models.CharField(max_length=64,blank=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=Q(state__in=['RESERVED','SETTLED','RELEASED','UNKNOWN']),name='ai_usage_state_valid'),models.CheckConstraint(condition=Q(reserved_cny__gte=0),name='ai_usage_reserved_nonnegative')]
class AIQuotaBucket(models.Model):
    scope=models.CharField(max_length=20)
    owner_key=models.PositiveBigIntegerField(default=0)
    day=models.DateField()
    count=models.PositiveIntegerField(default=0)
    reserved_cny=models.DecimalField(max_digits=12,decimal_places=6,default=0)
    spent_cny=models.DecimalField(max_digits=12,decimal_places=6,default=0)
    failures=models.PositiveIntegerField(default=0)
    blocked_until=models.DateTimeField(null=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['scope','owner_key','day'],name='ai_quota_bucket_unique'),models.CheckConstraint(condition=Q(reserved_cny__gte=0,spent_cny__gte=0),name='ai_quota_money_nonnegative')]
