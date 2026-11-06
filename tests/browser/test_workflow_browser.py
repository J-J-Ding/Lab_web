"""V5 real-browser contracts against disposable PostgreSQL and native pages."""
import secrets
import unittest
from playwright.sync_api import sync_playwright,expect
from support import Environment,EVIDENCE


class WorkflowBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env=Environment().start()
        try:
            cls.playwright=sync_playwright().start()
            cls.browser=cls.playwright.chromium.launch(channel='chromium',headless=True)
        except BaseException:
            cls.env.close();raise
    @classmethod
    def tearDownClass(cls):
        cls.browser.close();cls.playwright.stop();cls.env.close()
    def setUp(self):
        self.context=self.browser.new_context();self.page=self.context.new_page()
        self.page_errors=[];self.page.on('pageerror',lambda error:self.page_errors.append(str(error)))
        self.password=secrets.token_urlsafe(18)+'!7aA'
        self.username='v5_'+secrets.token_hex(5)
    def tearDown(self):
        self.context.close()
        self.assertEqual(self.page_errors,[],'Uncaught browser errors')
    def login(self,page=None,role='TEACHER',root=False):
        page=page or self.page
        username='v5_'+secrets.token_hex(5)
        self.env.seed(username,self.password,role,root)
        page.goto(self.env.url+'/login.html')
        page.get_by_label('用户名',exact=True).fill(username);page.get_by_label('密码',exact=True).fill(self.password)
        page.get_by_role('button',name='登录账号',exact=True).click()
        expect(page).to_have_url(self.env.url+'/profile.html');expect(page.locator('#profile-content')).to_be_visible()
        return username
    def test_new_pages_exist_and_anonymous_workspace_redirects(self):
        response=self.page.goto(self.env.url+'/workspace.html')
        self.assertEqual(response.status,200)
        expect(self.page).to_have_url(self.env.url+'/login.html');self.page.wait_for_load_state('load')
    def test_manager_pages_and_mobile_layout_keep_original_navigation(self):
        self.login()
        for width in (1440,390,320):
            self.page.set_viewport_size({'width':width,'height':900})
            for path in ('workspace.html','content-editor.html','member-application.html','manage/index.html','manage/users.html','manage/members.html','manage/reviews.html','manage/content.html'):
                response=self.page.goto(self.env.url+'/'+path)
                self.assertEqual(response.status,200)
                expect(self.page.locator('#business-content')).to_be_visible()
                if path=='content-editor.html':expect(self.page.locator('#content-form')).to_be_visible()
                self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= window.innerWidth + 1'),(path,width))
                if path in ('workspace.html','content-editor.html','member-application.html','manage/reviews.html'):
                    EVIDENCE.mkdir(parents=True,exist_ok=True)
                    self.page.screenshot(path=str(EVIDENCE/(path.replace('/','-').replace('.html','')+f'-{width}.png')),full_page=True)
                expect(self.page.get_by_role('navigation').get_by_role('link',name='新闻动态',exact=True)).to_be_visible()

    def test_author_and_peer_review_keep_old_public_version_until_approval(self):
        self.login();title='V5 blog '+secrets.token_hex(4)
        self.page.goto(self.env.url+'/content-editor.html')
        self.page.get_by_label('标题',exact=True).fill(title)
        self.page.get_by_label('正文',exact=True).fill('Original body')
        self.page.get_by_role('button',name='保存草稿',exact=True).click()
        expect(self.page.locator('#business-status')).to_contain_text('草稿已保存')
        item_id=self.page.url.split('id=')[1]
        self.page.get_by_role('button',name='提交审核',exact=True).click()
        expect(self.page.locator('#item-state')).to_contain_text('SUBMITTED')
        expect(self.page.get_by_role('button',name='审核通过',exact=True)).to_be_enabled()
        peer_context=self.browser.new_context();self.addCleanup(peer_context.close)
        peer=peer_context.new_page();self.login(peer,root=True)
        peer.goto(self.env.url+'/manage/reviews.html')
        peer.get_by_role('link',name=title,exact=True).click()
        peer.get_by_label('审核意见或核验理由',exact=True).fill('Verified by independent reviewer')
        peer.get_by_role('button',name='审核通过',exact=True).click()
        expect(peer.locator('#item-state')).to_contain_text('PUBLISHED')
        self.page.reload();self.page.get_by_role('button',name='创建新版本',exact=True).click()
        expect(self.page.locator('#item-state')).to_contain_text('DRAFT')
        self.page.get_by_label('标题',exact=True).fill(title+' B')
        self.page.get_by_role('button',name='保存草稿',exact=True).click()
        expect(self.page.locator('#business-status')).to_contain_text('草稿已保存')
        self.page.get_by_role('button',name='提交审核',exact=True).click()
        expect(self.page.locator('#item-state')).to_contain_text('SUBMITTED')
        result=self.env.orm("from apps.content.models import ContentItem; i=ContentItem.objects.get(pk=data['id']); result={'title':i.published_revision.title,'pending':i.working_revision.title}",{'id':item_id})
        self.assertEqual(result,{'title':title,'pending':title+' B'})
        peer.reload();expect(peer.locator('#published-preview')).to_contain_text(title)
        for width in (1440,390,320):
            peer.set_viewport_size({'width':width,'height':900})
            self.assertTrue(peer.evaluate('document.documentElement.scrollWidth <= window.innerWidth+1'))
            EVIDENCE.mkdir(parents=True,exist_ok=True)
            peer.screenshot(path=str(EVIDENCE/f'editor-review-pending-{width}.png'),full_page=True)
        peer.get_by_label('审核意见或核验理由',exact=True).fill('Approve new version')
        peer.get_by_role('button',name='审核通过',exact=True).click()
        expect(peer.locator('#business-status')).to_contain_text('审核通过')
        result=self.env.orm("from apps.content.models import ContentItem; result={'title':ContentItem.objects.get(pk=data['id']).published_revision.title}",{'id':item_id})
        self.assertEqual(result['title'],title+' B')

    def test_customer_application_teacher_identity_stays_student_role(self):
        username=self.login(role='CUSTOMER')
        self.page.goto(self.env.url+'/member-application.html')
        self.page.get_by_role('button',name='建立或重建资料草稿',exact=True).click()
        expect(self.page.get_by_label('展示姓名',exact=True)).to_be_enabled()
        self.page.get_by_label('展示姓名',exact=True).fill('Browser Applicant')
        self.page.get_by_label('个人主页标识',exact=True).fill('member-'+secrets.token_hex(4))
        self.page.get_by_role('button',name='保存成员草稿',exact=True).click()
        expect(self.page.locator('#business-status')).to_contain_text('成员草稿已保存')
        self.page.get_by_label('申请身份',exact=True).select_option('TEACHER')
        self.page.get_by_label('申请说明',exact=True).fill('Please verify teacher identity only')
        self.page.get_by_role('button',name='提交身份申请',exact=True).click()
        expect(self.page.locator('#application-list')).to_contain_text('SUBMITTED')
        manager_context=self.browser.new_context();self.addCleanup(manager_context.close)
        manager=manager_context.new_page();self.login(manager)
        manager.goto(self.env.url+'/manage/members.html')
        row=manager.locator('#member-application-tasks article').filter(has_text=username)
        row.get_by_role('textbox').fill('Independently verified teacher identity')
        row.get_by_role('button',name='通过身份申请',exact=True).click()
        expect(manager.locator('#business-status')).to_contain_text('身份申请已处理')
        result=self.env.orm("u=User.objects.get(username=data['name']);result={'role':u.role,'kind':u.member_profile.draft_revision.member_kind}",{'name':username})
        self.assertEqual(result,{'role':'STUDENT','kind':'TEACHER'})
        self.page.reload();expect(self.page.locator('#application-list')).to_contain_text('APPROVED')

    def test_private_avatar_upload_and_management_denial_and_logout(self):
        import base64
        self.login(role='CUSTOMER')
        self.page.goto(self.env.url+'/manage/users.html')
        expect(self.page.locator('#business-status')).to_contain_text('无管理权限')
        expect(self.page.locator('#business-content')).to_be_hidden()
        self.page.goto(self.env.url+'/member-application.html')
        self.page.get_by_role('button',name='建立或重建资料草稿',exact=True).click()
        expect(self.page.get_by_label('展示姓名',exact=True)).to_be_enabled()
        png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
        self.page.locator('#avatar-file').set_input_files({'name':'avatar.png','mimeType':'image/png','buffer':png})
        self.page.get_by_role('button',name='上传头像',exact=True).click()
        expect(self.page.locator('#avatar-result')).to_contain_text('头像已安全保存')
        self.page.get_by_role('navigation').get_by_role('button',name='退出登录',exact=True).click()
        expect(self.page).to_have_url(self.env.url+'/login.html');self.page.wait_for_load_state('load')
        self.page.goto(self.env.url+'/workspace.html')
        expect(self.page).to_have_url(self.env.url+'/login.html');self.page.wait_for_load_state('load')

    def test_user_management_creates_without_admin_option_and_no_password_prefill(self):
        self.login();name='managed_'+secrets.token_hex(4)
        self.page.goto(self.env.url+'/manage/users.html')
        expect(self.page.locator('#business-content')).to_be_visible()
        self.assertEqual(self.page.locator('#user-role option[value="ADMIN"]').count(),0)
        self.page.get_by_label('用户名',exact=True).fill(name)
        self.page.get_by_label('业务角色',exact=True).select_option('STUDENT')
        self.page.get_by_label('初始密码（仅新建时填写）',exact=True).fill(self.password)
        self.page.get_by_role('button',name='保存用户',exact=True).click()
        expect(self.page.locator('#business-status')).to_contain_text('用户已保存')
        self.page.get_by_role('button',name='编辑 '+name,exact=True).click()
        expect(self.page.locator('#user-password')).to_have_value('')
        expect(self.page.locator('#user-password')).to_be_disabled()
        result=self.env.orm("u=User.objects.get(username=data['name']);result={'role':u.role,'staff':u.is_staff,'root':u.is_superuser}",{'name':name})
        self.assertEqual(result,{'role':'STUDENT','staff':False,'root':False})

    def test_submit_blocks_unsaved_editor_changes_without_losing_input(self):
        self.login();title='Saved '+secrets.token_hex(4)
        self.page.goto(self.env.url+'/content-editor.html')
        self.page.get_by_label('标题',exact=True).fill(title)
        self.page.get_by_label('正文',exact=True).fill('Saved body')
        self.page.get_by_role('button',name='保存草稿',exact=True).click()
        expect(self.page.locator('#business-status')).to_contain_text('草稿已保存')
        self.page.get_by_label('标题',exact=True).fill('Unsaved new title')
        self.page.get_by_role('button',name='提交审核',exact=True).click()
        expect(self.page.locator('#business-status')).to_contain_text('先保存')
        expect(self.page.get_by_label('标题',exact=True)).to_have_value('Unsaved new title')
        expect(self.page.locator('#item-state')).to_contain_text('DRAFT')

    def test_member_submit_and_privacy_restrict_preserve_unsaved_input(self):
        username=self.login(role='STUDENT')
        self.env.orm("from apps.members.models import MemberProfile;u=User.objects.get(username=data['name']);MemberProfile.objects.create(user=u,membership_status='ACTIVE');result={}",{'name':username})
        self.page.goto(self.env.url+'/member-application.html')
        self.page.get_by_role('button',name='建立或重建资料草稿',exact=True).click()
        self.page.get_by_label('展示姓名',exact=True).fill('Saved member')
        self.page.get_by_label('个人主页标识',exact=True).fill('saved-member-'+secrets.token_hex(4))
        self.page.get_by_role('button',name='保存成员草稿',exact=True).click()
        expect(self.page.locator('#business-status')).to_contain_text('成员草稿已保存')
        self.page.get_by_label('个人简介',exact=True).fill('Unsaved member bio')
        self.page.get_by_role('button',name='提交资料审核',exact=True).click()
        expect(self.page.locator('#business-status')).to_contain_text('先保存')
        expect(self.page.get_by_label('个人简介',exact=True)).to_have_value('Unsaved member bio')
        self.page.get_by_role('button',name='停止公开联系邮箱',exact=True).click()
        expect(self.page.locator('#business-status')).to_contain_text('隐私范围已立即收紧')
        expect(self.page.get_by_label('个人简介',exact=True)).to_have_value('Unsaved member bio')
        self.page.get_by_role('button',name='保存成员草稿',exact=True).click()
        expect(self.page.locator('#business-status')).to_contain_text('成员草稿已保存')

    def test_root_admin_and_teacher_can_publish_own_submission(self):
        for role,root in [('CUSTOMER',True),('ADMIN',False),('TEACHER',False)]:
            with self.subTest(role='ROOT' if root else role):
                username=self.login(role=role,root=root)
                title='Self review '+secrets.token_hex(5)
                self.page.goto(self.env.url+'/content-editor.html')
                self.page.get_by_label('标题',exact=True).fill(title)
                self.page.get_by_label('正文',exact=True).fill('Self-reviewed example body')
                self.page.get_by_role('button',name='保存草稿',exact=True).click()
                expect(self.page.locator('#business-status')).to_contain_text('草稿已保存')
                item_id=self.page.url.split('id=')[1]
                self.page.get_by_role('button',name='提交审核',exact=True).click()
                expect(self.page.locator('#item-state')).to_contain_text('SUBMITTED')
                approve=self.page.get_by_role('button',name='审核通过',exact=True)
                expect(approve).to_be_enabled()
                self.page.get_by_label('审核意见或核验理由',exact=True).fill('Explicit permitted self review')
                approve.click();expect(self.page.locator('#item-state')).to_contain_text('PUBLISHED')
                audit=self.env.orm("from apps.workflow.models import ReviewDecision; result={'reviewer':ReviewDecision.objects.get(content_revision__item_id=data['id']).reviewer.username}",{'id':item_id})
                self.assertEqual(audit['reviewer'],username)
                response=self.context.request.get(self.env.url+'/api/public/content/'+item_id+'/')
                self.assertEqual(response.status,200);self.assertEqual(response.json()['title'],title)
