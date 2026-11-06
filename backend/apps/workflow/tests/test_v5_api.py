"""V5 behavior contracts: written before workflow endpoints exist."""
from django.test import TestCase
from apps.accounts.models import User
from apps.accounts.tests.helpers import AccountFixtures,login_as,write
from apps.members.models import MemberProfile


class WorkflowAPIContracts(AccountFixtures):
    def test_customer_can_apply_but_cannot_create_content(self):
        client=login_as(self.customer)
        response=write(client,'post','/api/members/applications/',{'application_kind':'STUDENT','statement':'实验室成员申请'})
        self.assertEqual(response.status_code,201)
        self.assertEqual(response.json()['state'],'SUBMITTED')
        self.assertEqual(write(client,'post','/api/content/items/',{'kind':'PAPER','title':'Unauthorized','detail':{}}).status_code,403)

    def test_teacher_identity_does_not_automatically_grant_management(self):
        c=login_as(self.customer)
        response=write(c,'post','/api/members/applications/',{'application_kind':'TEACHER','statement':'教师身份申请'})
        self.assertEqual(response.status_code,201)
        manager=login_as(self.teacher)
        response=write(manager,'post',f"/api/review/member-applications/{response.json()['id']}/decision/",{'decision':'APPROVE','reason':'已核实','lock_version':0})
        self.assertEqual(response.status_code,200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.role,'STUDENT')
        self.assertEqual(MemberProfile.objects.get(user=self.customer).membership_status,'ACTIVE')

    def test_self_review_role_matrix_and_audit(self):
        for user in (self.teacher,self.admin,self.root):
            c=login_as(user)
            response=write(c,'post','/api/content/items/',{'kind':'BLOG','title':'Original','detail':{'body':'Body'}})
            self.assertEqual(response.status_code,201)
            item=response.json()
            submitted=write(c,'post',f"/api/content/revisions/{item['working_revision']['id']}/submit/",{'lock_version':item['lock_version']})
            self.assertEqual(submitted.status_code,200)
            decision=write(c,'post',f"/api/review/revisions/{item['working_revision']['id']}/decision/",{'decision':'APPROVE','reason':'Self','lock_version':submitted.json()['lock_version']})
            expected=200 if user.is_superuser or user.role in ('ADMIN','TEACHER') else 403
            self.assertEqual(decision.status_code,expected,decision.content)
            from apps.workflow.models import ReviewDecision
            self.assertEqual(ReviewDecision.objects.filter(content_revision_id=item['working_revision']['id'],reviewer=user,decision='APPROVE').exists(),expected==200)

    def test_manager_task_list_and_user_data_remain_separate(self):
        self.assertEqual(self.client.get('/api/review/tasks/').status_code,403)
        c=login_as(self.student)
        self.assertEqual(c.get('/api/review/tasks/').status_code,403)
        c=login_as(self.teacher)
        self.assertEqual(c.get('/api/review/tasks/').status_code,200)
        self.assertEqual(c.get('/api/admin/users/').status_code,200)

    def test_missing_csrf_is_rejected_for_application(self):
        c=login_as(self.customer)
        self.assertEqual(c.post('/api/members/applications/',{'application_kind':'STUDENT'},format='json').status_code,403)
