from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError,close_old_connections,transaction
from django.test import TransactionTestCase
from rest_framework.exceptions import NotFound
from apps.accounts.models import User
from apps.accounts.tests.helpers import PASSWORD
from apps.workflow.models import BusinessAuditLog
from apps.members.models import MemberProfile,MemberRevision,MemberPrivateData,EducationEntry,AlumniDestination
from apps.members.services import initialize_draft,update_draft,create_unbound_profile,bind_profile,VersionConflict
from apps.members.serializers import public_member


class MemberServicesTests(TransactionTestCase):
    def setUp(self):
        self.user=User.objects.create(username='person',password=make_password(PASSWORD))
        self.manager=User.objects.create(username='manager',role='TEACHER')
        self.root=User.objects.create(username='root',is_superuser=True)

    def test_draft_edit_never_changes_published_snapshot_or_public_privacy(self):
        profile,rev,_=initialize_draft(self.user)
        from apps.members.models import MemberSlug
        MemberSlug.objects.create(profile=profile,slug='approved-member')
        rev.slug='approved-member'
        rev.display_name='Approved';rev.public_contact_email='public@example.org';rev.public_contact_enabled=True;rev.save()
        EducationEntry.objects.create(revision=rev,school='Public School',is_public=True,position=1)
        EducationEntry.objects.create(revision=rev,school='Private School',is_public=False,position=2)
        MemberPrivateData.objects.filter(profile=profile).update(phone='secret-phone',internal_contact='secret@example.org')
        with transaction.atomic():
            MemberRevision.objects.filter(pk=rev.pk).update(state='PUBLISHED')
            MemberProfile.objects.filter(pk=profile.pk).update(published_revision=rev,draft_revision=None,public_visible=True,education_visible=True)
        profile.refresh_from_db()
        public=public_member(profile)
        self.assertEqual(public['display_name'],'Approved')
        self.assertEqual([x['school'] for x in public['education']],['Public School'])
        self.assertNotIn('phone',public);self.assertNotIn('public_contact_email',public)
        profile,draft,_=initialize_draft(self.user)
        update_draft(self.user,{'lock_version':profile.lock_version,'display_name':'Unreviewed'})
        profile.refresh_from_db()
        self.assertEqual(public_member(profile)['display_name'],'Approved')
        self.assertEqual(MemberRevision.objects.get(pk=rev.pk).display_name,'Approved')
        self.assertEqual(draft.education.count(),2)
        profile.public_visible=False;profile.save()
        self.assertIsNone(public_member(profile))

    def test_public_revision_and_children_are_immutable(self):
        profile,rev,_=initialize_draft(self.user)
        with transaction.atomic():
            MemberRevision.objects.filter(pk=rev.pk).update(state='PUBLISHED')
            MemberProfile.objects.filter(pk=profile.pk).update(published_revision=rev,draft_revision=None)
        with self.assertRaises(IntegrityError),transaction.atomic():
            MemberRevision.objects.filter(pk=rev.pk).update(bio='Bypassed')
        with self.assertRaises(IntegrityError),transaction.atomic():
            EducationEntry.objects.create(revision=rev,school='Bypassed',position=1)

    def test_foreign_pointer_and_duplicate_binding_rejected(self):
        p1,r1,_=initialize_draft(self.user)
        p2=MemberProfile.objects.create()
        with self.assertRaises(IntegrityError),transaction.atomic():
            MemberProfile.objects.filter(pk=p2.pk).update(draft_revision=r1)
        with self.assertRaises(IntegrityError),transaction.atomic():
            MemberProfile.objects.create(user=self.user)

    def test_audit_failure_rolls_back_all_profile_writes(self):
        with patch('apps.members.services.record',side_effect=IntegrityError('injected')):
            with self.assertRaises(IntegrityError):
                initialize_draft(self.user)
        self.assertEqual(MemberProfile.objects.count(),0)
        profile,rev,_=initialize_draft(self.user)
        with patch('apps.members.services.record',side_effect=IntegrityError('injected')):
            with self.assertRaises(IntegrityError):
                update_draft(self.user,{'lock_version':0,'display_name':'No commit'})
        rev.refresh_from_db();profile.refresh_from_db()
        self.assertEqual(rev.display_name,'')
        self.assertEqual(profile.lock_version,0)

    def test_manager_cannot_bind_or_take_over_root_or_admin_profiles(self):
        admin=User.objects.create(username='admin',role='ADMIN')
        for target in (admin,self.root):
            p=create_unbound_profile(self.manager)
            with self.assertRaises(NotFound):
                bind_profile(self.manager,p.pk,target.pk)
        p=create_unbound_profile(self.root)
        bind_profile(self.root,p.pk,admin.pk)
        admin.refresh_from_db();self.assertEqual(admin.role,'ADMIN')

    def test_concurrent_initialization_creates_one_draft(self):
        def init(_):
            close_old_connections()
            try:
                user=User.objects.get(pk=self.user.pk)
                p,r,_=initialize_draft(user)
                return p.pk,r.pk
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(init,range(2)))
        self.assertEqual(results[0],results[1])
        self.assertEqual(MemberProfile.objects.count(),1)
        self.assertEqual(MemberRevision.objects.count(),1)

    def test_concurrent_optimistic_edits_have_one_conflict(self):
        initialize_draft(self.user)
        def edit(i):
            close_old_connections()
            try:
                user=User.objects.get(pk=self.user.pk)
                try:
                    update_draft(user,{'lock_version':0,'display_name':str(i)})
                    return 'ok'
                except VersionConflict:return 'conflict'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(edit,range(2)))
        self.assertCountEqual(results,['ok','conflict'])

    def test_concurrent_binding_one_account_two_profiles(self):
        profiles=[create_unbound_profile(self.manager) for _ in range(2)]
        def bind(p):
            close_old_connections()
            try:
                try:
                    bind_profile(User.objects.get(pk=self.manager.pk),p.pk,self.user.pk)
                    return 'ok'
                except VersionConflict:return 'conflict'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(bind,profiles))
        self.assertCountEqual(results,['ok','conflict'])
        self.assertEqual(MemberProfile.objects.filter(user=self.user).count(),1)

    def test_date_and_year_constraints_apply_in_database(self):
        p,r,_=initialize_draft(self.user)
        with self.assertRaises(IntegrityError),transaction.atomic():
            EducationEntry.objects.create(revision=r,school='S',position=1,start_date='2025-01-01',end_date='2020-01-01')
        with self.assertRaises(IntegrityError),transaction.atomic():
            AlumniDestination.objects.create(revision=r,graduation_year=1800,destination_type='WORK')

    def test_audit_never_copies_private_or_profile_values(self):
        initialize_draft(self.user)
        update_draft(self.user,{'lock_version':0,'display_name':'Sensitive Name','public_contact_email':'sensitive@example.org'})
        logs=list(BusinessAuditLog.objects.values())
        self.assertNotIn('Sensitive Name',str(logs))
        self.assertNotIn('sensitive@example.org',str(logs))
        self.assertIn('public_contact_email',str(logs))

    def test_published_research_term_cannot_be_renamed_under_a_snapshot(self):
        from apps.members.models import ResearchArea,MemberResearchArea
        profile,rev,_=initialize_draft(self.user)
        area=ResearchArea.objects.create(name='Approved research term')
        MemberResearchArea.objects.create(revision=rev,area=area,position=1)
        with transaction.atomic():
            MemberRevision.objects.filter(pk=rev.pk).update(state='PUBLISHED')
            MemberProfile.objects.filter(pk=profile.pk).update(published_revision=rev,draft_revision=None)
        with self.assertRaises(IntegrityError),transaction.atomic():
            ResearchArea.objects.filter(pk=area.pk).update(name='Unreviewed rename')

    def test_public_slug_must_be_reserved_to_the_same_profile(self):
        from apps.members.models import MemberSlug
        profile,rev,_=initialize_draft(self.user)
        rev.slug='member';rev.save()
        with transaction.atomic():
            MemberRevision.objects.filter(pk=rev.pk).update(state='PUBLISHED')
            MemberProfile.objects.filter(pk=profile.pk).update(published_revision=rev,draft_revision=None)
        with self.assertRaises(IntegrityError),transaction.atomic():
            MemberProfile.objects.filter(pk=profile.pk).update(public_visible=True)
        MemberSlug.objects.create(profile=profile,slug='member')
        MemberProfile.objects.filter(pk=profile.pk).update(public_visible=True)
