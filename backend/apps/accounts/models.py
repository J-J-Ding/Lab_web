import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserRole(models.TextChoices):
    ADMIN = "ADMIN", "管理员"
    TEACHER = "TEACHER", "教师"
    STUDENT = "STUDENT", "学生"
    CUSTOMER = "CUSTOMER", "访客"


class User(AbstractUser):
    session_version = models.PositiveBigIntegerField(default=0)
    role = models.CharField(max_length=8, choices=UserRole.choices, default=UserRole.CUSTOMER)

    class Meta(AbstractUser.Meta):
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=UserRole.values),
                name="accounts_user_valid_role",
            ),
        ]


class AuthAuditLog(models.Model):
    actor = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='auth_actions')
    target = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='auth_events')
    actor_snapshot = models.PositiveBigIntegerField(null=True)
    target_snapshot = models.PositiveBigIntegerField(null=True)
    action = models.CharField(max_length=48)
    outcome = models.CharField(max_length=12, default='success')
    changed_fields = models.JSONField(default=list)
    changes = models.JSONField(default=dict)
    source_digest = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)


class LoginThrottleBucket(models.Model):
    scope = models.CharField(max_length=16)
    key_digest = models.CharField(max_length=64)
    attempt_count = models.PositiveIntegerField(default=0)
    window_start = models.DateTimeField()
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['scope', 'key_digest'], name='unique_login_throttle_bucket')]


class AccountImportBatch(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    owner=models.ForeignKey(User,on_delete=models.PROTECT,related_name='account_imports')
    state=models.CharField(max_length=8,default='PREVIEW',choices=[(s,s) for s in ('PREVIEW','QUEUED','RUNNING','DONE','FAILED','EXPIRED')])
    storage_key=models.CharField(max_length=80,blank=True)
    rows=models.JSONField(default=list)
    errors=models.JSONField(default=list)
    created_ids=models.JSONField(default=list)
    expires_at=models.DateTimeField()
    started_at=models.DateTimeField(null=True)
    finished_at=models.DateTimeField(null=True)
    created_at=models.DateTimeField(auto_now_add=True)
