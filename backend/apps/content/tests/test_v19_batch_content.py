from io import BytesIO
from django.test import TestCase,override_settings
from django.utils import timezone
from datetime import timedelta
from tempfile import TemporaryDirectory
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook
from apps.content.tests import test_v10 as fixtures
from apps.content.models import ContentImportBatch,ContentItem
from apps.content.batch_excel import COMMON,SHEETS
from apps.content.batch_tasks import run_once


def xlsx(entries):
 b=Workbook();b.remove(b.active)
 for name,values in entries.items():
  s=b.create_sheet(name);s.append(COMMON+[label for _,label in SHEETS[name][1]])
  for row in values:s.append(row)
 o=BytesIO();b.save(o);return o.getvalue()


class BatchContentTests(TestCase):
 setUpTestData=classmethod(fixtures.DirectCollaborationTests.setUpTestData.__func__)
 client_for=fixtures.DirectCollaborationTests.client_for
 profile=fixtures.DirectCollaborationTests.profile

 def upload(self,rows,c=None):return (c or self.client_for(self.student)).post('/api/content/imports/',{'file':SimpleUploadedFile('records.xlsx',xlsx(rows),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')},format='multipart')
 def review(self,c,batch):
  for r in batch['records']:r.update(reviewed=True,selected=True)
  response=c.patch('/api/content/imports/'+batch['id']+'/',{'lock_version':batch['lock_version'],'records':batch['records']},format='json');self.assertEqual(response.status_code,200,response.data);return response.data

 def test_template_mixed_review_and_same_batch_project_link(self):
  c=self.client_for(self.student);self.profile(self.student,'导入作者')
  response=self.upload({'科研项目':[[1,'同批项目','','',self.student.username,'','','','BATCH-001','基金','省级','2026-01-01','','进行中']], '论文':[[2,'同批论文','摘要','正文',self.student.username,'','BATCH-001','','10.1234/batch','Test Journal','2026-02-01']]},c);self.assertEqual(response.status_code,201,response.data);batch=response.data
  self.assertTrue(all(not r['errors'] for r in batch['records']),batch['records'])
  self.assertEqual(c.post('/api/content/imports/'+batch['id']+'/confirm/',{'lock_version':0,'confirm':True},format='json').status_code,400)
  batch=self.review(c,batch);response=c.post('/api/content/imports/'+batch['id']+'/confirm/',{'lock_version':batch['lock_version'],'confirm':True},format='json');self.assertEqual(response.status_code,202,response.data)
  run_once();obj=ContentImportBatch.objects.get(pk=batch['id']);self.assertEqual(obj.state,'DONE',obj.errors);self.assertEqual(len(obj.created),2)
  paper=ContentItem.objects.get(pk=obj.created['2']);self.assertEqual(paper.visibility_scope,'TEAM');self.assertEqual(paper.published_revision.project_links.count(),1)
  c.post('/api/content/imports/'+batch['id']+'/confirm/',{'lock_version':0,'confirm':True},format='json');run_once();self.assertEqual(ContentItem.objects.filter(created_by=self.student).count(),2)

 def test_edit_resets_review_conflicts_and_permissions(self):
  self.assertEqual(self.upload({'论文':[[1,'禁止']]},self.client_for(self.customer)).status_code,403)
  c=self.client_for(self.student);batch=self.upload({'论文':[[1,'需要核验']]},c).data;batch['records'][0].update(title='改过的标题',reviewed=True,selected=True)
  response=c.patch('/api/content/imports/'+batch['id']+'/',{'lock_version':0,'records':batch['records']},format='json');self.assertEqual(response.status_code,200,response.data);self.assertFalse(response.data['records'][0]['reviewed'])
  self.assertEqual(self.client_for(self.teacher).get('/api/content/imports/'+batch['id']+'/').status_code,404)
  self.assertEqual(c.patch('/api/content/imports/'+batch['id']+'/',{'lock_version':0,'records':batch['records']},format='json').status_code,409)

 def test_duplicate_identifiers_and_atomic_rollback(self):
  c=self.client_for(self.student);batch=self.upload({'论文':[[1,'论文1','','','','','','','10.1234/same'],[2,'论文2','','','','','','','10.1234/same']]},c).data;self.assertTrue(batch['records'][1]['errors'])
  batch=self.upload({'论文':[[1,'论文1','','','','','','','10.1234/new'],[2,'论文2','','','','','','','10.1234/new2']]},c).data;batch=self.review(c,batch);c.post('/api/content/imports/'+batch['id']+'/confirm/',{'lock_version':batch['lock_version'],'confirm':True},format='json')
  from unittest.mock import patch
  from apps.content import direct_services
  original=direct_services.save;count=[0]
  def fail(request,payload):
   count[0]+=1
   if count[0]==2:raise ValueError('synthetic failure')
   return original(request,payload)
  with patch('apps.content.direct_services.save',side_effect=fail):run_once()
  self.assertEqual(ContentItem.objects.filter(created_by=self.student).count(),0)
  self.assertEqual(ContentImportBatch.objects.get(pk=batch['id']).state,'READY')

 def test_template_formulas_and_cycles(self):
  response=self.upload({'论文':[[1,'=1+1']]});self.assertEqual(response.status_code,400)
  response=self.upload({'科研项目':[[1,'项目A','','','','','B','','A'],[2,'项目B','','','','','A','','B']]});self.assertEqual(response.status_code,201,response.data);self.assertTrue(all(r['errors'] for r in response.data['records']))
 def test_existing_project_without_number_and_cancel(self):
  c=self.client_for(self.student)
  created=c.post('/api/content/items/',{'kind':'PROJECT','title':'无编号项目'},format='json');self.assertEqual(created.status_code,201,created.data)
  b=self.upload({'论文':[[1,'关联无编号项目']]},c).data;b['records'][0]['project_ids']=[created.data['id']]
  r=c.patch('/api/content/imports/'+b['id']+'/',{'lock_version':b['lock_version'],'records':b['records']},format='json');self.assertEqual(r.status_code,200,r.data);b=self.review(c,r.data)
  c.post('/api/content/imports/'+b['id']+'/confirm/',{'lock_version':b['lock_version'],'confirm':True},format='json');run_once();obj=ContentImportBatch.objects.get(pk=b['id']);self.assertEqual(obj.state,'DONE',obj.errors)
  paper=ContentItem.objects.get(pk=obj.created['1']);self.assertEqual(str(paper.published_revision.project_links.get().target_project_id),created.data['id'])
  b=self.upload({'论文':[[1,'取消候选']]},c).data;r=c.post('/api/content/imports/'+b['id']+'/cancel/',{},format='json');self.assertEqual(r.status_code,200);self.assertEqual(r.data['records'],[])
