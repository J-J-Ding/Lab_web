import csv,io,hashlib,json,uuid
from django.http import HttpResponse
from django.db import transaction
from django.db.models import Count,Q
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from apps.content.public_views import PublicView
from apps.workflow.api import BusinessAPIView
from apps.accounts.permissions import IsManager
from apps.workflow.permissions import actor_for,visible_items
from apps.workflow.audit import record
from apps.content.models import ContentItem
from . import metrics

class PublicOverview(PublicView):
    def get(self,request):
        f=metrics.filters(request);return Response(metrics.envelope(f,metrics.overview(f)))
class PublicAnnual(PublicView):
    def get(self,request):
        f=metrics.filters(request);return Response(metrics.envelope(f,metrics.annual(f)))
class Me(BusinessAPIView):
    def get(self,request):
        if request.query_params:raise ValidationError('No member_id or other private selectors accepted.')
        from apps.members.selectors import own_profile
        from apps.content.selectors import published_for_member
        p=own_profile(request.user);items=ContentItem.objects.filter(created_by=request.user)
        return Response(metrics.envelope({}, {'own_items':items.count(),'own_drafts':items.filter(working_revision__state='DRAFT').count(),'own_submitted':items.filter(working_revision__state='SUBMITTED').count(),'own_published':items.filter(published_revision__isnull=False,visibility_gate=True).count(),'participating_public':published_for_member(p).count()}))
class AdminOverview(BusinessAPIView):
    permission_classes=[IsManager]
    def get(self,request):
        f=metrics.filters(request)
        from apps.members.models import MemberProfile
        profiles=MemberProfile.objects.filter(merged_into__isnull=True)
        if not request.user.is_superuser:profiles=profiles.filter(Q(user=request.user)|Q(user__isnull=True)|Q(user__is_superuser=False,user__role__in=['CUSTOMER','STUDENT','TEACHER']))
        qs=visible_items(request.user).order_by().filter(created_at__year__gte=f['year_from'],created_at__year__lte=f['year_to'])
        if f.get('kind'):qs=qs.filter(kind=f['kind'])
        if f.get('category'):
            c=f['category'];qs=qs.filter(Q(working_revision__paper__category=c)|Q(working_revision__award__category=c)|Q(working_revision__news__category=c)|Q(working_revision__blog__category=c)|Q(published_revision__paper__category=c)|Q(published_revision__award__category=c)|Q(published_revision__news__category=c)|Q(published_revision__blog__category=c))
        return Response(metrics.envelope(f,{'items':qs.count(),'working_states':list(qs.values('working_revision__state').annotate(count=Count('pk'))),'manageable_member_profiles':profiles.count(),'review':metrics.review_metrics(f)}))
class AdminReview(BusinessAPIView):
    permission_classes=[IsManager]
    def get(self,request):
        f=metrics.filters(request);return Response(metrics.envelope(f,metrics.review_metrics(f)))
def safe_cell(value):
    s=str(value or '').replace('\x00','')
    if s.lstrip().startswith(('=','+','-','@')) or any(ord(c)<32 for c in s[:1]):s="'"+s
    return s
class Export(BusinessAPIView):
    permission_classes=[IsManager]
    @transaction.atomic
    def get(self,request):
        from apps.accounts.throttling import consume
        actor=actor_for(request,manager=True);consume('stats_export',str(actor.pk),10)
        f=metrics.filters(request)
        qs=metrics.scoped(f);ids=[]
        for kind in metrics.DATES:
            if not f.get('kind') or f['kind']==kind:ids.extend(list(metrics.kind_rows(f,kind).values_list('pk',flat=True)[:10001]))
        if len(ids)>10000:raise ValidationError('Export exceeds 10000 rows; narrow filters.')
        rows=ContentItem.objects.filter(pk__in=ids).select_related('published_revision').order_by('id')
        buf=io.StringIO();writer=csv.writer(buf);writer.writerow(['id','kind','title','summary'])
        for r in rows:writer.writerow([str(r.pk),r.kind,safe_cell(r.published_revision.title),safe_cell(r.published_revision.summary)])
        from types import SimpleNamespace
        record(actor,SimpleNamespace(pk=uuid.uuid4()),'stats.export',('id','kind','title','summary','count:'+str(len(ids)),'filters_sha256:'+hashlib.sha256(json.dumps(f,sort_keys=True).encode()).hexdigest()))
        response=HttpResponse('\ufeff'+buf.getvalue(),content_type='text/csv; charset=utf-8');response['Content-Disposition']='attachment; filename="lab-statistics.csv"';response['Cache-Control']='no-store';response['X-Content-Type-Options']='nosniff';return response
