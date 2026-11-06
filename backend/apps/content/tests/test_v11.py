from rest_framework.test import APIClient
from django.test import TestCase
from apps.content.tests.test_v10 import DirectCollaborationTests
from apps.assets.models import AssetFile

class PresentationContracts(TestCase):
    setUpTestData=classmethod(DirectCollaborationTests.setUpTestData.__func__)
    client_for=DirectCollaborationTests.client_for
    profile=DirectCollaborationTests.profile
    create=DirectCollaborationTests.create

    def image(self,user,purpose='image'):
        import secrets
        return AssetFile.objects.create(owner=user,purpose=purpose,storage_key=secrets.token_hex(16)+'.png',original_filename='封面.png',mime_type='image/png',size=100,sha256='0'*64,scan_status='CLEAN')

    def test_cover_roundtrip_and_public_projection(self):
        c=self.client_for(self.student);a=self.image(self.student)
        item=self.create(c,assets=[str(a.pk)],cover_asset=str(a.pk),detail={'venue':'示例期刊','publication_date':'2026-01-01'})
        self.assertEqual(item['cover_asset'],str(a.pk))
        public=APIClient().get('/api/public/content/'+item['id']+'/');self.assertEqual(public.data['cover']['id'],str(a.pk))
        changed=c.patch('/api/content/items/'+item['id']+'/',{'lock_version':item['lock_version'],'summary':'摘要更新'},format='json');self.assertEqual(changed.status_code,200,changed.data);self.assertEqual(changed.data['cover_asset'],str(a.pk))
        cleared=c.patch('/api/content/items/'+item['id']+'/',{'lock_version':changed.data['lock_version'],'cover_asset':None},format='json');self.assertEqual(cleared.status_code,200,cleared.data)
        self.assertIsNone(APIClient().get('/api/public/content/'+item['id']+'/').data['cover'])

    def test_cover_foreign_private_and_team_gate(self):
        c=self.client_for(self.student);other=self.image(self.customer)
        r=c.post('/api/content/items/',{'kind':'PAPER','title':'不能借用私有图','assets':[str(other.pk)],'cover_asset':str(other.pk)},format='json');self.assertEqual(r.status_code,400,r.data)
        own=self.image(self.student);item=self.create(c,assets=[str(own.pk)],cover_asset=str(own.pk),visibility_scope='TEAM')
        self.assertEqual(APIClient().get('/api/public/assets/'+str(own.pk)+'/').status_code,404)
        self.assertEqual(APIClient().get('/api/public/content/'+item['id']+'/').status_code,404)

    def test_single_character_name_and_category_filters(self):
        self.profile(self.student,'丁同学',True)
        r=APIClient().get('/api/public/members/',{'q':'丁'});self.assertEqual(r.status_code,200,r.data);self.assertEqual(r.data['count'],1)
        c=self.client_for(self.student);self.create(c,title='单字检索论文')
        r=APIClient().get('/api/public/content/',{'q':'单'});self.assertEqual(r.status_code,200,r.data);self.assertEqual(r.data['count'],1)
        self.assertEqual(APIClient().get('/api/public/content/',{'q':'x'*101}).status_code,400)

    def test_home_slides_only_use_public_images(self):
        c=self.client_for(self.student);a=self.image(self.student)
        self.create(c,kind='NEWS',assets=[str(a.pk)],cover_asset=str(a.pk),title='公开团队活动')
        private=self.image(self.student);self.create(c,kind='NEWS',assets=[str(private.pk)],cover_asset=str(private.pk),visibility_scope='TEAM',title='内部活动')
        r=APIClient().get('/api/public/home/');self.assertEqual(r.status_code,200,r.data)
        self.assertEqual(len(r.data['slides']),1);self.assertEqual(r.data['slides'][0]['image']['id'],str(a.pk))

    def test_graduate_category_does_not_require_public_destination(self):
        profile=self.profile(self.student,'丁毕业',True);c=self.client_for(self.student)
        r=c.patch('/api/members/me/profile/',{'lock_version':profile['lock_version'],'public_member_status':'ALUMNI'},format='json');self.assertEqual(r.status_code,200,r.data)
        public=APIClient().get('/api/public/graduates/',{'q':'丁'});self.assertEqual(public.status_code,200,public.data);self.assertEqual(public.data['count'],1);self.assertNotIn('alumni',public.data['results'][0])
