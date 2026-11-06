from io import BytesIO
from zipfile import ZipFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from apps.accounts.tests.helpers import login_as,write
from apps.assets.tests import test_uploads as helpers
from apps.accounts.tests.helpers import AccountFixtures
from apps.content.models import ContentItem,ContentRevision,RevisionAsset
from apps.content.services import create_content


class PublicAssetTests(AccountFixtures):
    setUp=helpers.UploadContracts.setUp
    png=helpers.UploadContracts.png
    upload=helpers.UploadContracts.upload
    def test_public_download_requires_current_reference_and_revokes_immediately(self):
        self.client=login_as(self.teacher)
        r=self.upload(self.png(),purpose='image');self.assertEqual(r.status_code,201,r.content)
        pk=r.json()['id'];path=f'/api/public/assets/{pk}/'
        from apps.assets.models import AssetFile
        self.assertEqual(self.client.get(path).status_code,404)
        item=create_content(self.teacher,'BLOG','Image article',{'body':'body'})
        RevisionAsset.objects.create(revision=item.working_revision,asset_id=pk,purpose='image')
        AssetFile.objects.filter(pk=pk).update(visibility='PUBLIC',expires_at=None)
        self.assertEqual(self.client.get(path).status_code,404)
        with transaction.atomic():
            ContentRevision.objects.filter(pk=item.working_revision_id).update(state='PUBLISHED')
            ContentItem.objects.filter(pk=item.pk).update(published_revision=item.working_revision,working_revision=None)
        response=self.client.get(path);self.assertEqual(response.status_code,200)
        self.assertTrue(b''.join(response.streaming_content).startswith(b'\x89PNG'))
        ContentItem.objects.filter(pk=item.pk).update(visibility_gate=False)
        self.assertEqual(self.client.get(path).status_code,404)
    def test_docx_budget_external_links_and_paths(self):
        def document(extra=None):
            data=BytesIO()
            with ZipFile(data,'w') as z:
                z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
                z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body/></w:document>')
                if extra:z.writestr(*extra)
            return data.getvalue()
        mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        r=self.upload(document(),name='sample.docx',mime=mime,purpose='attachment');self.assertEqual(r.status_code,201,r.content)
        for extra in [('.. /evil.xml','<x/>'),('../evil.xml','<x/>'),('word/_rels/document.xml.rels','<Relationships><Relationship TargetMode="External" Target="https://evil.invalid"/></Relationships>'),('word/vbaProject.bin','macro'),('word/bomb.xml','x'*2_000_000)]:
            self.assertEqual(self.upload(document(extra),name='bad.docx',mime=mime,purpose='attachment').status_code,400)
    def test_proof_never_public_and_owner_only_delete(self):
        from pypdf import PdfWriter
        from apps.assets.models import AssetFile
        out=BytesIO();w=PdfWriter();w.add_blank_page(width=100,height=100);w.write(out)
        r=self.upload(out.getvalue(),name='proof.pdf',mime='application/pdf',purpose='proof');self.assertEqual(r.status_code,201)
        pk=r.json()['id'];AssetFile.objects.filter(pk=pk).update(visibility='PUBLIC',expires_at=None)
        self.assertEqual(self.client.get(f'/api/public/assets/{pk}/').status_code,404)
        self.assertEqual(write(login_as(self.student),'post',f'/api/assets/{pk}/delete/',{}).status_code,404)
        self.assertEqual(write(self.client,'post',f'/api/assets/{pk}/delete/',{}).status_code,200)
    def test_avatar_privacy_revokes_download_and_public_metadata(self):
        from apps.assets.models import AssetFile
        from apps.members.models import MemberProfile,MemberRevision,MemberSlug
        r=self.upload(self.png());self.assertEqual(r.status_code,201)
        pk=r.json()['id'];AssetFile.objects.filter(pk=pk).update(visibility='PUBLIC',expires_at=None)
        p=MemberProfile.objects.create(public_visible=True,membership_status='ACTIVE')
        rev=MemberRevision.objects.create(profile=p,number=1,slug='avatar-example',display_name='Example',avatar_asset_id=pk)
        MemberSlug.objects.create(profile=p,slug=rev.slug)
        with transaction.atomic():
            MemberRevision.objects.filter(pk=rev.pk).update(state='PUBLISHED')
            MemberProfile.objects.filter(pk=p.pk).update(published_revision=rev)
        path=f'/api/public/assets/{pk}/';response=self.client.get(path);self.assertEqual(response.status_code,200);b''.join(response.streaming_content)
        self.assertEqual(self.client.get('/api/public/members/avatar-example/').json()['avatar']['id'],pk)
        MemberProfile.objects.filter(pk=p.pk).update(public_visible=False)
        self.assertEqual(self.client.get(path).status_code,404)
    def test_collaborator_preserves_attachments_and_reviewer_can_download(self):
        from apps.members.models import MemberProfile
        MemberProfile.objects.create(user=self.student,membership_status='ACTIVE')
        self.client=login_as(self.teacher);r=self.upload(self.png(),purpose='image');self.assertEqual(r.status_code,201);asset=r.json()
        r=write(self.client,'post','/api/content/items/',{'kind':'BLOG','title':'Shared attachment','detail':{'body':'Body'}});self.assertEqual(r.status_code,201);item=r.json()
        r=write(self.client,'patch',f"/api/content/items/{item['id']}/",{'lock_version':item['lock_version'],'assets':[asset['id']]});self.assertEqual(r.status_code,200);item=r.json()
        r=write(self.client,'post',f"/api/content/items/{item['id']}/grants/",{'lock_version':item['lock_version'],'user_id':self.student.pk,'can_edit':True});self.assertEqual(r.status_code,200);item=r.json()
        student=login_as(self.student)
        r=write(student,'patch',f"/api/content/items/{item['id']}/",{'lock_version':item['lock_version'],'title':'Collaborator update','assets':[asset['id']]});self.assertEqual(r.status_code,200,r.content)
        item=r.json();self.assertEqual(item["revision"]["state"],"PUBLISHED")
        response=login_as(self.root).get(asset['download_url']);self.assertEqual(response.status_code,200,response.content if not response.streaming else '');b''.join(response.streaming_content)
        response=student.get(asset['download_url']);self.assertEqual(response.status_code,200);b''.join(response.streaming_content)
        self.assertEqual(login_as(self.customer).get(asset['download_url']).status_code,404)
    def test_reviewer_downloads_private_content_file(self):
        self.client=login_as(self.teacher);r=self.upload(self.png(),purpose='image');asset=r.json()
        item=create_content(self.teacher,'BLOG','Review image',{'body':'Body'})
        RevisionAsset.objects.create(revision=item.working_revision,asset_id=asset['id'],purpose='image')
        response=login_as(self.root).get(asset['download_url']);self.assertEqual(response.status_code,200,response.content if not response.streaming else '');b''.join(response.streaming_content)
