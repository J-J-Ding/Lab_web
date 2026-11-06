from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.test import TestCase
from rest_framework.test import APIClient

PASSWORD = 'OnlyForTests7nK4zQ9'
NEW_PASSWORD = 'ChangedForTests9wT5mP2'


def csrf_client():
    client = APIClient(enforce_csrf_checks=True)
    response = client.get('/api/auth/csrf/')
    assert response.status_code == 200, response.status_code
    return client


def write(client, method, path, data=None, **extra):
    token = client.cookies.get('csrftoken')
    if token:
        extra.setdefault('HTTP_X_CSRFTOKEN', token.value)
    return getattr(client, method)(path, data or {}, format='json', **extra)


def login_as(user, password=PASSWORD):
    client = csrf_client()
    response = write(client, 'post', '/api/auth/login/', {'username': user.username, 'password': password})
    assert response.status_code == 200, response.content
    return client


class AccountFixtures(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        encoded = make_password(PASSWORD)
        for name, role, extra in [
            ('customer', 'CUSTOMER', {}), ('student', 'STUDENT', {}),
            ('teacher', 'TEACHER', {}), ('admin', 'ADMIN', {}),
            ('root', 'CUSTOMER', {'is_superuser': True, 'is_staff': True}),
            ('staff', 'CUSTOMER', {'is_staff': True}),
        ]:
            setattr(cls, name, User.objects.create(username=name, role=role, password=encoded, **extra))
