import base64,secrets,unittest,json
from io import BytesIO
from zipfile import ZipFile
from playwright.sync_api import sync_playwright,expect
from support import Environment,EVIDENCE,launch_browser

class AIBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env=Environment(ai_enabled=True).start()
        try:cls.p=sync_playwright().start();cls.browser=launch_browser(cls.p)
        except BaseException:cls.env.close();raise
    @classmethod
    def tearDownClass(cls):cls.browser.close();cls.p.stop();cls.env.close()
    def setUp(self):
        self.context=self.browser.new_context();self.page=self.context.new_page();self.errors=[]
        self.page.on('pageerror',lambda e:self.errors.append(str(e)))
    def tearDown(self):self.context.close();self.assertEqual(self.errors,[])
    def login(self,role='TEACHER'):
        username='ai_'+secrets.token_hex(5);password=secrets.token_urlsafe(18)+'!7Az';self.env.seed(username,password,role,False)
        self.page.goto(self.env.url+'/login.html');self.page.get_by_label('用户名',exact=True).fill(username);self.page.get_by_label('密码',exact=True).fill(password);self.page.get_by_role('button',name='登录账号',exact=True).click();expect(self.page).to_have_url(self.env.url+'/profile.html');return username
    def test_anonymous_redirect(self):
        self.page.goto(self.env.url+'/ai-import.html');expect(self.page).to_have_url(self.env.url+'/login.html')
    def test_preview_consent_candidate_then_draft(self):
        username=self.login();self.page.goto(self.env.url+'/ai-import.html');expect(self.page.locator('#business-content')).to_be_visible()
        out=BytesIO()
        with ZipFile(out,'w') as z:
            z.writestr('[Content_Types].xml','<Types><Override ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
            z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Example title. Example body.</w:t></w:r></w:p></w:body></w:document>')
        self.page.get_by_label('导入目标',exact=True).select_option('BLOG');self.page.get_by_label('私有文档',exact=True).set_input_files({'name':'example.docx','mimeType':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','buffer':out.getvalue()})
        self.page.get_by_label('同意在本服务器解析私有文件',exact=True).check();self.page.get_by_role('button',name='上传并本地解析',exact=True).click();expect(self.page.locator('#ai-job-state')).to_contain_text('QUEUED')
        job_id=self.page.locator('#ai-job-id').inner_text()
        self.env.orm("from apps.ai_assistant.tasks import run_once; result={'worked':run_once()}",{})
        self.page.get_by_role('button',name='刷新当前任务',exact=True).click();expect(self.page.locator('#ai-job-state')).to_contain_text('AWAITING_CONSENT')
        expect(self.page.get_by_label('将发送的脱敏文本',exact=True)).to_have_value(__import__('re').compile('.*Example title.*',__import__('re').S))
        self.page.get_by_label('同意将上方脱敏文本发送至 DeepSeek',exact=True).check();self.page.get_by_role('button',name='授权并生成候选',exact=True).click();expect(self.page.locator('#ai-job-state')).to_contain_text('QUEUED')
        self.env.orm("""
from apps.ai_assistant.tasks import run_once
from apps.ai_assistant.providers.base import ProviderResult
class FixtureProvider:
 def extract_fields(self,*args):
  return ProviderResult({'schema_version':1,'target_type':'BLOG','records':[{'fields':{'title':'Example title','detail':{'body':'Example body.'}},'evidence':[{'field':'title','page':1,'excerpt':'Example title'},{'field':'detail.body','page':1,'excerpt':'Example body.'}]}]},10,20,'browser-fixture')
result={'worked':run_once(FixtureProvider())}
""",{})
        self.page.get_by_role('button',name='刷新当前任务',exact=True).click();expect(self.page.locator('#ai-job-state')).to_contain_text('READY')
        self.page.get_by_label('确认字段 title',exact=True).check();self.page.get_by_label('确认字段 detail.body',exact=True).check()
        self.page.get_by_label('我已逐项核对所选字段和来源',exact=True).check();self.page.get_by_role('button',name='保存为草稿',exact=True).click()
        expect(self.page.get_by_role('link',name='打开已保存草稿',exact=True)).to_be_visible()
        result=self.env.orm("from apps.content.models import ContentItem; rows=ContentItem.objects.filter(created_by__username=data['username']); result={'count':rows.count(),'published':rows.filter(published_revision__isnull=False).count()}",{'username':username})
        self.assertEqual(result,{'count':1,'published':0})
        expect(self.page.get_by_role('button',name='保存为草稿',exact=True)).to_be_disabled()
        for width in (1440,768,390,320):
            self.page.set_viewport_size({'width':width,'height':900});self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= innerWidth+1'))
            EVIDENCE.mkdir(parents=True,exist_ok=True);self.page.screenshot(path=str(EVIDENCE/f'ai-import-{width}.png'),full_page=True)
    def test_customer_only_member_and_private_state_cleared_on_logout(self):
        self.login('CUSTOMER');self.page.goto(self.env.url+'/ai-import.html');expect(self.page.locator('#business-content')).to_be_visible()
        expect(self.page.get_by_label('导入目标',exact=True).locator('option:not([disabled])')).to_have_count(1)
        self.page.get_by_role('navigation').get_by_role('button',name='退出登录',exact=True).click();expect(self.page).to_have_url(self.env.url+'/login.html')
    def test_duplicate_hints_and_explicit_author_selection(self):
        self.login();data=self.env.orm("""
from django.db import transaction
from django.utils import timezone
from apps.accounts.models import User
from apps.content.services import create_content
from apps.content.models import Contributor
from apps.ai_assistant.models import AIImportJob,AICandidate
from apps.ai_assistant.quota import reserve
user=User.objects.filter(username__startswith='ai_').order_by('-id').first()
with transaction.atomic():
 item=create_content(user,'PAPER','Existing paper example',{'doi':'10.1234/example'})
 author=Contributor.objects.create(created_by=user,display_name='Example Author')
 job=AIImportJob.objects.create(owner=user,target_type='PAPER',state='READY',source_pages=[{'page':1,'text':'Example Author, Example new paper, 10.1234/example'}],source_preview='Example Author, Example new paper, 10.1234/example',selected_text='Example Author, Example new paper, 10.1234/example',expires_at=timezone.now()+timezone.timedelta(days=30))
 reserve(user,job)
 AICandidate.objects.create(job=job,expires_at=job.expires_at,data={'schema_version':1,'target_type':'PAPER','records':[{'fields':{'title':'Example new paper','detail':{'doi':'10.1234/example'},'authors':[{'name':'Example Author'}]},'evidence':[],'uncertain_fields':[],'warnings':[]}],'warnings':[]})
result={'job':str(job.pk),'author':str(author.pk)}
""",{})
        self.page.goto(self.env.url+'/ai-import.html')
        self.page.get_by_role('button',name=__import__('re').compile(data['job'])).click()
        self.page.get_by_role('button',name='刷新匹配提示',exact=True).click()
        expect(self.page.locator('#ai-duplicates')).to_contain_text('Existing paper example')
        self.page.locator('#ai-author-0').select_option(data['author'])
        self.page.get_by_label('确认字段 title',exact=True).check();self.page.get_by_label('确认字段 authors',exact=True).check();self.page.get_by_label('我已逐项核对所选字段和来源',exact=True).check()
        self.page.get_by_role('button',name='保存为草稿',exact=True).click();expect(self.page.get_by_role('link',name='打开已保存草稿',exact=True)).to_be_visible()
        result=self.env.orm("from apps.content.models import ContentItem; item=ContentItem.objects.get(working_revision__title='Example new paper'); result={'author':str(item.working_revision.contributions.get().contributor_id),'published':item.published_revision_id is not None}",{})
        self.assertEqual(result,{'author':data['author'],'published':False})
