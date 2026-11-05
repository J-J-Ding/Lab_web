from rest_framework.permissions import BasePermission

ORDINARY_ROLES = ('CUSTOMER', 'STUDENT', 'TEACHER')


def is_manager(user):
    return bool(user and user.is_authenticated and user.is_active and (user.is_superuser or user.role in ('ADMIN', 'TEACHER')))


def can_manage(actor, target):
    return is_manager(actor) and (actor.is_superuser or (not target.is_superuser and target.role in ORDINARY_ROLES))


class IsManager(BasePermission):
    def has_permission(self, request, view):
        return is_manager(request.user)
