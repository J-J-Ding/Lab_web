"""Executed inside disposable backend with an explicitly fresh upgrade-test database."""
import hashlib
import json
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

assert connection.settings_dict['NAME'].startswith('test_lab_web_upgrade_')
with connection.cursor() as c:
    c.execute('SELECT current_database()')
    assert c.fetchone()[0]==connection.settings_dict['NAME']
    c.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
    assert c.fetchone()[0]==0, 'Upgrade verification requires an empty disposable database'
executor=MigrationExecutor(connection)
executor.migrate([('accounts','0002_user_session_version_authauditlog_and_more'),('sessions','0001_initial')])
from apps.accounts.models import User,AuthAuditLog
from django.contrib.sessions.models import Session
from django.utils import timezone
u=User.objects.create_user(username='upgrade-test',password='Isolated-upgrade!7kRz2')
Session.objects.create(session_key='upgrade-session-only',session_data='opaque-test-data',expire_date=timezone.now()+timezone.timedelta(days=1))
AuthAuditLog.objects.create(actor=u,target=u,action='upgrade.fixture',actor_snapshot=u.pk,target_snapshot=u.pk)
def digest():
    data=[list(model.objects.order_by('pk').values()) for model in (User,Session,AuthAuditLog)]
    return hashlib.sha256(json.dumps(data,sort_keys=True,default=str).encode()).hexdigest()
before=digest()
executor=MigrationExecutor(connection)
executor.migrate(executor.loader.graph.leaf_nodes())
assert before==digest(),'V3 accounts, sessions or audit data changed during V4 migration'
with connection.cursor() as c:
    c.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'members_%'")
    assert c.fetchone()[0]>=9
print('PASS: actual V3 -> V4 migration preserves User, Session and AuthAuditLog byte-for-byte.')
