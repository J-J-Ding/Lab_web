from unittest.mock import patch
from django.test import override_settings
from django.utils import timezone
from apps.accounts.tests.helpers import AccountFixtures,login_as,write
from . import test_jobs as flow

@override_settings(**flow.CONFIG)
class MoreFlowTests(AccountFixtures):
    setUp=flow.JobFlowTests.setUp
    asset=flow.JobFlowTests.asset
    create=flow.JobFlowTests.create
    ready=flow.JobFlowTests.ready
    def test_customer_applies_only_own_member_draft_no_role_change(self):
        from apps.ai_assistant.models import AIImportJob,AICandidate
        from apps.ai_assistant.providers.base import ProviderResult
        from apps.ai_assistant.tasks import run_once
        from apps.members.models import MemberProfile
        c=login_as(self.customer);job=self.create(c,'MEMBER');run_once();job=c.get('/api/ai/imports/'+job['id']+'/').json()
        r=write(c,'post',f"/api/ai/imports/{job['id']}/consent/",{'lock_version':job['lock_version'],'consent_version':'deepseek-text-v1','text_digest':job['text_digest'],'selected_text':job['preview']});self.assertEqual(r.status_code,200)
        data={'schema_version':1,'target_type':'MEMBER','records':[{'fields':{'bio':'Example title'},'evidence':[{'field':'bio','page':1,'excerpt':'Example title'}]}]}
        with patch('apps.ai_assistant.providers.deepseek.DeepSeekProvider.extract_fields',return_value=ProviderResult(data,10,30)):run_once()
        job=c.get('/api/ai/imports/'+job['id']+'/').json()
        r=write(c,'post',f"/api/ai/imports/{job['id']}/apply/",{'lock_version':job['lock_version'],'record_index':0,'confirmed_fields':['bio'],'confirm':True});self.assertEqual(r.status_code,200,r.content)
        self.customer.refresh_from_db();self.assertEqual(self.customer.role,'CUSTOMER');p=MemberProfile.objects.get(user=self.customer);self.assertIsNone(p.published_revision_id);self.assertFalse(p.public_visible)
    def test_candidate_privileged_field_and_false_confirmation_denied(self):
        job=self.ready();bad={**job['candidate']};bad['records']=[{'fields':{'is_superuser':True}}]
        r=write(self.c,'patch',f"/api/ai/imports/{job['id']}/candidate/",{'lock_version':job['lock_version'],'candidate':bad});self.assertEqual(r.status_code,400)
        for confirm in (False,'true',1):
            r=write(self.c,'post',f"/api/ai/imports/{job['id']}/apply/",{'lock_version':job['lock_version'],'record_index':0,'confirmed_fields':['title'],'confirm':confirm});self.assertEqual(r.status_code,400)
    def test_edited_candidate_requires_matching_version(self):
        job=self.ready();data=job['candidate'];data['records'][0]['fields']['title']='Human corrected title'
        r=write(self.c,'patch',f"/api/ai/imports/{job['id']}/candidate/",{'lock_version':job['lock_version'],'candidate':data});self.assertEqual(r.status_code,200,r.content)
        self.assertIn('title',r.json()['candidate']['records'][0]['uncertain_fields'])
        r=write(self.c,'patch',f"/api/ai/imports/{job['id']}/candidate/",{'lock_version':job['lock_version'],'candidate':data});self.assertEqual(r.status_code,409)
    def test_summary_separate_quota_and_existing_draft_only(self):
        from apps.ai_assistant.tasks import run_once
        from apps.ai_assistant.providers.base import ProviderResult
        r=write(self.c,'post','/api/ai/summaries/',{'target_type':'BLOG','verified_fields':{'title':'Verified title'},'consent_version':'deepseek-text-v1'});self.assertEqual(r.status_code,202,r.content);job=r.json()
        output={'schema_version':1,'target_type':'BLOG','records':[{'fields':{'summary':'Verified title summary'},'evidence':[{'field':'summary','page':1,'excerpt':'Verified title'}]}]}
        with patch('apps.ai_assistant.providers.deepseek.DeepSeekProvider.extract_fields',return_value=ProviderResult(output,10,30)):run_once()
        job=self.c.get('/api/ai/imports/'+job['id']+'/').json();self.assertEqual(job['state'],'READY',job)
        r=write(self.c,'post',f"/api/ai/imports/{job['id']}/apply/",{'lock_version':job['lock_version'],'record_index':0,'confirmed_fields':['summary'],'confirm':True});self.assertEqual(r.status_code,400)
    def test_expiry_cleanup_preserves_applied_business_revision(self):
        from apps.ai_assistant.models import AIImportJob,AICandidate
        from apps.ai_assistant.retention import cleanup
        from apps.content.models import ContentItem
        job=self.ready();r=write(self.c,'post',f"/api/ai/imports/{job['id']}/apply/",{'lock_version':job['lock_version'],'record_index':0,'confirmed_fields':['title','detail.body'],'confirm':True});self.assertEqual(r.status_code,200)
        AIImportJob.objects.filter(pk=job['id']).update(expires_at=timezone.now()-timezone.timedelta(seconds=1))
        cleanup();self.assertTrue(AICandidate.objects.get(job_id=job['id']).data)
        cleanup(apply=True);self.assertEqual(AICandidate.objects.get(job_id=job['id']).data,{});self.assertEqual(ContentItem.objects.count(),1)
    def test_expired_source_expires_waiting_consent_and_releases_reservation(self):
        from apps.ai_assistant.tasks import run_once
        from apps.ai_assistant.retention import cleanup
        from apps.ai_assistant.models import AIImportJob,AIUsageLedger
        from apps.assets.models import AssetFile
        job=self.create();run_once();AssetFile.objects.filter(pk=AIImportJob.objects.get(pk=job['id']).asset_id).update(expires_at=timezone.now()-timezone.timedelta(seconds=1))
        cleanup(apply=True)
        self.assertEqual(AIImportJob.objects.get(pk=job['id']).state,'EXPIRED');self.assertEqual(AIUsageLedger.objects.get(job_id=job['id']).state,'RELEASED')
    def test_public_duplicate_hint_does_not_leak_pending_title(self):
        from django.db import transaction
        from apps.content.services import create_content
        from apps.content.models import ContentItem,ContentRevision
        from apps.members.models import MemberProfile
        from apps.ai_assistant.models import AIImportJob,AICandidate
        from apps.ai_assistant.quota import reserve
        item=create_content(self.teacher,'PAPER','Published safe paper',{'doi':'10.7777/example'})
        with transaction.atomic():
            ContentRevision.objects.filter(pk=item.working_revision_id).update(state='PUBLISHED');ContentItem.objects.filter(pk=item.pk).update(published_revision=item.working_revision,working_revision=None)
        item.refresh_from_db();r=write(self.c,'post',f'/api/content/items/{item.pk}/revisions/',{'lock_version':item.lock_version});self.assertEqual(r.status_code,201);pending=r.json()
        r=write(self.c,'patch',f"/api/content/revisions/{pending['working_revision']['id']}/",{'lock_version':pending['lock_version'],'title':'PRIVATE PENDING TITLE'});self.assertEqual(r.status_code,200)
        MemberProfile.objects.create(user=self.student,membership_status='ACTIVE');c=login_as(self.student)
        with transaction.atomic():
            job=AIImportJob.objects.create(owner=self.student,target_type='PAPER',state='READY',expires_at=timezone.now()+timezone.timedelta(days=30));reserve(self.student,job)
            AICandidate.objects.create(job=job,expires_at=job.expires_at,data={'records':[{'fields':{'detail':{'doi':'10.7777/example'}}}]})
        r=c.get(f'/api/ai/imports/{job.pk}/matches/');self.assertEqual(r.status_code,200,r.content)
        self.assertEqual(r.json()['records'][0]['duplicates'][0]['title'],'Published safe paper');self.assertNotIn('PRIVATE PENDING TITLE',str(r.json()))
