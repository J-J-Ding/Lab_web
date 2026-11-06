from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.test import TransactionTestCase,override_settings
from django.db import transaction,connections
from django.utils import timezone
from decimal import Decimal
from apps.accounts.models import User
from apps.ai_assistant.models import AIImportJob,AIUsageLedger,AIQuotaBucket
from .test_jobs import CONFIG

@override_settings(**{**CONFIG,'AI_GLOBAL_DAILY_BUDGET_CNY':'0.09'})
class ConcurrentBudgetTests(TransactionTestCase):
    def test_two_users_cannot_reserve_past_global_budget(self):
        from apps.ai_assistant.quota import reserve
        from rest_framework.exceptions import Throttled
        users=[User.objects.create(username='quota-'+str(i),role='TEACHER') for i in range(2)];barrier=Barrier(2)
        def attempt(pk):
            try:
                barrier.wait(timeout=10)
                with transaction.atomic():
                    actor=User.objects.get(pk=pk);job=AIImportJob.objects.create(owner=actor,target_type='BLOG',expires_at=timezone.now()+timezone.timedelta(days=30));reserve(actor,job)
                return 'reserved'
            except Throttled:return 'denied'
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,[u.pk for u in users]))
        self.assertCountEqual(results,['reserved','denied']);self.assertEqual(AIUsageLedger.objects.count(),1)
        bucket=AIQuotaBucket.objects.get(scope='GLOBAL');self.assertEqual(bucket.reserved_cny,Decimal('.08'));self.assertEqual(bucket.count,1)
    def test_network_boundary_outside_database_transaction(self):
        from apps.ai_assistant.tasks import run_once
        from apps.ai_assistant.models import AIConsent
        from apps.ai_assistant.quota import reserve
        from apps.ai_assistant.services import digest
        from apps.ai_assistant.providers.base import ProviderResult
        from django.db import connection
        actor=User.objects.create(username='network-boundary',role='TEACHER');text='Network example'
        with transaction.atomic():
            job=AIImportJob.objects.create(owner=actor,target_type='BLOG',source_pages=[{'page':1,'text':text}],source_preview=text,selected_text=text,input_digest=digest(text),expires_at=timezone.now()+timezone.timedelta(days=30));reserve(actor,job);AIConsent.objects.create(job=job,owner=actor,version='deepseek-text-v1',text_digest=job.input_digest)
        case=self
        class Provider:
            def extract_fields(self,*args):
                case.assertFalse(connection.in_atomic_block)
                return ProviderResult({'schema_version':1,'target_type':'BLOG','records':[{'fields':{'title':text},'evidence':[{'field':'title','page':1,'excerpt':text}]}]},10,20)
        self.assertTrue(run_once(Provider()));job.refresh_from_db();self.assertEqual(job.state,'READY')
