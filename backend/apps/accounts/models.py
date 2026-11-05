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
