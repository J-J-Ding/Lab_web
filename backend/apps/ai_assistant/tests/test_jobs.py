from io import BytesIO
from unittest.mock import patch
from django.test import override_settings
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.accounts.tests.helpers import AccountFixtures,login_as,write
from . import test_extraction as extraction_helpers

CONFIG={'AI_ENABLED':True,'DEEPSEEK_API_KEY':'fake-local-test','AI_PRICE_INPUT_CNY_PER_MILLION':'2','AI_PRICE_OUTPUT_CNY_PER_MILLION':'8','AI_PRICE_EFFECTIVE_DATE':timezone.localdate().isoformat()}
@override_settings(**CONFIG)
class JobFlowTests(AccountFixtures):
    def setUp(self):
        from tempfile import TemporaryDirectory
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.override=override_settings(PRIVATE_MEDIA_ROOT=self.tmp.name);self.override.enable();self.addCleanup(self.override.disable)
        self.c=login_as(self.teacher)
    def asset(self,client=None,text='Example title\nExample body of the document.'):
        c=client or self.c;raw=extraction_helpers.ExtractionTests.docx(self,text)
        r=c.post('/api/assets/',{'purpose':'ai_source','file':SimpleUploadedFile('example.docx',raw,content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')},format='multipart',HTTP_X_CSRFTOKEN=c.cookies['csrftoken'].value)
        self.assertEqual(r.status_code,201,r.content);return r.json()['id']
    def create(self,client=None,target='BLOG',asset=None):
        c=client or self.c;r=write(c,'post','/api/ai/imports/',{'asset':asset or self.asset(c),'target_type':target,'consent_version':'local-v1'})
        self.assertEqual(r.status_code,202,r.content);return r.json()
    def ready(self):
        from apps.ai_assistant.tasks import run_once
        from apps.ai_assistant.providers.base import ProviderResult
        job=self.create()
        with patch('apps.ai_assistant.providers.deepseek.DeepSeekProvider.extract_fields') as provider:
            self.assertTrue(run_once());provider.assert_not_called()
        job=self.c.get('/api/ai/imports/'+job['id']+'/').json();self.assertEqual(job['state'],'AWAITING_CONSENT')
        r=write(self.c,'post',f"/api/ai/imports/{job['id']}/consent/",{'lock_version':job['lock_version'],'consent_version':'deepseek-text-v1','text_digest':job['text_digest'],'selected_text':job['preview']});self.assertEqual(r.status_code,200,r.content)
        fields={'title':'Example title','detail':{'body':'Example body of the document.'}}
        data={'schema_version':1,'target_type':'BLOG','records':[{'fields':fields,'evidence':[{'field':'title','page':1,'excerpt':'Example title'},{'field':'detail.body','page':1,'excerpt':'Example body of the document.'}],'uncertain_fields':[],'warnings':[]}],'warnings':[]}
        with patch('apps.ai_assistant.providers.deepseek.DeepSeekProvider.extract_fields',return_value=ProviderResult(data,100,200,'fake-request')):
            self.assertTrue(run_once())
        result=self.c.get('/api/ai/imports/'+job['id']+'/').json();self.assertEqual(result['state'],'READY',result);return result
    def test_preview_no_network_then_explicit_consent_apply_draft_idempotent(self):
        job=self.ready();self.assertEqual(job['usage']['state'],'SETTLED')
        body={'lock_version':job['lock_version'],'record_index':0,'confirmed_fields':['title','detail.body'],'confirm':True}
        r=write(self.c,'post',f"/api/ai/imports/{job['id']}/apply/",body);self.assertEqual(r.status_code,200,r.content);first=r.json()
        r=write(self.c,'post',f"/api/ai/imports/{job['id']}/apply/",body);self.assertEqual(r.status_code,200,r.content);self.assertEqual(r.json()['revision_id'],first['revision_id'])
        from apps.content.models import ContentItem
        self.assertEqual(ContentItem.objects.count(),1);self.assertIsNone(ContentItem.objects.get().published_revision_id)
    def test_cross_user_candidate_asset_and_customer_posting_denied(self):
        asset=self.asset();other=login_as(self.customer)
        r=write(other,'post','/api/ai/imports/',{'asset':asset,'target_type':'MEMBER','consent_version':'local-v1'});self.assertEqual(r.status_code,404)
        own_asset=self.asset(other)
        self.assertEqual(write(other,'post','/api/ai/imports/',{'asset':own_asset,'target_type':'PAPER','consent_version':'local-v1'}).status_code,403)
        job=self.ready()
        self.assertEqual(other.get('/api/ai/imports/'+job['id']+'/').status_code,404)
        self.assertEqual(write(other,'patch',f"/api/ai/imports/{job['id']}/candidate/",{'lock_version':job['lock_version'],'candidate':job['candidate']}).status_code,404)
    def test_one_active_job_and_cancel_releases_budget(self):
        job=self.create();r=write(self.c,'post','/api/ai/imports/',{'asset':self.asset(),'target_type':'BLOG','consent_version':'local-v1'});self.assertEqual(r.status_code,409,r.content)
        r=write(self.c,'post',f"/api/ai/imports/{job['id']}/cancel/",{});self.assertEqual(r.status_code,200)
        from apps.ai_assistant.models import AIUsageLedger
        self.assertEqual(AIUsageLedger.objects.get(job_id=job['id']).state,'RELEASED')
        self.create()
    def test_stale_candidate_and_target_versions_preserve_candidate(self):
        job=self.ready();r=write(self.c,'patch',f"/api/ai/imports/{job['id']}/candidate/",{'lock_version':job['lock_version']+1,'candidate':job['candidate']});self.assertEqual(r.status_code,409)
        r=write(self.c,'post','/api/content/items/',{'kind':'BLOG','title':'Existing','detail':{'body':'Original'}});item=r.json()
        r=write(self.c,'post',f"/api/ai/imports/{job['id']}/apply/",{'lock_version':job['lock_version'],'record_index':0,'confirmed_fields':['title'],'confirm':True,'target_id':item['id'],'target_lock_version':999});self.assertEqual(r.status_code,409,r.content)
        self.assertEqual(self.c.get('/api/ai/imports/'+job['id']+'/').json()['state'],'READY')
    @override_settings(AI_GLOBAL_DAILY_BUDGET_CNY='0.000001')
    def test_budget_exhaustion_prevents_job(self):
        r=write(self.c,'post','/api/ai/imports/',{'asset':self.asset(),'target_type':'BLOG','consent_version':'local-v1'});self.assertEqual(r.status_code,429,r.content)
