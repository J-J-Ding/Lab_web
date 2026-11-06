import secrets,unittest
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from support import Environment,launch_browser,EVIDENCE

class V13BrowserTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.env=Environment().start();cls.p=sync_playwright().start();cls.browser=launch_browser(cls.p)
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.p.stop();cls.env.close()
 def login(self,page,name,password):
  page.goto(self.env.url+'/login.html');page.locator('[name=username]').fill(name);page.locator('[name=password]').fill(password);page.get_by_role('button',name='登录账号',exact=True).click();page.wait_for_url('**/profile.html')
 def test_unified_column_primary_submission_and_teacher_notice(self):
  password='Test123456';visitor='v13v_'+secrets.token_hex(4);teacher='v13t_'+secrets.token_hex(4)
  self.env.seed(visitor,password,'CUSTOMER',False);self.env.seed(teacher,password,'TEACHER',False)
  vc=self.browser.new_context(viewport={'width':1440,'height':1000});tc=self.browser.new_context();page=vc.new_page();staff=tc.new_page()
  try:
   self.login(page,visitor,password)
   expect(page.locator('#profile-content-column #resume-section')).to_be_visible()
   basic=page.locator('#basic').bounding_box();resume=page.locator('#resume-section').bounding_box();self.assertLess(abs(basic['x']-resume['x']),2);self.assertLess(abs(basic['width']-resume['width']),2)
   self.assertEqual(page.locator('label label').count(),0);self.assertEqual(page.locator('form form').count(),0)
   page.locator('[name=display_name]').fill('V13访客');page.get_by_role('button',name='保存资料',exact=True).click();expect(page.locator('#business-status')).to_contain_text('已保存')
   template=Path(__file__).resolve().parents[2]/'backend/apps/members/templates/cv-v12.docx';page.locator('#resume-file').set_input_files(str(template));page.get_by_role('button',name='上传简历文件',exact=True).click();expect(page.locator('#resume-file-status')).to_contain_text('已上传')
   page.locator('[name=bio]').fill('尚未保存的资料');page.get_by_role('button',name='保存并预览投递',exact=True).click();expect(page.locator('#resume-status')).to_contain_text('先保存个人资料');expect(page.locator('[name=bio]')).to_have_value('尚未保存的资料')
   page.get_by_role('button',name='保存资料',exact=True).click();expect(page.locator('#business-status')).to_contain_text('已保存');page.get_by_role('button',name='保存并预览投递',exact=True).click();expect(page.locator('#resume-preview')).to_contain_text('V13访客');page.get_by_role('button',name='确认共享并投递',exact=True).click();expect(page.locator('#resume-status')).to_contain_text('已投递')
   self.login(staff,teacher,password);staff.goto(self.env.url+'/notifications.html');expect(staff.locator('#notification-list')).to_contain_text('V13访客');staff.locator('#notification-list a').first.click();expect(staff.locator('#submission-detail')).to_contain_text('尚未保存的资料')
   EVIDENCE.mkdir(parents=True,exist_ok=True);page.locator('#resume-section').scroll_into_view_if_needed();page.screenshot(path=str(EVIDENCE/'v13-profile-desktop.png'))
   page.set_viewport_size({'width':390,'height':844});self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'));page.screenshot(path=str(EVIDENCE/'v13-profile-mobile.png'))
  finally:vc.close();tc.close()
 def test_navigation_links_fill_full_cells(self):
  context=self.browser.new_context(viewport={'width':1440,'height':900});page=context.new_page()
  try:
   page.goto(self.env.url+'/data/members/index.html');expect(page.locator('.site-nav .nav-group')).to_have_count(5)
   for link in page.locator('.site-nav li > a,.site-nav .nav-entry > a').all():
    box=link.bounding_box();parent=link.locator('xpath=ancestor::li').bounding_box();self.assertLess(abs(box['width']-parent['width']),2)
   page.get_by_role('link',name='科学研究',exact=True).hover();expect(page.locator('.nav-submenu').filter(has=page.get_by_role('link',name='科研项目',exact=True))).to_be_visible()
  finally:context.close()
