from unittest.mock import patch
from django.db import IntegrityError
from apps.accounts.tests.helpers import AccountFixtures,login_as,write
from apps.members.models import MemberProfile
from apps.content.models import ContentItem,ContentRevision,Contributor
from apps.content.selectors import published_content
from apps.workflow.models import ReviewDecision


class ContentFlowTests(AccountFixtures):
    def setUp(self):
        MemberProfile.objects.create(user=self.student,membership_status='ACTIVE')
        self.author=login_as(self.teacher);self.reviewer=login_as(self.root)

    def create(self,kind='BLOG',detail=None,contributions=None):
        r=write(self.author,'post','/api/content/items/',{'kind':kind,'title':'Published A','detail':detail or {'body':'First body'},'contributions':contributions or []})
        self.assertEqual(r.status_code,201,r.content);return r.json()
    def item(self,item,client=None):
        r=(client or self.author).get(f"/api/content/items/{item['id']}/")
        self.assertEqual(r.status_code,200,r.content);return r.json()
    def submit(self,item):
        r=write(self.author,'post',f"/api/content/revisions/{item['working_revision']['id']}/submit/",{'lock_version':item['lock_version']})
        self.assertEqual(r.status_code,200,r.content);return r.json()
    def decide(self,item,decision='APPROVE',client=None):
        return write(client or self.reviewer,'post',f"/api/review/revisions/{item['working_revision']['id']}/decision/",{'decision':decision,'reason':'Reviewed evidence','lock_version':item['lock_version']})

    def test_public_A_stays_while_B_pending_and_rejection_creates_new_revision(self):
        item=self.submit(self.create());r=self.decide(item);self.assertEqual(r.status_code,200,r.content);item=r.json()
        old=item['published_revision']['id']
        r=write(self.author,'post',f"/api/content/items/{item['id']}/revisions/",{'lock_version':item['lock_version']});self.assertEqual(r.status_code,201,r.content);item=r.json()
        r=write(self.author,'patch',f"/api/content/revisions/{item['working_revision']['id']}/",{'lock_version':item['lock_version'],'title':'Pending B'});self.assertEqual(r.status_code,200,r.content)
        item=self.submit(r.json())
        self.assertEqual(published_content().get().published_revision_id,ContentRevision.objects.get(pk=old).pk)
        self.assertEqual(published_content().get().published_revision.title,'Published A')
        r=self.decide(item,'REJECT');self.assertEqual(r.status_code,200,r.content);item=r.json()
        rejected=ContentRevision.objects.filter(item_id=item['id'],state='REJECTED').get()
        r=write(self.author,'post',f"/api/content/items/{item['id']}/revisions/",{'lock_version':item['lock_version'],'source_revision':str(rejected.pk)})
        self.assertEqual(r.status_code,201,r.content);item=self.submit(r.json())
        r=self.decide(item);self.assertEqual(r.status_code,200,r.content)
        self.assertEqual(published_content().get().published_revision.title,'Pending B')
        self.assertEqual(ContentItem.objects.count(),1)

    def test_stale_edit_conflicts_and_manager_editor_can_self_review(self):
        item=self.create();pk=item['working_revision']['id']
        admin=login_as(self.admin)
        r=write(admin,'patch',f'/api/content/revisions/{pk}/',{'lock_version':0,'title':'Admin edited'})
        self.assertEqual(r.status_code,200,r.content)
        self.assertEqual(write(self.author,'patch',f'/api/content/revisions/{pk}/',{'lock_version':0,'title':'Stale'}).status_code,409)
        item=self.submit(r.json())
        self.assertEqual(self.decide(item,client=admin).status_code,200)
        self.assertEqual(self.decide(item).status_code,409)

    def test_collaboration_readonly_revoke_and_unknown_object(self):
        item=self.create();student=login_as(self.student)
        path=f"/api/content/items/{item['id']}/grants/"
        r=write(self.author,'post',path,{'lock_version':0,'user_id':self.student.pk,'can_edit':False});self.assertEqual(r.status_code,200,r.content);item=r.json()
        self.assertEqual(student.get(f"/api/content/items/{item['id']}/").status_code,200)
        self.assertEqual(write(student,'patch',f"/api/content/revisions/{item['working_revision']['id']}/",{'lock_version':item['lock_version'],'title':'No'}).status_code,403)
        r=write(self.author,'post',path,{'lock_version':item['lock_version'],'user_id':self.student.pk,'revoke':True});self.assertEqual(r.status_code,200)
        self.assertEqual(student.get(f"/api/content/items/{item['id']}/").status_code,404)
        self.assertEqual(student.get(f"/api/content/items/{item['id']}/history/").status_code,404)

    def test_participation_confirmation_is_not_edit_permission_and_dispute_blocks_publication(self):
        contributor=Contributor.objects.create(member_profile=MemberProfile.objects.get(user=self.student),display_name='Student Author')
        item=self.create('PAPER',{'venue':'Journal','publication_date':'2025-01-01'},[{'contributor':str(contributor.pk),'contribution_role':'AUTHOR','position':1}])
        student=login_as(self.student);link=item['working_revision']['contributions'][0]['id']
        self.assertEqual(student.get(f"/api/content/items/{item['id']}/").status_code,404)
        self.assertEqual(student.get('/api/content/confirmations/').json()['count'],1)
        self.assertEqual(write(student,'post',f'/api/content/contributions/{link}/confirm/',{'decision':'CONFIRMED'}).status_code,200)
        item=self.submit(self.item(item))
        self.assertEqual(write(student,'post',f'/api/content/contributions/{link}/confirm/',{'decision':'DISPUTED','reason':'Wrong order'}).status_code,200)
        item=self.item(item)
        self.assertEqual(self.decide(item).status_code,400)
        self.assertFalse(ContentItem.objects.get(pk=item['id']).published_revision_id)
        self.assertEqual(write(student,'post',f'/api/content/contributions/{link}/confirm/',{'decision':'CONFIRMED','reason':'Now verified'}).status_code,200)
        self.assertEqual(self.decide(self.item(item)).status_code,200)
        self.assertEqual(student.get('/api/content/participations/').json()['count'],1)

    def test_audit_failure_rolls_back_review_and_snapshot(self):
        item=self.submit(self.create())
        with patch('apps.workflow.content_services.record',side_effect=IntegrityError('private-error')):
            response=self.decide(item)
        self.assertEqual(response.status_code,503)
        self.assertNotIn('private-error',response.content.decode())
        revision=ContentRevision.objects.get(pk=item['working_revision']['id'])
        self.assertEqual(revision.state,'SUBMITTED')
        self.assertEqual(ReviewDecision.objects.count(),0)
        self.assertIsNone(ContentItem.objects.get(pk=item['id']).published_revision_id)
        self.assertEqual(self.decide(item).status_code,200)

    def test_archive_unpublish_withdraw_and_restore_have_distinct_effects(self):
        item=self.submit(self.create());item=self.decide(item).json()
        r=write(self.reviewer,'post',f"/api/content/items/{item['id']}/archive/",{'lock_version':item['lock_version'],'reason':'Archive'});self.assertEqual(r.status_code,200);item=r.json()
        self.assertEqual(published_content().count(),1)
        self.assertEqual(write(self.author,'post',f"/api/content/items/{item['id']}/revisions/",{'lock_version':item['lock_version']}).status_code,409)
        r=write(self.reviewer,'post',f"/api/content/items/{item['id']}/unarchive/",{'lock_version':item['lock_version'],'reason':'Restore edits'});self.assertEqual(r.status_code,200);item=r.json()
        r=write(self.reviewer,'post',f"/api/content/items/{item['id']}/unpublish/",{'lock_version':item['lock_version'],'reason':'Remove public'});self.assertEqual(r.status_code,200);item=r.json()
        self.assertEqual(published_content().count(),0)
        r=write(self.author,'post',f"/api/content/items/{item['id']}/revisions/",{'lock_version':item['lock_version']});item=self.submit(r.json())
        r=write(self.author,'post',f"/api/content/revisions/{item['working_revision']['id']}/withdraw/",{'lock_version':item['lock_version']});self.assertEqual(r.status_code,200);item=r.json()
        self.assertEqual(published_content().count(),0)
        self.assertEqual(write(self.author,'post',f"/api/content/revisions/{ContentRevision.objects.filter(item_id=item['id'],state='WITHDRAWN').get().pk}/withdraw/",{'lock_version':item['lock_version']}).status_code,409)

    def test_ordinary_manager_cannot_promote_or_bind_root_via_membership(self):
        root=login_as(self.root)
        a=write(root,'post','/api/members/applications/',{'application_kind':'TEACHER','statement':'Root identity'})
        self.assertEqual(a.status_code,201)
        self.assertEqual(self.author.get('/api/review/member-applications/').json()['count'],0)
        self.assertEqual(write(self.author,'post',f"/api/review/member-applications/{a.json()['id']}/decision/",{'lock_version':0,'decision':'APPROVE','reason':'Cannot'}).status_code,404)
        self.assertEqual(write(login_as(self.customer),'post','/api/members/applications/',{'application_kind':'ADMIN','statement':'Escalate'}).status_code,400)

    def test_submission_authorship_records_cannot_be_erased(self):
        from django.db import transaction
        from apps.workflow.models import RevisionEditEvent
        item=self.submit(self.create())
        with self.assertRaises(IntegrityError),transaction.atomic():
            RevisionEditEvent.objects.filter(content_revision_id=item['working_revision']['id']).delete()

    def test_private_external_contributors_are_not_enumerated_by_other_members(self):
        response=write(self.author,'post','/api/content/contributors/',{'display_name':'Unpublished collaborator','external_affiliation':'Private affiliation'})
        self.assertEqual(response.status_code,201)
        student=login_as(self.student)
        self.assertNotIn('Unpublished collaborator',str(student.get('/api/content/contributors/').json()))
        response=write(student,'post','/api/content/items/',{'kind':'PAPER','title':'Cannot probe private authors','detail':{'venue':'J','publication_date':'2025-01-01'},'contributions':[{'contributor':response.json()['id'],'contribution_role':'AUTHOR','position':1}]})
        self.assertEqual(response.status_code,400)

    def test_public_contributor_lookup_uses_approved_signature_not_private_current_name(self):
        c=Contributor.objects.create(display_name='Approved signature',external_affiliation='Approved affiliation')
        item=self.create('PAPER',{'venue':'J','publication_date':'2025-01-01'},[{'contributor':str(c.pk),'contribution_role':'AUTHOR','position':1}])
        link=item['working_revision']['contributions'][0]['id']
        response=write(self.author,'post',f'/api/review/contributions/{link}/confirm/',{'decision':'CONFIRMED','reason':'Verified external author'})
        self.assertEqual(response.status_code,200)
        item=self.submit(self.item(item));self.assertEqual(self.decide(item).status_code,200)
        Contributor.objects.filter(pk=c.pk).update(display_name='Private current name',external_affiliation='Private current affiliation')
        student=login_as(self.student)
        result=student.get('/api/content/contributors/').json()
        self.assertNotIn('Private current',str(result))
        self.assertIn('Approved signature',str(result))

    def test_admin_member_uuid_denial_has_safe_status(self):
        profile=MemberProfile.objects.create(user=self.root)
        response=write(self.author,'post',f'/api/admin/members/{profile.pk}/bind/',{'user_id':self.student.pk})
        self.assertEqual(response.status_code,404)
        self.assertNotIn('Traceback',response.content.decode())

    def test_moderation_reason_is_preserved_in_visible_history(self):
        item=self.submit(self.create());item=self.decide(item).json()
        reason='Distinct unpublish reason retained for audit'
        response=write(self.reviewer,'post',f"/api/content/items/{item['id']}/unpublish/",{'lock_version':item['lock_version'],'reason':reason})
        self.assertEqual(response.status_code,200)
        history=self.author.get(f"/api/content/items/{item['id']}/moderation-history/")
        self.assertEqual(history.status_code,200)
        self.assertEqual(history.json()['results'][0]['reason'],reason)

    def test_reviewer_and_submitter_do_not_replace_actual_content_editor(self):
        item=self.create();admin=login_as(self.admin)
        response=write(admin,'patch',f"/api/content/revisions/{item['working_revision']['id']}/",{'lock_version':item['lock_version'],'title':'Edited by admin'})
        self.assertEqual(response.status_code,200)
        item=self.submit(response.json());self.assertEqual(self.decide(item).status_code,200)
        self.assertEqual(ContentItem.objects.get(pk=item['id']).last_edited_by_id,self.admin.pk)
