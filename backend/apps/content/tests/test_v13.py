from django.test import TestCase
from apps.content.tests import test_v10 as fixtures

class OwnProfileTests(TestCase):
    setUpTestData=classmethod(fixtures.DirectCollaborationTests.setUpTestData.__func__)
    client_for=fixtures.DirectCollaborationTests.client_for

    def test_all_roles_can_save_complete_own_profile_and_keep_strict_fields(self):
        for user in (self.customer,self.student,self.teacher,self.root):
            with self.subTest(role=user.role,root=user.is_superuser):
                c=self.client_for(user);url='/api/members/me/profile/'
                initial=c.get(url).data
                payload={'lock_version':initial['lock_version'],'display_name':'本人验收姓名','public_member_status':'ALUMNI','bio':'本人简介','phone':'12345678','internal_contact':'test@example.invalid','education':[{'school':'验收学校','major':'控制','degree':'硕士','start_date':None,'end_date':None,'position':1,'is_public':False}],'research_areas':['控制'],'cv_private':{'skills':'Python','internships':[],'practice':[]},'alumni':{'graduation_year':2025,'destination_type':'WORK','organization':'验收单位','is_public':False}}
                r=c.patch(url,payload,format='json');self.assertEqual(r.status_code,200,r.data)
                reread=c.get(url).data;self.assertEqual(reread['display_name'],payload['display_name']);self.assertEqual(reread['cv_private']['skills'],'Python');self.assertEqual(reread['education'][0]['school'],'验收学校')
                self.assertEqual(c.patch(url,payload,format='json').status_code,409)
                self.assertEqual(c.patch(url,{'lock_version':reread['lock_version'],'role':'TEACHER'},format='json').status_code,400)
