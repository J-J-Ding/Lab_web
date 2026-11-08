import uuid
from django.conf import settings
from django.db import models


class ContentImportBatch(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='content_imports')
    source=models.CharField(max_length=8)
    asset=models.ForeignKey('assets.AssetFile',null=True,on_delete=models.PROTECT,related_name='content_imports')
    state=models.CharField(max_length=24,default='READY',db_index=True)
    records=models.JSONField(default=list)
    pages=models.JSONField(default=list)
    selected_text=models.TextField(blank=True)
    segments=models.JSONField(default=list)
    processed=models.PositiveIntegerField(default=0)
    warnings=models.JSONField(default=list)
    errors=models.JSONField(default=list)
    selected=models.JSONField(default=list)
    created=models.JSONField(default=dict)
    lock_version=models.PositiveBigIntegerField(default=0)
    consent_at=models.DateTimeField(null=True)
    lease_at=models.DateTimeField(null=True)
    expires_at=models.DateTimeField()
    created_at=models.DateTimeField(auto_now_add=True)


class ContentImportCall(models.Model):
    batch=models.ForeignKey(ContentImportBatch,on_delete=models.PROTECT,related_name='calls')
    number=models.PositiveIntegerField()
    state=models.CharField(max_length=12,default='RESERVED')
    request_digest=models.CharField(max_length=64,unique=True)
    reserved=models.DecimalField(max_digits=12,decimal_places=6)
    actual=models.DecimalField(max_digits=12,decimal_places=6,null=True)
    prices=models.JSONField(default=dict)
    input_tokens=models.PositiveIntegerField(default=0)
    output_tokens=models.PositiveIntegerField(default=0)
    billing_day=models.DateField()
    sent_at=models.DateTimeField(null=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['batch','number'],name='content_import_call_number_unique')]


class ContentPatentReservation(models.Model):
    number=models.CharField(max_length=100,unique=True)
    item=models.ForeignKey('content.ContentItem',on_delete=models.PROTECT)
