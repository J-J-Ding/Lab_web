import secrets,unittest
from playwright.sync_api import sync_playwright,expect
from support import Environment,launch_browser,EVIDENCE
from test_v16_rich_content_browser import png


class CarouselBrowserTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.env=Environment().start();cls.p=sync_playwright().start();cls.browser=launch_browser(cls.p)
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.p.stop();cls.env.close()
 def test_root_upload_mode_edit_disable(self):
  username='carousel_'+secrets.token_hex(4);password='Test123456';self.env.seed(username,password,'TEACHER',True)
  context=self.browser.new_context();page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  try:
   page.goto(self.env.url+'/login.html');page.locator('[name=username]').fill(username);page.locator('[name=password]').fill(password);page.get_by_role('button',name='登录账号',exact=True).click();page.wait_for_url('**/profile.html');page.goto(self.env.url+'/manage/carousel.html');expect(page.locator('#business-status')).to_contain_text('仅Root可管理')
   page.locator('[name=image]').set_input_files({'name':'slide.png','mimeType':'image/png','buffer':png()});page.get_by_role('button',name='上传图片',exact=True).click();expect(page.locator('#upload-status')).to_contain_text('图片已上传');page.locator('[name=title]').fill('后台配置首页图片');page.locator('[name=subtitle]').fill('实验室副标题');page.get_by_role('button',name='保存轮播项',exact=True).click();expect(page.locator('#slide-list')).to_contain_text('后台配置首页图片')
   page.locator('[name=mode]').select_option('MANUAL');page.get_by_role('button',name='保存展示模式',exact=True).click();page.wait_for_function("document.querySelector('#mode-form button').disabled===false");expect(page.locator('#business-status')).to_contain_text('已保存');page.goto(self.env.url+'/index.html');expect(page.locator('.home-slide h1').filter(has_text='后台配置首页图片')).to_have_text('后台配置首页图片');expect(page.locator('.slide-caption p').filter(has_text='实验室副标题')).to_have_text('实验室副标题');page.wait_for_function("[...document.querySelectorAll('.home-slide img')].some(e=>e.complete&&e.naturalWidth>0)")
   page.set_viewport_size({'width':390,'height':844});self.assertFalse(page.evaluate('document.documentElement.scrollWidth>innerWidth'));EVIDENCE.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(EVIDENCE/'v17-carousel-mobile.png'),full_page=True)
   page.goto(self.env.url+'/manage/carousel.html');page.get_by_role('button',name='停用',exact=True).click();expect(page.locator('#slide-list')).to_contain_text('停用');page.goto(self.env.url+'/index.html');expect(page.locator('.home-slide--logo')).to_have_count(2)
   page.goto(self.env.url+'/manage/index.html');expect(page.locator('[name=account_state]')).to_be_visible();page.locator('[name=account_state]').select_option('cancelled');expect(page.locator('#account-list')).to_contain_text('共 0 个账号');self.assertEqual(errors,[])
  finally:context.close()
