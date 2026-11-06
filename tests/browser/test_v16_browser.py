import secrets,unittest
from io import BytesIO
from zipfile import ZipFile
from playwright.sync_api import sync_playwright,expect
from support import Environment,launch_browser,EVIDENCE

class BlueCVBrowserTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.env=Environment().start();cls.p=sync_playwright().start();cls.browser=launch_browser(cls.p)
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.p.stop();cls.env.close()
 def test_blue_cv_and_blank_word_download(self):
  username='bluecv_'+secrets.token_hex(4);password='Test123456';self.env.seed(username,password,'STUDENT',False)
  context=self.browser.new_context(accept_downloads=True);page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  try:
   page.goto(self.env.url+'/login.html');page.locator('[name=username]').fill(username);page.locator('[name=password]').fill(password);page.get_by_role('button',name='登录账号',exact=True).click();page.wait_for_url('**/profile.html')
   page.locator('[name=display_name]').fill('蓝白简历浏览器验收');page.locator('[name=phone]').fill('13800138000');page.locator('[name=public_contact_email]').fill('academic@example.org');page.locator('[name=cv_gender]').select_option('女');page.locator('[name=cv_political_status]').select_option('群众');page.locator('[name=highest_education]').select_option('硕士研究生');page.locator('[name=research_areas]').fill('智能控制');page.get_by_role('button',name='保存资料',exact=True).click();expect(page.locator('#business-status')).to_contain_text('已保存')
   page.get_by_role('button',name='预览 / 刷新简历内容',exact=True).click();expect(page.locator('#team-cv')).to_contain_text('模板：蓝白学术版')
   with page.expect_download() as event:page.get_by_role('button',name='一键生成Word',exact=True).click()
   file=event.value;EVIDENCE.mkdir(parents=True,exist_ok=True);path=EVIDENCE/'blue-academic-browser.docx';file.save_as(path);z=ZipFile(path);xml=z.read('word/document.xml').decode();self.assertIn('蓝白简历浏览器验收',xml);self.assertIn('academic@example.org',xml);self.assertIn('CVSection',z.read('word/styles.xml').decode());self.assertNotIn('{{',xml)
   with page.expect_download() as event:page.get_by_role('link',name='下载空白模板',exact=True).click()
   path=EVIDENCE/'blue-blank-browser.docx';event.value.save_as(path);z=ZipFile(path);self.assertNotIn('蓝白简历浏览器验收',z.read('word/document.xml').decode());self.assertIn('个人照片',z.read('word/document.xml').decode());self.assertEqual(errors,[])
  finally:context.close()
