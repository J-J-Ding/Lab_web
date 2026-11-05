from django.contrib.auth.models import AbstractUser
from django.db import models


class UserRole(models.TextChoices):
    ADMIN = "ADMIN", "管理员"
    TEACHER = "TEACHER", "教师"
    STUDENT = "STUDENT", "学生"
    CUSTOMER = "CUSTOMER", "访客"


class User(AbstractUser):
    role = models.CharField(max_length=8, choices=UserRole.choices, default=UserRole.CUSTOMER)

    class Meta(AbstractUser.Meta):
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=UserRole.values),
                name="accounts_user_valid_role",
            ),
        ]
