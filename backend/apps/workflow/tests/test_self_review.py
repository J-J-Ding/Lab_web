from apps.accounts.tests.helpers import AccountFixtures,login_as,write
from apps.members.models import MemberProfile
from apps.workflow.models import ReviewDecision

class SelfReviewTests(AccountFixtures):
    def content(self,user):
        c=login_as(user)
        r=write(c,'post','/api/content/items/',{'kind':'BLOG','title':'Self review sample','detail':{'body':'Body'}});self.assertEqual(r.status_code,201,r.content)
        item=r.json();r=write(c,'post',f"/api/content/revisions/{item['working_revision']['id']}/submit/",{'lock_version':item['lock_version']});self.assertEqual(r.status_code,200,r.content)
        return c,r.json()
    def test_content_detail_and_tasks_match_self_review_role(self):
        for user in (self.root,self.teacher,self.admin):
            with self.subTest(user=user.username):
                c,item=self.content(user);allowed=user.is_superuser or user.role in ('ADMIN','TEACHER')
                detail=c.get(f"/api/content/items/{item['id']}/").json();self.assertEqual(detail['can_review'],allowed)
                task=next(r for r in c.get('/api/review/tasks/').json()['results'] if r['id']==item['working_revision']['id'])
                self.assertEqual(task['can_review'],allowed)
    def test_own_application_for_all_managers(self):
        for user in (self.root,self.teacher,self.admin):
            with self.subTest(user=user.username):
                c=login_as(user);r=write(c,'post','/api/members/applications/',{'application_kind':'TEACHER','statement':'Own identity request'});self.assertEqual(r.status_code,201,r.content);a=r.json()
                task=next(t for t in c.get('/api/review/member-applications/').json()['results'] if t['id']==a['id']);self.assertTrue(task['can_review'])
                r=write(c,'post',f"/api/review/member-applications/{a['id']}/decision/",{'lock_version':a['lock_version'],'decision':'APPROVE','reason':'Explicit own identity verification'});self.assertEqual(r.status_code,200,r.content)
                self.assertTrue(ReviewDecision.objects.filter(application_id=a['id'],reviewer=user).exists())
    def test_own_public_profile_role_matrix(self):
        for user in (self.root,self.teacher,self.admin,self.customer,self.student):
            with self.subTest(user=user.username):
                c=login_as(user);MemberProfile.objects.create(user=user,membership_status='ACTIVE')
                r=write(c,'post','/api/members/me/draft/',{});self.assertEqual(r.status_code,201,r.content);draft=r.json()
                r=write(c,'patch','/api/members/me/draft/',{'lock_version':draft['lock_version'],'display_name':'Own public profile','slug':'own-'+user.username});self.assertEqual(r.status_code,200,r.content)
                r=write(c,'post','/api/members/me/draft/submit/',{'lock_version':r.json()['lock_version'],'public_visible':True});self.assertEqual(r.status_code,200,r.content);draft=r.json()
                allowed=user.is_superuser or user.role in ('ADMIN','TEACHER')
                if allowed:
                    task=next(t for t in c.get('/api/review/member-revisions/').json()['results'] if t['id']==draft['id']);self.assertTrue(task['can_review'])
                r=write(c,'post',f"/api/review/member-revisions/{draft['id']}/decision/",{'lock_version':draft['lock_version'],'decision':'APPROVE','reason':'Own public consent reviewed'})
                if allowed:
                    self.assertEqual(r.status_code,200,r.content);self.assertTrue(ReviewDecision.objects.filter(member_revision_id=draft['id'],reviewer=user).exists())
                else:self.assertIn(r.status_code,(403,404))
                self.assertEqual(MemberProfile.objects.get(user=user).public_visible,allowed)
    def test_teacher_demoted_to_customer_loses_self_review(self):
        c,item=self.content(self.teacher)
        self.assertTrue(c.get(f"/api/content/items/{item['id']}/").json()['can_review'])
        self.teacher.role='CUSTOMER';self.teacher.save(update_fields=['role'])
        self.assertFalse(c.get(f"/api/content/items/{item['id']}/").json()['can_review'])
        r=write(c,'post',f"/api/review/revisions/{item['working_revision']['id']}/decision/",{'lock_version':item['lock_version'],'decision':'APPROVE','reason':'Old role cannot authorize'})
        self.assertEqual(r.status_code,403,r.content)
