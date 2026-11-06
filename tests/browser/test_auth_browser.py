import secrets
import unittest
import time

from playwright.sync_api import sync_playwright, expect, Error as PlaywrightError
from support import Environment, EVIDENCE,launch_browser


class AuthBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = Environment().start()
        cls.addClassCleanup(cls.env.close)
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        cls.browser = launch_browser(cls.playwright, back_forward_cache=True)
        cls.addClassCleanup(cls.browser.close)
        EVIDENCE.mkdir(parents=True, exist_ok=True)

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width':1440,'height':900})
        self.page = self.context.new_page()
        self.page.set_default_timeout(7000)
        self.username = 'browser_' + secrets.token_hex(5)
        self.password = secrets.token_urlsafe(18) + '!aA3'

    def tearDown(self):
        self.context.close()

    def go(self, path):
        response=self.page.goto(self.env.url + path)
        self.assertEqual(response.status,200)
        return response

    def test_auth_pages_exist(self):
        for path, title in [('/register.html','注册账号'),('/login.html','登录账号'),('/profile.html','个人中心')]:
            with self.subTest(path=path):
                response = self.go(path)
                self.assertEqual(response.status, 200)
                if path != '/profile.html':
                    expect(self.page.get_by_role('heading', name=title, exact=True)).to_be_visible()
                else:
                    expect(self.page).to_have_url(self.env.url + '/login.html')
                    self.page.wait_for_load_state('load')

    def test_navigation_has_auth_entry(self):
        self.go('/index.html')
        expect(self.page.get_by_role('navigation').get_by_role('link', name='登录', exact=True)).to_be_visible()
        expect(self.page.get_by_role('navigation').get_by_role('link', name='注册', exact=True)).to_be_visible()

    def test_unauthenticated_profile_redirects(self):
        self.go('/profile.html')
        expect(self.page).to_have_url(self.env.url + '/login.html')
        self.page.wait_for_load_state('load')

    def seed(self, role='CUSTOMER', root=False):
        return self.env.seed(self.username, self.password, role, root)

    def login(self, username=None, password=None):
        self.go('/login.html')
        self.page.get_by_label('用户名', exact=True).fill(username or self.username)
        self.page.get_by_label('密码', exact=True).fill(password or self.password)
        self.page.get_by_role('button', name='登录账号', exact=True).click()
        expect(self.page).to_have_url(self.env.url + '/profile.html')
        expect(self.page.locator('#profile-content')).to_be_visible()

    def test_register_customer_then_login_refresh_and_navigation(self):
        self.go('/register.html')
        self.page.get_by_label('用户名', exact=True).fill(self.username)
        self.page.get_by_label('密码', exact=True).fill(self.password)
        self.page.get_by_label('确认密码', exact=True).fill(self.password)
        self.page.get_by_role('button', name='注册账号', exact=True).click()
        expect(self.page.locator('#register-status')).to_contain_text('注册成功')
        result = self.env.orm('user=User.objects.get(username=data["username"]); result={"role":user.role,"staff":user.is_staff,"root":user.is_superuser,"hashed":user.password != data["password"],"valid":user.check_password(data["password"])}', {'username':self.username,'password':self.password})
        self.assertEqual(result, {'role':'CUSTOMER','staff':False,'root':False,'hashed':True,'valid':True})
        self.page.get_by_role('link', name='前往登录', exact=True).click()
        self.page.get_by_label('用户名', exact=True).fill(self.username)
        self.page.get_by_label('密码', exact=True).fill(self.password)
        self.page.get_by_role('button', name='登录账号', exact=True).click()
        expect(self.page).to_have_url(self.env.url + '/profile.html')
        expect(self.page.locator('[data-user-role]')).to_contain_text('CUSTOMER')
        self.page.reload()
        expect(self.page.locator('#profile-content')).to_be_visible()
        self.assertEqual(self.page.evaluate('localStorage.length + sessionStorage.length'), 0)
        self.page.get_by_role('navigation').get_by_role('link', name='新闻动态', exact=True).click()
        expect(self.page.get_by_role('navigation').get_by_role('link', name='个人中心', exact=True)).to_be_visible()
        cookies = self.context.cookies()
        self.assertTrue(any(c['name']=='sessionid' and c['httpOnly'] for c in cookies))

    def test_duplicate_weak_and_mismatched_registration(self):
        self.seed()
        self.go('/register.html')
        self.page.get_by_label('用户名', exact=True).fill(self.username)
        self.page.get_by_label('密码', exact=True).fill(self.password)
        self.page.get_by_label('确认密码', exact=True).fill(self.password)
        self.page.get_by_role('button', name='注册账号', exact=True).click()
        expect(self.page.locator('#register-status')).to_contain_text('用户名已存在')
        self.page.get_by_label('用户名', exact=True).fill(self.username + '_weak')
        self.page.get_by_label('密码', exact=True).fill('1234567890')
        self.page.get_by_label('确认密码', exact=True).fill('1234567890')
        self.page.get_by_role('button', name='注册账号', exact=True).click()
        expect(self.page.locator('#register-status')).to_contain_text('密码')
        self.page.get_by_label('密码', exact=True).fill(self.password)
        self.page.get_by_label('确认密码', exact=True).fill(self.password + 'mismatch')
        self.page.get_by_role('button', name='注册账号', exact=True).click()
        expect(self.page.locator('#register-status')).to_contain_text('不一致')
        result=self.env.orm('result={"count":User.objects.filter(username=data["username"]).count(),"weak":User.objects.filter(username=data["username"]+"_weak").exists()}',{'username':self.username})
        self.assertEqual(result,{'count':1,'weak':False})

    def test_login_failure_then_success(self):
        self.seed()
        self.go('/login.html')
        self.page.get_by_label('用户名', exact=True).fill(self.username)
        self.page.get_by_label('密码', exact=True).fill('incorrect-password')
        self.page.get_by_role('button', name='登录账号', exact=True).click()
        expect(self.page.locator('#login-status')).to_contain_text('用户名或密码错误')
        self.assertTrue(self.page.url.endswith('/login.html'))
        self.page.get_by_label('密码', exact=True).fill(self.password)
        self.page.get_by_role('button', name='登录账号', exact=True).click()
        expect(self.page).to_have_url(self.env.url+'/profile.html')

    def test_profile_update_and_safe_text(self):
        self.seed()
        self.login()
        text = '<img src=x onerror="window.hacked=true">'
        self.page.get_by_label('名字', exact=True).fill(text)
        self.page.get_by_label('姓氏', exact=True).fill('测试')
        self.page.get_by_label('电子邮箱', exact=True).fill('browser-test@example.org')
        self.page.get_by_role('button', name='保存资料', exact=True).click()
        expect(self.page.locator('#profile-status')).to_contain_text('资料已保存')
        self.page.reload()
        expect(self.page.get_by_label('名字', exact=True)).to_have_value(text)
        self.assertFalse(self.page.evaluate('Boolean(window.hacked)'))
        result=self.env.orm('user=User.objects.get(username=data["username"]); result={"name":user.first_name,"email":user.email}',{'username':self.username})
        self.assertEqual(result,{'name':text,'email':'browser-test@example.org'})

    def test_password_change_old_password_invalid_and_logout(self):
        self.seed()
        self.login()
        new_password=secrets.token_urlsafe(18)+'!bB4'
        self.page.get_by_label('旧密码', exact=True).fill(self.password)
        self.page.get_by_label('新密码', exact=True).fill(new_password)
        self.page.get_by_label('确认新密码', exact=True).fill(new_password)
        self.page.get_by_role('button', name='修改密码', exact=True).click()
        expect(self.page.locator('#password-status')).to_contain_text('密码已修改',timeout=15000)
        expect(self.page.get_by_label('旧密码', exact=True)).to_have_value('')
        self.page.get_by_role('navigation').get_by_role('button',name='退出登录',exact=True).click()
        expect(self.page).to_have_url(self.env.url+'/login.html')
        self.page.get_by_label('用户名',exact=True).fill(self.username)
        self.page.get_by_label('密码',exact=True).fill(self.password)
        self.page.get_by_role('button',name='登录账号',exact=True).click()
        expect(self.page.locator('#login-status')).to_contain_text('用户名或密码错误')
        self.page.get_by_label('密码',exact=True).fill(new_password)
        self.page.get_by_role('button',name='登录账号',exact=True).click()
        expect(self.page).to_have_url(self.env.url+'/profile.html')

    def test_csrf_rotation_and_missing_wrong_tokens_rejected(self):
        self.seed()
        self.go('/login.html')
        expect(self.page.get_by_role('button',name='登录账号',exact=True)).to_be_enabled()
        before=next(c['value'] for c in self.context.cookies() if c['name']=='csrftoken')
        self.login()
        after=next(c['value'] for c in self.context.cookies() if c['name']=='csrftoken')
        self.assertTrue(before!=after,'Login must rotate CSRF token')
        self.page.get_by_label('名字',exact=True).fill('CSRF valid')
        with self.page.expect_request(lambda r:r.method=='PATCH' and r.url.endswith('/api/auth/me/')) as request:
            self.page.get_by_role('button',name='保存资料',exact=True).click()
        self.assertTrue(request.value.headers.get('x-csrftoken')==after,'Write must send rotated CSRF token')
        expect(self.page.locator('#profile-status')).to_contain_text('资料已保存')
        codes=self.page.evaluate('''async () => {
          const results=[];
          for(const token of [null, 'x'.repeat(32)]){
            const headers={'Content-Type':'application/json'};
            if(token) headers['X-CSRFToken']=token;
            const response=await fetch('/api/auth/me/',{method:'PATCH',credentials:'same-origin',headers,body:JSON.stringify({first_name:'forbidden'})});
            results.push(response.status);
          }
          return results;
        }''')
        self.assertEqual(codes,[403,403])
        result=self.env.orm('result={"name":User.objects.get(username=data["username"]).first_name}',{'username':self.username})
        self.assertEqual(result['name'],'CSRF valid')

    def test_logout_other_tab_and_back(self):
        self.seed()
        self.login()
        other=self.context.new_page()
        other.goto(self.env.url+'/profile.html')
        expect(other.locator('#profile-content')).to_be_visible()
        self.page.bring_to_front()
        self.page.get_by_role('navigation').get_by_role('link',name='新闻动态',exact=True).click()
        self.page.get_by_role('navigation').get_by_role('button',name='退出登录',exact=True).click()
        expect(self.page.get_by_role('navigation').get_by_role('link',name='登录',exact=True)).to_be_visible()
        self.page.go_back()
        expect(self.page).to_have_url(self.env.url+'/login.html')
        other.bring_to_front()
        expect(other).to_have_url(self.env.url+'/login.html')

    def test_roles_are_readonly_and_root_takes_precedence(self):
        for role,root in [('CUSTOMER',False),('STUDENT',False),('TEACHER',False),('ADMIN',False),('CUSTOMER',True)]:
            with self.subTest(role=role,root=root):
                name='role_'+secrets.token_hex(4)
                self.env.seed(name,self.password,role,root)
                self.login(name)
                expect(self.page.locator('[data-user-role]')).to_contain_text('ROOT' if root else role)
                self.assertEqual(self.page.locator('input[name=role],select[name=role],input[name=is_staff],input[name=is_superuser]').count(),0)
        # Last account is ROOT; even ROOT cannot inject readonly flags on self PATCH.
        status=self.page.evaluate('''async () => {
          const token=document.cookie.split('; ').find(x=>x.startsWith('csrftoken=')).split('=')[1];
          return (await fetch('/api/auth/me/',{method:'PATCH',headers:{'Content-Type':'application/json','X-CSRFToken':token},body:JSON.stringify({role:'ADMIN'})})).status;
        }''')
        self.assertEqual(status,400)

    def test_api_failure_does_not_break_navigation_or_show_profile(self):
        self.seed()
        self.login()
        self.page.route('**/api/auth/me/',lambda route:route.fulfill(status=503,content_type='text/html',body='<h1>unavailable</h1>'))
        self.page.reload()
        expect(self.page.locator('#profile-content')).to_be_hidden()
        expect(self.page.locator('#auth-status')).to_contain_text('暂不可用')
        expect(self.page.get_by_role('navigation').get_by_role('link',name='新闻动态',exact=True)).to_be_visible()
        self.page.unroute('**/api/auth/me/')
        self.page.get_by_role('button',name='重试',exact=True).click()
        expect(self.page.locator('#profile-content')).to_be_visible()

    def test_original_sections_deep_links_and_responsive_layouts(self):
        paths=['news','blogs','projects','papers','competitions','publications','members','graduates','activities']
        for path in paths:
            self.go(f'/data/{path}/index.html')
            nav=self.page.get_by_role('navigation')
            expect(nav.get_by_role('link',name='登录',exact=True)).to_be_visible()
            self.assertEqual(nav.locator('a.active').count(),1)
            self.assertTrue(nav.get_by_role('link',name='登录',exact=True).get_attribute('href').endswith('login.html'))
        self.go('/data/projects/202301NSFC_Key_Project/index.html')
        self.page.get_by_role('navigation').get_by_role('link',name='登录',exact=True).click()
        expect(self.page).to_have_url(self.env.url+'/login.html')
        for width,height in [(1440,900),(768,1024),(390,844),(320,800)]:
            for path in ['/register.html','/login.html']:
                self.page.set_viewport_size({'width':width,'height':height})
                self.go(path)
                expect(self.page.get_by_role('button',name='注册账号' if 'register' in path else '登录账号',exact=True)).to_be_visible()
                self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
                self.page.screenshot(path=str(EVIDENCE/f'{path[1:-5]}-{width}.png'),full_page=True)
        self.seed()
        self.login()
        for width,height in [(1440,900),(768,1024),(390,844),(320,800)]:
            self.page.set_viewport_size({'width':width,'height':height})
            expect(self.page.locator('#profile-content')).to_be_visible()
            self.assertTrue(self.page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
            button=self.page.get_by_role('button',name='保存资料',exact=True)
            button.scroll_into_view_if_needed()
            bounds=button.bounding_box()
            self.assertTrue(bounds['x']>=0 and bounds['x']+bounds['width']<=width+1)
            button.focus()
            expect(button).to_be_focused()
            self.page.screenshot(path=str(EVIDENCE/f'profile-{width}.png'),full_page=True)

    def test_logout_failure_remains_logged_in_and_displays_error(self):
        self.seed()
        self.login()
        self.go('/index.html')
        self.page.route('**/api/auth/logout/',lambda route:route.fulfill(status=503,content_type='application/json',body='{"detail":"Service temporarily unavailable."}'))
        self.page.get_by_role('navigation').get_by_role('button',name='退出登录',exact=True).click()
        expect(self.page.get_by_role('navigation').get_by_role('button',name='退出登录',exact=True)).to_be_enabled()
        expect(self.page.locator('.auth-nav-status')).to_contain_text('退出未完成')
        expect(self.page.locator('.auth-nav-status')).to_be_visible()
        expect(self.page.get_by_role('navigation').get_by_role('link',name='个人中心',exact=True)).to_be_visible()

    def test_write_csrf_error_does_not_replay_or_modify_data(self):
        self.seed()
        self.login()
        patches=[]
        def wrong_csrf(route):
            if route.request.method=='PATCH':
                patches.append(1)
                headers=dict(route.request.headers)
                headers['x-csrftoken']='x'*32
                route.continue_(headers=headers)
            else:
                route.continue_()
        self.page.route('**/api/auth/me/',wrong_csrf)
        self.page.get_by_label('名字',exact=True).fill('must-not-save')
        self.page.get_by_role('button',name='保存资料',exact=True).click()
        expect(self.page.locator('#profile-status')).to_contain_text('安全验证已过期')
        self.assertEqual(len(patches),1)
        result=self.env.orm('result={"name":User.objects.get(username=data["username"]).first_name}',{'username':self.username})
        self.assertEqual(result['name'],'')

    def test_rate_limit_message_and_csrf_bootstrap_failure(self):
        self.go('/login.html')
        self.page.route('**/api/auth/login/',lambda route:route.fulfill(status=429,content_type='application/json',headers={'Retry-After':'7'},body='{"detail":"Request was throttled."}'))
        self.page.get_by_label('用户名',exact=True).fill(self.username)
        self.page.get_by_label('密码',exact=True).fill(self.password)
        self.page.get_by_role('button',name='登录账号',exact=True).click()
        expect(self.page.locator('#login-status')).to_contain_text('7 秒')
        self.context.clear_cookies()
        self.page.route('**/api/auth/csrf/',lambda route:route.fulfill(status=503,content_type='text/html',body='unavailable'))
        self.go('/register.html')
        expect(self.page.locator('#auth-status')).to_contain_text('暂不可用')
        expect(self.page.get_by_role('button',name='注册账号',exact=True)).to_be_disabled()

    def test_focus_revalidation_preserves_same_user_draft(self):
        self.seed()
        self.login()
        self.page.get_by_label('名字',exact=True).fill('unsaved draft')
        with self.page.expect_response(lambda r:r.url.endswith('/api/auth/me/') and r.request.method=='GET') as response:
            self.page.evaluate("dispatchEvent(new Event('focus'))")
        response.value.body()
        expect(self.page.locator('#profile-content')).to_be_visible()
        expect(self.page.get_by_label('名字',exact=True)).to_have_value('unsaved draft')

    def test_post_save_get_is_newer_than_delayed_pre_save_get(self):
        self.seed()
        self.login()
        held_patch=[]
        held_get=[]
        def intercept(route):
            if route.request.method=='PATCH':
                held_patch.append(route)
            elif route.request.method=='GET' and not held_get:
                item={'route':route}
                held_get.append(item)
                try:
                    item['response']=route.fetch()
                except PlaywrightError:
                    item['failed']=True
            else:
                route.continue_()
        self.page.route('**/api/auth/me/',intercept)
        self.page.get_by_label('名字',exact=True).fill('after-commit')
        with self.page.expect_request(lambda r:r.method=='PATCH'):
            self.page.get_by_role('button',name='保存资料',exact=True).click()
        with self.page.expect_request(lambda r:r.url.endswith('/api/auth/me/') and r.method=='GET'):
            self.page.evaluate("dispatchEvent(new Event('focus'))")
        self.wait_held(held_get)
        self.assertEqual(len(held_patch),1)
        self.assertEqual(len(held_get),1)
        with self.page.expect_response(lambda r:r.request.method=='PATCH') as committed:
            held_patch[0].continue_()
        committed.value.body()
        held_get[0]['route'].fulfill(response=held_get[0]['response'])
        expect(self.page.locator('#profile-status')).to_contain_text('资料已保存')
        expect(self.page.get_by_label('名字',exact=True)).to_have_value('after-commit')

    def test_pagehide_does_not_allow_late_real_response_to_restore_profile(self):
        self.seed()
        self.login()
        held=[]
        def hold(route):
            item={'route':route}
            held.append(item)
            try:
                item['response']=route.fetch()
            except PlaywrightError:
                item['failed']=True
        self.page.route('**/api/auth/me/',hold)
        with self.page.expect_request(lambda r:r.url.endswith('/api/auth/me/') and r.method=='GET'):
            self.page.evaluate("dispatchEvent(new Event('focus'))")
        self.wait_held(held)
        self.page.evaluate("dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true}))")
        self.assertEqual(len(held),1)
        with self.page.expect_response(lambda r:r.url.endswith('/api/auth/me/')) as response:
            held[0]['route'].fulfill(response=held[0]['response'])
        response.value.body()
        self.page.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
        expect(self.page.locator('#profile-content')).to_be_hidden()
        expect(self.page.locator('#profile-summary')).to_be_hidden()
        self.assertEqual(self.page.locator('[data-user-name]').text_content(),'')

    def test_server_field_errors_are_associated_with_controls(self):
        self.seed()
        self.go('/register.html')
        self.page.get_by_label('用户名',exact=True).fill(self.username)
        self.page.get_by_label('密码',exact=True).fill(self.password)
        self.page.get_by_label('确认密码',exact=True).fill(self.password)
        self.page.get_by_role('button',name='注册账号',exact=True).click()
        expect(self.page.locator('#register-status')).to_contain_text('用户名已存在')
        field=self.page.get_by_label('用户名',exact=True)
        expect(field).to_have_attribute('aria-invalid','true')
        self.assertIn('register-status',field.get_attribute('aria-describedby'))
        expect(field).to_be_focused()

    def wait_held(self, items):
        deadline=time.monotonic()+10
        while not items or not ('response' in items[0] or items[0].get('failed')):
            if time.monotonic()>=deadline:
                self.fail('The intercepted real response did not complete')
            self.page.wait_for_timeout(10)
        self.assertFalse(items[0].get('failed'), 'Intercepted real response failed')
