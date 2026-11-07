from copy import deepcopy
from uuid import uuid4
from django.test import TestCase, SimpleTestCase
from rest_framework.exceptions import ValidationError
from apps.content.tests import test_v10 as fixtures


def document(text='图文正文'):
    return {'version':1,'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':text}]}]}


class DocumentValidationTests(SimpleTestCase):
    def test_valid_and_unsafe_documents(self):
        from apps.content.rich_content import validate_document
        self.assertEqual(validate_document(document()),document())
        for node in ({'type':'script'}, {'type':'image','attrs':{'asset_id':str(uuid4()),'src':'https://example.org/x'}}, {'type':'text','text':'链接','marks':[{'type':'link','attrs':{'href':'javascript:alert(1)'}}]}):
            with self.subTest(node=node),self.assertRaises(ValidationError):validate_document({'version':1,'type':'doc','content':[node]})
        for value in (document('a'*50001), {'version':True,'type':'doc','content':[]}, {'version':1,'type':'doc','content':[{'type':'paragraph','attrs':{'onclick':'x'}}]}):
            with self.assertRaises(ValidationError):validate_document(value)


class RichContentTests(TestCase):
    setUpTestData=classmethod(fixtures.DirectCollaborationTests.setUpTestData.__func__)
    client_for=fixtures.DirectCollaborationTests.client_for
    create=fixtures.DirectCollaborationTests.create

    def test_save_legacy_patch_restore_and_public_document(self):
        c=self.client_for(self.student);body=document('<不应当作HTML>')
        row=self.create(c,rich_body=body)
        self.assertEqual(row['revision']['rich_body'],body)
        first=row['revision']['id']
        response=c.patch('/api/content/items/'+row['id']+'/',{'lock_version':row['lock_version'],'title':'旧客户端只改标题'},format='json')
        self.assertEqual(response.status_code,200,response.data);row=response.data
        self.assertEqual(row['revision']['rich_body'],body)
        response=c.patch('/api/content/items/'+row['id']+'/',{'lock_version':row['lock_version'],'rich_body':document('新版正文')},format='json');self.assertEqual(response.status_code,200,response.data);row=response.data
        response=c.post('/api/content/items/'+row['id']+'/restore/',{'lock_version':row['lock_version'],'source_revision':first},format='json');self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['revision']['rich_body'],body)
        self.assertEqual(c.get('/api/site/content/'+row['id']+'/').data['rich_body'],body)

    def test_missing_or_foreign_image_rejected(self):
        c=self.client_for(self.student)
        response=c.post('/api/content/items/',{'kind':'PAPER','title':'图片越权','detail':{},'rich_body':{'version':1,'type':'doc','content':[{'type':'image','attrs':{'asset_id':str(uuid4()),'width':100,'align':'center','caption':''}}]}},format='json')
        self.assertEqual(response.status_code,400,response.data)

    def test_image_lifecycle_and_team_boundary(self):
        from tempfile import TemporaryDirectory
        from django.test import override_settings
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.utils import timezone
        from apps.assets.models import AssetFile
        from PIL import Image
        from io import BytesIO
        from pathlib import Path
        output=BytesIO();Image.new('RGB',(60,90),'blue').save(output,format='PNG')
        c=self.client_for(self.student);other=self.client_for(self.teacher)
        with TemporaryDirectory() as media,override_settings(PRIVATE_MEDIA_ROOT=media):
            response=c.post('/api/assets/',{'purpose':'image','file':SimpleUploadedFile('正文.png',output.getvalue(),content_type='image/png')},format='multipart')
            self.assertEqual(response.status_code,201,response.data);aid=response.data['id']
            body=document();body['content'].append({'type':'image','attrs':{'asset_id':aid.upper(),'width':50,'align':'center','caption':'实验图'}})
            bad=other.post('/api/content/items/',{'kind':'AWARD','title':'越权图片','rich_body':body},format='json');self.assertEqual(bad.status_code,400,bad.data)
            row=self.create(c,rich_body=body,visibility_scope='TEAM')
            asset=AssetFile.objects.get(pk=aid);self.assertIsNone(asset.expires_at)
            self.assertEqual(row['revision']['assets'],[aid])
            self.assertEqual(row['revision']['rich_body']['content'][-1]['attrs']['asset_id'],aid)
            from rest_framework.test import APIClient
            self.assertEqual(APIClient().get('/api/public/assets/'+aid+'/').status_code,404)
            self.assertEqual(self.client_for(self.customer).get('/api/site/assets/'+aid+'/').status_code,404)
            response=other.get('/api/site/assets/'+aid+'/');self.assertEqual(response.status_code,200);b''.join(response.streaming_content)
            response=APIClient().get('/api/public/content/'+row['id']+'/');self.assertEqual(response.status_code,404)
            response=c.patch('/api/content/items/'+row['id']+'/',{'lock_version':row['lock_version'],'visibility_scope':'PUBLIC'},format='json');self.assertEqual(response.status_code,200,response.data);row=response.data
            response=APIClient().get('/api/public/assets/'+aid+'/');self.assertEqual(response.status_code,200);b''.join(response.streaming_content)
            response=c.patch('/api/content/items/'+row['id']+'/',{'lock_version':row['lock_version'],'rich_body':document('图片已移除'),'assets':[],'cover_asset':None},format='json');self.assertEqual(response.status_code,200,response.data)
            self.assertTrue((Path(media)/asset.storage_key).exists())
            self.assertEqual(APIClient().get('/api/public/assets/'+aid+'/').status_code,404)
            self.assertTrue(asset.revisionasset_set.exists())
            asset.deletion_requested_at=timezone.now();asset.save()
            bad=c.patch('/api/content/items/'+row['id']+'/',{'lock_version':response.data['lock_version'],'rich_body':body},format='json');self.assertEqual(bad.status_code,400,bad.data)

    def test_flagged_public_image_is_not_served(self):
        from apps.assets.models import AssetFile
        from django.utils import timezone
        c=self.client_for(self.student)
        asset=AssetFile.objects.create(owner=self.student,purpose='image',storage_key='not-present.png',original_filename='image.png',mime_type='image/png',size=1,sha256='0'*64,scan_status='CLEAN',deletion_requested_at=timezone.now())
        response=c.post('/api/content/items/',{'kind':'PAPER','title':'已删除图片','assets':[str(asset.pk)]},format='json');self.assertEqual(response.status_code,400)
        self.assertEqual(c.get('/api/site/assets/'+str(asset.pk)+'/').status_code,404)

