"""V5 -> V6 preservation rehearsal, refuses nonempty/non-test databases."""
import hashlib,json,os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup()
from django.db import connection,transaction
from django.db.migrations.executor import MigrationExecutor
assert connection.settings_dict['NAME'].startswith('test_lab_web_upgrade_')
with connection.cursor() as c:
    c.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'");assert c.fetchone()[0]==0
base=[('accounts','0002_user_session_version_authauditlog_and_more'),('sessions','0001_initial'),('assets','0001_initial'),('members','0005_profile_baseline_guard'),('content','0003_contributor_created_by'),('workflow','0006_moderation_history_guard')]
e=MigrationExecutor(connection);e.migrate(base);apps=e.loader.project_state(base).apps
models={m._meta.label:m for m in apps.get_models() if m._meta.app_label in ('accounts','sessions','assets','members','content','workflow')}
def model(app,name):return apps.get_model(app,name)
u=model('accounts','User').objects.create(username='v5-upgrade-manager',role='TEACHER',password='!unusable')
a=model('assets','AssetFile').objects.create(owner=u,storage_key='upgrade-avatar.png',original_filename='avatar.png',mime_type='image/png',size=1,sha256='0'*64,scan_status='CLEAN')
proof=model('assets','AssetFile').objects.create(owner=u,storage_key='upgrade-proof.pdf',original_filename='proof.pdf',mime_type='application/pdf',size=1,sha256='1'*64,scan_status='CLEAN')
with transaction.atomic():
 p=model('members','MemberProfile').objects.create(user=u,public_visible=True,membership_status='ACTIVE')
 r=model('members','MemberRevision').objects.create(profile=p,number=1,display_name='Approved V5',slug='approved-v5',avatar_asset=a)
 model('members','MemberSlug').objects.create(profile=p,slug=r.slug)
 r.state='PUBLISHED';r.save(update_fields=['state']);p.published_revision=r;p.save()
 i=model('content','ContentItem').objects.create(kind='BLOG',created_by=u)
 rev=model('content','ContentRevision').objects.create(item=i,number=1,title='V5 published',edited_by=u)
 model('content','BlogDetail').objects.create(revision=rev,body='Original body')
 rev.state='PUBLISHED';rev.save(update_fields=['state']);i.published_revision=rev;i.save()
 model('workflow','RevisionEditEvent').objects.create(content_revision=rev,editor=u,editor_snapshot=u.pk)
 model('workflow','ReviewDecision').objects.create(content_revision=rev,reviewer=u,reviewer_snapshot=u.pk,decision='APPROVE',reason='Historical fixture')
 model('workflow','BusinessAuditLog').objects.create(actor=u,actor_snapshot=u.pk,target_id=i.pk,revision_id=rev.pk,action='upgrade.fixture')
fields={key:[f.name for f in m._meta.local_fields if not (key=='assets.AssetFile' and f.name=='visibility')] for key,m in models.items()}
def digest():return hashlib.sha256(json.dumps({key:list(m.objects.order_by('pk').values(*fields[key])) for key,m in models.items()},sort_keys=True,default=str).encode()).hexdigest()
before=digest();e=MigrationExecutor(connection);e.migrate(e.loader.graph.leaf_nodes());assert before==digest(),'Original V5 fields changed'
from apps.assets.models import AssetFile
assert AssetFile.objects.get(pk=a.pk).purpose=='avatar'
assert AssetFile.objects.get(pk=a.pk).visibility=='PUBLIC','Previously approved visible avatar should be available under V6 gate'
assert AssetFile.objects.get(pk=proof.pk).purpose=='proof' and AssetFile.objects.get(pk=proof.pk).visibility=='PRIVATE'
print('PASS: V5 -> V6 preserved original account/member/content/history fields; only approved visible avatar promoted; proof remains PRIVATE.')
