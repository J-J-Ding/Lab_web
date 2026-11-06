from rest_framework.exceptions import NotFound,PermissionDenied
from apps.accounts.models import User
from apps.accounts.permissions import can_manage


def lock_actor(actor):
    user=User.objects.select_for_update().get(pk=actor.pk)
    if not user.is_active:
        raise PermissionDenied()
    return user


def require_management(actor, profile):
    if actor.is_superuser or profile.user_id == actor.pk:
        return
    if actor.is_active and actor.role in ('ADMIN','TEACHER') and profile.user_id and profile.user.role in ('TEACHER','STUDENT') and not profile.user.is_superuser:
        return
    raise NotFound()
