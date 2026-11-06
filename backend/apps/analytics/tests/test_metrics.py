from django.test import TestCase
from django.db import transaction
from apps.accounts.tests.helpers import AccountFixtures,login_as
from apps.content.models import ContentItem,ContentRevision
from apps.content.services import create_content
from apps.analytics.views import safe_cell

class StatisticsTests(AccountFixtures):
    def publish(self,kind,detail,title='Example'):
        i=create_content(self.teacher,kind,title,detail)
        with transaction.atomic():
            ContentRevision.objects.filter(pk=i.working_revision_id).update(state='PUBLISHED');ContentItem.objects.filter(pk=i.pk).update(published_revision=i.working_revision,working_revision=None)
        i.refresh_from_db();return i
    def test_unique_public_counts_unknown_and_immediate_unpublish(self):
        i=self.publish('PAPER',{'publication_date':'2026-01-01'});self.publish('PAPER',{});create_content(self.teacher,'PAPER','Private',{})
        r=self.client.get('/api/public/stats/annual/',{'year_from':2025,'year_to':2026,'kind':'PAPER'});self.assertEqual(r.status_code,200,r.content);d=r.json()['data'][0]
        self.assertEqual(d['total'],2);self.assertEqual(d['unknown_date'],1);self.assertIsNone(d['growth_rate'])
        ContentItem.objects.filter(pk=i.pk).update(visibility_gate=False)
        self.assertEqual(self.client.get('/api/public/stats/annual/',{'year_from':2025,'year_to':2026,'kind':'PAPER'}).json()['data'][0]['total'],1)
    def test_private_permissions_and_export_formula_audit(self):
        self.publish('BLOG',{'event_date':'2026-01-01'},'=HYPERLINK("bad")')
        for user in (self.customer,self.student):self.assertEqual(login_as(user).get('/api/admin/stats/overview/').status_code,403)
        c=login_as(self.teacher);r=c.get('/api/admin/stats/overview/');self.assertEqual(r.status_code,200,r.content)
        r=c.get('/api/admin/stats/export/',{'year_from':2026,'year_to':2026});self.assertEqual(r.status_code,200,r.content);self.assertIn("'=HYPERLINK",r.content.decode())
        from apps.workflow.models import BusinessAuditLog
        self.assertTrue(BusinessAuditLog.objects.filter(action='stats.export').exists())
        for text in ('=bad',' +bad','\tbad','@bad','-bad'):self.assertTrue(safe_cell(text).startswith("'"))
    def test_filters_and_own_private_scope(self):
        for params in ({'year_from':1900,'year_to':2026},{'year_from':'²'},{'member_id':1},{'kind':'HIDDEN'}):self.assertEqual(self.client.get('/api/public/stats/overview/',params).status_code,400)
        self.assertEqual(login_as(self.customer).get('/api/stats/me/',{'member_id':self.teacher.pk}).status_code,400)
    def test_shanghai_new_year_boundary_and_member_privacy(self):
        from apps.members.models import MemberProfile,MemberRevision,MemberSlug
        self.publish('ACTIVITY',{'starts_at':'2025-12-31T16:30:00Z','body':'Shanghai new year'})
        r=self.client.get('/api/public/stats/annual/',{'year_from':2025,'year_to':2026,'kind':'ACTIVITY'});self.assertEqual(r.status_code,200,r.content)
        self.assertEqual(r.json()['data'][0]['series'],[{'year':2025,'count':0},{'year':2026,'count':1}])
        with transaction.atomic():
            p=MemberProfile.objects.create(public_visible=True);v=MemberRevision.objects.create(profile=p,number=1,display_name='Example',slug='stat-member',member_kind='TEACHER');MemberSlug.objects.create(profile=p,slug=v.slug);MemberRevision.objects.filter(pk=v.pk).update(state='PUBLISHED');MemberProfile.objects.filter(pk=p.pk).update(published_revision=v)
        self.assertEqual(self.client.get('/api/public/stats/overview/').json()['data']['members']['total'],1)
        MemberProfile.objects.filter(pk=p.pk).update(public_visible=False)
        self.assertEqual(self.client.get('/api/public/stats/overview/').json()['data']['members']['total'],0)
    def test_export_audit_failure_no_file(self):
        from unittest.mock import patch
        from django.db import OperationalError
        c=login_as(self.teacher)
        with patch('apps.analytics.views.record',side_effect=OperationalError('private failure')):
            r=c.get('/api/admin/stats/export/')
        self.assertEqual(r.status_code,503);self.assertNotIn('Content-Disposition',r)
    def test_public_order_date_is_derived_from_published_snapshot(self):
        i=self.publish('BLOG',{'event_date':'2025-02-03'});self.assertEqual(str(i.public_sort_date),'2025-02-03')
        ContentItem.objects.filter(pk=i.pk).update(public_sort_date='2099-01-01');i.refresh_from_db();self.assertEqual(str(i.public_sort_date),'2025-02-03')
        r=self.client.get('/api/public/content/'+str(i.pk)+'/');self.assertEqual(r.json()['date'],'2025-02-03')
