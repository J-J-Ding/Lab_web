from django.test import TestCase
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient
from apps.content.tests import test_v10 as fixtures
from apps.content.models import ContentItem


class V12Tests(TestCase):
    setUpTestData=classmethod(fixtures.DirectCollaborationTests.setUpTestData.__func__)
    client_for=fixtures.DirectCollaborationTests.client_for
    profile=fixtures.DirectCollaborationTests.profile
    create=fixtures.DirectCollaborationTests.create

    def test_deleted_content_all_projections_and_private_recycle(self):
        self.profile(self.student,'本人',True)
        c=self.client_for(self.student);item=self.create(c,authors=[self.student.pk])
        path='/api/content/items/'+item['id']+'/'
        r=c.post(path+'delete/',{'lock_version':item['lock_version']},format='json')
        self.assertEqual(r.status_code,200,r.data)
        self.assertTrue(r.data['deleted'])
        self.assertEqual(APIClient().get('/api/public/content/'+item['id']+'/').status_code,404)
        self.assertEqual(APIClient().get('/api/public/home/').data['stats']['papers'],0)
        self.assertEqual(c.get('/api/content/items/').data['count'],0)
        self.assertEqual(c.get('/api/content/items/?scope=deleted').data['count'],1)
        other=self.client_for(self.other)
        self.assertEqual(other.get('/api/content/items/?scope=deleted').data['count'],0)
        self.assertEqual(other.get(path).status_code,404)
        self.assertEqual(c.patch(path,{'lock_version':r.data['lock_version'],'title':'不能改'},format='json').status_code,409)
        restored=c.post(path+'undelete/',{'lock_version':r.data['lock_version']},format='json')
        self.assertEqual(restored.status_code,200,restored.data)
        self.assertFalse(restored.data['visible'])
        self.assertEqual(APIClient().get('/api/public/content/'+item['id']+'/').status_code,404)
        saved=c.patch(path,{'lock_version':restored.data['lock_version'],'title':'确认公开'},format='json')
        self.assertEqual(saved.status_code,200,saved.data)
        self.assertEqual(APIClient().get('/api/public/content/'+item['id']+'/').status_code,200)
        self.assertEqual(ContentItem.objects.get(pk=item['id']).revisions.count(),2)

    def test_delete_checks_edit_permission_and_version(self):
        self.profile(self.other,'署名者')
        c=self.client_for(self.student);item=self.create(c,authors=[self.other.pk]);path='/api/content/items/'+item['id']+'/delete/'
        self.assertEqual(self.client_for(self.other).post(path,{'lock_version':item['lock_version']},format='json').status_code,403)
        self.assertEqual(c.post(path,{'lock_version':0},format='json').status_code,409)
        self.assertEqual(c.post(path,{},format='json').status_code,400)

    def test_password_policy_and_old_login(self):
        for password in ('abc123','ABC123','a1bcde'):
            validate_password(password)
        for password in ('123456','abcdef','a1234','abc123!','汉字123abc','a1'+'b'*127):
            with self.assertRaises(ValidationError):validate_password(password)
        self.customer.set_password('Legacy!Password123');self.customer.save()
        self.assertEqual(APIClient().post('/api/auth/login/',{'username':self.customer.username,'password':'Legacy!Password123'},format='json').status_code,200)

    def test_business_role_separation(self):
        customer=self.client_for(self.customer)
        self.assertEqual(customer.get('/api/members/me/profile/').status_code,200)
        self.assertEqual(customer.get('/api/members/directory/').status_code,403)
        self.assertEqual(customer.get('/api/stats/me/').status_code,403)
        for user in (self.teacher,self.student,self.root,self.customer):
            c=self.client_for(user)
            self.assertEqual(c.post('/api/members/me/resumes/',{'title':'本人简历'},format='json').status_code,201)

    def test_alumni_only_public_when_graduated(self):
        c=self.client_for(self.student);p=self.profile(self.student,'毕业测试',True)
        r=c.patch('/api/members/me/profile/',{'lock_version':p['lock_version'],'alumni_visible':True,'alumni':{'graduation_year':2025,'destination_type':'WORK','organization':'保留单位','is_public':True}},format='json')
        self.assertEqual(r.status_code,200,r.data)
        from apps.members.models import MemberProfile
        slug=MemberProfile.objects.get(user=self.student).published_revision.slug
        url='/api/public/members/'+slug+'/'
        self.assertNotIn('alumni',APIClient().get(url).data)
        self.assertEqual(APIClient().get('/api/public/members/?year=2025').data['count'],0)
        graduated=c.patch('/api/members/me/profile/',{'lock_version':r.data['lock_version'],'public_member_status':'ALUMNI'},format='json')
        self.assertEqual(graduated.status_code,200,graduated.data)
        self.assertNotIn('alumni',APIClient().get(url).data)
        self.assertEqual(graduated.data['alumni']['organization'],'保留单位')

    def test_patent_and_contact_email(self):
        c=self.client_for(self.teacher)
        self.profile(self.teacher,'专利发明人')
        p=self.create(c,authors=[self.teacher.pk],kind='PATENT',title='专利',detail={'patent_number':'CN123','application_date':'2025-01-01','status':'APPLIED'})
        r=APIClient().get('/api/public/content/'+p['id']+'/');self.assertEqual(r.status_code,200,r.data);self.assertEqual(r.data['detail']['patent_number'],'CN123')
        page=self.create(c,kind='LAB_PAGE',detail={'page_key':'contact','contact_email':'team@example.org'})
        self.assertEqual(APIClient().get('/api/public/pages/contact/').data['detail']['contact_email'],'team@example.org')
        self.assertEqual(APIClient().get('/api/public/stats/annual/?kind=PATENT').data['data'][0]['total'],1)

    def test_submission_snapshot_notifications_withdraw_and_roles(self):
        from django.conf import settings
        from pathlib import Path
        from apps.assets.models import AssetFile
        from tempfile import TemporaryDirectory
        from django.test import override_settings
        c=self.client_for(self.customer);p=self.profile(self.customer,'访客甲')
        p=c.patch('/api/members/me/profile/',{'lock_version':p['lock_version'],'phone':'12345678'},format='json')
        self.assertEqual(p.status_code,200,p.data)
        with TemporaryDirectory() as media,override_settings(PRIVATE_MEDIA_ROOT=media):
            Path(media,'submitted.pdf').write_bytes(b'%PDF-submission-test')
            asset=AssetFile.objects.create(owner=self.customer,purpose='resume',storage_key='submitted.pdf',original_filename='简历.pdf',mime_type='application/pdf',size=20,sha256='0'*64,scan_status='CLEAN',visibility='PRIVATE')
            resume=c.post('/api/members/me/resumes/',{'title':'申请简历','asset':str(asset.pk)},format='json').data
            url='/api/members/me/resume-submissions/'
            self.assertEqual(c.post(url,{'resume_id':resume['id'],'consent':False},format='json').status_code,400)
            r=c.post(url,{'resume_id':resume['id'],'consent':True},format='json')
            self.assertEqual(r.status_code,201,getattr(r,'data',None))
            sid=r.data['id'];teacher=self.client_for(self.teacher)
            self.assertEqual(c.post(url,{'resume_id':resume['id'],'consent':True},format='json').status_code,200)
            self.assertEqual(teacher.get('/api/admin/resume-submissions/').status_code,403)
            notices=teacher.get('/api/members/notifications/')
            self.assertEqual(notices.status_code,200,getattr(notices,'data',None));self.assertEqual(notices.data['unread_count'],1)
            notice=notices.data['results'][0]
            self.assertEqual(teacher.post('/api/members/notifications/'+notice['id']+'/read/',{},format='json').status_code,200)
            self.assertEqual(teacher.get('/api/members/notifications/').data['unread_count'],0)
            self.assertEqual(self.client_for(self.root).get('/api/members/notifications/').data['unread_count'],1)
            detail='/api/members/resume-inbox/'+sid+'/'
            received=teacher.get(detail);self.assertEqual(received.status_code,200,getattr(received,'data',None))
            self.assertEqual(received.data['profile']['display_name'],'访客甲');self.assertEqual(received.data['profile']['phone'],'12345678')
            c.patch('/api/members/me/profile/',{'lock_version':p.data['lock_version'],'display_name':'更新姓名'},format='json')
            self.assertEqual(teacher.get(detail).data['profile']['display_name'],'访客甲')
            self.assertEqual(teacher.get(detail+'download/').status_code,200)
            self.assertEqual(teacher.get('/api/assets/'+str(asset.pk)+'/download/').status_code,404)
            for u in (self.student,self.other):self.assertEqual(self.client_for(u).get(detail).status_code,403)
            self.assertEqual(self.client_for(self.student).post(url,{'resume_id':resume['id'],'consent':True},format='json').status_code,403)
            self.assertEqual(c.post(url+sid+'/withdraw/',{},format='json').status_code,200)
            self.assertEqual(teacher.get(detail).status_code,404)
            self.assertEqual(teacher.get(detail+'download/').status_code,404)
            self.assertEqual(self.client_for(self.root).get(detail).status_code,200)
            self.assertTrue(teacher.get('/api/members/notifications/').data['results'][0]['withdrawn'])

    def test_cv_current_contributions_private_fields_and_docx(self):
        from zipfile import ZipFile
        from io import BytesIO
        from xml.etree import ElementTree as ET
        c=self.client_for(self.student);p=self.profile(self.student,'自动简历姓名')
        r=c.patch('/api/members/me/profile/',{'lock_version':p['lock_version'],'cv_private':{'skills':'Python与控制','political_status':'群众','education_note':'院系说明','internships':[{'organization':'实习单位','role':'研发','period':'2025','description':'真实工作'}],'practice':[]}},format='json')
        self.assertEqual(r.status_code,200,r.data)
        paper=self.create(c,title='本人论文',authors=[self.student.pk],detail={'venue':'示例会议','publication_date':'2025-01-01'})
        internal=self.create(c,kind='PROJECT',title='内部项目',authors=[self.student.pk],visibility_scope='TEAM',detail={'funding_amount':'99999'})
        other=self.create(c,title='不是本人参与')
        cv=c.get('/api/members/me/cv-data/');self.assertEqual(cv.status_code,200,getattr(cv,'data',None));self.assertEqual(len(cv.data['achievements']),2)
        self.assertEqual(self.client_for(self.customer).get('/api/members/me/cv-data/').status_code,403)
        r=c.post('/api/members/me/cv.docx',{'item_ids':[other['id']]},format='json');self.assertEqual(r.status_code,400)
        r=c.post('/api/members/me/cv.docx',{'item_ids':[paper['id'],internal['id']]},format='json');self.assertEqual(r.status_code,400)
        r=c.post('/api/members/me/cv.docx',{'item_ids':[paper['id']]},format='json');self.assertEqual(r.status_code,200,getattr(r,'data',None));self.assertEqual(r['Cache-Control'],'no-store')
        z=ZipFile(BytesIO(r.content));xml=z.read('word/document.xml').decode();self.assertIn('自动简历姓名',xml);self.assertIn('本人论文',xml);self.assertIn('实习单位',xml);self.assertNotIn('{{',xml);self.assertNotIn('内部项目',xml);self.assertNotIn('99999',xml)
        for name in z.namelist():
            if name.endswith('.rels'):self.assertNotIn('TargetMode="External"',z.read(name).decode())
        ET.fromstring(xml)
        r=c.post('/api/members/me/cv.docx',{'item_ids':[internal['id']],'include_team':True},format='json');self.assertEqual(r.status_code,200);self.assertIn('内部项目',ZipFile(BytesIO(r.content)).read('word/document.xml').decode())
        deleted=c.post('/api/content/items/'+paper['id']+'/delete/',{'lock_version':paper['lock_version']},format='json');self.assertEqual(deleted.status_code,200)
        self.assertEqual(c.post('/api/members/me/cv.docx',{'item_ids':[paper['id']]},format='json').status_code,400)
        self.assertNotIn('cv_private',str(APIClient().get('/api/public/members/').data))

    def test_shared_public_asset_survives_one_reference_delete(self):
        from apps.assets.models import AssetFile
        from django.test import override_settings
        from pathlib import Path
        from tempfile import TemporaryDirectory
        c=self.client_for(self.student)
        with TemporaryDirectory() as media,override_settings(PRIVATE_MEDIA_ROOT=media):
            Path(media,'shared.pdf').write_bytes(b'%PDF-test')
            a=AssetFile.objects.create(owner=self.student,purpose='attachment',storage_key='shared.pdf',original_filename='paper.pdf',mime_type='application/pdf',size=9,sha256='0'*64,scan_status='CLEAN')
            one=self.create(c,assets=[str(a.pk)]);two=self.create(c,assets=[str(a.pk)])
            r=c.post('/api/content/items/'+one['id']+'/delete/',{'lock_version':one['lock_version']},format='json');self.assertEqual(r.status_code,200)
            url='/api/public/assets/'+str(a.pk)+'/'
            self.assertEqual(APIClient().get(url).status_code,200)
            r=c.patch('/api/content/items/'+one['id']+'/',{'lock_version':r.data['lock_version'],'title':'已删除不能改'},format='json');self.assertEqual(r.status_code,409)
            r=c.post('/api/content/items/'+two['id']+'/delete/',{'lock_version':two['lock_version']},format='json');self.assertEqual(r.status_code,200)
            self.assertEqual(APIClient().get(url).status_code,404)

    def test_private_cv_not_writable_by_teacher_and_snapshot_is_frozen(self):
        from django.db import transaction,IntegrityError
        from apps.members.models import ResumeSubmission,Resume
        from apps.assets.models import AssetFile
        p=self.profile(self.student,'本人私有简历')
        teacher=self.client_for(self.teacher)
        r=teacher.patch('/api/members/'+p['id']+'/profile/',{'lock_version':p['lock_version'],'cv_private':{'skills':'不准代填私有信息'}},format='json');self.assertEqual(r.status_code,403)
        a=AssetFile.objects.create(owner=self.customer,purpose='resume',storage_key='snapshot.pdf',original_filename='cv.pdf',mime_type='application/pdf',size=1,sha256='0'*64,scan_status='CLEAN')
        resume=Resume.objects.create(owner=self.customer,asset=a)
        row=ResumeSubmission.objects.create(owner=self.customer,resume=resume,asset=a,resume_version=0,profile_snapshot={'display_name':'不可改'},resume_snapshot={})
        with self.assertRaises(IntegrityError),transaction.atomic():ResumeSubmission.objects.filter(pk=row.pk).update(profile_snapshot={'display_name':'篡改'})

    def test_shared_asset_team_scope_does_not_break_other_public_reference(self):
        from apps.assets.models import AssetFile
        from django.test import override_settings
        from tempfile import TemporaryDirectory
        from pathlib import Path
        c=self.client_for(self.student)
        with TemporaryDirectory() as media,override_settings(PRIVATE_MEDIA_ROOT=media):
            Path(media,'scope.pdf').write_bytes(b'%PDF-test')
            a=AssetFile.objects.create(owner=self.student,purpose='attachment',storage_key='scope.pdf',original_filename='paper.pdf',mime_type='application/pdf',size=9,sha256='0'*64,scan_status='CLEAN')
            one=self.create(c,assets=[str(a.pk)]);self.create(c,assets=[str(a.pk)])
            r=c.patch('/api/content/items/'+one['id']+'/',{'lock_version':one['lock_version'],'visibility_scope':'TEAM'},format='json');self.assertEqual(r.status_code,200)
            self.assertEqual(APIClient().get('/api/public/assets/'+str(a.pk)+'/').status_code,200)

    def test_password_policy_register_change_and_root_reset(self):
        c=APIClient()
        r=c.post('/api/auth/register/',{'username':'v12register','password':'abc123'},format='json');self.assertEqual(r.status_code,201,r.data)
        self.assertEqual(c.post('/api/auth/login/',{'username':'v12register','password':'abc123'},format='json').status_code,200)
        r=c.post('/api/auth/change-password/',{'old_password':'abc123','new_password':'def456'},format='json');self.assertEqual(r.status_code,204,r.data)
        from apps.accounts.models import User
        user=User.objects.get(username='v12register')
        root=self.client_for(self.root)
        r=root.post('/api/admin/users/'+str(user.pk)+'/reset-password/',{'new_password':'ghi789'},format='json');self.assertEqual(r.status_code,204,r.data)
        self.assertEqual(APIClient().post('/api/auth/login/',{'username':'v12register','password':'ghi789'},format='json').status_code,200)
