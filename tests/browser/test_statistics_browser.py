import unittest
from playwright.sync_api import sync_playwright,expect
from support import Environment,launch_browser
class StatisticsBrowserTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.env=Environment().start();cls.p=sync_playwright().start();cls.browser=launch_browser(cls.p)
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.p.stop();cls.env.close()
 def test_public_table_filters_and_responsive(self):
  context=self.browser.new_context();page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  try:
   for width in (1440,768,390,320):
    page.set_viewport_size({'width':width,'height':900});page.goto(self.env.url+'/statistics.html');expect(page.locator('#stats-status')).to_contain_text('统计已更新');self.assertEqual(page.locator('#stats-data table').count(),7);self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= innerWidth+1'))
   page.get_by_label('起始年份',exact=True).fill('1900');page.get_by_role('button',name='更新统计',exact=True).click();expect(page.locator('#stats-status')).to_contain_text('无效')
   page.goto(self.env.url+'/manage/statistics.html');expect(page.locator('#stats-status')).to_contain_text('管理账号')
   self.assertEqual(errors,[])
  finally:context.close()
