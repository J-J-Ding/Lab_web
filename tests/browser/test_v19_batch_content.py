import secrets,base64,unittest
from playwright.sync_api import sync_playwright,expect
from support import Environment,launch_browser,EVIDENCE


class BatchContentBrowserTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.env=Environment(ai_enabled=True).start();cls.p=sync_playwright().start();cls.browser=launch_browser(cls.p)
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.p.stop();cls.env.close()
 def test_template_review_and_create_two_kinds(self):
  username='contentbatch_'+secrets.token_hex(4);password='Test123456';self.env.seed(username,password,'STUDENT',False)
  c=self.browser.new_context(accept_downloads=True);page=c.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  try:
   page.goto(self.env.url+'/login.html');page.locator('[name=username]').fill(username);page.locator('[name=password]').fill(password);page.get_by_role('button',name='登录账号',exact=True).click();page.wait_for_url('**/profile.html');page.goto(self.env.url+'/content-import.html');page.wait_for_selector('body[data-import-ready=true]');expect(page.get_by_role('link',name='下载科研经历模板',exact=True)).to_be_visible()
   with page.expect_download() as e:page.get_by_role('link',name='下载科研经历模板',exact=True).click()
   EVIDENCE.mkdir(parents=True,exist_ok=True);e.value.save_as(EVIDENCE/'research-content-template.xlsx')
   fixture=self.env.orm("from io import BytesIO\nimport base64\nfrom openpyxl import Workbook\nfrom apps.content.batch_excel import COMMON,SHEETS\nb=Workbook();b.remove(b.active)\nfor name,title in [('论文','浏览器批量论文'),('竞赛荣誉','浏览器批量竞赛')]:\n s=b.create_sheet(name);s.append(COMMON+[label for _,label in SHEETS[name][1]]);s.append([1,title,'说明','正文测试'])\no=BytesIO();b.save(o);result={'file':base64.b64encode(o.getvalue()).decode()}")
   page.locator('#template-form [name=file]').set_input_files({'name':'research.xlsx','mimeType':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','buffer':base64.b64decode(fixture['file'])});page.get_by_role('button',name='上传模板并预览',exact=True).click();expect(page.locator('.batch-card')).to_have_count(2);expect(page.locator('#apply-batch')).to_be_disabled()
   for card in page.locator('.batch-card').all():card.get_by_label('我已核验本条内容',exact=True).check();card.get_by_label('选择此卡片',exact=True).check()
   page.get_by_role('button',name='保存候选修改与核验',exact=True).click();expect(page.locator('#business-status')).to_contain_text('候选已保存');page.locator('#batch-final-confirm').check();page.get_by_role('button',name='创建所选内容并生效',exact=True).click();expect(page.locator('#batch-state')).to_contain_text('等待批量创建')
   self.env.orm('from apps.content.batch_tasks import run_once\nrun_once()\nresult={"processed":True}')
   expect(page.locator('#batch-state')).to_contain_text('批量创建完成',timeout=20000);expect(page.locator('#batch-created a')).to_have_count(2);page.screenshot(path=str(EVIDENCE/'v19-batch-result.png'),full_page=True)
   page.locator('#batch-created a').first.click();page.wait_for_selector('#direct-content-form[data-ready=true]');expect(page.locator('[name=visibility_scope]')).to_have_value('TEAM');expect(page.locator('[name=title]')).to_have_value('浏览器批量论文');self.assertEqual(errors,[])
  finally:c.close()

 def test_ai_local_preview_consent_and_mixed_candidates(self):
  username='mixedbrowser_'+secrets.token_hex(4);password='Test123456';self.env.seed(username,password,'STUDENT',False)
  c=self.browser.new_context();page=c.new_page()
  try:
   page.goto(self.env.url+'/login.html');page.locator('[name=username]').fill(username);page.locator('[name=password]').fill(password);page.get_by_role('button',name='登录账号',exact=True).click();page.wait_for_url('**/profile.html');page.goto(self.env.url+'/content-import.html');page.wait_for_selector('body[data-import-ready=true]')
   fixture=self.env.orm("from apps.ai_assistant.tests.test_extraction import ExtractionTests\nimport base64\nresult={'file':base64.b64encode(ExtractionTests().docx('测试论文与测试竞赛；邮箱 test@example.org')).decode()}")
   page.locator('#ai-batch-form [name=file]').set_input_files({'name':'mixed.docx','mimeType':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','buffer':base64.b64decode(fixture['file'])});page.get_by_role('button',name='上传文档并本地解析',exact=True).click();expect(page.locator('#batch-state')).to_contain_text('本地提取')
   self.env.orm('from apps.content.batch_tasks import run_once\nrun_once()\nresult={"parsed":True}')
   expect(page.locator('#batch-consent')).to_be_visible(timeout=15000);self.assertNotIn('test@example.org',page.locator('#batch-source').input_value());page.locator('#batch-consent [name=consent]').check();page.get_by_role('button',name='确认发送并提取候选',exact=True).click();expect(page.locator('#batch-state')).to_contain_text('AI请求排队')
   self.env.orm("import json\nfrom apps.content.batch_tasks import run_once\ndef fake(payload,digest):\n records=[{'kind':k,'fields':{'title':t},'evidence':[{'field':'title','page':1,'excerpt':t}],'warnings':[],'uncertain_fields':[]} for k,t in [('PAPER','测试论文'),('AWARD','测试竞赛')]]\n return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'records':records,'warnings':[]})}}],'usage':{'prompt_tokens':1000,'completion_tokens':300}}\nrun_once(fake)\nresult={'processed':True}")
   expect(page.locator('.batch-card')).to_have_count(2,timeout=15000);expect(page.locator('#batch-cost')).to_contain_text('1/5');self.assertEqual(page.locator('.batch-card input[aria-label="我已核验本条内容"]:checked').count(),0);expect(page.locator('.batch-card').first).to_contain_text('查看原文证据')
  finally:c.close()
