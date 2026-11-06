import unittest,secrets
from playwright.sync_api import sync_playwright,expect
from support import Environment,launch_browser

class V10BrowserTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.env=Environment().start();cls.p=sync_playwright().start();cls.browser=launch_browser(cls.p)
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.p.stop();cls.env.close()
 def test_direct_profile_content_home_and_mobile(self):
  username='v10_'+secrets.token_hex(4);password=secrets.token_urlsafe(18)+'!A4';self.env.seed(username,password,'STUDENT',False)
  context=self.browser.new_context();page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  try:
   page.goto(self.env.url+'/login.html');page.locator('[name=username]').fill(username);page.locator('[name=password]').fill(password);page.get_by_role('button',name='登录账号',exact=True).click();page.wait_for_url('**/profile.html')
   expect(page.locator('#business-profile-form')).to_be_visible();page.locator('[name=display_name]').fill('联调同学');page.locator('[name=public_visible]').check();page.get_by_role('button',name='保存资料',exact=True).click();expect(page.locator('#business-status')).to_contain_text('已保存')
   page.goto(self.env.url+'/content-editor.html');page.locator('[name=title]').fill('浏览器联调论文');page.get_by_role('button',name='保存并生效',exact=True).click();page.wait_for_url('**/content-editor.html?id=*');expect(page.locator('[name=title]')).to_have_value('浏览器联调论文')
   page.goto(self.env.url+'/index.html');expect(page.locator('#home-papers')).to_contain_text('浏览器联调论文');expect(page.locator('#home-stats')).to_contain_text('发表论文')
   page.set_viewport_size({'width':390,'height':844});expect(page.get_by_role('button',name='菜单')).to_be_visible();page.get_by_role('button',name='菜单').click();expect(page.locator('.site-nav')).to_be_visible();self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
   self.assertEqual(errors,[])
  finally:context.close()
 def test_customer_private_resume_and_account_denied(self):
  username='v10_customer_'+secrets.token_hex(4);password=secrets.token_urlsafe(18)+'!A4';self.env.seed(username,password,'CUSTOMER',False)
  context=self.browser.new_context();page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  try:
   page.goto(self.env.url+'/login.html');page.locator('[name=username]').fill(username);page.locator('[name=password]').fill(password);page.get_by_role('button',name='登录账号',exact=True).click();page.wait_for_url('**/profile.html')
   expect(page.locator('#privacy-fields')).to_be_hidden();page.locator('[name=display_name]').fill('求职同学');page.get_by_role('button',name='保存资料',exact=True).click();expect(page.locator('#business-status')).to_contain_text('已保存')
   page.goto(self.env.url+'/resume.html');page.locator('[name=title]').fill('测试私有简历');page.locator('[name=intention]').fill('科研助理');page.get_by_role('button',name='保存简历',exact=True).click();expect(page.locator('#resume-list')).to_contain_text('测试私有简历');expect(page.locator('#business-status')).to_contain_text('私密保存')
   page.goto(self.env.url+'/manage/index.html');expect(page.locator('#business-status')).to_contain_text('仅 Teacher');expect(page.locator('#root-accounts')).to_be_hidden();self.assertEqual(errors,[])
  finally:context.close()
 def test_ai_education_candidate_enters_structured_form_without_saving(self):
  username='v10_ai_'+secrets.token_hex(4);password=secrets.token_urlsafe(18)+'!A4';self.env.seed(username,password,'STUDENT',False)
  context=self.browser.new_context();page=context.new_page()
  try:
   page.goto(self.env.url+'/login.html');page.locator('[name=username]').fill(username);page.locator('[name=password]').fill(password);page.get_by_role('button',name='登录账号',exact=True).click();page.wait_for_url('**/profile.html')
   job='11111111-1111-1111-1111-111111111111'
   page.route('**/api/ai/imports/'+job+'/',lambda route:route.fulfill(json={'candidate':{'records':[{'fields':{'display_name':'AI候选姓名','education':[{'school':'示例大学','major':'计算机','is_public':False}],'alumni':{'graduation_year':2025,'destination_type':'WORK','organization':'示例单位','is_public':False}}}]}}))
   page.goto(self.env.url+'/profile.html?ai_job='+job+'&ai_fields=display_name,education,alumni')
   expect(page.locator('[name=display_name]')).to_have_value('AI候选姓名');expect(page.locator('#education-rows [name=school]')).to_have_value('示例大学');expect(page.locator('[name=organization]')).to_have_value('示例单位');expect(page.locator('#business-status')).to_contain_text('候选已填入')
   result=page.request.get(self.env.url+'/api/members/me/profile/').json();self.assertNotEqual(result.get('display_name'),'AI候选姓名')
  finally:context.close()
