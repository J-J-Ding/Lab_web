from unittest.mock import patch
from django.test import override_settings
from django.utils import timezone
from apps.accounts.tests.helpers import write
from . import test_jobs as flow
from apps.accounts.tests.helpers import AccountFixtures
CONFIG=flow.CONFIG

@override_settings(**CONFIG)
class WorkerFailureTests(AccountFixtures):
    setUp=flow.JobFlowTests.setUp
    asset=flow.JobFlowTests.asset
    create=flow.JobFlowTests.create
    # Reuse fixture helpers, not inherited behavior tests (defined below).
    def queued_call(self):
        from apps.ai_assistant.tasks import run_once
        job=self.create();run_once();job=self.c.get('/api/ai/imports/'+job['id']+'/').json()
        r=write(self.c,'post',f"/api/ai/imports/{job['id']}/consent/",{'lock_version':job['lock_version'],'consent_version':'deepseek-text-v1','text_digest':job['text_digest'],'selected_text':job['preview']});self.assertEqual(r.status_code,200,r.content);return r.json()
    def test_unknown_usage_cancel_delete_and_cleanup_do_not_refund(self):
        from apps.ai_assistant.tasks import run_once
        from apps.ai_assistant.providers.base import ProviderError
        from apps.ai_assistant.retention import cleanup
        from apps.ai_assistant.models import AIUsageLedger
        job=self.queued_call();client=self.c;case=self
        class Interrupted:
            def extract_fields(self,*args):
                response=client.delete(f"/api/ai/imports/{job['id']}/",HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
                case.assertEqual(response.status_code,204);cleanup(apply=True)
                raise ProviderError('provider_network_unknown',unknown=True)
        run_once(Interrupted())
        self.assertEqual(AIUsageLedger.objects.get(job_id=job['id']).state,'UNKNOWN')
    def test_calling_lease_expiry_never_resends(self):
        from apps.ai_assistant.tasks import claim_job,recover_leases,run_once
        from apps.ai_assistant.models import AIImportJob,AIUsageLedger
        job=self.queued_call();ref=claim_job();self.assertEqual(str(ref.pk),job['id'])
        AIImportJob.objects.filter(pk=ref.pk).update(lease_expires_at=timezone.now()-timezone.timedelta(seconds=1));recover_leases()
        self.assertEqual(AIUsageLedger.objects.get(job_id=ref.pk).state,'UNKNOWN')
        with patch('apps.ai_assistant.providers.deepseek.DeepSeekProvider.extract_fields') as provider:
            run_once();provider.assert_not_called()
    def test_extraction_lease_recovers_before_send(self):
        from apps.ai_assistant.tasks import claim_job,recover_leases
        from apps.ai_assistant.models import AIImportJob
        job=self.create();ref=claim_job();self.assertEqual(ref.state,'EXTRACTING')
        AIImportJob.objects.filter(pk=ref.pk).update(lease_expires_at=timezone.now()-timezone.timedelta(seconds=1));recover_leases()
        self.assertEqual(AIImportJob.objects.get(pk=ref.pk).state,'QUEUED')
    def test_provider_bad_schema_settles_known_usage_but_no_candidate(self):
        from apps.ai_assistant.tasks import run_once
        from apps.ai_assistant.providers.base import ProviderResult
        job=self.queued_call()
        class Bad:
            def extract_fields(self,*args):return ProviderResult({'role':'ADMIN'},10,20,'bad-result')
        run_once(Bad());r=self.c.get('/api/ai/imports/'+job['id']+'/').json()
        self.assertEqual(r['state'],'FAILED');self.assertEqual(r['usage']['state'],'SETTLED');self.assertIsNone(r['candidate'])
    def test_expired_source_is_not_sent_even_after_consent(self):
        from apps.ai_assistant.tasks import run_once
        from apps.ai_assistant.models import AIImportJob
        from apps.assets.models import AssetFile
        job=self.queued_call();AssetFile.objects.filter(pk=AIImportJob.objects.get(pk=job['id']).asset_id).update(expires_at=timezone.now()-timezone.timedelta(seconds=1))
        with patch('apps.ai_assistant.providers.deepseek.DeepSeekProvider.extract_fields') as provider:
            run_once();provider.assert_not_called()
