"""Real HTTP acceptance driver. Refuses any database outside lab_web_v2_http_*.

Run only in the disposable verification container described in docs/auth-api.md.
Generated credentials and cookies never leave this process or enter stdout.
"""
import copy
from http.cookiejar import CookieJar
from io import StringIO
import json
import os
import secrets
from unittest.mock import patch
import urllib.error
import urllib.request

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django

django.setup()

from django.conf import settings
from django.core.management import call_command
from django.db import connection
from apps.accounts.models import AuthAuditLog, User


def main():
    db = settings.DATABASES['default']['NAME']
    if not db.startswith('lab_web_v2_http_'):
        raise SystemExit('Refusing HTTP fixture setup outside the disposable verification database.')
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_database()')
        assert cursor.fetchone()[0] == db
    assert User.objects.count() == 0, 'Verification database must contain no existing users.'
    password = secrets.token_urlsafe(24) + '!aA3'
    changed = secrets.token_urlsafe(24) + '!bB4'
    reset = secrets.token_urlsafe(24) + '!cC5'
    checks = []
    cookie_secrets = []

    class Client:
        def __init__(self):
            self.jar = CookieJar()
            self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(self.jar))
            self.expect('get', '/api/auth/csrf/', 200)

        def token(self):
            return next((c.value for c in self.jar if c.name == 'csrftoken'), '')

        def expect(self, method, path, code, payload=None, csrf=True):
            headers = {'Content-Type': 'application/json'}
            if csrf:
                headers['X-CSRFToken'] = self.token()
            request = urllib.request.Request('http://127.0.0.1:8000' + path, method=method.upper(), headers=headers, data=None if payload is None else json.dumps(payload).encode())
            try:
                response = self.opener.open(request, timeout=15)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                raw = response.read()
                status = response.status
                retry = response.headers.get('Retry-After')
            assert status == code, f'{method} {path}: expected {code}, got {status}'
            body = json.loads(raw) if raw else None
            if isinstance(body, dict):
                assert not {'password', 'sessionid', 'session_key'} & set(body)
            cookie_secrets.extend(c.value for c in self.jar if c.name in ('sessionid', 'csrftoken'))
            checks.append(f'{method.upper()} {path} -> {status}')
            return body, retry

        def login(self, username, secret=password):
            return self.expect('post', '/api/auth/login/', 200, {'username': username, 'password': secret})[0]

    with patch('getpass.getpass', side_effect=[password, password]):
        call_command('init_root', username='http-root', stdout=StringIO())
    root = Client()
    root.expect('post', '/api/auth/login/', 403, {'username': 'http-root', 'password': password}, csrf=False)
    root.login('http-root')
    root.expect('get', '/api/auth/me/', 200)
    public = Client()
    user, _ = public.expect('post', '/api/auth/register/', 201, {'username': 'http-customer', 'password': password})
    assert user['role'] == 'CUSTOMER' and not user['is_superuser']
    public.expect('get', '/api/auth/me/', 403)
    public.expect('post', '/api/auth/register/', 400, {'username': 'http-evil', 'password': password, 'role': 'ADMIN'})
    assert not User.objects.filter(username='http-evil').exists()
    customer = Client()
    customer.expect('post', '/api/auth/login/', 400, {'username': 'http-customer', 'password': 'incorrect'})
    customer.login('http-customer')
    customer.expect('get', '/api/admin/users/', 403)
    customer.expect('patch', '/api/auth/me/', 400, {'role': 'ADMIN'})
    customer.expect('patch', '/api/auth/me/', 200, {'first_name': 'HTTP test'})
    customer.expect('patch', '/api/auth/me/', 403, {'first_name': 'no CSRF'}, csrf=False)
    admin, _ = root.expect('post', '/api/admin/users/', 201, {'username': 'http-admin', 'password': password, 'role': 'ADMIN'})
    teacher, _ = root.expect('post', '/api/admin/users/', 201, {'username': 'http-teacher', 'password': password, 'role': 'TEACHER'})
    root_user = root.expect('get', '/api/auth/me/', 200)[0]
    for name in ('http-admin', 'http-teacher'):
        manager = Client()
        manager.login(name)
        manager.expect('get', '/api/admin/users/', 200)
        manager.expect('get', f'/api/admin/users/{user["id"]}/', 200)
        manager.expect('patch', f'/api/admin/users/{user["id"]}/', 200, {'role': 'STUDENT'})
        manager.expect('patch', f'/api/admin/users/{user["id"]}/', 403, {'role': 'ADMIN'})
        manager.expect('patch', f'/api/admin/users/{root_user["id"]}/', 404, {'email': 'forbidden@example.org'})
        manager.expect('post', f'/api/admin/users/{admin["id"]}/reset-password/', 404, {'new_password': reset})
    other = Client()
    other.login('http-customer')
    customer.expect('post', '/api/auth/change-password/', 204, {'old_password': password, 'new_password': changed})
    customer.expect('get', '/api/auth/me/', 200)
    other.expect('get', '/api/auth/me/', 403)
    other.expect('post', '/api/auth/login/', 400, {'username': 'http-customer', 'password': password})
    other.login('http-customer', changed)
    root.expect('post', f'/api/admin/users/{user["id"]}/reset-password/', 204, {'new_password': reset})
    customer.expect('get', '/api/auth/me/', 403)
    other.expect('get', '/api/auth/me/', 403)
    restored = Client()
    restored.login('http-customer', reset)
    root.expect('patch', f'/api/admin/users/{user["id"]}/', 200, {'is_active': False})
    disabled = Client()
    disabled.expect('post', '/api/auth/login/', 400, {'username': 'http-customer', 'password': reset})
    root.expect('patch', f'/api/admin/users/{user["id"]}/', 200, {'is_active': True})
    restored.expect('get', '/api/auth/me/', 403)
    fresh = Client()
    fresh.login('http-customer', reset)
    replay = Client()
    replay.jar = CookieJar()
    for cookie in fresh.jar:
        replay.jar.set_cookie(copy.copy(cookie))
    replay.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(replay.jar))
    fresh.expect('post', '/api/auth/logout/', 204, {})
    replay.expect('get', '/api/auth/me/', 403)
    brute = Client()
    for i in range(settings.AUTH_LOGIN_ACCOUNT_IP_LIMIT):
        brute.expect('post', '/api/auth/login/', 400, {'username': 'http-missing', 'password': password})
    _, retry = brute.expect('post', '/api/auth/login/', 429, {'username': 'http-missing', 'password': password})
    assert int(retry) > 0
    health, _ = public.expect('get', '/api/health/', 200)
    assert health == {'status': 'ok', 'backend': 'running', 'database': 'connected'}
    records = json.dumps(list(AuthAuditLog.objects.values()), default=str)
    for value in [password, changed, reset, *cookie_secrets]:
        assert value not in records, 'Sensitive value leaked into audit records'
    assert AuthAuditLog.objects.filter(action='user.password_reset').exists()
    assert AuthAuditLog.objects.filter(outcome='denied').exists()
    assert AuthAuditLog.objects.filter(outcome='throttled').exists()
    print(json.dumps({'http_checks_passed': len(checks), 'failed': 0, 'skipped': 0, 'database': db, 'checks': checks}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
