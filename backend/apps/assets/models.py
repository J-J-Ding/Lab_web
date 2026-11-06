import uuid
from django.conf import settings
from django.db import models


class AssetFile(models.Model):
    class Visibility(models.TextChoices):
        PRIVATE='PRIVATE'
        PUBLIC='PUBLIC'
    class ScanStatus(models.TextChoices):
        PENDING='PENDING'
        CLEAN='CLEAN'
        REJECTED='REJECTED'
    id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner=models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    purpose=models.CharField(max_length=12,choices=[('avatar','avatar'),('proof','proof'),('image','image'),('attachment','attachment'),('ai_source','ai_source')],default='proof')
    deletion_requested_at=models.DateTimeField(null=True,blank=True)
    storage_key=models.CharField(max_length=255, unique=True)
    original_filename=models.CharField(max_length=255)
    mime_type=models.CharField(max_length=100)
    size=models.PositiveBigIntegerField()
    sha256=models.CharField(max_length=64)
    visibility=models.CharField(max_length=8, choices=Visibility, default=Visibility.PRIVATE)
    scan_status=models.CharField(max_length=8, choices=ScanStatus, default=ScanStatus.PENDING)
    expires_at=models.DateTimeField(null=True, blank=True, db_index=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(visibility__in=['PRIVATE','PUBLIC']), name='asset_visibility_valid'),models.CheckConstraint(condition=models.Q(scan_status__in=['PENDING','CLEAN','REJECTED']),name='asset_scan_valid')]
