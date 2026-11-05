from datetime import timedelta
import math

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac
from rest_framework.exceptions import Throttled

from .models import LoginThrottleBucket


def digest(value):
    return salted_hmac('lab-web-auth', value, algorithm='sha256').hexdigest()


def source_digest(request):
    return digest(request.META.get('REMOTE_ADDR', 'unknown'))


def consume(scope, identity, limit):
    now = timezone.now()
    wait = None
    with transaction.atomic():
        bucket, _ = LoginThrottleBucket.objects.select_for_update().get_or_create(
            scope=scope, key_digest=digest(identity),
            defaults={'window_start': now, 'expires_at': now + timedelta(seconds=settings.AUTH_LOGIN_WINDOW_SECONDS)},
        )
        if bucket.expires_at <= now:
            bucket.window_start = now
            bucket.expires_at = now + timedelta(seconds=settings.AUTH_LOGIN_WINDOW_SECONDS)
            bucket.attempt_count = 0
        if bucket.attempt_count >= limit:
            wait = max(1, math.ceil((bucket.expires_at - now).total_seconds()))
        else:
            bucket.attempt_count += 1
            bucket.save(update_fields=['attempt_count', 'window_start', 'expires_at'])
    if wait is not None:
        raise Throttled(wait=wait)


def consume_ip(request):
    consume('ip', request.META.get('REMOTE_ADDR', 'unknown'), settings.AUTH_LOGIN_IP_LIMIT)


def consume_account(request, username):
    ip = request.META.get('REMOTE_ADDR', 'unknown')
    consume('account_ip', f'{ip}\0{username}', settings.AUTH_LOGIN_ACCOUNT_IP_LIMIT)
