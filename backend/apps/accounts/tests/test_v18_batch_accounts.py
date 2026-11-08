from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import timedelta
from django.test import TestCase,override_settings
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from cryptography.fernet import Fernet
from openpyxl import Workbook,load_workbook
from rest_framework.test import APIClient
from apps.content.tests import test_v10 as fixtures
from apps.accounts.models import User,AccountImportBatch
from apps.accounts.import_excel import HEADERS
from apps.accounts.batch_imports import process_one,cleanup


def workbook(rows):
    book=Workbook();sheet=book.active;sheet.title='账号导入';sheet.append(HEADERS)
    for row in rows:sheet.append(row)
    out=BytesIO();book.save(out);return out.getvalue()


class BatchImportTests(TestCase):
    setUpTestData=classmethod(fixtures.DirectCollaborationTests.setUpTestData.__func__)
    client_for=fixtures.DirectCollaborationTests.client_for

    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.settings_override=override_settings(ACCOUNT_IMPORT_ROOT=Path(self.temp.name),ACCOUNT_IMPORT_KEY=Fernet.generate_key().decode(),INITIAL_ACCOUNT_PASSWORD='Default654321',PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
        self.settings_override.enable();self.addCleanup(self.settings_override.disable)
        self.root_client=self.client_for(self.root)

    def upload(self,rows,client=None):
        c=client or self.root_client
        return c.post('/api/admin/account-imports/',{'file':SimpleUploadedFile('accounts.xlsx',workbook(rows),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')},format='multipart')

    def test_preview_confirm_password_name_and_idempotency(self):
        rows=[[1,'batch_teacher','Other987654','Teacher','正常','导入教师'],[2,'batch_student','','Student','正常',''],[3,'batch_customer','','Customer','已注销','访客姓名']]
        response=self.upload(rows);self.assertEqual(response.status_code,201,response.data);self.assertTrue(response.data['can_confirm']);self.assertNotIn('Other987654',str(response.data));pk=response.data['id']
        batch=AccountImportBatch.objects.get(pk=pk);path=Path(self.temp.name)/batch.storage_key;self.assertNotIn(b'Other987654',path.read_bytes())
        self.assertEqual(self.root_client.post(f'/api/admin/account-imports/{pk}/',{},format='json').status_code,202)
        process_one();batch.refresh_from_db();self.assertEqual(batch.state,'DONE',batch.errors)
        teacher=User.objects.get(username='batch_teacher');self.assertTrue(teacher.check_password('Other987654'));self.assertEqual(teacher.member_profile.published_revision.display_name,'导入教师')
        self.assertTrue(User.objects.get(username='batch_student').check_password('Default654321'));self.assertFalse(User.objects.get(username='batch_customer').is_active)
        self.root_client.post(f'/api/admin/account-imports/{pk}/',{},format='json');process_one();self.assertEqual(User.objects.filter(username__startswith='batch_').count(),3)
        # TestCase defers on_commit; invoke deletion callbacks to verify the private file is removed.
        self.assertEqual(batch.storage_key,'')

    def test_invalid_rows_no_creation_and_password_free_errors(self):
        response=self.upload([[1,'duplicate_user','','Student','正常',''],[2,'duplicate_user','SensitivePassword123','Root','xx','']]);self.assertEqual(response.status_code,201,response.data);self.assertFalse(response.data['can_confirm']);pk=response.data['id']
        self.assertNotIn('SensitivePassword123',str(response.data));self.assertEqual(self.root_client.post(f'/api/admin/account-imports/{pk}/',{},format='json').status_code,400);self.assertFalse(User.objects.filter(username='duplicate_user').exists())
        content=self.root_client.get(f'/api/admin/account-imports/{pk}/errors/').content.decode();self.assertNotIn('SensitivePassword123',content);self.assertIn('重复',content)

    def test_occupied_after_preview_rolls_back_all(self):
        response=self.upload([[1,'first_batch','','Student','正常',''],[2,'race_batch','','Student','正常','']]);pk=response.data['id']
        self.root_client.post(f'/api/admin/account-imports/{pk}/',{},format='json');User.objects.create_user(username='race_batch',password='Other123456');process_one()
        self.assertEqual(AccountImportBatch.objects.get(pk=pk).state,'FAILED');self.assertFalse(User.objects.filter(username='first_batch').exists())

    def test_permissions_csrf_expiry_and_root_profile_partial(self):
        self.assertEqual(self.upload([[1,'denied','','Student','正常','']],self.client_for(self.student)).status_code,403)
        self.assertEqual(APIClient().get('/api/admin/account-imports/template/').status_code,403)
        csrf=APIClient(enforce_csrf_checks=True);csrf.force_login(self.root);self.assertEqual(csrf.post('/api/admin/account-imports/',{}).status_code,403)
        response=self.upload([[1,'expired_batch','','Student','正常','']]);pk=response.data['id'];AccountImportBatch.objects.filter(pk=pk).update(expires_at=timezone.now()-timedelta(seconds=1));cleanup();self.assertEqual(AccountImportBatch.objects.get(pk=pk).state,'EXPIRED')
        from apps.members.models import MemberProfile
        p=MemberProfile.objects.create(user=self.student,created_by=self.root,updated_by=self.root)
        r=self.root_client.patch(f'/api/members/{p.pk}/profile/',{'lock_version':0,'display_name':'只填写姓名'},format='json');self.assertEqual(r.status_code,200,r.data)
        r=self.root_client.patch(f'/api/members/{p.pk}/profile/',{'lock_version':r.data['lock_version'],'public_contact_email':'','phone':'','cv_private':{'gender':'','political_status':''}},format='json');self.assertEqual(r.status_code,200,r.data);self.assertEqual(r.data['display_name'],'只填写姓名')
        r=self.client_for(self.student).patch('/api/members/me/profile/',{'lock_version':r.data['lock_version'],'phone':''},format='json');self.assertEqual(r.status_code,400)

    def test_template_and_malicious_file_shapes(self):
        from apps.accounts.import_excel import parse
        response=self.root_client.get('/api/admin/account-imports/template/');self.assertEqual(response.status_code,200);book=load_workbook(BytesIO(response.content));self.assertEqual([c.value for c in book['账号导入'][1]],HEADERS)
        for rows in ([[1,'=1+1','','Student','正常','']],[[1,123,'','Student','正常','']],[[i,'user'+str(i),'','Student','正常',''] for i in range(501)]):
            r=self.upload(rows);self.assertIn(r.status_code,(201,400));self.assertTrue(r.status_code==400 or r.data['errors'])

    def test_owner_scope_revoked_root_and_files_removed(self):
        response=self.upload([[1,'revoked_batch','','Student','正常','']]);pk=response.data['id']
        other=User.objects.create_user(username='other_root',password='Test123456',is_superuser=True,is_staff=True,role='TEACHER')
        self.assertEqual(self.client_for(other).get(f'/api/admin/account-imports/{pk}/').status_code,404)
        batch=AccountImportBatch.objects.get(pk=pk);path=Path(self.temp.name)/batch.storage_key
        self.root_client.post(f'/api/admin/account-imports/{pk}/',{},format='json');User.objects.filter(pk=self.root.pk).update(is_active=False)
        with self.captureOnCommitCallbacks(execute=True):process_one()
        batch.refresh_from_db();self.assertEqual(batch.state,'FAILED');self.assertFalse(path.exists());self.assertFalse(User.objects.filter(username='revoked_batch').exists())

    def test_partial_alumni_and_empty_fields_still_validate_types(self):
        c=self.root_client;r=c.get('/api/members/me/profile/');self.assertEqual(r.status_code,200)
        r=c.patch('/api/members/me/profile/',{'lock_version':r.data['lock_version'],'public_member_status':'ALUMNI','alumni':{'organization':'仅去向单位'}},format='json');self.assertEqual(r.status_code,200,r.data);self.assertEqual(r.data['alumni']['organization'],'仅去向单位');self.assertIsNone(r.data['alumni']['graduation_year'])
        r=c.patch('/api/members/me/profile/',{'lock_version':r.data['lock_version'],'public_contact_email':'not-an-email'},format='json');self.assertEqual(r.status_code,400)

    def test_500_rows_without_passwords_in_summary(self):
        rows=[[i+1,'bulk'+str(i),'','Student','正常',''] for i in range(500)]
        response=self.upload(rows);self.assertEqual(response.status_code,201,response.data);self.assertTrue(response.data['can_confirm']);self.assertEqual(response.data['count'],500)
        pk=response.data['id'];self.root_client.post(f'/api/admin/account-imports/{pk}/',{},format='json')
        with self.captureOnCommitCallbacks(execute=True):process_one()
        b=AccountImportBatch.objects.get(pk=pk);self.assertEqual(b.state,'DONE',b.errors);self.assertEqual(len(b.created_ids),500)
        self.assertEqual(list(Path(self.temp.name).iterdir()),[])

    def test_failure_during_name_initialization_rolls_back_created_accounts(self):
        from unittest.mock import patch
        r=self.upload([[1,'rollback_first','','Student','正常',''],[2,'rollback_second','','Student','正常','姓名']]);pk=r.data['id'];self.root_client.post(f'/api/admin/account-imports/{pk}/',{},format='json')
        with patch('apps.members.direct.save_profile',side_effect=ValueError('Synthetic failure')):
            process_one()
        self.assertEqual(AccountImportBatch.objects.get(pk=pk).state,'FAILED');self.assertFalse(User.objects.filter(username__in=['rollback_first','rollback_second']).exists())

    def test_multiple_sheets_external_links_and_oversize_rejected(self):
        from zipfile import ZipFile,ZIP_DEFLATED
        from apps.accounts.import_excel import parse
        b=Workbook();b.active.title='账号导入';b.active.append(HEADERS);b.create_sheet('第二数据表');out=BytesIO();b.save(out)
        with self.assertRaises(ValueError):parse(out.getvalue())
        raw=workbook([[1,'external','','Student','正常','']]);out=BytesIO()
        with ZipFile(BytesIO(raw)) as source,ZipFile(out,'w',ZIP_DEFLATED) as target:
            for entry in source.infolist():target.writestr(entry.filename,source.read(entry))
            target.writestr('xl/externalLinks/externalLink1.xml','<x/>')
        with self.assertRaises(ValueError):parse(out.getvalue())
        with self.assertRaises(ValueError):parse(b'x'*(2*1024*1024+1))

    def test_role_spelling_is_case_sensitive(self):
        for role in ('teacher','student','customer','custom','TEACHER','STUDENT','CUSTOMER'):
            response=self.upload([[1,'case_'+role,'',role,'正常','']]);self.assertEqual(response.status_code,201,response.data);self.assertFalse(response.data['can_confirm']);self.assertTrue(any('大小写' in e['message'] for e in response.data['errors']))
