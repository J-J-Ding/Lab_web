from django.apps import apps
from django.db import IntegrityError, connection, transaction
from django.test import TransactionTestCase
from apps.accounts.models import User


class ContentGraphContracts(TransactionTestCase):
    def setUp(self):
        self.user=User.objects.create_user(username='creator',role='TEACHER')

    def models(self):
        self.assertTrue(apps.is_installed('apps.content'))
        from apps.content import models
        self.assertTrue(hasattr(models, "ContentItem"), "V4 content model missing")
        return models

    def paper(self, title='Paper', doi=''):
        from apps.content.services import create_content
        return create_content(self.user, 'PAPER', title, {'doi':doi,'publication_date':'2024-01-01'})

    def test_one_paper_three_members_external_author_and_no_duplicate_counts(self):
        m=self.models()
        from apps.members.models import MemberProfile
        from apps.content.services import add_contribution
        from apps.content.selectors import published_for_member
        item=self.paper()
        revision=item.working_revision
        profiles=[MemberProfile.objects.create() for _ in range(3)]
        for index,profile in enumerate(profiles):
            contributor=m.Contributor.objects.create(display_name=f'Member {index}', member_profile=profile)
            add_contribution(self.user, revision.pk, contributor.pk, 'AUTHOR',index+1)
        external=m.Contributor.objects.create(display_name='External',external_affiliation='University')
        add_contribution(self.user, revision.pk, external.pk,'AUTHOR',4)
        with transaction.atomic():
            m.ContentRevision.objects.filter(pk=revision.pk).update(state='PUBLISHED')
            m.ContentItem.objects.filter(pk=item.pk).update(published_revision=revision,working_revision=None)
        for profile in profiles:
            self.assertEqual(list(published_for_member(profile).values_list('pk',flat=True)),[item.pk])
        self.assertEqual(m.ContentItem.objects.count(),1)
        self.assertEqual(m.RevisionContribution.objects.count(),4)

    def test_normalized_doi_is_unique_and_survives_drafts(self):
        self.models()
        first=self.paper(doi='https://doi.org/10.1000/ABC')
        self.models().PaperDetail.objects.filter(revision=first.working_revision).update(doi='')
        with self.assertRaises(IntegrityError):
            self.paper(doi=' 10.1000/abc ')
        m=self.models()
        self.assertEqual(m.ContentItem.objects.count(),1)
        self.assertEqual(m.ContentIdentifier.objects.get(item=first).value,'10.1000/abc')

    def test_similar_titles_are_not_automatically_merged(self):
        m=self.models()
        from apps.content.services import possible_duplicates
        self.paper('A paper without DOI')
        other=self.paper('A paper without DOI')
        self.assertEqual(m.ContentItem.objects.count(),2)
        self.assertTrue(possible_duplicates(other))

    def test_missing_or_wrong_detail_fails_at_commit_even_direct_orm(self):
        m=self.models()
        with self.assertRaises(IntegrityError),transaction.atomic():
            item=m.ContentItem.objects.create(kind='PAPER',created_by=self.user)
            m.ContentRevision.objects.create(item=item,number=1,title='Missing')
        with self.assertRaises(IntegrityError),transaction.atomic():
            item=m.ContentItem.objects.create(kind='PAPER',created_by=self.user)
            revision=m.ContentRevision.objects.create(item=item,number=1,title='Wrong')
            m.ProjectDetail.objects.create(revision=revision)

    def test_published_pointer_cannot_reference_other_item(self):
        m=self.models();a=self.paper('A');b=self.paper('B')
        with self.assertRaises(IntegrityError),transaction.atomic():
            m.ContentItem.objects.filter(pk=a.pk).update(published_revision=b.working_revision)

    def test_author_role_position_and_snapshot_are_enforced(self):
        m=self.models()
        from apps.content.services import add_contribution
        from rest_framework.exceptions import ValidationError
        item=self.paper()
        c=m.Contributor.objects.create(display_name='Original name')
        add_contribution(self.user,item.working_revision_id,c.pk,'AUTHOR',1)
        c.display_name='Renamed';c.save()
        self.assertEqual(m.RevisionContribution.objects.get().approved_display_name,'Original name')
        with self.assertRaises(ValidationError):
            add_contribution(self.user,item.working_revision_id,c.pk,'LEAD',2)
        c2=m.Contributor.objects.create(display_name='Other')
        with self.assertRaises(IntegrityError):
            add_contribution(self.user,item.working_revision_id,c2.pk,'AUTHOR',1)

    def test_direct_sql_cross_type_and_immutable_snapshot_rejected(self):
        m=self.models();item=self.paper();rev=item.working_revision
        with self.assertRaises(IntegrityError),transaction.atomic():
            with connection.cursor() as c:
                c.execute('INSERT INTO content_projectdetail (revision_id, project_number, funder, level, start_date, end_date, status, funding_amount) VALUES (%s,%s,%s,%s,NULL,NULL,%s,NULL)',[str(rev.pk),'','','','ACTIVE'])
        with transaction.atomic():
            m.ContentRevision.objects.filter(pk=rev.pk).update(state='PUBLISHED')
            m.ContentItem.objects.filter(pk=item.pk).update(published_revision=rev,working_revision=None)
        with self.assertRaises(IntegrityError),transaction.atomic():
            m.PaperDetail.objects.filter(revision=rev).update(venue='Mutated')
        with self.assertRaises(IntegrityError),transaction.atomic():
            m.ContentRevision.objects.filter(pk=rev.pk).update(title='Mutated')

    def test_account_deletion_preserves_history(self):
        m=self.models();item=self.paper()
        self.user.delete()
        item.refresh_from_db()
        self.assertIsNone(item.created_by)
        self.assertEqual(m.PaperDetail.objects.count(),1)

    def test_database_rejects_noncanonical_identifier_and_unreserved_doi(self):
        m=self.models();item=self.paper()
        with self.assertRaises(IntegrityError),transaction.atomic():
            m.ContentIdentifier.objects.create(item=item,scheme='DOI',value='https://doi.org/10.1000/UPPER')
        with self.assertRaises(IntegrityError),transaction.atomic():
            m.PaperDetail.objects.filter(revision=item.working_revision).update(doi='10.1000/unreserved')

    def test_wrong_project_target_and_contribution_role_direct_writes(self):
        m=self.models();item=self.paper();other=self.paper('Other')
        with self.assertRaises(IntegrityError),transaction.atomic():
            m.ContentProjectLink.objects.create(source_revision=item.working_revision,target_project=other)
        c=m.Contributor.objects.create(display_name='Name')
        with self.assertRaises(IntegrityError),transaction.atomic():
            m.RevisionContribution.objects.create(revision=item.working_revision,contributor=c,contribution_role='LEAD',position=1,approved_display_name='Name')

    def test_private_project_funding_is_not_in_participation_projection(self):
        self.models()
        from apps.content.services import create_content
        from apps.content.serializers import public_content
        item=create_content(self.user,'PROJECT','Secret funding',{'funding_amount':'123456.00'})
        with transaction.atomic():
            m=self.models()
            m.ContentRevision.objects.filter(pk=item.working_revision_id).update(state='PUBLISHED')
            m.ContentItem.objects.filter(pk=item.pk).update(published_revision=item.working_revision,working_revision=None)
        item.refresh_from_db()
        self.assertNotIn('funding_amount',str(public_content(item)))
        self.assertNotIn('123456',str(public_content(item)))

    def test_concurrent_doi_reservation_has_one_winner(self):
        from concurrent.futures import ThreadPoolExecutor
        from django.db import close_old_connections
        from apps.content.services import create_content
        m=self.models()
        users=[User.objects.create(username='manager'+str(i),role='TEACHER') for i in range(2)]
        def create(user):
            close_old_connections()
            try:
                try:
                    create_content(User.objects.get(pk=user.pk),'PAPER','Same DOI',{'doi':'10.1000/concurrent'})
                    return 'created'
                except IntegrityError:return 'duplicate'
            finally:close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            result=list(pool.map(create,users))
        self.assertCountEqual(result,['created','duplicate'])
        self.assertEqual(m.ContentItem.objects.count(),1)
        self.assertEqual(m.ContentRevision.objects.count(),1)

    def test_all_independent_detail_types_and_identifier_normalization(self):
        from apps.content.services import create_content
        m=self.models()
        data={'PROJECT':{'project_number':' abc 001 '},'AWARD':{'event_name':'Competition'},
              'ACTIVITY':{'location':'Lab'},'NEWS':{'body':'News'},'BLOG':{'body':'Blog'},
              'PUBLICATION':{'isbn':'978-0-306-40615-7'},'LAB_PAGE':{'page_key':'about'}}
        for kind,detail in data.items():
            item=create_content(self.user,kind,kind,detail)
            self.assertTrue(m.DETAIL_MODELS[kind].objects.filter(revision=item.working_revision).exists())
        self.assertEqual(m.ContentIdentifier.objects.get(scheme='PROJECT').value,'ABC001')
        self.assertEqual(m.ContentIdentifier.objects.get(scheme='ISBN').value,'9780306406157')

    def test_customer_cannot_create_content_even_with_profile_and_invalid_fields_fail(self):
        from apps.content.services import create_content
        from apps.members.models import MemberProfile
        from rest_framework.exceptions import PermissionDenied,ValidationError
        u=User.objects.create(username='customer')
        MemberProfile.objects.create(user=u,membership_status='ACTIVE')
        with self.assertRaises(PermissionDenied):
            create_content(u,'PAPER','Unauthorized',{})
        with self.assertRaises(ValidationError):
            create_content(self.user,'PAPER','Title',{'role':'ADMIN'})
        with self.assertRaises(ValidationError):
            create_content(self.user,'PROJECT','Title',{'start_date':'2025-01-01','end_date':'2020-01-01'})
        with self.assertRaises(ValidationError):
            create_content(self.user,'PUBLICATION','Title',{'isbn':'9780306406158'})

    def test_content_audit_failure_rolls_back_identifier_and_details(self):
        from unittest.mock import patch
        m=self.models()
        with patch('apps.content.services.record',side_effect=IntegrityError('injected')):
            with self.assertRaises(IntegrityError):
                self.paper(doi='10.1000/rollback')
        self.assertEqual(m.ContentItem.objects.count(),0)
        self.assertEqual(m.PaperDetail.objects.count(),0)
        self.assertEqual(m.ContentIdentifier.objects.count(),0)

    def test_referenced_project_cannot_change_its_stable_content_kind(self):
        from apps.content.services import create_content
        m=self.models()
        target=create_content(self.user,'PROJECT','Project',{})
        source=self.paper()
        m.ContentProjectLink.objects.create(source_revision=source.working_revision,target_project=target)
        with self.assertRaises(IntegrityError),transaction.atomic():
            m.ProjectDetail.objects.filter(revision=target.working_revision).delete()
            m.PaperDetail.objects.create(revision=target.working_revision)
            m.ContentItem.objects.filter(pk=target.pk).update(kind='PAPER')
        target.refresh_from_db()
        self.assertEqual(target.kind,'PROJECT')
