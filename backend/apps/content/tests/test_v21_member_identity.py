from django.test import TestCase
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.members.models import MemberProfile, MemberRevision, MemberSlug


class MemberIdentityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username='identity-fixture', role='TEACHER')
        self.profile = self.make_member('identity-person', self.user, 'TEACHER')

    def make_member(self, slug, user=None, kind='STUDENT', status='ACTIVE'):
        profile = MemberProfile.objects.create(user=user, public_visible=True)
        revision = MemberRevision.objects.create(profile=profile, number=1, state='PUBLISHED',
            display_name=slug, slug=slug, member_kind=kind, public_member_status=status)
        profile.published_revision = revision
        profile.save(update_fields=['published_revision'])
        MemberSlug.objects.create(profile=profile, slug=slug)
        return profile

    def members(self, kind=None):
        response = self.client.get('/api/public/members/', {'member_kind':kind} if kind else {})
        self.assertEqual(response.status_code, 200)
        return response.json()['results']

    def test_current_identity_updates_both_filter_and_detail_without_profile_save(self):
        for role in ('STUDENT', 'TEACHER'):
            User.objects.filter(pk=self.user.pk).update(role=role)
            rows = self.members(role)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['member_kind'], role)
            other = 'TEACHER' if role == 'STUDENT' else 'STUDENT'
            self.assertEqual(self.members(other), [])
            detail = self.client.get('/api/public/members/identity-person/')
            self.assertEqual(detail.json()['member_kind'], role)
        self.profile.published_revision.refresh_from_db()
        self.assertEqual(self.profile.published_revision.member_kind, 'TEACHER')

    def test_cancelled_customer_and_root_are_hidden(self):
        for fields in ({'is_active':False}, {'is_active':True,'role':'CUSTOMER'},
                       {'role':'TEACHER','is_superuser':True}):
            User.objects.filter(pk=self.user.pk).update(**fields)
            self.assertEqual(self.members(), [])
            self.assertEqual(self.client.get('/api/public/members/identity-person/').status_code, 404)

    def test_legacy_unlinked_member_and_graduation_remain_independent(self):
        self.make_member('legacy', kind='TEACHER')
        alumni = User.objects.create(username='alumni-fixture', role='TEACHER')
        self.make_member('alumni', alumni, kind='TEACHER', status='ALUMNI')
        User.objects.filter(pk__in=[self.user.pk, alumni.pk]).update(role='STUDENT')
        self.assertEqual([r['slug'] for r in self.members('TEACHER')], ['legacy'])
        self.assertEqual(next(r for r in self.members('STUDENT') if r['slug']=='identity-person')['public_member_status'], 'ACTIVE')
        graduates = self.client.get('/api/public/graduates/').json()['results']
        self.assertEqual(graduates[0]['member_kind'], 'STUDENT')
