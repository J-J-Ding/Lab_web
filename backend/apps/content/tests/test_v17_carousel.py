from django.test import TestCase,override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from tempfile import TemporaryDirectory
from io import BytesIO
from PIL import Image
from apps.content.tests import test_v10 as fixtures


class CarouselTests(TestCase):
    setUpTestData=classmethod(fixtures.DirectCollaborationTests.setUpTestData.__func__)
    client_for=fixtures.DirectCollaborationTests.client_for

    def test_root_carousel_permissions_modes_and_lifecycle(self):
        for user in (self.student,self.teacher,self.customer):self.assertEqual(self.client_for(user).get('/api/admin/carousel/').status_code,403)
        c=self.client_for(self.root)
        with TemporaryDirectory() as media,override_settings(PRIVATE_MEDIA_ROOT=media):
            out=BytesIO();Image.new('RGB',(80,40),'blue').save(out,format='PNG')
            asset=c.post('/api/assets/',{'purpose':'image','file':SimpleUploadedFile('slide.png',out.getvalue(),content_type='image/png')},format='multipart');self.assertEqual(asset.status_code,201,asset.data)
            response=c.post('/api/admin/carousel/',{'lock_version':0,'asset':asset.data['id'],'title':'实验室轮播','subtitle':'副标题','position':2},format='json');self.assertEqual(response.status_code,200,response.data);slide=response.data['slide'];version=response.data['lock_version']
            self.assertEqual(APIClient().get('/api/public/assets/'+asset.data['id']+'/').status_code,404)
            response=c.post('/api/admin/carousel/',{'lock_version':version,'mode':'MANUAL'},format='json');self.assertEqual(response.status_code,200,response.data);version=response.data['lock_version']
            self.assertEqual(APIClient().get('/api/public/home/').data['slides'][0]['title'],'实验室轮播')
            image=APIClient().get('/api/public/assets/'+asset.data['id']+'/');self.assertEqual(image.status_code,200);b''.join(image.streaming_content)
            self.assertEqual(c.post('/api/admin/carousel/'+slide['id']+'/',{'lock_version':0,'enabled':False},format='json').status_code,409)
            response=c.post('/api/admin/carousel/'+slide['id']+'/',{'lock_version':version,'enabled':False},format='json');self.assertEqual(response.status_code,200);version=response.data['lock_version']
            self.assertEqual(APIClient().get('/api/public/home/').data['slides'],[]);self.assertEqual(APIClient().get('/api/public/assets/'+asset.data['id']+'/').status_code,404)
            response=c.post('/api/admin/carousel/'+slide['id']+'/',{'lock_version':version,'delete':True},format='json');self.assertEqual(response.status_code,200);self.assertEqual(c.get('/api/admin/carousel/').data['count'],0)

    @override_settings(INITIAL_ACCOUNT_PASSWORD='Synthetic98765')
    def test_account_default_filter_password_and_duplicate(self):
        c=self.client_for(self.root)
        response=c.post('/api/admin/users/',{'username':'v17_unique','role':'STUDENT'},format='json');self.assertEqual(response.status_code,201,response.data);uid=response.data['id']
        from apps.accounts.models import User
        self.assertTrue(User.objects.get(pk=uid).check_password('Synthetic98765'))
        self.assertEqual(c.get('/api/admin/usernames/available/?username=v17_unique').status_code,400)
        self.assertEqual(c.post('/api/admin/users/',{'username':'v17_unique'},format='json').status_code,400)
        u=User.objects.get(pk=uid);u.is_active=False;u.save()
        self.assertFalse(any(x['id']==uid for x in c.get('/api/admin/users/').data['results']))
        self.assertTrue(any(x['id']==uid for x in c.get('/api/admin/users/?state=cancelled').data['results']))
        self.assertEqual(c.post('/api/admin/users/',{'username':'v17_unique'},format='json').status_code,400)
        self.assertEqual(c.get('/api/admin/users/?state=bad').status_code,400)

    def test_five_item_pages_and_unowned_asset_rejected(self):
        from apps.assets.models import AssetFile
        from apps.content.models import CarouselSlide,CarouselSettings
        asset=AssetFile.objects.create(owner=self.student,purpose='image',storage_key='synthetic.png',original_filename='synthetic.png',mime_type='image/png',size=1,sha256='0'*64,scan_status='CLEAN')
        c=self.client_for(self.root)
        response=c.post('/api/admin/carousel/',{'lock_version':0,'asset':str(asset.pk)},format='json');self.assertEqual(response.status_code,400,response.data)
        for i in range(7):CarouselSlide.objects.create(asset=asset,title=str(i),position=i+1)
        response=c.get('/api/admin/carousel/');self.assertEqual(len(response.data['results']),5);self.assertEqual(response.data['count'],7)
        self.assertEqual(len(c.get('/api/admin/carousel/?page=2').data['results']),2)
        self.assertEqual(c.get('/api/admin/carousel/?page_size=100').status_code,400)
        self.assertEqual(APIClient().get('/api/admin/carousel/').status_code,403)

    def test_username_database_constraint_and_root_csrf(self):
        from django.db import IntegrityError,transaction
        from apps.accounts.models import User
        User.objects.create_user(username='v17_db_unique',password='Test123456')
        with self.assertRaises(IntegrityError),transaction.atomic():User.objects.create_user(username='v17_db_unique',password='Test123456')
        c=APIClient(enforce_csrf_checks=True);c.force_login(self.root)
        response=c.post('/api/admin/carousel/',{'lock_version':0,'mode':'MANUAL'},format='json');self.assertEqual(response.status_code,403)
