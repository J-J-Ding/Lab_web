"""V6 public pages, actual Chromium + isolated PostgreSQL."""
import unittest
from playwright.sync_api import sync_playwright,expect
from support import Environment,EVIDENCE,launch_browser

class PublicBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env=Environment().start()
        try:
            cls.p=sync_playwright().start();cls.browser=launch_browser(cls.p)
        except BaseException:cls.env.close();raise
    @classmethod
    def tearDownClass(cls):cls.browser.close();cls.p.stop();cls.env.close()
    def setUp(self):
        self.context=self.browser.new_context();self.page=self.context.new_page();self.errors=[]
        self.page.on('pageerror',lambda e:self.errors.append(str(e)))
    def tearDown(self):self.context.close();self.assertEqual(self.errors,[])
    def seed(self):
        return self.env.orm("""
from django.db import transaction
from apps.accounts.models import User
from apps.content.services import create_content
from apps.content.models import ContentItem,ContentRevision
actor=User.objects.create(username='public_'+__import__('secrets').token_hex(6),role='TEACHER')
i=create_content(actor,'BLOG','Browser public sample',{'body':'<script>unsafe()</script> rendered as text'})
with transaction.atomic():
 ContentRevision.objects.filter(pk=i.working_revision_id).update(state='PUBLISHED')
 ContentItem.objects.filter(pk=i.pk).update(published_revision=i.working_revision,working_revision=None)
result={'id':str(i.pk)}
""",{})
    def test_nine_categories_responsive_navigation(self):
        for width in (1440,768,390,320):
            self.page.set_viewport_size({'width':width,'height':900})
            for category in ('papers','projects','competitions','publications','members','graduates','activities','news','blogs'):
                r=self.page.goto(self.env.url+f'/data/{category}/index.html');self.assertEqual(r.status,200)
                self.page.get_by_label('年份',exact=True).fill('1900')
                self.page.get_by_role('button',name='搜索',exact=True).click()
                expect(self.page.locator('#public-status')).to_contain_text('暂无')
                expect(self.page.get_by_role('navigation').get_by_role('link',name='新闻动态',exact=True)).to_be_visible()
                self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth+1'),(category,width))
            EVIDENCE.mkdir(parents=True,exist_ok=True)
            self.page.screenshot(path=str(EVIDENCE/f'public-list-{width}.png'),full_page=True)
    def test_detail_text_and_unpublish(self):
        row=self.seed();self.page.goto(self.env.url+'/content.html?id='+row['id'])
        expect(self.page.locator('#public-content')).to_contain_text('Browser public sample')
        expect(self.page.locator('#public-content')).to_contain_text('<script>unsafe()</script>')
        self.assertEqual(self.page.locator('#public-content script').count(),0)
        self.env.orm("from apps.content.models import ContentItem; ContentItem.objects.filter(pk=data['id']).update(visibility_gate=False); result={}",row)
        self.page.reload();expect(self.page.locator('#public-status')).to_contain_text('不存在')
        self.assertNotIn('Browser public sample',self.page.locator('#public-content').inner_text())
    def test_api_failure_retry_and_search_validation(self):
        self.page.route('**/api/public/content/**',lambda route:route.fulfill(status=503,content_type='application/json',body='{"detail":"Unavailable"}'))
        self.page.goto(self.env.url+'/data/blogs/index.html')
        expect(self.page.locator('#public-status')).to_contain_text('暂不可用')
        self.page.get_by_role('button',name='重试',exact=True).click()
        expect(self.page.locator('#public-status')).to_contain_text('暂不可用')
        self.page.unroute('**/api/public/content/**')
        self.page.get_by_label('搜索公开内容',exact=True).fill('x')
        self.page.get_by_role('button',name='搜索',exact=True).click()
        expect(self.page.locator('#public-status')).to_contain_text('至少')
    def test_legacy_shell_no_static_fallback(self):
        path='/data/papers/202308_A new deep clustering method with application to customer selection for demand response program/index.html'
        self.page.goto(self.env.url+path)
        expect(self.page.locator('#public-status')).to_contain_text('不存在')
        self.assertNotIn('demand response program',self.page.locator('#public-content').inner_text())
    def test_legacy_media_inventory_no_longer_serves_original_bytes(self):
        import json
        from pathlib import Path
        from urllib.parse import quote
        rows=json.loads((Path(__file__).resolve().parents[2]/'legacy_samples/inventory.json').read_text())
        for row in rows:
            response=self.context.request.get(self.env.url+quote(row['path'],safe='/'))
            self.assertEqual(response.status,404 if row['action']=='offline-only' else 200,row['path'])
        self.assertEqual(self.context.request.get(self.env.url+'/legacy_samples/manifest.json').status,404)
    def test_editor_upload_attachment_and_persist_reference(self):
        import secrets,base64
        name='v6_'+secrets.token_hex(5);password=secrets.token_urlsafe(18)+'!A4'
        self.env.seed(name,password,'TEACHER',False)
        self.page.goto(self.env.url+'/login.html');self.page.get_by_label('用户名',exact=True).fill(name);self.page.get_by_label('密码',exact=True).fill(password)
        self.page.get_by_role('button',name='登录账号',exact=True).click();expect(self.page).to_have_url(self.env.url+'/profile.html')
        self.page.goto(self.env.url+'/content-editor.html');self.page.get_by_label('标题',exact=True).fill('Image attachment example');self.page.get_by_label('正文',exact=True).fill('Body')
        self.page.get_by_label('内容附件',exact=True).set_input_files({'name':'example.png','mimeType':'image/png','buffer':base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')})
        self.page.get_by_role('button',name='上传附件',exact=True).click()
        expect(self.page.locator('#business-status')).to_contain_text('附件已上传')
        self.page.get_by_role('button',name='保存草稿',exact=True).click();expect(self.page.locator('#business-status')).to_contain_text('草稿已保存')
        item_id=self.page.url.split('id=')[1]
        result=self.env.orm("from apps.content.models import ContentItem; i=ContentItem.objects.get(pk=data['id']); result={'files':i.working_revision.assets.count(),'public':i.published_revision_id is not None}",{'id':item_id})
        self.assertEqual(result,{'files':1,'public':False})
    def test_navigation_search_uses_published_api(self):
        row=self.seed();self.page.goto(self.env.url+'/index.html')
        self.page.locator('#globalSearch').fill('Browser public sample')
        result=self.page.locator('.search-results').get_by_role('link',name='Browser public sample',exact=True)
        expect(result).to_be_visible();result.click()
        expect(self.page).to_have_url(self.env.url+'/content.html?id='+row['id'])
    def test_member_achievements_and_project_outputs_render_nonempty(self):
        row=self.env.orm("""
from django.db import transaction
from apps.accounts.models import User
from apps.content.services import create_content
from apps.content.models import ContentItem,ContentRevision,Contributor,RevisionContribution,ContentProjectLink
from apps.members.models import MemberProfile,MemberRevision,MemberSlug
import secrets
actor=User.objects.create(username='linked_'+secrets.token_hex(5),role='TEACHER')
p=MemberProfile.objects.create(public_visible=False,membership_status='ACTIVE')
slug='linked-'+secrets.token_hex(5)
r=MemberRevision.objects.create(profile=p,number=1,display_name='Linked example',slug=slug)
MemberSlug.objects.create(profile=p,slug=slug)
c=Contributor.objects.create(member_profile=p,display_name='Example Author')
project=create_content(actor,'PROJECT','Browser linked project',{'funder':'Example','start_date':'2026-01-01'})
paper=create_content(actor,'PAPER','Browser linked paper',{'venue':'Example','publication_date':'2026-01-01'})
RevisionContribution.objects.create(revision=paper.working_revision,contributor=c,contribution_role='AUTHOR',position=1,approved_display_name='Example Author')
ContentProjectLink.objects.create(source_revision=paper.working_revision,target_project=project)
with transaction.atomic():
 MemberRevision.objects.filter(pk=r.pk).update(state='PUBLISHED')
 MemberProfile.objects.filter(pk=p.pk).update(published_revision=r,public_visible=True)
 for i in (project,paper):
  ContentRevision.objects.filter(pk=i.working_revision_id).update(state='PUBLISHED')
  ContentItem.objects.filter(pk=i.pk).update(published_revision=i.working_revision,working_revision=None)
result={'slug':slug,'project':str(project.pk),'paper':str(paper.pk)}
""",{})
        for path in ['/member.html?slug='+row['slug'],'/content.html?id='+row['project']]:
            self.page.goto(self.env.url+path)
            link=self.page.locator('#public-content').get_by_role('link',name='Browser linked paper',exact=True)
            expect(link).to_be_visible();self.assertTrue(link.get_attribute('href').endswith('/content.html?id='+row['paper']))
