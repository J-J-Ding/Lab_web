from django.db import transaction
from django.test import TestCase
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.content.services import create_content
from apps.content.models import ContentItem,ContentRevision,Contributor,RevisionContribution,ContentProjectLink
from apps.members.models import MemberProfile,MemberRevision,MemberSlug,EducationEntry,AlumniDestination


class PublicTests(TestCase):
    def setUp(self):
        self.actor=User.objects.create(username='public-fixture',role='TEACHER')
        self.client=APIClient()
    def published(self,kind='BLOG',title='Public A',detail=None):
        item=create_content(self.actor,kind,title,detail or {'body':'Approved body'})
        with transaction.atomic():
            ContentRevision.objects.filter(pk=item.working_revision_id).update(state='PUBLISHED')
            ContentItem.objects.filter(pk=item.pk).update(published_revision=item.working_revision,working_revision=None)
        item.refresh_from_db();return item
    def member(self,slug='person'):
        p=MemberProfile.objects.create(membership_status='ACTIVE',public_visible=True,education_visible=True,alumni_visible=True)
        r=MemberRevision.objects.create(profile=p,number=1,display_name='Approved Name',slug=slug)
        MemberSlug.objects.create(profile=p,slug=slug);MemberSlug.objects.create(profile=p,slug=slug+'-old')
        EducationEntry.objects.create(revision=r,school='Public School',is_public=True,position=1)
        EducationEntry.objects.create(revision=r,school='PRIVATE SCHOOL',is_public=False,position=2)
        with transaction.atomic():
            MemberRevision.objects.filter(pk=r.pk).update(state='PUBLISHED')
            MemberProfile.objects.filter(pk=p.pk).update(published_revision=r)
        p.refresh_from_db();return p
    def test_public_projection_and_pending_not_searchable(self):
        item=self.published('PROJECT',detail={'funding_amount':'12345.00','project_number':'DEMO-1'})
        create_content(self.actor,'BLOG','PRIVATE DRAFT',{'body':'Private'})
        response=self.client.get('/api/public/content/')
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response.json()['count'],1)
        self.assertNotIn('funding_amount',str(response.json()))
        self.assertEqual(self.client.get('/api/public/content/',{'q':'PRIVATE'}).json()['count'],0)
        self.assertEqual(self.client.get('/api/public/content/',{'q':'x'}).status_code,400)
        self.assertEqual(self.client.get('/api/public/content/',{'include_private':'true'}).status_code,400)
        self.assertEqual(self.client.get('/api/public/content/',{'year':'bad'}).status_code,400)
        self.assertEqual(self.client.post('/api/public/content/',{},format='json').status_code,405)
        self.assertEqual(self.client.get(f'/api/public/content/{item.pk}/').status_code,200)
    def test_three_member_achievements_and_project_visibility(self):
        project=self.published('PROJECT',detail={'project_number':'PRJ-2'})
        paper=create_content(self.actor,'PAPER','Shared paper',{'publication_date':'2026-01-01'})
        people=[self.member('person'+str(i)) for i in range(3)]
        for i,p in enumerate(people,1):
            c=Contributor.objects.create(member_profile=p,display_name='PRIVATE NEW NAME')
            RevisionContribution.objects.create(revision=paper.working_revision,contributor=c,contribution_role='AUTHOR',position=i,approved_display_name='Approved '+str(i))
        ContentProjectLink.objects.create(source_revision=paper.working_revision,target_project=project)
        with transaction.atomic():
            ContentRevision.objects.filter(pk=paper.working_revision_id).update(state='PUBLISHED')
            ContentItem.objects.filter(pk=paper.pk).update(published_revision=paper.working_revision,working_revision=None)
        for p in people:
            r=self.client.get(f'/api/public/members/{p.published_revision.slug}/achievements/')
            self.assertEqual(r.status_code,200,r.content);self.assertEqual(r.json()['results'][0]['id'],str(paper.pk))
        r=self.client.get(f'/api/public/projects/{project.pk}/outputs/')
        self.assertEqual(r.json()['results'][0]['id'],str(paper.pk))
        self.assertNotIn('PRIVATE NEW NAME',str(r.json()))
        ContentItem.objects.filter(pk=paper.pk).update(visibility_gate=False)
        self.assertEqual(self.client.get(f'/api/public/projects/{project.pk}/outputs/').json()['count'],0)
        self.assertEqual(self.client.get(f'/api/public/content/{paper.pk}/').status_code,404)
    def test_member_alias_and_privacy_immediate(self):
        p=self.member()
        r=self.client.get('/api/public/members/person-old/')
        self.assertEqual(r.status_code,200,r.content)
        self.assertNotIn('PRIVATE SCHOOL',str(r.json()));self.assertNotIn('user',r.json())
        self.assertIn('no-store',r['Cache-Control'])
        MemberProfile.objects.filter(pk=p.pk).update(education_visible=False)
        self.assertNotIn('education',self.client.get('/api/public/members/person/').json())
        MemberProfile.objects.filter(pk=p.pk).update(public_visible=False)
        self.assertEqual(self.client.get('/api/public/members/person-old/').status_code,404)
        self.assertEqual(self.client.get('/api/public/members/person/achievements/').status_code,404)
    def test_fixed_pages_and_graduates(self):
        self.published('LAB_PAGE',detail={'page_key':'about','body':'About laboratory'})
        self.assertEqual(self.client.get('/api/public/pages/about/').status_code,200)
        self.assertEqual(self.client.get('/api/public/pages/secret/').status_code,404)
        p=self.member('alumnus')
        # No alumni record means no destination disclosure.
        self.assertEqual(self.client.get('/api/public/graduates/').json()['count'],0)
    def test_database_failure_safe_503(self):
        from unittest.mock import patch
        from django.db import OperationalError
        with patch('apps.content.public_views.content_queryset',side_effect=OperationalError('private database details')):
            r=self.client.get('/api/public/content/')
        self.assertEqual(r.status_code,503);self.assertNotIn('private database',str(r.content))

    def test_query_budget_20_and_100_rows(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from time import perf_counter
        for n in range(100):self.published(title=f'Benchmark {n:03d}')
        counts=[]
        for size in (20,100):
            with CaptureQueriesContext(connection) as captured:
                start=perf_counter();r=self.client.get('/api/public/content/',{'page_size':size});elapsed=perf_counter()-start
            self.assertEqual(r.status_code,200,r.content);self.assertEqual(len(r.json()['results']),size)
            counts.append(len(captured));print(f'V6 PERF N={size} queries={len(captured)} elapsed_ms={elapsed*1000:.2f}')
        self.assertLessEqual(counts[1],counts[0]+1);self.assertLessEqual(counts[1],15)

from apps.accounts.tests.helpers import AccountFixtures,login_as,write

class PublicWorkflowIntegrationTests(AccountFixtures):
    member=PublicTests.member
    def test_approved_paper_three_profiles_project_and_pending_isolation(self):
        author=login_as(self.teacher);reviewer=login_as(self.root)
        people=[self.member('linked-'+str(i)) for i in range(3)]
        contributors=[Contributor.objects.create(member_profile=p,display_name='Approved author '+str(i)) for i,p in enumerate(people)]
        def draft(kind,title,detail,links):
            r=write(author,'post','/api/content/items/',{'kind':kind,'title':title,'detail':detail,'contributions':links});self.assertEqual(r.status_code,201,r.content);return r.json()
        def approve(item):
            for link in item['working_revision']['contributions']:
                r=write(reviewer,'post',f"/api/review/contributions/{link['id']}/confirm/",{'decision':'CONFIRMED','reason':'Explicit example evidence'});self.assertEqual(r.status_code,200,r.content)
            item=author.get(f"/api/content/items/{item['id']}/").json()
            r=write(author,'post',f"/api/content/revisions/{item['working_revision']['id']}/submit/",{'lock_version':item['lock_version']});self.assertEqual(r.status_code,200,r.content);item=r.json()
            r=write(reviewer,'post',f"/api/review/revisions/{item['working_revision']['id']}/decision/",{'decision':'APPROVE','reason':'Independent review','lock_version':item['lock_version']});self.assertEqual(r.status_code,200,r.content);return r.json()
        project=approve(draft('PROJECT','Shared project',{'funder':'Example fund','start_date':'2026-01-01'},[{'contributor':str(contributors[0].pk),'position':1,'contribution_role':'LEAD'}]))
        paper=draft('PAPER','Shared publication',{'venue':'Example journal','publication_date':'2026-01-01'},[{'contributor':str(c.pk),'position':i,'contribution_role':'AUTHOR'} for i,c in enumerate(contributors,1)])
        r=write(author,'patch',f"/api/content/revisions/{paper['working_revision']['id']}/",{'lock_version':paper['lock_version'],'project_links':[project['id']]});self.assertEqual(r.status_code,200,r.content)
        paper=approve(r.json());anonymous=APIClient()
        for p in people:
            rows=anonymous.get(f'/api/public/members/{p.published_revision.slug}/achievements/',{'kind':'PAPER'}).json()['results'];self.assertEqual([x['id'] for x in rows],[paper['id']])
        self.assertEqual(anonymous.get(f"/api/public/projects/{project['id']}/outputs/").json()['results'][0]['id'],paper['id'])
        r=write(author,'post',f"/api/content/items/{paper['id']}/revisions/",{'lock_version':paper['lock_version']});self.assertEqual(r.status_code,201);pending=r.json()
        r=write(author,'patch',f"/api/content/revisions/{pending['working_revision']['id']}/",{'lock_version':pending['lock_version'],'title':'SECRET PENDING B'});self.assertEqual(r.status_code,200)
        self.assertEqual(anonymous.get(f"/api/public/content/{paper['id']}/").json()['title'],'Shared publication')
        self.assertEqual(anonymous.get('/api/public/content/',{'q':'SECRET'}).json()['count'],0)

class PublicInputTests(TestCase):
    def test_numeric_unicode_and_long_parameters_are_validation_errors(self):
        for key,value in [('page','²'),('page_size','²'),('year','²'),('page','1'*5000),('direction','a'*1000)]:
            r=self.client.get('/api/public/members/',{key:value});self.assertEqual(r.status_code,400,(key,r.status_code))
