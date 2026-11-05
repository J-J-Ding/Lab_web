import json
from unittest.mock import patch

from django.db import DatabaseError

from apps.accounts.models import AuthAuditLog, User
from .helpers import AccountFixtures, NEW_PASSWORD, PASSWORD, csrf_client, login_as, write


class AuditTests(AccountFixtures):
    def test_role_password_and_disable_changes_have_safe_audit(self):
        client = login_as(self.teacher)
        write(client, 'patch', f'/api/admin/users/{self.student.pk}/', {'role': 'CUSTOMER', 'is_active': False, 'email': 'private@example.org'})
        write(client, 'post', f'/api/admin/users/{self.student.pk}/reset-password/', {'new_password': NEW_PASSWORD})
        event = AuthAuditLog.objects.get(action='user.updated')
        self.assertEqual(event.actor_snapshot, self.teacher.pk)
        self.assertEqual(event.target_snapshot, self.student.pk)
        self.assertEqual(event.changes['role'], {'before': 'STUDENT', 'after': 'CUSTOMER'})
        self.assertEqual(event.changes['is_active'], {'before': True, 'after': False})
        self.assertIn('email', event.changed_fields)
        self.assertTrue(AuthAuditLog.objects.filter(action='user.password_reset', target=self.student).exists())
        data = json.dumps(list(AuthAuditLog.objects.values()), default=str)
        for value in (PASSWORD, NEW_PASSWORD, self.student.password, 'private@example.org', client.cookies['sessionid'].value, client.cookies['csrftoken'].value):
            self.assertNotIn(value, data)

    def test_denied_root_management_is_audited(self):
        client = login_as(self.teacher)
        response = write(client, 'post', f'/api/admin/users/{self.root.pk}/reset-password/', {'new_password': NEW_PASSWORD})
        self.assertEqual(response.status_code, 404)
        self.assertTrue(AuthAuditLog.objects.filter(action='management.denied', outcome='denied', actor_snapshot=self.teacher.pk, target_snapshot=self.root.pk).exists())

    def test_audit_failure_rolls_back_password_role_disable_and_creation(self):
        client = login_as(self.root)
        before = User.objects.get(pk=self.student.pk)
        with patch('apps.accounts.services.audit', side_effect=DatabaseError('audit unavailable')):
            for path, method, data in [
                (f'/api/admin/users/{self.student.pk}/reset-password/', 'post', {'new_password': NEW_PASSWORD}),
                (f'/api/admin/users/{self.student.pk}/', 'patch', {'role': 'ADMIN', 'is_active': False}),
                ('/api/admin/users/', 'post', {'username': 'rolled-back-user', 'password': PASSWORD}),
            ]:
                self.assertEqual(write(client, method, path, data).status_code, 503)
        current = User.objects.get(pk=self.student.pk)
        self.assertEqual((current.password, current.role, current.is_active, current.session_version), (before.password, before.role, before.is_active, before.session_version))
        self.assertFalse(User.objects.filter(username='rolled-back-user').exists())

    def test_failed_login_audit_does_not_create_authenticated_session(self):
        client = csrf_client()
        with patch('apps.accounts.services.audit', side_effect=DatabaseError('audit unavailable')):
            response = write(client, 'post', '/api/auth/login/', {'username': self.customer.username, 'password': PASSWORD})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(client.get('/api/auth/me/').status_code, 403)

    def test_login_failure_and_logout_are_audited(self):
        client = csrf_client()
        write(client, 'post', '/api/auth/login/', {'username': 'unknown', 'password': PASSWORD})
        self.assertTrue(AuthAuditLog.objects.filter(action='auth.login', outcome='failure').exists())
        client = login_as(self.customer)
        write(client, 'post', '/api/auth/logout/')
        self.assertTrue(AuthAuditLog.objects.filter(action='auth.login', outcome='success', actor=self.customer).exists())
        self.assertTrue(AuthAuditLog.objects.filter(action='auth.logout', actor=self.customer).exists())

    def test_deleted_account_preserves_stable_audit_identity(self):
        client = login_as(self.teacher)
        write(client, 'patch', f'/api/admin/users/{self.student.pk}/', {'first_name': 'X'})
        pk = self.student.pk
        self.student.delete()
        event = AuthAuditLog.objects.get(action='user.updated')
        self.assertIsNone(event.target)
        self.assertEqual(event.target_snapshot, pk)
