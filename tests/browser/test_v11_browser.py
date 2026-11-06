import unittest,secrets,io
from playwright.sync_api import sync_playwright,expect
import zlib,struct
from support import Environment,launch_browser,EVIDENCE

class V11BrowserTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.env=Environment().start();cls.p=sync_playwright().start();cls.browser=launch_browser(cls.p)
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.p.stop();cls.env.close()

 def test_navigation_profile_cover_search_and_responsive(self):
  username='v11_'+secrets.token_hex(4);password=secrets.token_urlsafe(18)+'!A4';self.env.seed(username,password,'STUDENT',False)
  context=self.browser.new_context(viewport={'width':1440,'height':1000});page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  try:
   page.goto(self.env.url+'/login.html');page.locator('[name=username]').fill(username);page.locator('[name=password]').fill(password);page.get_by_role('button',name='登录账号',exact=True).click();page.wait_for_url('**/profile.html')
   expect(page.locator('#basic')).to_be_visible();self.assertEqual(page.locator('#basic #education').count(),0);self.assertEqual(page.locator('#business-profile-form > #education').count(),1)
   page.locator('[name=display_name]').fill('丁测试');page.locator('[name=public_visible]').check();page.get_by_role('button',name='保存资料',exact=True).click();expect(page.locator('#business-status')).to_contain_text('已保存')
   page.goto(self.env.url+'/content-editor.html');page.locator('[name=title]').fill('封面联调论文');page.locator('[name=summary]').fill('这是一段完整摘要');page.locator('[name=detail_venue]').fill('示例会议');page.locator('[name=detail_publication_date]').fill('2026-11-01')
   chunk=lambda kind,data:struct.pack('!I',len(data))+kind+data+struct.pack('!I',zlib.crc32(kind+data)&0xffffffff);image=io.BytesIO(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!IIBBBBB',320,180,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+bytes([33,109,184])*320)*180))+chunk(b'IEND',b''));page.locator('#cover-file').set_input_files({'name':'测试封面.png','mimeType':'image/png','buffer':image.getvalue()});page.get_by_role('button',name='上传封面',exact=True).click();expect(page.locator('.cover-uploader img')).to_be_visible()
   page.get_by_role('button',name='保存并生效',exact=True).click();page.wait_for_url('**/content-editor.html?id=*');expect(page.locator('.cover-uploader img')).to_be_visible();item_id=page.url.split('id=')[1]
   page.goto(self.env.url+'/data/papers/index.html');expect(page.locator('.content-teaser img')).to_be_visible();page.locator('#public-search [name=q]').fill('封');page.locator('#public-search button[type=submit]').click();expect(page.locator('#public-status')).to_contain_text('共 1');page.reload();expect(page.locator('#public-search [name=q]')).to_have_value('封')
   page.locator('#public-search [name=year]').fill('2025');page.locator('#public-search button[type=submit]').click();expect(page.locator('#public-status')).to_contain_text('共 0');page.get_by_role('button',name='重置',exact=True).click();expect(page.locator('#public-status')).to_contain_text('共 1')
   page.goto(self.env.url+'/content.html?id='+item_id);expect(page.locator('.detail-cover')).to_be_visible();expect(page.locator('.detail-article')).to_contain_text('示例会议');expect(page.locator('.detail-article')).to_contain_text('这是一段完整摘要')
   page.goto(self.env.url+'/data/members/index.html');expect(page.locator('.member-teaser')).to_contain_text('丁测试');page.get_by_role('link',name='老师',exact=True).last.click();expect(page.locator('#public-status')).to_contain_text('共 0');page.get_by_role('link',name='同学',exact=True).last.click();expect(page.locator('#public-status')).to_contain_text('共 1')
   page.locator('#globalSearch').fill('丁');page.locator('#globalSearch').press('Enter');expect(page.locator('.search-results')).to_contain_text('丁测试');page.locator('#globalSearch').press('Escape')
   self.assertEqual(page.locator('.site-quick').count(),0);page.get_by_role('link',name='科学研究',exact=True).click();page.wait_for_url('**/data/projects/index.html');expect(page.locator('.section-tabs')).to_contain_text('发表论文')
   page.set_viewport_size({'width':2550,'height':1200});self.assertGreater(page.locator('main').bounding_box()['width'],1600);EVIDENCE.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(EVIDENCE/'v11-wide.png'),full_page=True)
   page.set_viewport_size({'width':390,'height':844});page.get_by_role('button',name='菜单').click();expect(page.locator('.site-nav')).to_be_visible();self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'));page.screenshot(path=str(EVIDENCE/'v11-mobile.png'),full_page=True)
   self.assertEqual(errors,[])
  finally:context.close()

 def test_photo_carousel_uses_public_api_slides(self):
  context=self.browser.new_context();page=context.new_page()
  try:
   home={'schema_version':'v11','stats':{'members':0,'papers':0,'projects':0,'competitions':0},'research_areas':[],'news':[],'papers':[],'projects':[],'competitions':[],'members':[],'resources':[],'slides':[{'title':'公开团队合影一','url':'/content.html?id=1','image':{'url':'/lab-logo.png'}},{'title':'公开团队合影二','url':'/content.html?id=2','image':{'url':'/lab-logo.png'}}]}
   page.route('**/api/public/home/',lambda route:route.fulfill(json=home));page.goto(self.env.url+'/index.html');expect(page.locator('.home-slide h1')).to_have_text('公开团队合影一');page.get_by_role('button',name='下一张',exact=True).click();expect(page.locator('.home-slide h1')).to_have_text('公开团队合影二');page.get_by_role('button',name='暂停',exact=True).click();expect(page.get_by_role('button',name='播放',exact=True)).to_be_visible()
  finally:context.close()

 def test_competitions_and_honors_are_separate_categories(self):
  self.env.orm("""
from apps.accounts.models import User
from apps.content.models import ContentItem,ContentRevision,AwardDetail
from django.db import transaction
u=User.objects.create(username='award-'+__import__('secrets').token_hex(4),role='TEACHER')
with transaction.atomic():
 for category,title in [('COMPETITION','竞赛样本专属'),('HONOR','荣誉样本专属')]:
  item=ContentItem.objects.create(kind='AWARD',created_by=u)
  r=ContentRevision.objects.create(item=item,number=1,title=title,edited_by=u)
  AwardDetail.objects.create(revision=r,category=category)
  r.state='PUBLISHED';r.save(update_fields=['state']);item.published_revision=r;item.save()
result={}
""",{})
  context=self.browser.new_context();page=context.new_page()
  try:
   page.goto(self.env.url+'/data/competitions/index.html');expect(page.locator('#public-content')).to_contain_text('竞赛样本专属');expect(page.locator('#public-content')).not_to_contain_text('荣誉样本专属')
   page.locator('.section-tabs').get_by_role('link',name='荣誉奖励',exact=True).click();expect(page.locator('#public-content')).to_contain_text('荣誉样本专属');expect(page.locator('#public-content')).not_to_contain_text('竞赛样本专属')
  finally:context.close()

 def test_workspace_reset_ignores_late_old_filter_response(self):
  username='v11_race_'+secrets.token_hex(4);password=secrets.token_urlsafe(18)+'!A4';self.env.seed(username,password,'STUDENT',False)
  context=self.browser.new_context();page=context.new_page();pending=[]
  def response(title):return {'count':1,'next':None,'previous':None,'results':[{'id':'11111111-1111-1111-1111-111111111111','kind':'PAPER','revision':{'title':title},'visibility_scope':'PUBLIC','visible':True,'can_edit':False}]}
  def route_request(route):
   if 'q=stale' in route.request.url:pending.append(route)
   else:route.fulfill(json=response('最新结果'))
  try:
   page.goto(self.env.url+'/login.html');page.locator('[name=username]').fill(username);page.locator('[name=password]').fill(password);page.get_by_role('button',name='登录账号',exact=True).click();page.wait_for_url('**/profile.html')
   page.route('**/api/content/items/?*',route_request);page.goto(self.env.url+'/workspace.html');expect(page.locator('#workspace-list')).to_contain_text('最新结果')
   page.locator('#workspace-filter [name=q]').fill('stale')
   with page.expect_request(lambda r:'/api/content/items/' in r.url and 'q=stale' in r.url):page.get_by_role('button',name='筛选',exact=True).click()
   page.get_by_role('button',name='重置',exact=True).click();expect(page.locator('#workspace-list')).to_contain_text('最新结果');self.assertTrue(pending);pending[0].fulfill(json=response('过期错误结果'));page.wait_for_timeout(100)
   expect(page.locator('#workspace-list')).not_to_contain_text('过期错误结果');self.assertNotIn('q=stale',page.url)
  finally:context.close()
