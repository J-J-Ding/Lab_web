from django.contrib.auth import HASH_SESSION_KEY, authenticate, login, logout, update_session_auth_hash
from django.db import DatabaseError, IntegrityError, transaction
from django.utils.crypto import constant_time_compare
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from .authentication import SESSION_VERSION_KEY
from .models import AuthAuditLog, User
from .permissions import ORDINARY_ROLES, can_manage, is_manager
from .serializers import check_password
from .throttling import source_digest


def audit(action, *, actor=None, target=None, request=None, fields=(), changes=None, outcome='success', actor_snapshot=None, target_snapshot=None):
    return AuthAuditLog.objects.create(
        actor=actor, target=target,
        actor_snapshot=actor.pk if actor else actor_snapshot,
        target_snapshot=target.pk if target else target_snapshot,
        action=action, outcome=outcome, changed_fields=list(fields), changes=changes or {},
        source_digest=source_digest(request) if request else '',
    )


def locked_users(request, target_id=None):
    ids = {request.user.pk}
    if target_id is not None:
        ids.add(target_id)
    users = {u.pk: u for u in User.objects.select_for_update().filter(pk__in=ids).order_by('pk')}
    actor = users.get(request.user.pk)
    if not actor or not actor.is_active or request.session.get(SESSION_VERSION_KEY) != actor.session_version or not constant_time_compare(request.session.get(HASH_SESSION_KEY, ''), actor.get_session_auth_hash()):
        raise PermissionDenied('Session is no longer valid.')
    target = users.get(target_id) if target_id is not None else None
    return actor, target


def visible_users(actor):
    if actor.is_superuser:
        return User.objects.all().order_by('pk')
    return User.objects.none()


def create_user(data, request, managed=False):
    try:
        with transaction.atomic():
            actor = None
            if managed:
                actor, _ = locked_users(request)
                if not actor.is_superuser:
                    raise PermissionDenied()
                if not actor.is_superuser and data.get('role', 'CUSTOMER') not in ORDINARY_ROLES:
                    raise PermissionDenied('Role is not assignable.')
            fields = dict(data)
            password = fields.pop('password')
            user = User(**fields)
            user.set_password(password)
            user.save()
            audit('user.created' if managed else 'auth.registered', actor=actor, target=user, request=request, fields=fields.keys())
            return user
    except IntegrityError:
        if User.objects.filter(username=data['username']).exists():
            raise ValidationError({'username': ['Username already exists.']}) from None
        raise


def login_user(request, data):
    try:
        with transaction.atomic():
            target = User.objects.select_for_update().filter(username=data['username']).first()
            user = authenticate(request=request._request, **data)
            if user is None:
                audit('auth.login', target=target, request=request, outcome='failure')
                return None
            login(request._request, user)
            request.session[SESSION_VERSION_KEY] = user.session_version
            audit('auth.login', actor=user, target=user, request=request)
            return user
    except DatabaseError:
        request.session.flush()
        raise


def logout_user(request):
    with transaction.atomic():
        actor, _ = locked_users(request)
        audit('auth.logout', actor=actor, target=actor, request=request)
        logout(request._request)


def update_profile(request, data):
    with transaction.atomic():
        actor, _ = locked_users(request)
        for key, value in data.items():
            setattr(actor, key, value)
        actor.save(update_fields=list(data))
        audit('user.profile_changed', actor=actor, target=actor, request=request, fields=data.keys())
        return actor


def change_password(request, data):
    with transaction.atomic():
        actor, _ = locked_users(request)
        if not actor.check_password(data['old_password']):
            raise ValidationError({'old_password': ['Incorrect password.']})
        check_password(data['new_password'], actor)
        actor.set_password(data['new_password'])
        actor.save(update_fields=['password'])
        audit('auth.password_changed', actor=actor, target=actor, request=request, fields=['password'])
        update_session_auth_hash(request._request, actor)


def manage_user(request, target_id, data, reset_password=False):
    with transaction.atomic():
        actor, target = locked_users(request, target_id)
        if not actor.is_superuser:
            raise PermissionDenied()
        if target is None or not can_manage(actor, target):
            raise NotFound()
        if reset_password:
            check_password(data['new_password'], target)
            target.set_password(data['new_password'])
            target.save(update_fields=['password'])
            audit('user.password_reset', actor=actor, target=target, request=request, fields=['password'])
        else:
            if 'role' in data and not actor.is_superuser:
                if data['role'] not in ORDINARY_ROLES or actor.pk == target.pk:
                    raise PermissionDenied('Role is not assignable.')
            changes = {key: {'before': getattr(target, key), 'after': data[key]} for key in ('role', 'is_active') if key in data and getattr(target, key) != data[key]}
            if (target.is_active and data.get('is_active') is False) or ('role' in data and target.role!=data['role']):
                target.session_version += 1
            for key, value in data.items():
                setattr(target, key, value)
            target.save()
            if 'role' in data:
                from apps.members.models import MemberProfile
                profile,_=MemberProfile.objects.get_or_create(user=target,defaults={'created_by':actor,'updated_by':actor})
                if target.role=='CUSTOMER':
                    profile.public_visible=profile.contact_visible=profile.education_visible=profile.alumni_visible=False
                    profile.save()
            audit('user.updated', actor=actor, target=target, request=request, fields=data.keys(), changes=changes)
        return target
