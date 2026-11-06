from concurrent.futures import ThreadPoolExecutor
import time
from django.contrib.auth.hashers import make_password
from django.db import connection,close_old_connections,transaction
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.accounts.tests.helpers import PASSWORD,login_as,write
from apps.content.models import ContentItem
from apps.workflow.models import ReviewDecision


class WorkflowConcurrencyTests(TransactionTestCase):
    def setUp(self):
        hashed=make_password(PASSWORD)
        self.author_user=User.objects.create(username='author',role='TEACHER',password=hashed)
        self.root=User.objects.create(username='root',is_superuser=True,password=hashed)
        self.manager=User.objects.create(username='manager',role='ADMIN',password=hashed)
        self.author=login_as(self.author_user);self.c1=login_as(self.root);self.c2=login_as(self.manager)
        response=write(self.author,'post','/api/content/items/',{'kind':'BLOG','title':'Concurrent paper','detail':{'body':'Body'}})
        self.assertEqual(response.status_code,201,response.content);self.item=response.json()
        response=write(self.author,'post',f"/api/content/revisions/{self.item['working_revision']['id']}/submit/",{'lock_version':self.item['lock_version']})
        self.assertEqual(response.status_code,200,response.content);self.item=response.json()
    def decide(self,cookies):
        close_old_connections()
        try:
            client=APIClient(enforce_csrf_checks=True);client.cookies=cookies.copy()
            response=write(client,'post',f"/api/review/revisions/{self.item['working_revision']['id']}/decision/",{'lock_version':self.item['lock_version'],'decision':'APPROVE','reason':'Independent review'})
            return response.status_code
        finally:close_old_connections()
    def test_two_reviewers_only_one_publication_and_decision(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(self.decide,[self.c1.cookies,self.c2.cookies]))
        self.assertCountEqual(outcomes,[200,409])
        self.assertEqual(ReviewDecision.objects.count(),1)
        self.assertEqual(str(ContentItem.objects.get(pk=self.item['id']).published_revision_id),self.item['working_revision']['id'])
    def test_reviewer_demotion_while_request_waits_prevents_approval(self):
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                user=User.objects.select_for_update().get(pk=self.manager.pk)
                future=pool.submit(self.decide,self.c2.cookies)
                deadline=time.monotonic()+10
                while True:
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT pg_stat_clear_snapshot()')
                        cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND wait_event_type='Lock' AND query LIKE '%%accounts_user%%'")
                        waiting=cursor.fetchone()[0]
                    if waiting:break
                    if time.monotonic()>=deadline:self.fail('Review did not reach expected actor lock')
                    time.sleep(.02)
                user.role='STUDENT';user.save(update_fields=['role'])
            self.assertEqual(future.result(timeout=15),403)
        self.assertEqual(ReviewDecision.objects.count(),0)
        self.assertIsNone(ContentItem.objects.get(pk=self.item['id']).published_revision_id)

    def test_member_draft_password_reset_while_waiting_invalidates_old_write(self):
        response=write(self.author,'post','/api/members/me/draft/',{})
        self.assertEqual(response.status_code,201)
        version=response.json()['lock_version']
        cookies=self.author.cookies.copy()
        def patch_profile():
            close_old_connections()
            try:
                client=APIClient(enforce_csrf_checks=True);client.cookies=cookies.copy()
                return write(client,'patch','/api/members/me/draft/',{'lock_version':version,'bio':'Must not persist after reset'}).status_code
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                user=User.objects.select_for_update().get(pk=self.author_user.pk)
                future=pool.submit(patch_profile)
                deadline=time.monotonic()+10
                while True:
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT pg_stat_clear_snapshot()')
                        cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND wait_event_type='Lock' AND query LIKE '%%accounts_user%%'")
                        waiting=cursor.fetchone()[0]
                    if waiting:break
                    if time.monotonic()>=deadline:self.fail('Profile write did not reach the user lock')
                    time.sleep(.02)
                user.set_password('Reset-only-in-isolated-test!8MpQ');user.save(update_fields=['password'])
            self.assertEqual(future.result(timeout=15),403)
        from apps.members.models import MemberProfile
        self.assertEqual(MemberProfile.objects.get(user=self.author_user).draft_revision.bio,'')