class DocumentBoundsTests(SimpleTestCase):
    def test_bounds_and_malformed_table(self):
        from apps.content.rich_content import validate_document
        paragraph={'type':'paragraph'}
        table={'type':'table','content':[{'type':'tableRow','content':[{'type':'tableCell','content':[paragraph]}]}]}
        valid={'version':1,'type':'doc','content':[table]}
        self.assertEqual(validate_document(valid),valid)
        bads=[]
        b=deepcopy(valid);b['content'][0]['content'][0]['content']=None;bads.append(b)
        b=deepcopy(valid);b['content'][0]['content']*=21;bads.append(b)
        b=deepcopy(valid);b['content'][0]['content'][0]['content']*=11;bads.append(b)
        b=deepcopy(valid);b['content'][0]['content'][0]['content'][0]['attrs']={'colspan':2};bads.append(b)
        b=document();b['content']=[{'type':'image','attrs':{'asset_id':str(uuid4())}}]*31;bads.append(b)
        b=document();b['content'][0]['content'][0]['marks']='bold';bads.append(b)
        b=document();b['content'][0]['content'][0]['marks']=[{'type':'link','attrs':{'href':'https://example.org','onclick':'alert(1)'}}];bads.append(b)
        for b in bads:
            with self.subTest(value=str(b)[:100]),self.assertRaises(ValidationError):validate_document(b)

    def test_untrusted_shapes_never_raise_internal_error(self):
        from apps.content.rich_content import validate_document
        for node in ({'type':[]},{'type':{}},{'type':'text','text':'x','marks':[{'type':[]}]},{'type':'table','content':[1]},{'type':'table','content':[{'type':'tableRow','content':None}]},{'type':'image','attrs':None},{'type':'listItem','content':[]}):
            with self.subTest(node=node),self.assertRaises(ValidationError):validate_document({'version':1,'type':'doc','content':[node]})
        with self.assertRaises(ValidationError):validate_document(document('\ud800'))
