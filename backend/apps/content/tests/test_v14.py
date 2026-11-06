from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from django.test import TestCase,override_settings
from rest_framework.test import APIClient
from apps.content.tests import test_v10 as fixtures
from apps.assets.inspect_file import clean
from pypdf import PdfWriter,PdfReader
from pypdf.annotations import Link

class V14Contracts(TestCase):
    setUpTestData=classmethod(fixtures.DirectCollaborationTests.setUpTestData.__func__)
    client_for=fixtures.DirectCollaborationTests.client_for
    profile=fixtures.DirectCollaborationTests.profile
    create=fixtures.DirectCollaborationTests.create

    def pdf(self):
        from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject,NumberObject
        w=PdfWriter()
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        for index in range(2):
            page=w.add_blank_page(width=600,height=800)
            image=DecodedStreamObject();image.set_data(bytes([30,90,150]));image.update({NameObject('/Type'):NameObject('/XObject'),NameObject('/Subtype'):NameObject('/Image'),NameObject('/Width'):NumberObject(1),NameObject('/Height'):NumberObject(1),NameObject('/ColorSpace'):NameObject('/DeviceRGB'),NameObject('/BitsPerComponent'):NumberObject(8)})
            page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):w._add_object(font)}),NameObject('/XObject'):DictionaryObject({NameObject('/Im1'):w._add_object(image)})})
            stream=DecodedStreamObject();stream.set_data(b'BT /F1 18 Tf 50 700 Td (Research CV) Tj ET q 40 0 0 40 50 600 cm /Im1 Do Q');page[NameObject('/Contents')]=w._add_object(stream)
            w.add_annotation(page_number=index,annotation=Link(rect=(1,1,80,20),url='https://example.org'))
        b=BytesIO();w.write(b);return b.getvalue()

    def test_ordinary_pdf_link_is_removed_but_dangerous_pdf_rejected(self):
        output=clean('proof',self.pdf());r=PdfReader(BytesIO(output));self.assertEqual(len(r.pages),2);self.assertNotIn('/Annots',r.pages[0]);self.assertIn('Research CV',r.pages[0].extract_text());self.assertEqual(len(r.pages[0].images),1)
        w=PdfWriter();w.add_blank_page(width=600,height=800);w.add_js('app.alert(1)');b=BytesIO();w.write(b)
        with self.assertRaises(ValueError):clean('proof',b.getvalue())

    def test_fixed_member_fields_and_private_customer(self):
        c=self.client_for(self.student);initial=c.get('/api/members/me/profile/').data
        payload={'lock_version':initial['lock_version'],'display_name':'固定展示成员','bio':'绝不公开简介','public_contact_email':'member@example.org','enrollment_year':2025,'phone':'绝不公开电话','education':[{'school':'绝不公开学校','major':'绝不公开专业','degree':'硕士','education_level':'硕士研究生','position':1}],'research_areas':['控制'],'cv_private':{'gender':'女','political_status':'群众'}}
        r=c.patch('/api/members/me/profile/',payload,format='json');self.assertEqual(r.status_code,200,r.data)
        rows=APIClient().get('/api/public/members/').data['results'];self.assertEqual(len(rows),1);row=rows[0];self.assertEqual(row['enrollment_year'],2025);self.assertEqual(row['education'][0],{'education_level':'硕士研究生'});self.assertEqual(row['public_contact_email'],'member@example.org')
        self.assertFalse(set(row)&{'bio','phone','cv_private','alumni','internal_contact'})
        self.profile(self.customer,'不进入成员目录');self.assertEqual(APIClient().get('/api/public/members/').data['count'],1)
        r=c.patch('/api/members/me/profile/',{'lock_version':r.data['lock_version'],'public_contact_email':''},format='json');self.assertEqual(r.status_code,200,r.data);self.assertNotIn('public_contact_email',APIClient().get('/api/public/members/').data['results'][0])

    def test_site_team_matrix_details_stats_home_and_deleted(self):
        c=self.client_for(self.student);self.profile(self.student,'成果成员');public=self.create(c,title='公开论文',authors=[self.student.pk]);internal=self.create(c,title='内部论文',authors=[self.student.pk],visibility_scope='TEAM')
        for user in (None,self.customer,self.student,self.teacher,self.root):
            client=self.client_for(user) if user else APIClient();team=bool(user and (user.is_superuser or user.role in ('TEACHER','STUDENT')))
            with self.subTest(user=str(user)):
                r=client.get('/api/site/content/');self.assertEqual(r.status_code,200,getattr(r,'data',None));self.assertEqual(r.data['count'],2 if team else 1)
                self.assertEqual(client.get('/api/site/content/'+internal['id']+'/').status_code,200 if team else 404)
                self.assertEqual(client.get('/api/public/content/').data['count'],1)
                self.assertEqual(client.get('/api/site/home/').data['stats']['papers'],2 if team else 1)
                self.assertEqual(client.get('/api/site/stats/annual/?kind=PAPER').data['data'][0]['total'],2 if team else 1)
                self.assertIn('no-store',r['Cache-Control']);self.assertIn('Cookie',r.get('Vary',''))
        r=c.post('/api/content/items/'+internal['id']+'/delete/',{'lock_version':internal['lock_version']},format='json');self.assertEqual(r.status_code,200)
        self.assertEqual(c.get('/api/site/content/').data['count'],1)

    def test_pdf_generic_mime_upload_submission_and_teacher_download(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        c=self.client_for(self.customer);self.profile(self.customer,'PDF投递人')
        with TemporaryDirectory() as media,override_settings(PRIVATE_MEDIA_ROOT=media):
            r=c.post('/api/assets/',{'purpose':'resume','file':SimpleUploadedFile('含链接简历.pdf',self.pdf(),content_type='application/octet-stream')},format='multipart');self.assertEqual(r.status_code,201,r.data)
            resume=c.post('/api/members/me/resumes/',{'title':'学术简历','asset':r.data['id']},format='json').data
            row=c.post('/api/members/me/resume-submissions/',{'resume_id':resume['id'],'consent':True},format='json');self.assertEqual(row.status_code,201,row.data);self.assertNotIn('intention',row.data['resume'])
            teacher=self.client_for(self.teacher);response=teacher.get(row.data['download_url']);self.assertEqual(response.status_code,200);parsed=PdfReader(BytesIO(b''.join(response.streaming_content)));self.assertNotIn('/Annots',parsed.pages[0])

    def test_region_choices_dates_and_historical_fields(self):
        c=self.client_for(self.student);initial=c.get('/api/members/me/profile/').data
        bads=[{'gender':'伪造'},{'political_status':'伪造'},{'native_region':{'province':'42','city':'1101'}},{'internships':[{'start_date':'2026-02-01','end_date':'2025-01-01'}]}]
        for data in bads:self.assertEqual(c.patch('/api/members/me/profile/',{'lock_version':initial['lock_version'],'cv_private':data},format='json').status_code,400)
        good={'gender':'男','political_status':'群众','native_region':{'province':'42','city':'4201','district':'420102'},'internships':[{'start_date':'2025-01-01','end_date':None,'organization':'单位'}]}
        r=c.patch('/api/members/me/profile/',{'lock_version':initial['lock_version'],'display_name':'下拉成员','cv_private':good},format='json');self.assertEqual(r.status_code,200,r.data);self.assertEqual(r.data['cv_private']['native_region']['names'][0],'湖北省')
        self.assertEqual(c.patch('/api/members/me/profile/',{'lock_version':r.data['lock_version'],'cv_private':r.data['cv_private']},format='json').status_code,200)

    def test_team_assets_relations_and_logout_are_guarded(self):
        from apps.assets.models import AssetFile
        c=self.client_for(self.student);self.profile(self.student,'贡献成员');profile=c.get('/api/members/me/profile/').data
        with TemporaryDirectory() as media,override_settings(PRIVATE_MEDIA_ROOT=media):
            Path(media,'internal.pdf').write_bytes(self.pdf())
            a=AssetFile.objects.create(owner=self.student,purpose='attachment',storage_key='internal.pdf',original_filename='内部.pdf',mime_type='application/pdf',size=len(self.pdf()),sha256='0'*64,scan_status='CLEAN')
            project=self.create(c,kind='PROJECT',title='内部项目',visibility_scope='TEAM')
            item=self.create(c,title='内部关联',authors=[self.student.pk],assets=[str(a.pk)],project_links=[project['id']],visibility_scope='TEAM')
            url='/api/site/assets/'+str(a.pk)+'/'
            self.assertEqual(c.get(url).status_code,200);self.assertEqual(APIClient().get(url).status_code,404);self.assertEqual(self.client_for(self.customer).get(url).status_code,404);self.assertEqual(c.get('/api/public/assets/'+str(a.pk)+'/').status_code,404)
            self.assertEqual(c.get('/api/site/projects/'+project['id']+'/outputs/').data['count'],1)
            slug=c.get('/api/members/me/profile/').data['slug'];self.assertEqual(c.get('/api/site/members/'+slug+'/achievements/').data['count'],1);self.assertEqual(APIClient().get('/api/site/members/'+slug+'/achievements/').data['count'],0)
            from apps.accounts.models import User
            User.objects.filter(pk=self.student.pk).update(role='CUSTOMER',session_version=self.student.session_version+1)
            self.assertEqual(c.get(url).status_code,404);self.assertEqual(c.get('/api/site/content/').data['count'],0)

    def test_history_preserves_year_and_level_and_no_extra_public_fields(self):
        c=self.client_for(self.student);initial=c.get('/api/members/me/profile/').data
        first=c.patch('/api/members/me/profile/',{'lock_version':initial['lock_version'],'display_name':'历史成员','enrollment_year':2025,'education':[{'school':'','degree':'硕士','education_level':'硕士研究生','position':1}]},format='json');self.assertEqual(first.status_code,200,first.data)
        history=c.get('/api/members/me/history/').data['results'];revision=history[0]['id']
        changed=c.patch('/api/members/me/profile/',{'lock_version':first.data['lock_version'],'enrollment_year':2026,'education':[{'school':'','degree':'硕士','position':1}]},format='json');self.assertEqual(changed.status_code,200,changed.data);self.assertEqual(changed.data['education'][0]['education_level'],'硕士研究生')
        restored=c.post('/api/members/me/restore/',{'lock_version':changed.data['lock_version'],'source_revision':revision},format='json');self.assertEqual(restored.status_code,200,restored.data);self.assertEqual(restored.data['enrollment_year'],2025);self.assertEqual(restored.data['education'][0]['education_level'],'硕士研究生')
