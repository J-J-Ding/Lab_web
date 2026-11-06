"""Real V4 -> V5 upgrade rehearsal, restricted to an empty disposable database."""
import hashlib
import json
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
django.setup()
from django.contrib.auth.hashers import make_password
from django.db import connection,transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

assert connection.settings_dict['NAME'].startswith('test_lab_web_upgrade_')
with connection.cursor() as cursor:
    cursor.execute('SELECT current_database()')
    assert cursor.fetchone()[0]==connection.settings_dict['NAME']
    cursor.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
    assert cursor.fetchone()[0]==0
base=[('accounts','0002_user_session_version_authauditlog_and_more'),('sessions','0001_initial'),
      ('assets','0001_initial'),('members','0002_graph_guards'),('content','0002_graph_guards'),('workflow','0001_initial')]
executor=MigrationExecutor(connection);executor.migrate(base)
old_apps=executor.loader.project_state(base).apps
models={name:old_apps.get_model(app,name) for app,name in [
 ('accounts','User'),('sessions','Session'),('accounts','AuthAuditLog'),
 ('members','MemberProfile'),('members','MemberRevision'),('members','EducationEntry'),
 ('content','ContentItem'),('content','ContentRevision'),('content','BlogDetail'),
 ('content','Contributor'),('content','RevisionContribution'),('workflow','BusinessAuditLog')]}
user=models['User'].objects.create(username='upgrade-v4-person',role='TEACHER',password=make_password('Isolated-upgrade-only!7kRz'))
models['Session'].objects.create(session_key='upgrade-v4-session',session_data='opaque-test-value',expire_date=timezone.now()+timezone.timedelta(days=1))
models['AuthAuditLog'].objects.create(actor=user,target=user,actor_snapshot=user.pk,target_snapshot=user.pk,action='upgrade.fixture')
with transaction.atomic():
    profile=models['MemberProfile'].objects.create(user=user,membership_status='ACTIVE',created_by=user)
    member_pub=models['MemberRevision'].objects.create(profile=profile,number=1,display_name='Approved V4 member',state='PUBLISHED',edited_by=user)
    member_draft=models['MemberRevision'].objects.create(profile=profile,number=2,display_name='V4 pending member',edited_by=user)
    profile.published_revision=member_pub;profile.draft_revision=member_draft;profile.save()
    models['EducationEntry'].objects.create(revision=member_draft,school='Private V4 school',position=1)
    item=models['ContentItem'].objects.create(kind='BLOG',created_by=user,last_edited_by=user)
    published=models['ContentRevision'].objects.create(item=item,number=1,title='V4 approved A',edited_by=user)
    models['BlogDetail'].objects.create(revision=published,body='Immutable V4 A body')
    contributor=models['Contributor'].objects.create(display_name='V4 signature',member_profile=profile)
    models['RevisionContribution'].objects.create(revision=published,contributor=contributor,contribution_role='AUTHOR',position=1,approved_display_name='V4 signature')
    published.state='PUBLISHED';published.save(update_fields=['state'])
    pending=models['ContentRevision'].objects.create(item=item,number=2,title='V4 private draft B',edited_by=user,base_published_revision=published)
    models['BlogDetail'].objects.create(revision=pending,body='V4 private B body')
    item.published_revision=published;item.working_revision=pending;item.save()
    models['BusinessAuditLog'].objects.create(actor=user,actor_snapshot=user.pk,target_id=item.pk,revision_id=pending.pk,action='content.draft.update',changed_fields=['title'])
fields={name:[f.name for f in model._meta.local_fields] for name,model in models.items()}
def digest():
    data={name:list(model.objects.order_by('pk').values(*fields[name])) for name,model in models.items()}
    return hashlib.sha256(json.dumps(data,sort_keys=True,default=str).encode()).hexdigest()
before=digest()
executor=MigrationExecutor(connection);executor.migrate(executor.loader.graph.leaf_nodes())
assert digest()==before,'Existing V4 fields changed during upgrade'
from apps.workflow.models import RevisionEditEvent
from apps.members.models import MemberRevision
assert RevisionEditEvent.objects.filter(content_revision_id=pending.pk,editor_snapshot=user.pk).exists()
assert RevisionEditEvent.objects.filter(member_revision_id=member_draft.pk,editor_snapshot=user.pk).exists()
assert MemberRevision.objects.get(pk=member_draft.pk).base_published_revision_id==member_pub.pk
print('PASS: V4 -> V5 upgrade preserved all original account/session/audit/member/content/signature fields; editor history and member baseline backfilled.')
