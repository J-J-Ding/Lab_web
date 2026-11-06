from io import BytesIO
from tempfile import TemporaryDirectory
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from apps.accounts.tests.helpers import AccountFixtures,login_as,write


class UploadContracts(AccountFixtures):
    def setUp(self):
        self.temp=TemporaryDirectory()
        self.override=override_settings(PRIVATE_MEDIA_ROOT=self.temp.name)
        self.override.enable();self.addCleanup(self.override.disable);self.addCleanup(self.temp.cleanup)
        self.client=login_as(self.customer)
    def png(self):
        # A fixed valid one-pixel PNG, independent of future server-side Pillow code.
        import base64
        return base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
    def upload(self,data,name='avatar.png',mime='image/png',purpose='avatar',csrf=True):
        args={'HTTP_X_CSRFTOKEN':self.client.cookies['csrftoken'].value} if csrf else {}
        return self.client.post('/api/assets/',{'purpose':purpose,'file':SimpleUploadedFile(name,data,content_type=mime)},format='multipart',**args)
    def test_upload_is_private_and_another_user_cannot_download(self):
        response=self.upload(self.png())
        self.assertEqual(response.status_code,201,response.content)
        data=response.json();self.assertNotIn('storage_key',data)
        response=self.client.get(data['download_url']);self.assertEqual(response.status_code,200)
        self.assertEqual(response['X-Content-Type-Options'],'nosniff')
        self.assertIn('attachment',response['Content-Disposition'])
        self.assertTrue(b''.join(response.streaming_content).startswith(b'\x89PNG'))
        self.assertEqual(login_as(self.student).get(data['download_url']).status_code,404)
    def test_wrong_magic_svg_and_missing_csrf_rejected(self):
        self.assertEqual(self.upload(b'<svg><script>bad()</script></svg>').status_code,400)
        self.assertEqual(self.upload(self.png(),name='avatar.svg',mime='image/svg+xml').status_code,400)
        self.assertEqual(self.upload(self.png(),csrf=False).status_code,403)
    def test_oversized_and_unknown_upload_fields_rejected(self):
        self.assertEqual(self.upload(b'a'*(5*1024*1024+1)).status_code,400)
        response=self.client.post('/api/assets/',{'purpose':'avatar','role':'ADMIN','file':SimpleUploadedFile('a.png',self.png(),content_type='image/png')},format='multipart',HTTP_X_CSRFTOKEN=self.client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code,400)

    def test_proof_download_only_by_owner_or_authorized_application_reviewer(self):
        from pypdf import PdfWriter
        buf=BytesIO();writer=PdfWriter();writer.add_blank_page(width=72,height=72);writer.write(buf)
        response=self.upload(buf.getvalue(),name='proof.pdf',mime='application/pdf',purpose='proof')
        self.assertEqual(response.status_code,201,response.content);data=response.json()
        manager=login_as(self.teacher)
        self.assertEqual(manager.get(data['download_url']).status_code,404)
        application=write(self.client,'post','/api/members/applications/',{'application_kind':'STUDENT','statement':'Proof attached','proof_asset':data['id']})
        self.assertEqual(application.status_code,201,application.content)
        response=manager.get(data['download_url']);self.assertEqual(response.status_code,200);self.assertTrue(b''.join(response.streaming_content).startswith(b'%PDF'))

    def test_pdf_with_actions_and_malformed_pdf_are_rejected(self):
        from pypdf import PdfWriter
        writer=PdfWriter();writer.add_blank_page(width=72,height=72);writer.add_js("app.alert('never execute')")
        buf=BytesIO();writer.write(buf)
        self.assertEqual(self.upload(buf.getvalue(),name='proof.pdf',mime='application/pdf',purpose='proof').status_code,400)
        self.assertEqual(self.upload(b'%PDF-1.7 broken',name='proof.pdf',mime='application/pdf',purpose='proof').status_code,400)

    def test_teacher_cannot_download_root_unpublished_avatar(self):
        from apps.members.models import MemberProfile
        MemberProfile.objects.create(user=self.root,membership_status='ACTIVE')
        self.client=login_as(self.root)
        asset=self.upload(self.png()).json()
        draft=write(self.client,'post','/api/members/me/draft/',{}).json()
        draft=write(self.client,'patch','/api/members/me/draft/',{'lock_version':draft['lock_version'],'display_name':'Root avatar','slug':'root-avatar','avatar_asset':asset['id']}).json()
        submitted=write(self.client,'post','/api/members/me/draft/submit/',{'lock_version':draft['lock_version']})
        self.assertEqual(submitted.status_code,200,submitted.content)
        response=login_as(self.teacher).get(asset['download_url']);status=response.status_code
        if getattr(response,'streaming',False):b''.join(response.streaming_content)
        self.assertEqual(status,404)
