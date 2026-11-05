"""Loopback-only browser harness using an explicitly isolated PostgreSQL database."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import http.client
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path(os.environ.get('LAB_V3_EVIDENCE', '/tmp/lab-web-v3-evidence'))
COMPOSE = json.loads(os.environ.get('LAB_BROWSER_COMPOSE', '[]'))


def run(args, *, data=None):
    result = subprocess.run(args, input=data, text=True, capture_output=True, timeout=120)
    if result.returncode:
        # Commands contain no passwords; never print input or environment.
        raise RuntimeError(f'Isolated test command failed: {args[:5]}: {result.stderr[-1500:]}')
    return result.stdout.strip()


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class Environment:
    def __init__(self):
        suffix = f'{os.getpid()}_{secrets.token_hex(3)}'
        self.database = f'test_lab_web_browser_{suffix}'
        self.container = f'lab-web-v3-api-{suffix}'
        self.port = free_port()
        self.created_database = False
        self.created_container = False
        self.server = None

    def start(self):
        if not COMPOSE or '-p' not in COMPOSE or not COMPOSE[COMPOSE.index('-p') + 1].startswith('lab-web-test-v4-'):
            raise RuntimeError('Use tests/support/v4_environment.py browser: isolated Compose configuration is required.')
        assert self.database.startswith('test_lab_web_browser_') and self.port not in (80, 8000)
        try:
            run(COMPOSE + ['exec', '-T', 'db', 'sh', '-c', 'createdb -U "$POSTGRES_USER" "$1"', 'v3-test', self.database])
            self.created_database = True
            run(COMPOSE + ['run', '--rm', '--no-deps', '-e', f'POSTGRES_DB={self.database}', 'backend', 'python', 'manage.py', 'migrate', '--noinput'])
            run(COMPOSE + ['run', '-d', '--rm', '--no-deps', '--name', self.container, '-e', f'POSTGRES_DB={self.database}', '-p', f'127.0.0.1:{self.port}:8000', 'backend'])
            self.created_container = True
            deadline = time.monotonic() + 40
            while True:
                try:
                    conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
                    conn.request('GET', '/api/health/')
                    response = conn.getresponse()
                    healthy = response.status == 200
                    response.read()
                    conn.close()
                    if healthy:
                        break
                except (OSError, http.client.HTTPException):
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError('Isolated backend did not become healthy')
                time.sleep(0.2)
            backend_port = self.port

            class Handler(SimpleHTTPRequestHandler):
                def handle(self):
                    try:
                        super().handle()
                    except (BrokenPipeError, ConnectionResetError):
                        # Browsers cancel favicon/static requests while navigating or closing.
                        pass

                def log_message(self, *args):
                    pass

                def do_POST(self):
                    self.forward()

                def do_PATCH(self):
                    self.forward()

                def do_GET(self):
                    if self.path.startswith('/api/'):
                        self.forward()
                    elif any(part.startswith('.') for part in self.path.split('/')[1:]):
                        self.send_error(404)
                    else:
                        super().do_GET()

                def forward(self):
                    if not self.path.startswith('/api/'):
                        self.send_error(404)
                        return
                    upstream = http.client.HTTPConnection('127.0.0.1', backend_port, timeout=20)
                    ignored = {'connection', 'transfer-encoding', 'keep-alive', 'proxy-authorization', 'proxy-authenticate'}
                    headers = {key: value for key, value in self.headers.items() if key.lower() not in ignored}
                    headers['Accept-Encoding'] = 'identity'
                    size = int(self.headers.get('Content-Length', 0))
                    body = self.rfile.read(size) if size else None
                    try:
                        # Preserve original Host/Origin and Cookie; no CSRF bypass or CORS headers.
                        upstream.request(self.command, self.path, body=body, headers=headers)
                        response = upstream.getresponse()
                        content = response.read()
                        self.send_response(response.status)
                        for key, value in response.getheaders():
                            if key.lower() not in ignored | {'content-length', 'server', 'date'}:
                                self.send_header(key, value)
                        self.send_header('Content-Length', str(len(content)))
                        self.end_headers()
                        self.wfile.write(content)
                    except (OSError, http.client.HTTPException):
                        self.send_error(502, 'Isolated API unavailable')
                    finally:
                        upstream.close()

            self.server = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(ROOT / 'frontend')))
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            self.url = f'http://127.0.0.1:{self.server.server_port}'
            self.orm('result = {"database": connection.settings_dict["NAME"]}')
            return self
        except BaseException:
            self.close()
            raise

    def orm(self, code, payload=None):
        guard = f'''import os,json,sys,django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()
from django.db import connection
from apps.accounts.models import User
assert connection.settings_dict['NAME'] == {self.database!r}
assert connection.settings_dict['NAME'].startswith('test_lab_web_browser_')
with connection.cursor() as cursor:
    cursor.execute('SELECT current_database()')
    assert cursor.fetchone()[0] == {self.database!r}
data=json.load(sys.stdin)
'''
        output = run(['sudo', '-n', 'docker', 'exec', '-i', self.container, 'python', '-c', guard + code + '\nprint(json.dumps(result))'], data=json.dumps(payload or {}))
        return json.loads(output)

    def seed(self, username, password, role='CUSTOMER', root=False):
        return self.orm('user=User.objects.create_user(username=data["username"], password=data["password"], role=data["role"], is_superuser=data["root"], is_staff=data["root"]); result={"id":user.pk}', {'username':username, 'password':password, 'role':role, 'root':root})

    def close(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.created_container:
            run(['sudo', '-n', 'docker', 'stop', self.container])
            self.created_container = False
        if self.created_database:
            assert self.database.startswith('test_lab_web_browser_')
            run(COMPOSE + ['exec', '-T', 'db', 'sh', '-c', 'dropdb -U "$POSTGRES_USER" "$1"', 'v3-test', self.database])
            self.created_database = False
