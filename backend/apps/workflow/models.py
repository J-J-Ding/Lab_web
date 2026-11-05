import uuid
from django.conf import settings
from django.db import models


class RevisionState(models.TextChoices):
    DRAFT='DRAFT'
    SUBMITTED='SUBMITTED'
    APPROVED='APPROVED'
    PUBLISHED='PUBLISHED'
    REJECTED='REJECTED'
    WITHDRAWN='WITHDRAWN'


class BusinessAuditLog(models.Model):
    id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    actor_snapshot=models.PositiveBigIntegerField(null=True)
    target_id=models.UUIDField(db_index=True)
    revision_id=models.UUIDField(null=True)
    action=models.CharField(max_length=64)
    outcome=models.CharField(max_length=16, default='success')
    changed_fields=models.JSONField(default=list)
    request_id=models.UUIDField(default=uuid.uuid4)
    created_at=models.DateTimeField(auto_now_add=True, db_index=True)
