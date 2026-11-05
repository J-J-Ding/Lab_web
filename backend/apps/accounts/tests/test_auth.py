from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from .helpers import AccountFixtures, PASSWORD, NEW_PASSWORD, csrf_client, login_as, write


class AuthenticationTests(AccountFixtures):
    def test_registration_is_customer_without_privileges_or_auto_login(self):
        client = csrf_client()
        response = write(client, 'post', '/api/auth/register/', {'username': 'new-customer', 'password': PASSWORD})
        self.assertEqual(response.status_code, 201)
        user = get_user_model().objects.get(username='new-customer')
        self.assertEqual(user.role, 'CUSTOMER')
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_staff)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotIn('password', response.json())
        self.assertNotIn('sessionid', client.cookies)
        self.assertEqual(client.get('/api/auth/me/').status_code, 403)

    def test_registration_rejects_all_privileged_or_unknown_fields(self):
        client = csrf_client()
        for field, value in [('role', 'ADMIN'), ('role', 'ROOT'), ('is_staff', True), ('is_superuser', True), ('is_active', True), ('groups', []), ('user_permissions', []), ('actor', 1)]:
            with self.subTest(field=field, value=value):
                response = write(client, 'post', '/api/auth/register/', {'username': 'attacker', 'password': PASSWORD, field: value})
                self.assertEqual(response.status_code, 400)
                self.assertFalse(get_user_model().objects.filter(username='attacker').exists())

    def test_registration_validates_username_email_password_and_duplicates(self):
        client = csrf_client()
        for payload in [
            {}, {'username': 'a', 'password': '123'},
            {'username': [], 'password': PASSWORD}, {'username': 123, 'password': PASSWORD},
            {'username': 'bad name', 'password': PASSWORD}, {'username': 'x' * 151, 'password': PASSWORD},
            {'username': 'new', 'password': PASSWORD, 'email': 'broken'},
            {'username': 'customer', 'password': PASSWORD},
            {'username': 'new', 'password': 'x' * 129},
        ]:
            with self.subTest(payload=payload):
                self.assertEqual(write(client, 'post', '/api/auth/register/', payload).status_code, 400)

    def test_correct_login_returns_safe_user_and_http_only_session(self):
        client = login_as(self.customer)
        response = client.get('/api/auth/me/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {'id', 'username', 'first_name', 'last_name', 'email', 'role', 'is_active', 'is_superuser', 'date_joined'})
        self.assertEqual(response.json()['id'], self.customer.pk)
        self.assertTrue(client.cookies['sessionid']['httponly'])
        self.assertEqual(client.cookies['sessionid']['samesite'], 'Lax')
        self.assertIn('no-store', response['Cache-Control'])

    def test_wrong_missing_and_disabled_login_have_same_response(self):
        self.student.is_active = False
        self.student.save()
        client = csrf_client()
        responses = [write(client, 'post', '/api/auth/login/', {'username': name, 'password': password}) for name, password in [
            ('customer', 'wrong'), ('not-an-account', PASSWORD), ('student', PASSWORD),
        ]]
        self.assertEqual([r.status_code for r in responses], [400, 400, 400])
        self.assertEqual(responses[0].json(), responses[1].json())
        self.assertEqual(responses[1].json(), responses[2].json())

    def test_login_rotates_existing_session(self):
        client = csrf_client()
        session = client.session
        session['marker'] = 'before-login'
        session.save()
        old_key = session.session_key
        response = write(client, 'post', '/api/auth/login/', {'username': self.customer.username, 'password': PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(client.cookies['sessionid'].value, old_key)

    def test_logout_invalidates_replayed_session_cookie(self):
        client = login_as(self.customer)
        stolen = APIClient(enforce_csrf_checks=True)
        stolen.cookies = client.cookies.copy()
        self.assertEqual(write(client, 'post', '/api/auth/logout/').status_code, 204)
        self.assertEqual(client.get('/api/auth/me/').status_code, 403)
        self.assertEqual(stolen.get('/api/auth/me/').status_code, 403)

    def test_expired_or_legacy_session_is_rejected(self):
        from django.contrib.sessions.models import Session
        client = login_as(self.customer)
        Session.objects.filter(session_key=client.cookies['sessionid'].value).update(expire_date=timezone.now() - timedelta(seconds=1))
        self.assertEqual(client.get('/api/auth/me/').status_code, 403)
        client = login_as(self.customer)
        session = client.session
        del session['account_session_version']
        session.save()
        self.assertEqual(client.get('/api/auth/me/').status_code, 403)

    def test_change_password_preserves_current_but_invalidates_other_sessions(self):
        client = login_as(self.customer)
        other = login_as(self.customer)
        self.assertEqual(write(client, 'post', '/api/auth/change-password/', {'old_password': PASSWORD, 'new_password': NEW_PASSWORD}).status_code, 204)
        self.assertEqual(client.get('/api/auth/me/').status_code, 200)
        self.assertEqual(other.get('/api/auth/me/').status_code, 403)
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.check_password(NEW_PASSWORD))
        self.assertFalse(self.customer.check_password(PASSWORD))
        self.assertEqual(write(client, 'post', '/api/auth/login/', {'username': 'customer', 'password': PASSWORD}).status_code, 400)
        self.assertEqual(login_as(self.customer, NEW_PASSWORD).get('/api/auth/me/').status_code, 200)

    def test_wrong_old_or_weak_new_password_changes_nothing(self):
        client = login_as(self.customer)
        for old, new in [('wrong', NEW_PASSWORD), (PASSWORD, '12345678')]:
            self.assertEqual(write(client, 'post', '/api/auth/change-password/', {'old_password': old, 'new_password': new}).status_code, 400)
            self.customer.refresh_from_db()
            self.assertTrue(self.customer.check_password(PASSWORD))

    def test_self_profile_only_updates_allowed_fields(self):
        client = login_as(self.student)
        response = write(client, 'patch', '/api/auth/me/', {'first_name': 'Updated', 'email': 'student@example.org'})
        self.assertEqual(response.status_code, 200)
        self.student.refresh_from_db()
        self.assertEqual(self.student.first_name, 'Updated')
        for field, value in [('role', 'ADMIN'), ('id', self.customer.pk), ('is_superuser', True), ('is_staff', True), ('is_active', False), ('password', NEW_PASSWORD), ('username', 'other')]:
            with self.subTest(field=field):
                self.assertEqual(write(client, 'patch', '/api/auth/me/', {field: value}).status_code, 400)
        self.student.refresh_from_db()
        self.assertEqual(self.student.role, 'STUDENT')

    def test_unauthenticated_protected_endpoints_are_denied(self):
        client = csrf_client()
        for method, path in [('get', '/api/auth/me/'), ('patch', '/api/auth/me/'), ('post', '/api/auth/logout/'), ('post', '/api/auth/change-password/'), ('get', '/api/admin/users/'), ('post', '/api/admin/users/'), ('get', f'/api/admin/users/{self.customer.pk}/'), ('patch', f'/api/admin/users/{self.customer.pk}/'), ('post', f'/api/admin/users/{self.customer.pk}/reset-password/')]:
            with self.subTest(method=method, path=path):
                response = client.get(path) if method == 'get' else write(client, method, path)
                self.assertEqual(response.status_code, 403)

    def test_registration_rejects_invalid_normalized_username(self):
        client = csrf_client()
        response = write(client, 'post', '/api/auth/register/', {'username': '\ufc5euser', 'password': PASSWORD})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(get_user_model().objects.filter(username=' \u064c\u0651user').exists())

    def test_valid_unicode_username_can_login_using_returned_canonical_name(self):
        client = csrf_client()
        response = write(client, 'post', '/api/auth/register/', {'username': 'ｎｅｗｃａｎｏｎｉｃａｌ', 'password': PASSWORD})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['username'], 'newcanonical')
        user = get_user_model().objects.get(username=response.json()['username'])
        self.assertEqual(login_as(user).get('/api/auth/me/').status_code, 200)
