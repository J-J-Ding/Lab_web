from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from tempfile import TemporaryDirectory
from django.test import TestCase,override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from apps.content.tests import test_v14 as fixtures


class BlueAcademicCVTests(TestCase):
    setUpTestData=classmethod(fixtures.V14Contracts.setUpTestData.__func__)
    client_for=fixtures.V14Contracts.client_for
    profile=fixtures.V14Contracts.profile
    def test_blue_template_has_photo_contact_and_readable_word_styles(self):
        c=self.client_for(self.student);initial=c.get('/api/members/me/profile/').data
        with TemporaryDirectory() as media,override_settings(PRIVATE_MEDIA_ROOT=media):
            b=BytesIO();Image.new('RGB',(120,180),(45,105,155)).save(b,format='PNG')
            asset=c.post('/api/assets/',{'purpose':'avatar','file':SimpleUploadedFile('照片.png',b.getvalue(),content_type='image/png')},format='multipart').data
            payload={'lock_version':initial['lock_version'],'display_name':'蓝白学术简历','highest_education':'硕士研究生','enrollment_year':2025,'public_contact_email':'academic@example.org','phone':'13800138000','avatar_asset':asset['id'],'research_areas':['智能控制','机器学习'],'education':[{'school':'示例大学','major':'控制科学与工程','education_level':'硕士研究生','degree':'硕士','start_date':'2025-09-01','position':1}],'cv_private':{'gender':'女','political_status':'群众','skills':'Python、模型预测控制'}}
            saved=c.patch('/api/members/me/profile/',payload,format='json');self.assertEqual(saved.status_code,200,saved.data)
            metadata=c.get('/api/members/me/cv-data/').data;self.assertEqual(metadata['template_version'],'v16.blue-academic.1')
            result=c.post('/api/members/me/cv.docx',{'item_ids':[]},format='json');self.assertEqual(result.status_code,200)
            z=ZipFile(BytesIO(result.content));xml=z.read('word/document.xml').decode();styles=z.read('word/styles.xml').decode()
            for value in ('蓝白学术简历','academic@example.org','13800138000','示例大学','智能控制','硕士研究生','2025级'):self.assertIn(value,xml)
            self.assertIn('word/media/avatar.png',z.namelist());self.assertIn('CVSection',styles);self.assertIn('keepNext',styles);self.assertIn('173F6B',styles);self.assertIn('footerReference',xml)
            self.assertNotIn('{{',xml);self.assertNotIn('项目经历',xml)
            for name in z.namelist():
                if name.endswith('.xml') or name.endswith('.rels'):ET.fromstring(z.read(name))
                if name.endswith('.rels'):self.assertNotIn('TargetMode="External"',z.read(name).decode())

    def test_blank_template_and_legacy_request_remain_editable(self):
        c=self.client_for(self.student);self.profile(self.student,'只能用于本人生成')
        blank=c.get('/api/members/me/cv-template.docx');self.assertEqual(blank.status_code,200)
        xml=ZipFile(BytesIO(blank.content)).read('word/document.xml').decode();self.assertNotIn('只能用于本人生成',xml);self.assertNotIn('{{',xml);self.assertIn('教育背景',xml)
        old=c.post('/api/members/me/cv.docx',{'template_version':'v12.1','item_ids':[]},format='json');self.assertEqual(old.status_code,200)
        self.assertEqual(self.client_for(self.customer).get('/api/members/me/cv-template.docx').status_code,403)

    def test_empty_entries_and_unselected_sections_do_not_leave_headings(self):
        c=self.client_for(self.student);initial=c.get('/api/members/me/profile/').data
        response=c.patch('/api/members/me/profile/',{'lock_version':initial['lock_version'],'display_name':'空栏目验收','education':[{'position':1}]},format='json');self.assertEqual(response.status_code,200,response.data)
        result=c.post('/api/members/me/cv.docx',{'item_ids':[],'sections':['教育经历']},format='json');self.assertEqual(result.status_code,200)
        z=ZipFile(BytesIO(result.content));xml=z.read('word/document.xml').decode();self.assertNotIn('教育背景',xml);self.assertNotIn('项目经历',xml);self.assertNotIn('word/media/avatar.png',z.namelist());self.assertIn('空栏目验收',xml)
