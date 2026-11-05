from rest_framework.test import APIClient

from .helpers import AccountFixtures, PASSWORD, csrf_client, login_as, write


class CsrfTests(AccountFixtures):
    def test_anonymous_login_and_register_require_csrf(self):
        for endpoint in ('login', 'register'):
            client = APIClient(enforce_csrf_checks=True)
            payload = {'username': 'customer' if endpoint == 'login' else 'new', 'password': PASSWORD}
            self.assertEqual(client.post(f'/api/auth/{endpoint}/', payload, format='json').status_code, 403)
            client = csrf_client()
            self.assertEqual(client.post(f'/api/auth/{endpoint}/', payload, format='json', HTTP_X_CSRFTOKEN='x'*32).status_code, 403)

    def test_csrf_origin_and_post_login_rotation(self):
        client = csrf_client()
        old_token = client.cookies['csrftoken'].value
        payload = {'username': 'customer', 'password': PASSWORD}
        self.assertEqual(write(client, 'post', '/api/auth/login/', payload, HTTP_ORIGIN='https://attacker.example').status_code, 403)
        self.assertEqual(write(client, 'post', '/api/auth/login/', payload).status_code, 200)
        self.assertNotEqual(client.cookies['csrftoken'].value, old_token)
        self.assertEqual(write(client, 'patch', '/api/auth/me/', {'first_name': 'X'}, HTTP_X_CSRFTOKEN=old_token).status_code, 403)
        self.assertEqual(write(client, 'patch', '/api/auth/me/', {'first_name': 'X'}).status_code, 200)

    def test_authenticated_mutations_require_csrf(self):
        client = login_as(self.root)
        for path, method in [('/api/auth/me/', 'patch'), ('/api/auth/change-password/', 'post'), ('/api/auth/logout/', 'post'), ('/api/admin/users/', 'post'), (f'/api/admin/users/{self.student.pk}/', 'patch'), (f'/api/admin/users/{self.student.pk}/reset-password/', 'post')]:
            with self.subTest(path=path):
                response = getattr(client, method)(path, {}, format='json')
                self.assertEqual(response.status_code, 403)
