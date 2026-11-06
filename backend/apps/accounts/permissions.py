from rest_framework.permissions import BasePermission

ORDINARY_ROLES = ('CUSTOMER', 'STUDENT', 'TEACHER')


def is_manager(user):
    return bool(user and user.is_authenticated and user.is_active and (user.is_superuser or user.role in ('ADMIN', 'TEACHER')))


def can_manage(actor, target):
    return bool(actor and actor.is_authenticated and actor.is_active and actor.is_superuser)


class IsManager(BasePermission):
    def has_permission(self, request, view):
        return is_manager(request.user)


class IsRoot(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_active and request.user.is_superuser)
