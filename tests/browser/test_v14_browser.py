import secrets,unittest
from playwright.sync_api import sync_playwright,expect
from support import Environment,launch_browser,EVIDENCE

class V14BrowserTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.env=Environment().start();cls.p=sync_playwright().start();cls.browser=launch_browser(cls.p)
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.p.stop();cls.env.close()
 def login(self,page,user,password):
  page.goto(self.env.url+'/login.html');page.locator('[name=username]').fill(user);page.locator('[name=password]').fill(password);page.get_by_role('button',name='登录账号',exact=True).click();page.wait_for_url('**/profile.html')
 def test_profile_choices_fixed_fields_and_navigation(self):
  user='v14_'+secrets.token_hex(4);password='Test123456';self.env.seed(user,password,'STUDENT',False)
  context=self.browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce');page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  try:
   self.login(page,user,password);expect(page.locator('[name=cv_gender]')).to_be_visible();self.assertEqual(page.locator('#privacy,#account-email-form,[name=intention],[name=public_contact_enabled]').count(),0)
   page.locator('[name=display_name]').fill('固定字段成员');page.locator('[name=cv_gender]').select_option('女');page.locator('[name=cv_political_status]').select_option('群众');page.locator('[name=enrollment_year]').select_option('2025');page.locator('[name=native_province]').select_option('42');page.locator('[name=native_city]').select_option('4201');page.locator('[name=native_district]').select_option(index=1)
   page.get_by_role('button',name='添加教育经历',exact=True).click();page.locator('[name=school]').fill('不公开学校');page.locator('[name=education_level]').select_option('硕士研究生');page.locator('[name=degree]').select_option('硕士');page.get_by_role('button',name='保存资料',exact=True).click();expect(page.locator('#business-status')).to_contain_text('已保存');page.reload();expect(page.locator('[name=cv_gender]')).to_have_value('女');expect(page.locator('[name=native_city]')).to_have_value('4201')
   for target in ['education','profile-research','security','resume-section']:
    page.locator('.v10-sidebar a[href="#'+target+'"]').click();expect(page.locator('.v10-sidebar a[href="#'+target+'"]')).to_have_attribute('aria-current','true');self.assertEqual(page.locator('.v10-sidebar [aria-current=true]').count(),1)
   page.goto(self.env.url+'/data/members/index.html');expect(page.locator('#public-content')).to_contain_text('固定字段成员');expect(page.locator('#public-content')).to_contain_text('硕士研究生');expect(page.locator('#public-content')).not_to_contain_text('不公开学校');self.assertEqual(errors,[])
  finally:context.close()
 def test_home_motion_photo_menu_and_filter_changes(self):
  user='v14w_'+secrets.token_hex(4);password='Test123456';self.env.seed(user,password,'STUDENT',False)
  context=self.browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce');page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  try:
   page.goto(self.env.url+'/index.html');expect(page.locator('#home-stats strong')).to_have_count(4);self.assertTrue(page.locator('.stats-strip').evaluate('(el)=>el.compareDocumentPosition(document.querySelector(".home-intro")) & Node.DOCUMENT_POSITION_FOLLOWING')>0)
   page.get_by_role('link',name='竞赛成果',exact=True).first.hover();sub=page.locator('.nav-submenu a').filter(has_text='学科竞赛');expect(sub).to_be_visible();sub.hover();self.assertEqual(sub.evaluate('(el)=>getComputedStyle(el).color'),'rgb(23, 63, 107)')
   self.login(page,user,password);page.goto(self.env.url+'/workspace.html');expect(page.locator('[name=scope]')).to_be_visible();self.assertTrue(page.locator('#workspace-filter').evaluate('(f)=>f.querySelector("[name=scope]").compareDocumentPosition(f.querySelector("button[type=submit]")) & Node.DOCUMENT_POSITION_FOLLOWING')>0)
   page.locator('[name=scope]').select_option('deleted');expect(page).to_have_url(__import__('re').compile('scope=deleted'));page.locator('[name=q]').fill('自动查询');expect(page).to_have_url(__import__('re').compile('q='));page.get_by_role('button',name='重置',exact=True).click();expect(page.locator('[name=scope]')).to_have_value('normal');expect(page.locator('[name=q]')).to_have_value('');self.assertEqual(errors,[])
  finally:context.close()
 def test_pdf_submit_and_site_team_visibility_then_logout(self):
  import base64
  password='Test123456';visitor='v14pdf_'+secrets.token_hex(4);teacher='v14team_'+secrets.token_hex(4)
  self.env.seed(visitor,password,'CUSTOMER',False);self.env.seed(teacher,password,'TEACHER',False)
  fixture=self.env.orm("""
from apps.content.tests.test_v14 import V14Contracts
import base64
result={'pdf':base64.b64encode(V14Contracts().pdf()).decode()}
""")
  vc=self.browser.new_context();tc=self.browser.new_context();page=vc.new_page();staff=tc.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));staff.on('pageerror',lambda e:errors.append(str(e)))
  try:
   self.login(page,visitor,password);page.locator('[name=display_name]').fill('PDF浏览器投递');page.get_by_role('button',name='保存资料',exact=True).click();expect(page.locator('#business-status')).to_contain_text('已保存')
   page.locator('#resume-file').set_input_files({'name':'含文字图片链接简历.pdf','mimeType':'application/pdf','buffer':base64.b64decode(fixture['pdf'])});page.get_by_role('button',name='上传简历文件',exact=True).click();expect(page.locator('#resume-file-status')).to_contain_text('已上传');page.get_by_role('button',name='保存并预览投递',exact=True).click();expect(page.locator('#resume-preview')).to_contain_text('PDF浏览器投递');page.get_by_role('button',name='确认共享并投递',exact=True).click();expect(page.locator('#resume-status')).to_contain_text('已投递')
   self.login(staff,teacher,password);staff.goto(self.env.url+'/notifications.html');notice=staff.locator('#notification-list article').filter(has_text='PDF浏览器投递');notice.get_by_role('link',name='查看投递资料').click();expect(staff.locator('#submission-detail')).to_contain_text('PDF浏览器投递')
   staff.goto(self.env.url+'/content-editor.html');staff.locator('[name=kind]').select_option('PAPER');staff.locator('[name=title]').fill('只限团队网页样本');staff.locator('[name=visibility_scope]').select_option('TEAM');staff.get_by_role('button',name='保存并生效',exact=True).click();staff.wait_for_url('**/content-editor.html?id=*');item=staff.url.split('id=')[1]
   staff.goto(self.env.url+'/data/papers/index.html');expect(staff.locator('#public-content')).to_contain_text('只限团队网页样本');page.goto(self.env.url+'/data/papers/index.html');expect(page.locator('#public-status')).to_contain_text('共');expect(page.locator('#public-content')).not_to_contain_text('只限团队网页样本')
   staff.locator('[data-auth-logout]').click();expect(staff.locator('#public-content')).not_to_contain_text('只限团队网页样本');self.assertEqual(staff.request.get(self.env.url+'/api/site/content/'+item+'/').status,404);self.assertEqual(errors,[])
  finally:vc.close();tc.close()

 def test_fullscreen_logo_carousel_and_header_logo(self):
  context=self.browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce');page=context.new_page()
  try:
   page.goto(self.env.url+'/index.html');expect(page.locator('.home-slide')).to_be_visible();expect(page.locator('.home-slide>img')).to_have_attribute('src','/lab-logo.png');header=page.locator('.site-header').bounding_box();hero=page.locator('.home-slide').bounding_box();self.assertLess(abs(header['height']+hero['height']-1000),3);self.assertGreater(page.locator('.brand-link img').bounding_box()['width']/page.locator('.brand-link img').bounding_box()['height'],1.5)
   first=page.locator('.slide-caption h1').inner_text();page.get_by_role('button',name='下一张',exact=True).click();expect(page.locator('.slide-caption h1')).not_to_have_text(first)
   EVIDENCE.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(EVIDENCE/'v14-home-desktop.png'));page.set_viewport_size({'width':390,'height':844});self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'));page.screenshot(path=str(EVIDENCE/'v14-home-mobile.png'))
  finally:context.close()
