import secrets,unittest
from playwright.sync_api import sync_playwright,expect
from support import Environment,launch_browser,EVIDENCE

class V12BrowserTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.env=Environment().start();cls.p=sync_playwright().start();cls.browser=launch_browser(cls.p)
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.p.stop();cls.env.close()
 def test_unified_customer_profile_conditional_alumni_and_resume(self):
  name='v12_'+secrets.token_hex(4);password='Test123456';self.env.seed(name,password,'CUSTOMER',False)
  context=self.browser.new_context(viewport={'width':1440,'height':1000});page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  try:
   page.goto(self.env.url+'/login.html');page.locator('[name=username]').fill(name);page.locator('[name=password]').fill(password);page.get_by_role('button',name='登录账号',exact=True).click();page.wait_for_url('**/profile.html')
   expect(page.locator('#basic')).to_be_visible();expect(page.locator('#alumni-fields')).to_be_hidden();expect(page.locator('#resume-section')).to_be_visible()
   page.locator('[name=display_name]').fill('访客统一资料');page.locator('[name=public_member_status]').select_option('ALUMNI');expect(page.locator('#alumni-fields')).to_be_visible()
   page.locator('[name=graduation_year]').fill('2025');page.locator('[name=organization]').fill('测试去向');page.get_by_role('button',name='保存资料',exact=True).click();expect(page.locator('#business-status')).to_contain_text('已保存')
   page.locator('[name=public_member_status]').select_option('ACTIVE');expect(page.locator('#alumni-fields')).to_be_hidden();page.get_by_role('button',name='保存资料',exact=True).click();expect(page.locator('#business-status')).to_contain_text('已保存');page.reload();expect(page.locator('#alumni-fields')).to_be_hidden()
   expect(page.locator('#resume-submit-note')).to_be_visible();self.assertEqual(page.locator('.work-nav a[href="/resume.html"]').count(),0);self.assertEqual(page.locator('.nav-expand').count(),0)
   page.set_viewport_size({'width':390,'height':844});self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'));self.assertEqual(errors,[])
   EVIDENCE.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(EVIDENCE/'v12-profile-mobile.png'),full_page=True)
  finally:context.close()
 def test_teacher_inbox_and_notice(self):
  teacher='v12_teacher_'+secrets.token_hex(4);password='Test123456';self.env.seed(teacher,password,'TEACHER',False)
  self.env.orm("""
from apps.accounts.models import User
from apps.members.models import Resume,ResumeSubmission,SubmissionNotification
from apps.assets.models import AssetFile
u=User.objects.create(username='visitor-'+__import__('secrets').token_hex(4),role='CUSTOMER')
a=AssetFile.objects.create(owner=u,purpose='resume',storage_key='notice.pdf',original_filename='cv.pdf',mime_type='application/pdf',size=1,sha256='0'*64,scan_status='CLEAN')
r=Resume.objects.create(owner=u,title='访客投递示例',asset=a)
s=ResumeSubmission.objects.create(owner=u,resume=r,asset=a,resume_version=0,profile_snapshot={'display_name':'通知访客','phone':'12345678'},resume_snapshot={'title':'访客投递示例'})
SubmissionNotification.objects.create(recipient=User.objects.get(username=data["teacher"]),submission=s)
result={}
""",{'teacher':teacher})
  context=self.browser.new_context();page=context.new_page()
  try:
   page.goto(self.env.url+'/login.html');page.locator('[name=username]').fill(teacher);page.locator('[name=password]').fill(password);page.get_by_role('button',name='登录账号',exact=True).click();page.wait_for_url('**/profile.html')
   expect(page.locator('[data-submission-notice]')).to_contain_text('1');page.locator('[data-submission-notice]').click();expect(page.locator('#notification-list')).to_contain_text('通知访客');page.locator('#notification-list a').first.click();expect(page.locator('#submission-detail')).to_contain_text('12345678')
  finally:context.close()
 def test_stats_six_columns_ai_failure_and_contact_empty(self):
  context=self.browser.new_context(viewport={'width':1440,'height':1000});page=context.new_page()
  try:
   page.goto(self.env.url+'/statistics.html');expect(page.locator('.stats-grid > .stats-card')).to_have_count(6);self.assertEqual(page.locator('.stats-grid').evaluate('(el)=>getComputedStyle(el).gridTemplateColumns.split(" ").length'),3)
   page.set_viewport_size({'width':390,'height':844});self.assertEqual(page.locator('.stats-grid').evaluate('(el)=>getComputedStyle(el).gridTemplateColumns.split(" ").length'),1)
   page.goto(self.env.url+'/contact.html');expect(page.locator('h1')).to_have_text('联系我们');expect(page.locator('#public-content')).to_contain_text('联系信息暂未填写')
   page.goto(self.env.url+'/ai-import.html');expect(page.get_by_role('heading',name='处理范围与额度')).to_be_visible();expect(page.get_by_role('link',name='手工填写个人资料')).to_be_visible()
  finally:context.close()
 def test_editor_recycle_and_team_cv_download(self):
  name='v12_team_'+secrets.token_hex(4);password='Test123456';self.env.seed(name,password,'STUDENT',False)
  context=self.browser.new_context(accept_downloads=True);page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  try:
   page.goto(self.env.url+'/login.html');page.locator('[name=username]').fill(name);page.locator('[name=password]').fill(password);page.get_by_role('button',name='登录账号',exact=True).click();page.wait_for_url('**/profile.html')
   page.locator('[name=display_name]').fill('Word成员');page.get_by_role('button',name='保存资料',exact=True).click();expect(page.locator('#business-status')).to_contain_text('已保存')
   page.get_by_role('button',name='预览 / 刷新简历内容',exact=True).click();expect(page.locator('#team-cv')).to_contain_text('显示章节')
   with page.expect_download() as result:page.get_by_role('button',name='一键生成Word',exact=True).click()
   self.assertTrue(result.value.suggested_filename.endswith('.docx'))
   page.goto(self.env.url+'/content-editor.html?kind=PATENT');page.locator('[name=title]').fill('回收站专利样本');page.locator('[name=detail_patent_number]').fill('CNtest123');page.get_by_role('button',name='保存并生效',exact=True).click();page.wait_for_url('**/content-editor.html?id=*')
   page.goto(self.env.url+'/workspace.html');expect(page.locator('#workspace-list')).to_contain_text('回收站专利样本');page.once('dialog',lambda d:d.accept());page.get_by_role('button',name='移入已删除',exact=True).click();expect(page.locator('#workspace-list')).not_to_contain_text('回收站专利样本')
   page.locator('[name=scope]').select_option('deleted');page.get_by_role('button',name='筛选',exact=True).click();expect(page.locator('#workspace-list')).to_contain_text('回收站专利样本');page.get_by_role('button',name='恢复内容',exact=True).click();expect(page.locator('#business-status')).to_contain_text('默认不公开');self.assertEqual(errors,[])
  finally:context.close()
 def test_customer_upload_and_submit(self):
  from pathlib import Path
  name='v12_apply_'+secrets.token_hex(4);password='Test123456';self.env.seed(name,password,'CUSTOMER',False)
  context=self.browser.new_context();page=context.new_page()
  try:
   page.goto(self.env.url+'/login.html');page.locator('[name=username]').fill(name);page.locator('[name=password]').fill(password);page.get_by_role('button',name='登录账号',exact=True).click();page.wait_for_url('**/profile.html')
   page.locator('[name=display_name]').fill('实际投递访客');page.get_by_role('button',name='保存资料',exact=True).click();expect(page.locator('#business-status')).to_contain_text('已保存')
   template=Path(__file__).resolve().parents[2]/'backend/apps/members/templates/cv-v12.docx';page.locator('#resume-file').set_input_files(str(template));page.get_by_role('button',name='上传简历文件',exact=True).click();expect(page.locator('#resume-file-status')).to_contain_text('已上传')
   page.get_by_role('button',name='保存简历',exact=True).click();expect(page.locator('#resume-list')).to_contain_text('我的简历');page.get_by_role('button',name='预览并投递简历',exact=True).click();expect(page.locator('#resume-list')).to_contain_text('实际投递访客');page.get_by_role('button',name='确认共享并投递',exact=True).click();expect(page.locator('#resume-submissions')).to_contain_text('已投递')
   page.once('dialog',lambda d:d.accept());page.get_by_role('button',name='撤回投递',exact=True).click();expect(page.locator('#resume-submissions')).to_contain_text('已撤回')
  finally:context.close()
 def test_ai_disabled_and_quota_failure_keep_instructions(self):
  name='v12_ai_'+secrets.token_hex(4);password='Test123456';self.env.seed(name,password,'CUSTOMER',False)
  context=self.browser.new_context();page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  try:
   page.goto(self.env.url+'/login.html');page.locator('[name=username]').fill(name);page.locator('[name=password]').fill(password);page.get_by_role('button',name='登录账号',exact=True).click();page.wait_for_url('**/profile.html')
   page.goto(self.env.url+'/ai-import.html');expect(page.locator('#ai-quota')).to_contain_text('暂未启用');expect(page.locator('#ai-upload-form button')).to_be_disabled();expect(page.get_by_role('link',name='手工填写个人资料')).to_be_visible()
   page.route('**/api/ai/quota/',lambda route:route.fulfill(status=503,json={'detail':'unavailable'}));page.reload();expect(page.locator('#ai-quota')).to_contain_text('读取失败');expect(page.get_by_role('heading',name='处理范围与额度')).to_be_visible();expect(page.locator('#ai-upload-form button')).to_be_disabled();self.assertEqual(errors,[])
  finally:context.close()
