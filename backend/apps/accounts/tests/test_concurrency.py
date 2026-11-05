from concurrent.futures import ThreadPoolExecutor
import time

from django.contrib.auth.hashers import make_password
from django.db import close_old_connections, connection, transaction
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from .helpers import PASSWORD, login_as, write


class ConcurrentPermissionsTests(TransactionTestCase):
    def setUp(self):
        encoded = make_password(PASSWORD)
        self.actor = User.objects.create(username='manager', role='TEACHER', password=encoded)
        self.target = User.objects.create(username='target', password=encoded)
        self.client = login_as(self.actor)

    def wait_for_row_lock(self):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_stat_clear_snapshot()")
                cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND wait_event_type='Lock' AND query LIKE '%%accounts_user%%'")
                if cursor.fetchone()[0]:
                    return
            time.sleep(0.02)
        self.fail('Management write never reached the expected PostgreSQL row lock')

    def run_delayed_write(self, lock_actor):
        cookies = self.client.cookies.copy()
        def modify():
            close_old_connections()
            try:
                client = APIClient(enforce_csrf_checks=True)
                client.cookies = cookies.copy()
                return write(client, 'patch', f'/api/admin/users/{self.target.pk}/', {'email': 'should-not-change@example.org'}).status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                row = User.objects.select_for_update().get(pk=self.actor.pk if lock_actor else self.target.pk)
                future = pool.submit(modify)
                self.wait_for_row_lock()
                row.role = 'STUDENT' if lock_actor else 'ADMIN'
                row.save(update_fields=['role'])
            status = future.result(timeout=15)
        self.target.refresh_from_db()
        self.assertEqual(self.target.email, '')
        return status

    def test_actor_demotion_during_request_prevents_write(self):
        self.assertEqual(self.run_delayed_write(lock_actor=True), 403)

    def test_target_promotion_during_request_prevents_takeover(self):
        self.assertEqual(self.run_delayed_write(lock_actor=False), 404)
