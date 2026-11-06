from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from apps.accounts.authentication import SESSION_VERSION_KEY
from apps.members.models import MemberProfile, Resume
from apps.content.models import ContentItem

User=get_user_model()

class DirectCollaborationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.root=User.objects.create_user(username='root-test',is_superuser=True)
        cls.teacher=User.objects.create_user(username='teacher-test',role='TEACHER')
        cls.student=User.objects.create_user(username='student-test',role='STUDENT')
        cls.other=User.objects.create_user(username='other-test',role='STUDENT')
        cls.customer=User.objects.create_user(username='customer-test')

    def client_for(self,user):
        c=APIClient();c.force_login(user);session=c.session;session[SESSION_VERSION_KEY]=user.session_version;session.save();return c

    def profile(self,user,name,public=False):
        c=self.client_for(user);r=c.get('/api/members/me/profile/');self.assertEqual(r.status_code,200,r.data)
        r=c.patch('/api/members/me/profile/',{'lock_version':r.data['lock_version'],'display_name':name,'public_visible':public},format='json');self.assertEqual(r.status_code,200,r.data);return r.data

    def create(self,c,**extra):
        r=c.post('/api/content/items/',{'kind':'PAPER','title':'科研成果',**extra},format='json');self.assertEqual(r.status_code,201,r.data);return r.data

    def test_customer_private_profile_and_resume(self):
        c=self.client_for(self.customer);p=self.profile(self.customer,'求职者')
        self.assertFalse(p['public_visible'])
        r=c.post('/api/members/me/resumes/',{'title':'个人简历'},format='json');self.assertEqual(r.status_code,201,r.data)
        self.assertEqual(self.client_for(self.other).get('/api/members/me/resumes/'+r.data['id']+'/').status_code,404)
        self.assertEqual(c.get('/api/members/directory/').status_code,403)
        self.assertEqual(c.post('/api/content/items/',{'kind':'NEWS','title':'越权'},format='json').status_code,403)
        self.assertEqual(c.patch('/api/members/me/profile/',{'lock_version':p['lock_version'],'public_visible':True},format='json').status_code,403)

    def test_teacher_business_edit_not_security(self):
        p=self.profile(self.student,'学生姓名');c=self.client_for(self.teacher)
        r=c.patch('/api/members/'+p['id']+'/profile/',{'lock_version':p['lock_version'],'bio':'研究方向'},format='json');self.assertEqual(r.status_code,200,r.data)
        customer=self.profile(self.customer,'私有姓名')
        self.assertEqual(c.get('/api/members/'+customer['id']+'/profile/').status_code,404)
        for method,path,body in [('get','/api/admin/users/',None),('patch',f'/api/admin/users/{self.student.pk}/',{'role':'TEACHER'}),('post',f'/api/admin/users/{self.student.pk}/reset-password/',{'new_password':'Unsafe999!Long'})]:
            r=getattr(c,method)(path,body,format='json');self.assertEqual(r.status_code,403,r.data)
        self.assertEqual(c.patch('/api/members/'+p['id']+'/profile/',{'lock_version':r.data.get('lock_version',1),'role':'TEACHER'},format='json').status_code,400)

    def test_direct_save_single_source_and_home(self):
        self.profile(self.student,'张同学',True);self.profile(self.teacher,'李老师',True)
        c=self.client_for(self.student);item=self.create(c,authors=[self.teacher.pk,self.student.pk])
        self.assertEqual(ContentItem.objects.count(),1)
        self.assertEqual(item['revision']['state'],'PUBLISHED')
        public=APIClient().get('/api/public/content/'+item['id']+'/');self.assertEqual(public.status_code,200,public.data)
        self.assertEqual({p['name'] for p in public.data['contributions']},{'张同学','李老师'})
        self.assertEqual(APIClient().get('/api/public/home/').data['stats']['papers'],1)
        for user in (self.student,self.teacher):
            p=MemberProfile.objects.get(user=user)
            self.assertEqual(APIClient().get('/api/public/members/'+p.published_revision.slug+'/achievements/').data['count'],1)
        r=c.patch('/api/content/items/'+item['id']+'/',{'lock_version':item['lock_version'],'title':'修改生效'},format='json');self.assertEqual(r.status_code,200,r.data)
        self.assertEqual(APIClient().get('/api/public/content/'+item['id']+'/').data['title'],'修改生效')
        self.assertEqual(ContentItem.objects.get(pk=item['id']).revisions.count(),2)

    def test_author_is_not_editor_and_author_validation(self):
        self.profile(self.student,'同学甲');self.profile(self.other,'同学乙')
        c=self.client_for(self.student);item=self.create(c,authors=[self.other.pk])
        other=self.client_for(self.other)
        r=other.patch('/api/content/items/'+item['id']+'/',{'lock_version':item['lock_version'],'title':'不应保存'},format='json');self.assertEqual(r.status_code,403,r.data)
        for authors in ([self.customer.pk],[self.student.pk,self.student.pk],[999999]):
            r=c.post('/api/content/items/',{'kind':'PAPER','title':'非法关联','authors':authors},format='json');self.assertEqual(r.status_code,400,r.data)
        self.assertEqual(ContentItem.objects.count(),1)

    def test_team_visibility_and_conflict(self):
        c=self.client_for(self.student);item=self.create(c,visibility_scope='TEAM')
        self.assertEqual(APIClient().get('/api/public/content/'+item['id']+'/').status_code,404)
        self.assertEqual(APIClient().get('/api/public/home/').data['stats']['papers'],0)
        self.assertEqual(self.client_for(self.other).get('/api/content/items/'+item['id']+'/').status_code,200)
        r=c.patch('/api/content/items/'+item['id']+'/',{'lock_version':0,'title':'冲突'},format='json');self.assertEqual(r.status_code,409)

    def test_root_role_grant_and_session_invalidation(self):
        c=self.client_for(self.customer);root=self.client_for(self.root)
        r=root.patch(f'/api/admin/users/{self.customer.pk}/',{'role':'STUDENT'},format='json');self.assertEqual(r.status_code,200,r.data)
        self.assertTrue(MemberProfile.objects.filter(user=self.customer).exists())
        self.assertIn(c.get('/api/auth/me/').status_code,(401,403))

    def test_retired_approval_and_restore(self):
        c=self.client_for(self.student);item=self.create(c)
        original=item['revision']['id']
        r=c.patch('/api/content/items/'+item['id']+'/',{'lock_version':item['lock_version'],'title':'新标题'},format='json');self.assertEqual(r.status_code,200,r.data)
        r=c.post('/api/content/items/'+item['id']+'/restore/',{'lock_version':r.data['lock_version'],'source_revision':original},format='json');self.assertEqual(r.status_code,200,r.data)
        self.assertEqual(r.data['revision']['title'],'科研成果');self.assertNotEqual(r.data['revision']['id'],original)
        self.assertEqual(c.post('/api/content/revisions/'+original+'/submit/',{},format='json').status_code,410)
        self.assertEqual(c.get('/api/review/tasks/').status_code,410)

    def test_contact_and_fixed_home(self):
        c=self.client_for(self.teacher)
        r=c.post('/api/content/items/',{'kind':'LAB_PAGE','title':'联系我们','detail':{'page_key':'contact','body':'联系信息'}},format='json');self.assertEqual(r.status_code,201,r.data)
        self.assertEqual(APIClient().get('/api/public/pages/contact/').status_code,200)
        self.assertEqual(c.post('/api/content/items/',{'kind':'LAB_PAGE','title':'首页','detail':{'page_key':'home'}},format='json').status_code,400)

    def test_missing_name_not_username_and_private_author(self):
        self.profile(self.student,'真实姓名')
        c=self.client_for(self.student);item=self.create(c,authors=[self.student.pk])
        public=APIClient().get('/api/public/content/'+item['id']+'/').data
        self.assertEqual(public['contributions'][0]['name'],'团队成员')
        self.assertNotIn(self.student.username,str(public))
        directory=c.get('/api/members/directory/').data['results'];self.assertEqual(directory[0]['display_name'],'真实姓名')

    def test_new_ascii_registration_and_legacy_login_name(self):
        c=APIClient();r=c.post('/api/auth/register/',{'username':'中文登录','password':'Secure-long-Password19!'},format='json');self.assertEqual(r.status_code,400)
        legacy=User.objects.create_user(username='旧中文',password='Secure-long-Password19!')
        self.assertEqual(c.post('/api/auth/login/',{'username':legacy.username,'password':'Secure-long-Password19!'},format='json').status_code,200)

    def test_restore_never_revives_revoked_field_privacy(self):
        c=self.client_for(self.student);initial=c.get('/api/members/me/profile/').data
        fields={'lock_version':initial['lock_version'],'display_name':'隐私同学','public_visible':True,'contact_visible':True,'education_visible':True,'alumni_visible':True,'public_contact_enabled':True,'public_contact_email':'public@example.com','education':[{'school':'原学校','is_public':True,'position':1}],'alumni':{'graduation_year':2025,'destination_type':'WORK','organization':'原单位','is_public':True}}
        first=c.patch('/api/members/me/profile/',fields,format='json');self.assertEqual(first.status_code,200,first.data)
        second=c.patch('/api/members/me/profile/',{'lock_version':first.data['lock_version'],'public_contact_enabled':False,'education':[{'school':'原学校','is_public':False,'position':1}],'alumni':{'graduation_year':2025,'destination_type':'WORK','organization':'原单位','is_public':False}},format='json');self.assertEqual(second.status_code,200,second.data)
        r=self.client_for(self.teacher).post('/api/members/'+first.data['id']+'/restore/',{'lock_version':second.data['lock_version'],'source_revision':str(MemberProfile.objects.get(user=self.student).revisions.get(number=1).pk)},format='json')
        self.assertEqual(r.status_code,200,r.data);self.assertFalse(r.data['public_contact_enabled']);self.assertFalse(r.data['education'][0]['is_public']);self.assertFalse(r.data['alumni']['is_public'])

    def test_restore_rejects_disabled_author_and_preserves_history(self):
        self.profile(self.student,'作者');c=self.client_for(self.student);item=self.create(c,authors=[self.student.pk]);revision=item['revision']['id']
        User.objects.filter(pk=self.student.pk).update(role='CUSTOMER')
        r=self.client_for(self.teacher).post('/api/content/items/'+item['id']+'/restore/',{'lock_version':item['lock_version'],'source_revision':revision},format='json');self.assertEqual(r.status_code,409,r.data)
        self.assertEqual(ContentItem.objects.get(pk=item['id']).revisions.count(),1)

    def test_teacher_cannot_download_customer_legacy_review_avatar(self):
        from apps.assets.models import AssetFile
        from apps.members.models import MemberRevision
        a=AssetFile.objects.create(owner=self.customer,purpose='avatar',storage_key='v10-private.png',original_filename='private.png',mime_type='image/png',size=1,sha256='0'*64,scan_status='CLEAN')
        p=MemberProfile.objects.create(user=self.customer);r=MemberRevision.objects.create(profile=p,number=1,state='SUBMITTED',avatar_asset=a);p.draft_revision=r;p.save()
        self.assertEqual(self.client_for(self.teacher).get('/api/assets/'+str(a.pk)+'/download/').status_code,404)
