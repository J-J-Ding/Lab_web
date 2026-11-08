import secrets,unittest,base64
from playwright.sync_api import sync_playwright,expect
from support import Environment,launch_browser,EVIDENCE


class BatchAccountsBrowserTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.env=Environment();key=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode();cls.env.ai_environment+=['-e','ACCOUNT_IMPORT_KEY='+key,'-e','INITIAL_ACCOUNT_PASSWORD=Default987654'];cls.env.start();cls.p=sync_playwright().start();cls.browser=launch_browser(cls.p)
 @classmethod
 def tearDownClass(cls):cls.browser.close();cls.p.stop();cls.env.close()
 def test_template_preview_confirm_accounts_and_root_incomplete_profile(self):
  root='batchroot_'+secrets.token_hex(4);password='Test123456';self.env.seed(root,password,'TEACHER',True)
  context=self.browser.new_context(accept_downloads=True);page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  names=['import_'+secrets.token_hex(4) for _ in range(7)]
  try:
   page.goto(self.env.url+'/login.html');page.locator('[name=username]').fill(root);page.locator('[name=password]').fill(password);page.get_by_role('button',name='登录账号',exact=True).click();page.wait_for_url('**/profile.html')
   page.locator('[name=display_name]').fill('Root仅姓名保存');page.get_by_role('button',name='保存资料',exact=True).click();expect(page.locator('#business-status')).to_contain_text('已保存')
   page.goto(self.env.url+'/manage/account-import.html');expect(page.locator('#business-status')).to_contain_text('规范模板')
   with page.expect_download() as event:page.get_by_role('link',name='下载账号导入模板',exact=True).click()
   EVIDENCE.mkdir(parents=True,exist_ok=True);event.value.save_as(EVIDENCE/'account-import-template.xlsx')
   def make(rows):
    result=self.env.orm("from io import BytesIO\nfrom openpyxl import Workbook\nfrom apps.accounts.import_excel import HEADERS\nimport base64\nb=Workbook();s=b.active;s.title='账号导入';s.append(HEADERS)\nfor row in data['rows']:s.append(row)\no=BytesIO();b.save(o);result={'file':base64.b64encode(o.getvalue()).decode()}",{'rows':rows});return base64.b64decode(result['file'])
   bad=make([[1,names[0],'','student','正常',''],[2,names[0],'','student','正常','']]);page.get_by_label('账号Excel文件').set_input_files({'name':'bad.xlsx','mimeType':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','buffer':bad});page.get_by_role('button',name='上传并预览',exact=True).click();expect(page.locator('#import-state')).to_contain_text('未通过');expect(page.locator('#confirm-import')).to_be_hidden();expect(page.locator('#import-errors')).to_contain_text('重复')
   rows=[[i+1,n,'Custom987654' if i==1 else '', 'Teacher' if i==0 else 'custom' if i==2 else 'student','已注销' if i==2 else '正常','导入姓名' if i==0 else ''] for i,n in enumerate(names)]
   good=make(rows);page.get_by_label('账号Excel文件').set_input_files({'name':'good.xlsx','mimeType':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','buffer':good});page.get_by_role('button',name='上传并预览',exact=True).click();expect(page.locator('#import-state')).to_contain_text('校验通过');expect(page.locator('#import-rows tr')).to_have_count(5);self.assertNotIn('Custom987654',page.locator('#import-preview').text_content());page.get_by_role('button',name='下一页',exact=True).click();expect(page.locator('#import-rows tr')).to_have_count(2)
   page.get_by_role('button',name='确认创建整批账号',exact=True).click();expect(page.locator('#import-state')).to_contain_text('等待后台');self.env.orm('from apps.accounts.batch_imports import process_one\nprocess_one()\nresult={"processed":True}')
   expect(page.locator('#import-state')).to_contain_text('创建完成',timeout=20000);page.reload();expect(page.locator('#import-state')).to_contain_text('创建完成');page.screenshot(path=str(EVIDENCE/'v18-import-result.png'),full_page=True)
   profile=self.env.orm("u=User.objects.get(username=data['name']);result={'name':u.member_profile.published_revision.display_name}",{'name':names[0]});self.assertEqual(profile['name'],'导入姓名')
   for username,pw,allowed in [(names[0],'Default987654',True),(names[1],'Custom987654',True),(names[2],'Default987654',False)]:
    ctx=self.browser.new_context();q=ctx.new_page();q.goto(self.env.url+'/login.html');q.locator('[name=username]').fill(username);q.locator('[name=password]').fill(pw);q.get_by_role('button',name='登录账号',exact=True).click()
    if allowed:q.wait_for_url('**/profile.html');self.assertEqual(ctx.request.get(self.env.url+'/api/admin/account-imports/template/').status,403)
    else:expect(q.locator('[role=status]').filter(has_text='账号不可用')).to_contain_text('账号不可用')
    ctx.close()
   self.assertEqual(errors,[])
  finally:context.close()
