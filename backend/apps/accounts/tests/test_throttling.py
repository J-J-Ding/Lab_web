from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from django.core.management import call_command
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from apps.accounts.models import AuthAuditLog, LoginThrottleBucket
from .helpers import PASSWORD, csrf_client, write


@override_settings(AUTH_LOGIN_ACCOUNT_IP_LIMIT=2, AUTH_LOGIN_IP_LIMIT=10)
class ThrottleTests(TestCase):
    def attempt(self, client=None, **extra):
        return write(client or csrf_client(), 'post', '/api/auth/login/', {'username': 'missing', 'password': PASSWORD}, **extra)

    def test_repeated_login_is_limited_across_clients_and_forwarded_ips(self):
        responses = [self.attempt(HTTP_X_FORWARDED_FOR=f'10.1.1.{i}') for i in range(3)]
        self.assertEqual([r.status_code for r in responses], [400, 400, 429])
        self.assertGreater(int(responses[-1]['Retry-After']), 0)
        self.assertTrue(AuthAuditLog.objects.filter(outcome='throttled').exists())

    def test_expired_window_allows_new_attempt(self):
        self.attempt()
        self.attempt()
        self.assertEqual(self.attempt().status_code, 429)
        LoginThrottleBucket.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.attempt().status_code, 400)

    @override_settings(AUTH_LOGIN_IP_LIMIT=2)
    def test_invalid_payload_counts_against_ip_limit(self):
        client = csrf_client()
        codes = [write(client, 'post', '/api/auth/login/', {'username': [], 'password': PASSWORD}).status_code for _ in range(3)]
        self.assertEqual(codes, [400, 400, 429])

    def test_counter_storage_does_not_retain_raw_identity(self):
        self.attempt(REMOTE_ADDR='192.0.2.99')
        for bucket in LoginThrottleBucket.objects.all():
            self.assertEqual(len(bucket.key_digest), 64)
            self.assertNotIn('missing', bucket.key_digest)
            self.assertNotIn('192.0.2.99', bucket.key_digest)

    def test_cleanup_only_removes_expired_buckets(self):
        self.attempt()
        expired = LoginThrottleBucket.objects.first()
        expired.expires_at = timezone.now() - timedelta(seconds=1)
        expired.save()
        keep = LoginThrottleBucket.objects.exclude(pk=expired.pk).get()
        call_command('clear_auth_throttles')
        self.assertFalse(LoginThrottleBucket.objects.filter(pk=expired.pk).exists())
        self.assertTrue(LoginThrottleBucket.objects.filter(pk=keep.pk).exists())


@override_settings(AUTH_LOGIN_ACCOUNT_IP_LIMIT=2, AUTH_LOGIN_IP_LIMIT=50)
class ConcurrentThrottleTests(TransactionTestCase):
    def test_simultaneous_requests_do_not_exceed_limit(self):
        def attempt(_):
            close_old_connections()
            try:
                client = csrf_client()
                return write(client, 'post', '/api/auth/login/', {'username': 'concurrent', 'password': PASSWORD}).status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=8) as executor:
            codes = list(executor.map(attempt, range(8)))
        self.assertEqual(codes.count(400), 2, codes)
        self.assertEqual(codes.count(429), 6, codes)
        self.assertEqual(LoginThrottleBucket.objects.get(scope='account_ip').attempt_count, 2)
