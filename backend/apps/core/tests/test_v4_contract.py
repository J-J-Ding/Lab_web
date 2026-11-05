"""V4 acceptance contracts, written before the new apps and endpoints."""
from django.apps import apps
from django.db import IntegrityError, connection, transaction
from django.test import TestCase, TransactionTestCase
from apps.accounts.models import User
from apps.accounts.tests.helpers import AccountFixtures, login_as, write, PASSWORD

DRAFT = '/api/members/me/draft/'


class MemberAPIContracts(AccountFixtures):
    def test_get_draft_is_read_only_and_returns_explicit_empty(self):
        client = login_as(self.customer)
        response = client.get(DRAFT)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['draft'])
        self.assertEqual(apps.get_model('members', 'MemberProfile').objects.count(), 0)

    def test_initialization_is_idempotent_and_keeps_customer_role(self):
        client = login_as(self.customer)
        first = write(client, 'post', DRAFT)
        self.assertEqual(first.status_code, 201)
        second = write(client, 'post', DRAFT)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()['id'], second.json()['id'])
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.role, 'CUSTOMER')

    def test_update_requires_version_and_rejects_privilege_fields(self):
        client = login_as(self.customer)
        initial = write(client, 'post', DRAFT)
        self.assertEqual(initial.status_code, 201)
        for extra in ({'role':'ADMIN'}, {'user':self.root.pk}, {'state':'PUBLISHED'}, {'member_kind':'TEACHER'}):
            response = write(client, 'patch', DRAFT, {'lock_version':0, **extra})
            self.assertEqual(response.status_code, 400)
        response = write(client, 'patch', DRAFT, {'lock_version':0, 'display_name':'New name', 'bio':'Research'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['display_name'], 'New name')
        response = write(client, 'patch', DRAFT, {'lock_version':0, 'display_name':'Stale'})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(client.get(DRAFT).json()['draft']['display_name'], 'New name')

    def test_csrf_and_anonymous_and_cross_account_boundaries(self):
        self.assertEqual(self.client.get(DRAFT).status_code, 403)
        client = login_as(self.customer)
        self.assertEqual(client.post(DRAFT, {}, format='json').status_code, 403)
        write(client, 'post', DRAFT)
        other = login_as(self.student)
        self.assertIsNone(other.get(DRAFT).json()['draft'])
        profile = apps.get_model('members', 'MemberProfile').objects.get(user=self.customer)
        self.assertEqual(other.get(f'/api/members/{profile.pk}/').status_code, 404)
        for user in (self.root, self.admin, self.teacher, self.staff):
            c = login_as(user)
            self.assertIsNone(c.get(DRAFT).json()['draft'])

    def test_nested_profile_validation_and_private_fields(self):
        client = login_as(self.customer)
        write(client, 'post', DRAFT)
        response = write(client, 'patch', DRAFT, {'lock_version':0, 'education':[{'school':'S','start_date':'2025-01-01','end_date':'2020-01-01','position':1}]})
        self.assertEqual(response.status_code, 400)
        response = write(client, 'patch', DRAFT, {'lock_version':0, 'education':[{'school':'S','degree':'MSc','position':1}], 'research_areas':['Control'], 'alumni':{'graduation_year':2024,'destination_type':'WORK','organization':'Lab'}, 'public_contact_enabled':True})
        self.assertEqual(response.status_code, 400)
        response = write(client, 'patch', DRAFT, {'lock_version':0, 'education':[{'school':'S','degree':'MSc','position':1}], 'research_areas':['Control'], 'public_contact_email':'public@example.org','public_contact_enabled':True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['education'][0]['school'],'S')
        body=response.json()
        self.assertNotIn('email', body)
        self.assertNotIn('phone', body)
        self.assertNotIn('user', body)

    def test_overview_and_participations_do_not_create_profiles(self):
        client=login_as(self.customer)
        response=client.get('/api/members/me/overview/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['published_content_count'],0)
        response=client.get('/api/content/participations/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['count'],0)
        self.assertEqual(client.get('/api/content/participations/?kind=INVALID').status_code,400)


class V4InstalledContract(TestCase):
    def test_modular_apps_exist(self):
        for name in ('members','content','assets','workflow'):
            self.assertTrue(apps.is_installed('apps.'+name), name)


class MemberAPIAdditionalContracts(AccountFixtures):
    def test_published_achievements_hide_pending_version_and_other_members(self):
        from apps.content.models import ContentItem,ContentRevision,PaperDetail,Contributor,RevisionContribution
        from apps.content.services import create_content,add_contribution
        from apps.members.services import initialize_draft
        profile,_,_=initialize_draft(self.customer)
        contributor=Contributor.objects.create(display_name='Author',member_profile=profile)
        item=create_content(self.teacher,'PAPER','Published title',{})
        add_contribution(self.teacher,item.working_revision_id,contributor.pk,'AUTHOR',1)
        old=item.working_revision
        ContentRevision.objects.filter(pk=old.pk).update(state='PUBLISHED')
        ContentItem.objects.filter(pk=item.pk).update(published_revision=old,working_revision=None)
        new=ContentRevision.objects.create(item=item,number=2,title='Secret pending title',edited_by=self.teacher)
        PaperDetail.objects.create(revision=new)
        ContentItem.objects.filter(pk=item.pk).update(working_revision=new)
        client=login_as(self.customer)
        response=client.get('/api/content/participations/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['count'],1)
        self.assertEqual(response.json()['results'][0]['title'],'Published title')
        self.assertNotIn('Secret pending title',str(response.json()))
        self.assertEqual(login_as(self.student).get('/api/content/participations/').json()['count'],0)
        ContentItem.objects.filter(pk=item.pk).update(visibility_gate=False)
        self.assertEqual(client.get('/api/content/participations/').json()['count'],0)

    def test_disabled_account_rejected_and_audit_failure_returns_safe_503(self):
        from unittest.mock import patch
        from apps.members.models import MemberProfile
        client=login_as(self.customer)
        with patch('apps.members.services.record',side_effect=IntegrityError('private-debug-secret')):
            response=write(client,'post',DRAFT)
        self.assertEqual(response.status_code,503)
        self.assertNotIn('private-debug-secret',response.content.decode())
        self.assertEqual(MemberProfile.objects.count(),0)
        User.objects.filter(pk=self.customer.pk).update(is_active=False)
        self.assertEqual(client.get(DRAFT).status_code,403)

    def test_unknown_fields_strict_types_and_asset_ownership(self):
        from apps.assets.models import AssetFile
        client=login_as(self.customer)
        write(client,'post',DRAFT)
        asset=AssetFile.objects.create(owner=self.student,storage_key='private/foreign',original_filename='image.png',mime_type='image/png',size=12,sha256='a'*64,scan_status='CLEAN')
        for body in ({'lock_version':True},{'lock_version':'0'}, {'lock_version':0,'phone':'private'}, {'lock_version':0,'public_contact_enabled':'true'}, {'lock_version':0,'avatar_asset':str(asset.pk)}):
            self.assertEqual(write(client,'patch',DRAFT,body).status_code,400)
        self.assertEqual(write(client,'post',DRAFT,{'role':'ADMIN'}).status_code,400)
