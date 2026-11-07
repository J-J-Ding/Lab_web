import secrets, unittest, struct, zlib
from playwright.sync_api import sync_playwright, expect
from support import Environment, launch_browser, EVIDENCE


def png():
    def chunk(t,d):return struct.pack('!I',len(d))+t+d+struct.pack('!I',zlib.crc32(t+d)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',80,120,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+bytes([40,110,180])*80)*120))+chunk(b'IEND',b'')


class RichContentBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.env=Environment().start();cls.p=sync_playwright().start();cls.browser=launch_browser(cls.p)
    @classmethod
    def tearDownClass(cls):cls.browser.close();cls.p.stop();cls.env.close()

    def test_edit_image_table_save_reopen_and_render(self):
        username='rich_'+secrets.token_hex(4);password='Test123456';self.env.seed(username,password,'STUDENT',False)
        context=self.browser.new_context();page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            page.goto(self.env.url+'/login.html');page.locator('[name=username]').fill(username);page.locator('[name=password]').fill(password);page.get_by_role('button',name='登录账号',exact=True).click();page.wait_for_url('**/profile.html')
            page.goto(self.env.url+'/content-editor.html?kind=AWARD');page.wait_for_selector('#direct-content-form[data-ready=true]');expect(page.get_by_role('textbox',name='图文正文编辑区')).to_be_visible()
            page.locator('[name=title]').fill('图文竞赛浏览器验收');edit=page.get_by_role('textbox',name='图文正文编辑区');edit.fill('图文正文第一段 <保留文字>');page.get_by_role('button',name='二级标题',exact=True).click();edit.press('End');edit.press('Enter');page.get_by_role('button',name='正文',exact=True).click();edit.press_sequentially('第二段说明')
            page.locator('input[aria-label="选择正文图片"]').set_input_files({'name':'research.png','mimeType':'image/png','buffer':png()});expect(page.locator('.rich-status')).to_contain_text('图片已插入')
            page.locator('.tiptap figure').click();page.get_by_label('图片宽度',exact=True).select_option('50');page.get_by_label('图片对齐',exact=True).select_option('center');page.get_by_label('图片说明',exact=True).fill('图1：竞赛实验结果');page.get_by_label('图片说明',exact=True).press('Tab')
            self.assertTrue(page.evaluate("()=>{const e=document.querySelector('#rich-body-editor')._labRich.editor,before=e.getJSON();e.commands.setContent(e.getHTML());return JSON.stringify(e.getJSON())===JSON.stringify(before);}"))
            # Put the caret after the image before inserting a table.
            edit.press('End');edit.press('ArrowDown')
            answers=iter(['3','2']);page.on('dialog',lambda d:d.accept(next(answers)));page.get_by_role('button',name='插入表格',exact=True).click();expect(page.locator('.tiptap table')).to_be_visible();page.locator('.tiptap th p').first.click();page.keyboard.type('实验指标');expect(page.locator('.tiptap table')).to_contain_text('实验指标')
            page.get_by_role('button',name='增加行',exact=True).click();expect(page.locator('.tiptap tr')).to_have_count(4);page.locator('.tiptap tr').nth(1).locator('td p').first.click();page.get_by_role('button',name='删除行',exact=True).click();expect(page.locator('.tiptap tr')).to_have_count(3)
            page.locator('.tiptap > p').last.click();edit.press('End');edit.press('Enter');page.get_by_role('button',name='有序列表',exact=True).click();page.keyboard.type('步骤一');expect(page.locator('.tiptap ol')).to_contain_text('步骤一')
            with page.expect_response(lambda r:r.url.endswith('/api/content/items/') and r.request.method=='POST') as saved:page.get_by_role('button',name='保存并生效',exact=True).click()
            if saved.value.status!=201:self.fail(saved.value.text())
            page.wait_for_url('**/content-editor.html?id=*');page.wait_for_selector('#direct-content-form[data-ready=true]');expect(page.locator('.tiptap')).to_contain_text('图文正文第一段 <保留文字>');expect(page.locator('.tiptap figcaption')).to_have_text('图1：竞赛实验结果');expect(page.locator('.tiptap table')).to_contain_text('实验指标')
            item_id=page.url.split('id=')[1];page.goto(self.env.url+'/content.html?id='+item_id);expect(page.locator('.detail-section .rich-document')).to_contain_text('图文正文第一段 <保留文字>');expect(page.locator('.rich-figure img')).to_be_visible();expect(page.locator('.rich-document table')).to_contain_text('实验指标');expect(page.locator('.rich-document ol')).to_contain_text('步骤一');self.assertEqual(page.locator('.rich-figure').count(),1)
            EVIDENCE.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(EVIDENCE/'rich-public-desktop.png'),full_page=True);page.set_viewport_size({'width':390,'height':844});page.screenshot(path=str(EVIDENCE/'rich-public-mobile.png'),full_page=True);self.assertFalse(page.evaluate('document.documentElement.scrollWidth>innerWidth'))
            self.assertEqual(errors,[])
        finally:context.close()

    def test_failed_upload_keeps_text_and_blocks_premature_save(self):
        username='richfail_'+secrets.token_hex(4);password='Test123456';self.env.seed(username,password,'STUDENT',False)
        context=self.browser.new_context();page=context.new_page()
        try:
            page.goto(self.env.url+'/login.html');page.locator('[name=username]').fill(username);page.locator('[name=password]').fill(password);page.get_by_role('button',name='登录账号',exact=True).click();page.wait_for_url('**/profile.html')
            page.goto(self.env.url+'/content-editor.html?kind=PAPER');page.wait_for_selector('#direct-content-form[data-ready=true]');page.locator('[name=title]').fill('上传失败仍可编辑');edit=page.get_by_role('textbox',name='图文正文编辑区');edit.fill('这段正文不会因上传失败丢失')
            held=[];page.route('**/api/assets/',lambda route:held.append(route))
            page.locator('input[aria-label="选择正文图片"]').set_input_files({'name':'test.png','mimeType':'image/png','buffer':png()});expect(page.locator('.rich-status')).to_contain_text('正在上传')
            page.get_by_role('button',name='保存并生效',exact=True).click();expect(page.locator('#business-status')).to_contain_text('正在上传')
            self.assertTrue(held);held[0].fulfill(status=400,content_type='application/json',body='{"detail":"测试上传失败"}')
            expect(page.locator('.rich-status')).to_contain_text('正文已保留');expect(edit).to_contain_text('这段正文不会因上传失败丢失');page.unroute('**/api/assets/')
            page.get_by_role('button',name='保存并生效',exact=True).click();page.wait_for_url('**/content-editor.html?id=*');page.wait_for_selector('#direct-content-form[data-ready=true]');expect(page.get_by_role('textbox',name='图文正文编辑区')).to_contain_text('这段正文不会因上传失败丢失')
        finally:context.close()

    def test_old_blog_body_remains_literal_when_migrated(self):
        username='richold_'+secrets.token_hex(4);password='Test123456';self.env.seed(username,password,'STUDENT',False)
        context=self.browser.new_context();page=context.new_page()
        try:
            page.goto(self.env.url+'/login.html');page.locator('[name=username]').fill(username);page.locator('[name=password]').fill(password);page.get_by_role('button',name='登录账号',exact=True).click();page.wait_for_url('**/profile.html')
            page.goto(self.env.url+'/content-editor.html?kind=BLOG');page.wait_for_selector('#direct-content-form[data-ready=true]');expect(page.locator('[name=detail_category] option').first).to_have_text('技术博客')
            row=page.evaluate(r"""async()=>await LabContent.request('/api/content/items/',{method:'POST',data:{kind:'BLOG',title:'旧博客兼容',detail:{body:'第一行 <b>仍然是文字</b>\n第二行'}}})""")
            page.goto(self.env.url+'/content.html?id='+row['id']);expect(page.locator('.detail-section')).to_contain_text('<b>仍然是文字</b>');self.assertEqual(page.locator('.detail-section b').count(),0)
            page.goto(self.env.url+'/content-editor.html?id='+row['id']);page.wait_for_selector('#direct-content-form[data-ready=true]');expect(page.locator('.tiptap')).to_contain_text('<b>仍然是文字</b>');self.assertEqual(page.locator('.tiptap').evaluate('(el)=>el.closest("label")===null'),True)
            page.get_by_role('button',name='保存并生效',exact=True).click();expect(page.locator('#business-status')).to_contain_text('已保存');page.goto(self.env.url+'/content.html?id='+row['id']);expect(page.locator('.rich-document')).to_contain_text('<b>仍然是文字</b>');self.assertEqual(page.locator('.rich-document b').count(),0)
            page.goto(self.env.url+'/content-editor.html?id='+row['id']);page.wait_for_selector('#direct-content-form[data-ready=true]');page.locator('[name=visibility_scope]').select_option('TEAM');page.get_by_role('button',name='保存并生效',exact=True).click();expect(page.locator('#business-status')).to_contain_text('已保存')
            peer='richpeer_'+secrets.token_hex(4);self.env.seed(peer,password,'STUDENT',False)
            peer_context=self.browser.new_context();peer_page=peer_context.new_page()
            try:
                peer_page.goto(self.env.url+'/login.html');peer_page.locator('[name=username]').fill(peer);peer_page.locator('[name=password]').fill(password);peer_page.get_by_role('button',name='登录账号',exact=True).click();peer_page.wait_for_url('**/profile.html');peer_page.goto(self.env.url+'/workspace.html?q='+row['revision']['title']);peer_page.get_by_role('button',name='查看团队内容',exact=True).click();expect(peer_page.locator('#workspace-list .rich-document')).to_contain_text('仍然是文字');self.assertEqual(peer_page.locator('#workspace-list').text_content().count('仍然是文字'),1)
            finally:peer_context.close()
        finally:context.close()
