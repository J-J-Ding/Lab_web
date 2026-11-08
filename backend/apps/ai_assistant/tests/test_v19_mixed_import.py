import json
from decimal import Decimal
from datetime import timedelta
from django.test import TestCase,override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.content.tests import test_v10 as fixtures
from apps.content.models import ContentImportBatch,ContentImportCall,ContentItem
from apps.content.batch_tasks import run_once
from apps.content.batch_ai import payload_for,reserve
from apps.ai_assistant.providers.base import ProviderError


@override_settings(AI_ENABLED=True,AI_PROVIDER='deepseek',DEEPSEEK_API_KEY='fake-no-network',DEEPSEEK_MODEL='deepseek-flash',DEEPSEEK_BASE_URL='https://api.deepseek.com',AI_PRICE_INPUT_CNY_PER_MILLION='2.4',AI_PRICE_OUTPUT_CNY_PER_MILLION='9.6',AI_MAX_INPUT_TOKENS=24000,AI_MAX_OUTPUT_TOKENS=4000,AI_GLOBAL_DAILY_BUDGET_CNY='10',AI_USER_DAILY_LIMIT=100,AI_GLOBAL_DAILY_LIMIT=100)
class MixedImportTests(TestCase):
 setUpTestData=classmethod(fixtures.DirectCollaborationTests.setUpTestData.__func__)
 client_for=fixtures.DirectCollaborationTests.client_for
 def setUp(self):self.settings_override=override_settings(AI_PRICE_EFFECTIVE_DATE=str(timezone.localdate()));self.settings_override.enable();self.addCleanup(self.settings_override.disable)
 def batch(self,text='测试论文与测试竞赛',segments=None):
  return ContentImportBatch.objects.create(owner=self.student,source='AI',state='QUEUED_AI',pages=[{'page':1,'text':text}],selected_text=text,segments=segments or [text],consent_at=timezone.now(),expires_at=timezone.now()+timedelta(days=1))
 def fake(self,payload,digest):
  self.assertEqual(payload['thinking'],{'type':'disabled'});self.assertNotIn('tools',payload)
  records=[{'kind':k,'fields':{'title':title},'evidence':[{'field':'title','page':1,'excerpt':title}],'warnings':[],'uncertain_fields':[]} for k,title in [('PAPER','测试论文'),('AWARD','测试竞赛')]]
  return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'records':records,'warnings':[]})}}],'usage':{'prompt_tokens':1000,'completion_tokens':300}}
 def test_mixed_candidates_no_creation_before_human_confirmation(self):
  b=self.batch();run_once(self.fake);b.refresh_from_db();self.assertEqual(b.state,'READY',b.errors);self.assertEqual([r['kind'] for r in b.records],['PAPER','AWARD']);self.assertTrue(all(not r['reviewed'] and r['visibility_scope']=='TEAM' and not r['authors'] for r in b.records));self.assertFalse(ContentItem.objects.filter(created_by=self.student).exists());call=b.calls.get();self.assertEqual(call.state,'SETTLED');self.assertLessEqual(call.reserved,Decimal('.10'))
 def test_five_calls_and_incomplete_range_report(self):
  b=self.batch(segments=['测试论文与测试竞赛']*8)
  for _ in range(8):run_once(self.fake)
  b.refresh_from_db();self.assertEqual(b.calls.count(),5);self.assertEqual(b.processed,5);self.assertEqual(b.state,'READY');self.assertTrue(any('未处理' in w for w in b.warnings));self.assertLessEqual(sum(b.calls.values_list('reserved',flat=True)),Decimal('.50'))
 def test_unknown_billing_does_not_retry(self):
  b=self.batch()
  def error(*args):raise ProviderError('provider_network_unknown',unknown=True)
  run_once(error);run_once(error);b.refresh_from_db();self.assertEqual(b.calls.count(),1);self.assertEqual(b.calls.get().state,'UNKNOWN');self.assertEqual(b.state,'READY')
 def test_cost_gate_before_send_and_consent_bounds(self):
  b=self.batch();b.state='CALLING';b.save()
  payload=payload_for('x'*24000)
  with self.assertRaises(ProviderError):reserve(b.pk,payload)
  self.assertEqual(b.calls.count(),0)
  b.state='AWAITING_CONSENT';b.save();c=self.client_for(self.student)
  r=c.post(f'/api/content/imports/{b.pk}/consent/',{'lock_version':0,'text_digest':'bad','selected_text':'凭空编写','confirm':True},format='json');self.assertEqual(r.status_code,400)
 def test_bad_evidence_not_repaired_or_published(self):
  b=self.batch()
  def response(payload,digest):
   data=self.fake(payload,digest);obj=json.loads(data['choices'][0]['message']['content']);obj['records'][0]['evidence'][0]['excerpt']='文档没有这句话';data['choices'][0]['message']['content']=json.dumps(obj);return data
  run_once(response);b.refresh_from_db();self.assertEqual(b.records,[]);self.assertEqual(b.calls.count(),1);self.assertEqual(b.calls.get().state,'SETTLED')
 def test_cross_segment_records_merge_with_evidence_and_warning(self):
  b=self.batch(segments=['测试论文与测试竞赛']*2);run_once(self.fake);run_once(self.fake);b.refresh_from_db();self.assertEqual(len(b.records),2);self.assertTrue(any('跨片段' in w for w in b.records[0]['warnings']));self.assertEqual(len(b.records[0]['evidence']),2)
 def test_cancellation_during_call_keeps_usage_but_no_candidate(self):
  b=self.batch()
  def respond(payload,digest):
   ContentImportBatch.objects.filter(pk=b.pk).update(state='CANCELLED')
   return self.fake(payload,digest)
  run_once(respond);b.refresh_from_db();self.assertEqual(b.state,'CANCELLED');self.assertEqual(b.records,[]);self.assertEqual(b.calls.get().state,'SETTLED')
 def test_unknown_usage_reconciliation_does_not_resend(self):
  from django.core.management import call_command
  b=self.batch()
  def fail(*args):raise ProviderError('timeout',unknown=True)
  run_once(fail);call=b.calls.get();call_command('reconcile_content_import_usage',call=call.pk,not_billed=True,reason='Verified synthetic provider ledger',input_tokens=0,output_tokens=0);call.refresh_from_db();self.assertEqual(call.state,'RELEASED')
