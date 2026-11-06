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
 def fill_required(self,page):
  page.locator('[name=phone]').fill('13800138000');page.locator('[name=public_contact_email]').fill('member@example.org');page.locator('[name=cv_gender]').select_option('女');page.locator('[name=cv_political_status]').select_option('群众')
 def test_profile_choices_fixed_fields_and_navigation(self):
  user='v14_'+secrets.token_hex(4);password='Test123456';self.env.seed(user,password,'STUDENT',False)
  context=self.browser.new_context(viewport={'width':1440,'height':1000},reduced_motion='reduce');page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  try:
   self.login(page,user,password);expect(page.locator('[name=cv_gender]')).to_be_visible();self.assertEqual(page.locator('#privacy,#account-email-form,[name=intention],[name=public_contact_enabled]').count(),0)
   self.fill_required(page);page.locator('[name=highest_education]').select_option('硕士研究生');self.assertNotIn('选填',page.locator('#business-profile-form').inner_text());self.assertEqual(page.locator('[name=cv_education_note]').count(),0);page.locator('[name=display_name]').fill('固定字段成员');page.locator('[name=cv_gender]').select_option('女');page.locator('[name=cv_political_status]').select_option('群众');page.locator('[name=enrollment_year]').select_option('2025');page.locator('[name=native_province]').select_option('42');page.locator('[name=native_city]').select_option('4201');page.locator('[name=native_district]').select_option(index=1)
   page.get_by_role('button',name='添加教育经历',exact=True).click();page.locator('[name=school]').fill('不公开学校');page.locator('[name=education_level]').select_option('硕士研究生');page.locator('[name=degree]').select_option('硕士');page.get_by_role('button',name='保存资料',exact=True).click();expect(page.locator('#business-status')).to_contain_text('已保存');page.reload();expect(page.locator('[name=cv_gender]')).to_have_value('女');expect(page.locator('[name=native_city]')).to_have_value('4201')
   for target in ['education','profile-research','security','resume-section']:
    page.locator('.v10-sidebar a[href="#'+target+'"]').click();expect(page.locator('.v10-sidebar a[href="#'+target+'"]')).to_have_attribute('aria-current','true');self.assertEqual(page.locator('.v10-sidebar [aria-current=true]').count(),1)
   page.goto(self.env.url+'/data/members/index.html?q='+__import__('urllib.parse',fromlist=['quote']).quote('固定字段成员'));expect(page.locator('#public-content')).to_contain_text('固定字段成员');expect(page.locator('#public-content')).to_contain_text('硕士研究生');expect(page.locator('#public-content')).not_to_contain_text('不公开学校');self.assertEqual(errors,[])
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
   self.login(page,visitor,password);self.fill_required(page);page.locator('[name=display_name]').fill('PDF浏览器投递');page.get_by_role('button',name='保存资料',exact=True).click();expect(page.locator('#business-status')).to_contain_text('已保存')
   page.locator('#resume-file').set_input_files({'name':'超大简历.pdf','mimeType':'application/pdf','buffer':b'%PDF-'+b'0'*(20*1024*1024)});page.get_by_role('button',name='上传简历文件',exact=True).click();expect(page.locator('#resume-file-status')).to_contain_text('不超过20 MiB');expect(page.get_by_role('button',name='上传简历文件',exact=True)).to_be_enabled();page.locator('#resume-file').set_input_files({'name':'含文字图片链接简历.pdf','mimeType':'application/pdf','buffer':base64.b64decode(fixture['pdf'])});page.get_by_role('button',name='上传简历文件',exact=True).click();expect(page.locator('#resume-file-status')).to_contain_text('已上传');page.get_by_role('button',name='保存并预览投递',exact=True).click();expect(page.locator('#resume-preview')).to_contain_text('PDF浏览器投递');page.get_by_role('button',name='确认共享并投递',exact=True).click();expect(page.locator('#resume-status')).to_contain_text('已投递')
   self.login(staff,teacher,password);staff.goto(self.env.url+'/notifications.html');notice=staff.locator('#notification-list article').filter(has_text='PDF浏览器投递');notice.get_by_role('link',name='查看投递资料').click();expect(staff.locator('#submission-detail')).to_contain_text('PDF浏览器投递')
   staff.goto(self.env.url+'/content-editor.html');staff.wait_for_load_state('networkidle');staff.locator('[name=kind]').select_option('PAPER');staff.locator('[name=title]').fill('只限团队网页样本');staff.locator('[name=visibility_scope]').select_option('TEAM');staff.get_by_role('button',name='保存并生效',exact=True).click();staff.wait_for_url('**/content-editor.html?id=*');item=staff.url.split('id=')[1]
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
 def test_root_search_table_account_header_and_avatar(self):
  import base64
  name='rootui_'+secrets.token_hex(4);target='targetui_'+secrets.token_hex(4);password='Test123456'
  self.env.seed(name,password,'TEACHER',True);self.env.seed(target,password,'STUDENT',False)
  fixture=self.env.orm("""
from PIL import Image
from io import BytesIO
import base64
b=BytesIO();Image.new('RGB',(40,60),(50,120,180)).save(b,format='PNG')
result={'png':base64.b64encode(b.getvalue()).decode()}
""")
  context=self.browser.new_context(viewport={'width':1440,'height':1000});page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  try:
   self.login(page,name,password);expect(page.locator('[data-account-identity]')).to_contain_text(name);expect(page.locator('.account-avatar-fallback')).to_be_visible()
   self.fill_required(page);page.locator('[name=bio]').fill('上传头像时保留的未保存简介');page.locator('[name=avatar_file]').set_input_files({'name':'avatar.png','mimeType':'image/png','buffer':base64.b64decode(fixture['png'])});page.get_by_role('button',name='上传头像',exact=True).click();expect(page.locator('.v10-file-status').first).to_contain_text('头像已保存');expect(page.locator('.profile-photo-preview img')).to_be_visible();expect(page.locator('.account-avatar')).to_be_visible();expect(page.locator('[name=bio]')).to_have_value('上传头像时保留的未保存简介');self.assertLess(page.get_by_role('button',name='上传头像',exact=True).bounding_box()['width'],160);page.get_by_role('button',name='保存资料',exact=True).click();expect(page.locator('#business-status')).to_contain_text('已保存');expect(page.locator('.account-avatar')).to_be_visible();expect(page.locator('.account-avatar-fallback')).to_be_hidden()
   page.goto(self.env.url+'/manage/index.html');search=page.locator('[name=account_q]');expect(search).to_be_visible();search.fill(target);row=page.locator('.account-table tbody tr').filter(has_text=target);expect(row).to_have_count(1);expect(page.locator('.account-table th')).to_have_count(4);row.locator('[name=role]').select_option('TEACHER');row.get_by_role('button',name='保存身份与状态',exact=True).click();expect(page.locator('#business-status')).to_contain_text('已更新');expect(row.locator('[name=role]')).to_have_value('TEACHER')
   row.locator('[name=new_password]').fill('ChangedPass123');row.get_by_role('button',name='重置密码',exact=True).click();expect(page.locator('#business-status')).to_contain_text('密码已重置');expect(row.locator('[name=new_password]')).to_have_value('')
   search.fill('没有此账号');expect(page.locator('.account-table tbody')).to_contain_text('没有匹配的账号');search.fill(name);expect(page.locator('.account-table tbody')).to_contain_text(name)
   EVIDENCE.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(EVIDENCE/'root-account-table.png'),full_page=True)
   page.set_viewport_size({'width':390,'height':844});self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'));self.assertEqual(errors,[])
  finally:context.close()

 def test_all_home_cover_images_contain_and_stats_button_compact(self):
  import base64
  fixture=self.env.orm("""
from PIL import Image,ImageDraw
from io import BytesIO
import base64
im=Image.new('RGB',(200,600),'white');d=ImageDraw.Draw(im);d.rectangle((0,0,199,599),outline='blue',width=10);d.text((20,10),'TOP',fill='black');d.text((20,570),'BOTTOM',fill='black');b=BytesIO();im.save(b,format='PNG')
result={'png':base64.b64encode(b.getvalue()).decode()}
""")
  context=self.browser.new_context(viewport={'width':1440,'height':1000});page=context.new_page()
  try:
   data=page.request.get(self.env.url+'/api/site/home/').json();asset='/api/site/assets/11111111-1111-1111-1111-111111111111/'
   for key in ('papers','projects','news','competitions','resources'):data[key]=[{'id':'11111111-1111-1111-1111-111111111111','title':'完整封面验收','summary':'图片上下边缘应完整显示','cover':{'url':asset}}]
   page.route('**/api/site/home/',lambda route:route.fulfill(json=data));page.route('**'+asset,lambda route:route.fulfill(content_type='image/png',body=base64.b64decode(fixture['png'])))
   page.goto(self.env.url+'/index.html');images=page.locator('.home-card img');expect(images).to_have_count(5)
   for image in images.all():expect(image).to_have_css('object-fit','contain')
   page.locator('#home-papers').scroll_into_view_if_needed();page.screenshot(path=str(EVIDENCE/'home-complete-covers.png'))
   page.goto(self.env.url+'/statistics.html');button=page.get_by_role('button',name='更新统计',exact=True);expect(button).to_be_visible();self.assertLessEqual(button.bounding_box()['height'],48);self.assertGreaterEqual(button.bounding_box()['height'],40)
  finally:context.close()

 def test_management_lists_five_per_page_and_directory_photos(self):
  root='pagerroot_'+secrets.token_hex(4);prefix='pager_'+secrets.token_hex(4);password='Test123456'
  self.env.seed(root,password,'TEACHER',True)
  self.env.orm("""
from apps.accounts.models import User
from apps.members.models import MemberProfile,MemberRevision
from apps.assets.models import AssetFile
from PIL import Image
from io import BytesIO
from pathlib import Path
from django.conf import settings
import uuid
b=BytesIO();Image.new('RGB',(40,60),(30,120,160)).save(b,format='PNG');key=uuid.uuid4().hex+'.png';Path(settings.PRIVATE_MEDIA_ROOT).mkdir(parents=True,exist_ok=True);Path(settings.PRIVATE_MEDIA_ROOT,key).write_bytes(b.getvalue())
for i in range(7):
 u=User.objects.create_user(username='"""+prefix+"""'+str(i),role='STUDENT')
 p=MemberProfile.objects.create(user=u,created_by=u,updated_by=u)
 key=uuid.uuid4().hex+'.png';Path(settings.PRIVATE_MEDIA_ROOT,key).write_bytes(b.getvalue())
 a=AssetFile.objects.create(owner=u,purpose='avatar',storage_key=key,mime_type='image/png',size=len(b.getvalue()),sha256='0'*64,scan_status='CLEAN',visibility='PRIVATE')
 r=MemberRevision.objects.create(profile=p,number=1,display_name='"""+prefix+"""'+str(i),member_kind='STUDENT',state='PUBLISHED',avatar_asset=a,edited_by=u)
 p.published_revision=r;p.save()
result={}
""")
  context=self.browser.new_context(viewport={'width':1440,'height':1000});page=context.new_page()
  try:
   self.login(page,root,password);page.goto(self.env.url+'/manage/index.html');page.locator('#directory-filter [name=q]').fill(prefix);page.locator('#directory-filter').get_by_role('button',name='查找成员',exact=True).click();expect(page.locator('#directory-list article')).to_have_count(5);expect(page.locator('#directory-list .directory-photo img')).to_have_count(5);expect(page.locator('#directory-list .directory-photo img').first).to_be_visible();page.locator('#directory-list').get_by_role('button',name='下一页',exact=True).click();expect(page.locator('#directory-list article')).to_have_count(2);page.locator('#directory-list').get_by_role('button',name='上一页',exact=True).click();expect(page.locator('#directory-list article')).to_have_count(5)
   search=page.locator('[name=account_q]');search.fill(prefix);expect(page.locator('#account-list>.v10-caption')).to_have_text('共 7 个账号');expect(page.locator('.account-table tbody tr')).to_have_count(5);page.locator('#account-pages').get_by_role('button',name='下一页',exact=True).click();expect(page.locator('.account-table tbody tr')).to_have_count(2)
   EVIDENCE.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(EVIDENCE/'directory-avatar-pagination.png'),full_page=True)
  finally:context.close()
