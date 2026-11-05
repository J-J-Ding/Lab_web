"""Disposable V4 Compose resources; never reads production .env or uses its volumes."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / '.browser-artifacts/v4-runtime'


def prepare():
    RUNTIME.mkdir(parents=True, exist_ok=True, mode=0o700)
    state = RUNTIME / 'state.json'
    if not state.exists():
        suffix = secrets.token_hex(4)
        config = {'project': 'lab-web-test-v4-' + suffix,
                  'database': 'test_lab_web_v4_' + suffix,
                  'image': 'lab-web-backend:test-v4-' + suffix}
        state.write_text(json.dumps(config))
        os.chmod(state, 0o600)
        values = {'POSTGRES_DB': config['database'], 'POSTGRES_USER': 'lab_test',
                  'POSTGRES_PASSWORD': secrets.token_hex(24), 'DJANGO_SECRET_KEY': secrets.token_hex(32),
                  'DJANGO_ALLOWED_HOSTS': '127.0.0.1,localhost,testserver', 'POSTGRES_HOST': 'db',
                  'DJANGO_COOKIE_SECURE': 'False'}
        env = RUNTIME / 'test.env'
        env.write_text(''.join(f'{k}={v}\n' for k, v in values.items()))
        os.chmod(env, 0o600)
        (RUNTIME / 'override.yml').write_text(
            'services:\n  backend:\n    image: ' + config['image'] +
            '\n    ports: !reset []\n    volumes:\n      - ' + str(ROOT / 'backend') + ':/app:ro\n')
    config = json.loads(state.read_text())
    assert config['project'].startswith('lab-web-test-v4-')
    assert config['database'].startswith('test_lab_web_v4_')
    assert config['image'].startswith('lab-web-backend:test-v4-')
    return config


def compose():
    config = prepare()
    return ['sudo', '-n', 'docker', 'compose', '--project-directory', str(ROOT),
            '-f', str(ROOT / 'docker-compose.yml'), '-f', str(RUNTIME / 'override.yml'),
            '--env-file', str(RUNTIME / 'test.env'), '-p', config['project']]


def guarded():
    prefix = compose()
    raw = subprocess.check_output(prefix + ['config', '--format', 'json'], text=True)
    config = json.loads(raw)
    backend, db = config['services']['backend'], config['services']['db']
    assert backend['image'].startswith('lab-web-backend:test-v4-')
    assert not backend.get('ports') and not db.get('ports')
    assert backend['environment']['POSTGRES_DB'].startswith('test_lab_web_v4_')
    assert backend['environment']['POSTGRES_HOST'] == 'db'
    assert backend['environment']['POSTGRES_USER'] == 'lab_test'
    assert all(not v.get('external') for v in config['volumes'].values())
    assert all(v['name'].startswith(prepare()['project'] + '_') for v in config['volumes'].values())
    return prefix


def main():
    prefix = guarded()
    action, *args = sys.argv[1:]
    if action == 'up':
        subprocess.run(prefix + ['build', 'backend'], check=True)
        subprocess.run(prefix + ['up', '-d', '--wait', 'db'], check=True)
        print('Independent test database and image ready:', prepare()['project'])
    elif action == 'manage':
        options = ['run', '--rm', '--no-deps']
        if args and args[0] == 'makemigrations' and '--check' not in args:
            options += ['--user', f'{os.getuid()}:{os.getgid()}', '-v', f'{ROOT / "backend"}:/w:rw', '--workdir', '/w']
        database = None
        if args and args[0] == 'test':
            database = 'test_lab_web_run_' + secrets.token_hex(4)
            subprocess.run(prefix + ['exec', '-T', 'db', 'sh', '-c', 'createdb -U "$POSTGRES_USER" "$1"', 'test-run', database], check=True)
            options += ['-e', f'POSTGRES_DB={database}']
        try:
            subprocess.run(prefix + options + ['backend', 'python', 'manage.py'] + args, check=True)
        finally:
            if database:
                subprocess.run(prefix + ['exec', '-T', 'db', 'sh', '-c', 'dropdb -U "$POSTGRES_USER" "$1"', 'test-run', database], check=True)
    elif action == 'upgrade':
        database = 'test_lab_web_upgrade_' + secrets.token_hex(4)
        subprocess.run(prefix + ['exec', '-T', 'db', 'sh', '-c', 'createdb -U "$POSTGRES_USER" "$1"', 'test-upgrade', database], check=True)
        try:
            script = (ROOT / 'tests/support/verify_upgrade.py').read_text()
            subprocess.run(prefix + ['run', '--rm', '--no-deps', '-T', '-e', f'POSTGRES_DB={database}', 'backend', 'python', '-c', script], check=True)
        finally:
            subprocess.run(prefix + ['exec', '-T', 'db', 'sh', '-c', 'dropdb -U "$POSTGRES_USER" "$1"', 'test-upgrade', database], check=True)
    elif action == 'http':
        env = os.environ.copy()
        env['LAB_BROWSER_COMPOSE'] = json.dumps(prefix)
        subprocess.run([sys.executable, str(ROOT / 'tests/support/v4_http_smoke.py')], cwd=ROOT, env=env, check=True)
    elif action == 'browser':
        env = os.environ.copy()
        env['LAB_BROWSER_COMPOSE'] = json.dumps(prefix)
        env['LAB_V3_EVIDENCE'] = str(ROOT / '.browser-artifacts/v4')
        subprocess.run([args[0], '-m', 'unittest', 'discover', '-s', 'tests/browser', '-p', 'test_*.py', '-v'], cwd=ROOT, env=env, check=True)
        subprocess.run([args[0], 'tests/browser/check_cleanup.py'], cwd=ROOT, env=env, check=True)
    elif action == 'down':
        # Only this validated disposable project; never run against the business project.
        subprocess.run(prefix + ['down', '--volumes', '--remove-orphans'], check=True)
    else:
        raise SystemExit('Use up/manage/upgrade/http/browser/down')


if __name__ == '__main__':
    main()
