from apps.accounts.tests.helpers import AccountFixtures,login_as,write
from apps.members.models import MemberProfile,MemberRevision
from apps.content.models import Contributor


class MembershipFlowTests(AccountFixtures):
    def setUp(self):
        self.person=login_as(self.customer);self.manager=login_as(self.teacher);self.root_client=login_as(self.root)
    def initialize(self):
        response=write(self.person,'post','/api/members/me/draft/',{});self.assertEqual(response.status_code,201);return response.json()
    def apply(self,target=None):
        response=write(self.person,'post','/api/members/applications/',{'application_kind':'STUDENT','statement':'Please verify membership',**({'target_profile':target} if target else {})})
        self.assertEqual(response.status_code,201,response.content);return response.json()
    def decide(self,application,extra=None):
        return write(self.manager,'post',f"/api/review/member-applications/{application['id']}/decision/",{'lock_version':application['lock_version'],'decision':'APPROVE','reason':'Verified',**(extra or {})})
    def member(self):
        draft=self.initialize();application=self.apply();response=self.decide(application);self.assertEqual(response.status_code,200,response.content)
        response=self.person.get('/api/members/me/draft/');return response.json()['draft']
    def update(self,draft):
        response=write(self.person,'patch','/api/members/me/draft/',{'lock_version':draft['lock_version'],'display_name':'Member','slug':'member-test','public_contact_email':'public@example.org','public_contact_enabled':True})
        self.assertEqual(response.status_code,200,response.content);return response.json()
    def submit(self,draft):
        response=write(self.person,'post','/api/members/me/draft/submit/',{'lock_version':draft['lock_version'],'public_visible':True,'contact_visible':True})
        self.assertEqual(response.status_code,200,response.content);return response.json()

    def test_claim_merges_temporary_profile_only_with_explicit_field_choice(self):
        draft=self.initialize();draft=self.update(draft)
        old=MemberProfile.objects.get(user=self.customer)
        target=write(self.manager,'post','/api/admin/members/',{'display_name':'Catalog identity'}).json()
        application=self.apply(target['id'])
        response=self.decide(application,{'use_applicant_fields':True})
        self.assertEqual(response.status_code,200,response.content)
        old.refresh_from_db();self.assertIsNone(old.user_id);self.assertEqual(str(old.merged_into_id),target['id'])
        self.assertEqual(MemberProfile.objects.get(user=self.customer).draft_revision.bio,draft['bio'])
        self.assertEqual(MemberProfile.objects.get(user=self.customer).draft_revision.display_name,'Member')
        self.customer.refresh_from_db();self.assertEqual(self.customer.role,'STUDENT')

    def test_claim_with_existing_contributor_is_not_automatically_reassigned(self):
        self.initialize();old=MemberProfile.objects.get(user=self.customer)
        Contributor.objects.create(member_profile=old,display_name='Protected authorship')
        target=write(self.manager,'post','/api/admin/members/',{'display_name':'Other'}).json()
        response=self.decide(self.apply(target['id']))
        self.assertEqual(response.status_code,409)
        old.refresh_from_db();self.assertEqual(old.user_id,self.customer.pk)
        self.assertIsNone(MemberProfile.objects.get(pk=target['id']).user_id)

    def test_privacy_restriction_invalidates_pending_consent_and_requires_new_review(self):
        draft=self.submit(self.update(self.member()))
        response=write(self.person,'post','/api/members/me/privacy/restrict/',{'scopes':['contact']});self.assertEqual(response.status_code,200)
        version=response.json()['lock_version']
        response=write(self.root_client,'post',f"/api/review/member-revisions/{draft['id']}/decision/",{'lock_version':version,'decision':'APPROVE','reason':'Stale consent'})
        self.assertEqual(response.status_code,409)
        response=write(self.person,'post','/api/members/me/draft/withdraw/',{'lock_version':version});self.assertEqual(response.status_code,200)
        draft=write(self.person,'post','/api/members/me/draft/',{}).json()
        self.assertEqual(draft['display_name'],'Member')
        draft=self.submit(draft)
        response=write(self.root_client,'post',f"/api/review/member-revisions/{draft['id']}/decision/",{'lock_version':draft['lock_version'],'decision':'APPROVE','reason':'Fresh consent'})
        self.assertEqual(response.status_code,200,response.content)
        profile=MemberProfile.objects.get(user=self.customer);self.assertTrue(profile.public_visible);self.assertTrue(profile.contact_visible)
        write(self.person,'post','/api/members/me/privacy/restrict/',{'scopes':['public','contact']})
        profile.refresh_from_db();self.assertFalse(profile.public_visible);self.assertFalse(profile.contact_visible)
        self.assertEqual(profile.published_revision.state,'PUBLISHED')

    def test_repeated_application_and_approval_and_disabled_target(self):
        application=self.apply()
        self.assertEqual(write(self.person,'post','/api/members/applications/',{'application_kind':'STUDENT','statement':'duplicate'}).status_code,409)
        from apps.accounts.models import User
        User.objects.filter(pk=self.customer.pk).update(is_active=False)
        self.assertEqual(self.decide(application).status_code,409)

    def test_teacher_cannot_read_or_approve_root_unpublished_member_profile(self):
        MemberProfile.objects.create(user=self.root,membership_status='ACTIVE')
        draft=write(self.root_client,'post','/api/members/me/draft/',{}).json()
        draft=write(self.root_client,'patch','/api/members/me/draft/',{'lock_version':draft['lock_version'],'display_name':'Root private candidate','slug':'root-private-candidate','education':[{'school':'Root private school','position':1,'is_public':False}]}).json()
        draft=write(self.root_client,'post','/api/members/me/draft/submit/',{'lock_version':draft['lock_version']}).json()
        tasks=self.manager.get('/api/review/member-revisions/')
        self.assertEqual(tasks.status_code,200)
        self.assertNotIn('Root private',str(tasks.json()))
        response=write(self.manager,'post',f"/api/review/member-revisions/{draft['id']}/decision/",{'lock_version':draft['lock_version'],'decision':'APPROVE','reason':'Should not access root profile'})
        self.assertEqual(response.status_code,404)
