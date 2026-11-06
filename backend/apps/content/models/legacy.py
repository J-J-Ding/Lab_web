import uuid
from django.conf import settings
from django.db import models

class ImportBatch(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    manifest_sha256=models.CharField(max_length=64)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL)
    created_at=models.DateTimeField(auto_now_add=True)
class ImportRecord(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    batch=models.ForeignKey(ImportBatch,on_delete=models.PROTECT,related_name='records')
    source_path=models.CharField(max_length=1000)
    source_sha256=models.CharField(max_length=64)
    payload_sha256=models.CharField(max_length=64)
    kind=models.CharField(max_length=12)
    status=models.CharField(max_length=12)
    error=models.CharField(max_length=2000,blank=True)
    item=models.ForeignKey('ContentItem',null=True,on_delete=models.PROTECT)
    member=models.ForeignKey('members.MemberProfile',null=True,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['batch','source_path'],name='legacy_batch_source_unique')]
class LegacyURLMap(models.Model):
    path=models.CharField(max_length=1000,unique=True)
    item=models.ForeignKey('ContentItem',null=True,on_delete=models.PROTECT)
    member=models.ForeignKey('members.MemberProfile',null=True,on_delete=models.PROTECT)
    batch=models.ForeignKey(ImportBatch,on_delete=models.PROTECT)
    source_sha256=models.CharField(max_length=64)
    class Meta:
        constraints=[models.CheckConstraint(condition=(models.Q(item__isnull=False,member__isnull=True)|models.Q(item__isnull=True,member__isnull=False)),name='legacy_exactly_one_target')]
