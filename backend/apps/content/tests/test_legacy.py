import hashlib,json,uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from apps.accounts.models import User
from apps.content.models import ContentItem

class LegacyTests(TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=self.root/'旧目录 space.html';self.source.write_text('demonstration source')
        self.actor=User.objects.create(username='importer',role='TEACHER')
        self.manifest=self.root/'manifest.json';self.report=self.root/'report.json';self.batch=str(uuid.uuid4())
        self.row={'source':'旧目录 space.html','sha256':hashlib.sha256(self.source.read_bytes()).hexdigest(),'legacy_paths':['/data/blogs/中文 space/index.html'],'kind':'BLOG','public_authorized':True,'payload':{'title':'Example blog','detail':{'body':'Example body'}}}
        self.save()
    def save(self):self.manifest.write_text(json.dumps({'version':1,'records':[self.row]},ensure_ascii=False))
    def run_import(self,apply=False):
        return call_command('import_legacy_content','--apply' if apply else '--dry-run',manifest=str(self.manifest),source_root=str(self.root),report=str(self.report),batch_id=self.batch,actor=self.actor.pk)
    def test_dry_run_apply_idempotence_and_safe_mapping(self):
        self.run_import();self.assertEqual(ContentItem.objects.count(),0)
        self.run_import(True);self.run_import(True)
        self.assertEqual(ContentItem.objects.count(),1)
        self.assertIsNone(ContentItem.objects.get().published_revision_id)
        from apps.content.models import ImportRecord,LegacyURLMap
        self.assertEqual(ImportRecord.objects.count(),1);self.assertEqual(LegacyURLMap.objects.count(),1)
        self.assertEqual(self.client.get('/api/public/legacy/',{'path':self.row['legacy_paths'][0]}).status_code,404)
        call_command('verify_legacy_import',batch_id=self.batch)
    def test_bad_hash_paths_and_missing_authorization_recorded(self):
        for key,value in [('sha256','0'*64),('source','../secret'),('legacy_paths',['/data/../secret']),('public_authorized',False)]:
            old=self.row[key];self.row[key]=value;self.save();self.report.unlink(missing_ok=True)
            with self.assertRaises(CommandError):self.run_import()
            report=json.loads(self.report.read_text());self.assertEqual(report['records'][0]['status'],'ERROR')
            self.row[key]=old
        self.assertEqual(ContentItem.objects.count(),0)
    def test_changed_source_new_batch_preserves_old_draft(self):
        self.run_import(True);item=ContentItem.objects.get();old=item.working_revision_id
        self.source.write_text('revised demo source');self.row['sha256']=hashlib.sha256(self.source.read_bytes()).hexdigest();self.row['payload']['title']='Revised example';self.save()
        self.batch=str(uuid.uuid4());self.run_import(True)
        item.refresh_from_db();self.assertNotEqual(item.working_revision_id,old)
        self.assertEqual(item.revisions.count(),2);self.assertIsNone(item.published_revision_id)
    def test_explicit_member_draft_never_creates_account_or_name_match(self):
        self.row['kind']='MEMBER';self.row['payload']={'display_name':'Example Person','slug':'example-person','member_kind':'STUDENT'};self.save()
        self.run_import(True)
        from apps.members.models import MemberProfile
        self.assertEqual(User.objects.count(),1);p=MemberProfile.objects.get();self.assertIsNone(p.user_id);self.assertFalse(p.public_visible)
        self.assertEqual(p.draft_revision.display_name,'Example Person')
    def test_import_error_nonzero_and_private_report(self):
        self.row['sha256']='0'*64;self.save()
        with self.assertRaises(CommandError):self.run_import(True)
        self.assertEqual(self.report.stat().st_mode & 0o777,0o600)
        from apps.content.models import ImportRecord
        self.assertEqual(ImportRecord.objects.get().status,'ERROR')
    def test_asset_rollback_removes_bytes_if_later_asset_invalid(self):
        import base64
        from django.test import override_settings
        from apps.assets.models import AssetFile
        media=self.root/'media';media.mkdir()
        good=self.root/'good.png';good.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=') )
        bad=self.root/'bad.png';bad.write_bytes(b'bad image')
        self.row['assets']=[{'source':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'purpose':'image','mime_type':'image/png'} for p in (good,bad)];self.save()
        with override_settings(PRIVATE_MEDIA_ROOT=media):
            with self.assertRaises(CommandError):self.run_import(True)
        self.assertEqual(AssetFile.objects.count(),0);self.assertEqual(list(media.iterdir()),[])
    def test_full_example_manifest_has_no_duplicate_imports(self):
        import os
        from django.test import override_settings
        from apps.members.models import MemberProfile
        source=Path(os.environ['LAB_LEGACY_ROOT'])
        manifest=source.parent/'manifest.json'
        with override_settings(PRIVATE_MEDIA_ROOT=self.root/'files'):
            kwargs={'manifest':str(manifest),'source_root':str(source),'report':str(self.report),'batch_id':self.batch,'actor':self.actor.pk}
            call_command('import_legacy_content','--dry-run',**kwargs)
            call_command('import_legacy_content','--apply',**kwargs)
            first=(ContentItem.objects.count(),MemberProfile.objects.count())
            call_command('import_legacy_content','--apply',**kwargs)
        self.assertEqual((ContentItem.objects.count(),MemberProfile.objects.count()),first)
        self.assertGreater(first[0],20);self.assertGreaterEqual(first[1],4)
        self.assertFalse(ContentItem.objects.filter(published_revision__isnull=False).exists())
        call_command('verify_legacy_import',batch_id=self.batch)
    def test_member_alumni_payload_imported_as_private_draft(self):
        self.row['kind']='MEMBER';self.row['payload']={'display_name':'Example graduate','slug':'graduate-example','public_member_status':'ALUMNI','alumni':{'graduation_year':2026,'degree':'硕士','destination_type':'WORK','organization':'Example institute','is_public':True}};self.save()
        self.run_import(True)
        from apps.members.models import MemberProfile
        p=MemberProfile.objects.get();self.assertEqual(p.draft_revision.alumni.organization,'Example institute');self.assertFalse(p.alumni_visible)
    def test_cross_record_alias_collision_rejected_before_any_import(self):
        second=self.root/'second.html';second.write_text('second source')
        other={**self.row,'source':second.name,'sha256':hashlib.sha256(second.read_bytes()).hexdigest(),'payload':{'title':'Second','detail':{'body':'Different'}}}
        self.manifest.write_text(json.dumps({'version':1,'records':[self.row,other]}))
        with self.assertRaises(CommandError):self.run_import(True)
        self.assertEqual(ContentItem.objects.count(),0)
    def test_new_batch_different_source_cannot_take_over_alias(self):
        self.run_import(True);original=ContentItem.objects.get().working_revision_id
        second=self.root/'second.html';second.write_text('other source')
        self.row['source']=second.name;self.row['sha256']=hashlib.sha256(second.read_bytes()).hexdigest();self.row['payload']['title']='Takeover';self.save();self.batch=str(uuid.uuid4())
        with self.assertRaises(CommandError):self.run_import(True)
        self.assertEqual(ContentItem.objects.get().working_revision_id,original)
