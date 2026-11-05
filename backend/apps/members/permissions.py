from rest_framework.exceptions import NotFound,PermissionDenied
from apps.accounts.models import User
from apps.accounts.permissions import can_manage


def lock_actor(actor):
    user=User.objects.select_for_update().get(pk=actor.pk)
    if not user.is_active:
        raise PermissionDenied()
    return user


def require_management(actor, profile):
    if profile.user_id:
        if not can_manage(actor,profile.user):
            raise NotFound()
    elif not (actor.is_superuser or actor.role in ('ADMIN','TEACHER')) or not actor.is_active:
        raise NotFound()
