"""Versioned metric definitions; all public counts start at the public visibility boundary."""
from datetime import datetime,time
from zoneinfo import ZoneInfo
from django.db.models import Count,Q,F,DurationField,ExpressionWrapper
from django.db.models.functions import ExtractYear
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from apps.content.public_selectors import content_queryset,member_queryset,published_items_base
from apps.content.models import ContentItem

VERSION='v8.1'
DATES={'PATENT':'published_revision__patent__application_date','PAPER':'published_revision__paper__publication_date','PROJECT':'published_revision__project__start_date','AWARD':'published_revision__award__award_date','ACTIVITY':'published_revision__activity__starts_at','NEWS':'published_revision__news__event_date','BLOG':'published_revision__blog__event_date','PUBLICATION':'published_revision__publication__publication_date'}
def filters(request):
    p=request.query_params
    if set(p)-{'year_from','year_to','kind','category'}:raise ValidationError('Unsupported statistics filter.')
    for key in p:
        if len(p.getlist(key))!=1 or len(p[key])>100:raise ValidationError('Invalid filter.')
    now=timezone.localdate().year
    try:
        start=int(p.get('year_from',now-9));end=int(p.get('year_to',now))
        if not all(p.get(k,'0').isascii() and p.get(k,'0').isdigit() for k in ('year_from','year_to')) or not 1900<=start<=end<=2200 or end-start>=20:raise ValueError()
    except (ValueError,TypeError):raise ValidationError('Use a year range of at most 20 years, 1900–2200.') from None
    if p.get('kind') and p['kind'] not in DATES:raise ValidationError('Unsupported metric kind.')
    return {'year_from':start,'year_to':end,**{k:p[k] for k in ('kind','category') if k in p}}
def envelope(f,data):return {'metric_version':VERSION,'as_of':timezone.now(),'filters':f,'data':data}
def scoped(f):
    qs=published_items_base().order_by()
    if f.get('kind'):qs=qs.filter(kind=f['kind'])
    if f.get('category'):
        c=f['category'];qs=qs.filter(Q(published_revision__paper__category=c)|Q(published_revision__award__category=c)|Q(published_revision__news__category=c)|Q(published_revision__blog__category=c))
    return qs

def kind_rows(f,kind):
    qs=scoped(f).filter(kind=kind);field=DATES[kind]
    if kind=='ACTIVITY':
        begin=datetime(f['year_from'],1,1,tzinfo=ZoneInfo('Asia/Shanghai'));end=datetime(f['year_to']+1,1,1,tzinfo=ZoneInfo('Asia/Shanghai'))
        qs=qs.filter(Q(**{field+'__gte':begin,field+'__lt':end})|Q(**{field+'__isnull':True}))
    else:qs=qs.filter(Q(**{field+'__year__gte':f['year_from'],field+'__year__lte':f['year_to']})|Q(**{field+'__isnull':True}))
    return qs

def annual(f):
    data=[]
    for kind,field in DATES.items():
        if f.get('kind') and kind!=f['kind']:continue
        rows=kind_rows(f,kind)
        grouped=rows.annotate(year=ExtractYear(field,tzinfo=ZoneInfo('Asia/Shanghai')) if kind=='ACTIVITY' else ExtractYear(field)).values('year').annotate(count=Count('pk',distinct=True)).order_by('year')
        counts={r['year']:r['count'] for r in grouped}
        series=[{'year':year,'count':counts.get(year,0)} for year in range(f['year_from'],f['year_to']+1)]
        base=counts.get(f['year_to']-1,0);current=counts.get(f['year_to'],0)
        entry={'kind':kind,'total':sum(counts.values()),'unknown_date':counts.get(None,0),'series':series,'growth_rate':(current-base)/base if base else None}
        if kind=='AWARD':
            entry['categories']=[]
            for category in ('COMPETITION','HONOR'):
                grouped_category=rows.filter(published_revision__award__category=category).annotate(year=ExtractYear(field)).values('year').annotate(count=Count('pk',distinct=True))
                values={r['year']:r['count'] for r in grouped_category}
                entry['categories'].append({'kind':category,'total':sum(values.values()),'unknown_date':values.get(None,0),'series':[{'year':year,'count':values.get(year,0)} for year in range(f['year_from'],f['year_to']+1)],'growth_rate':None})
        data.append(entry)
    return data

def overview(f):
    people=member_queryset().order_by()
    groups=list(people.values('published_revision__member_kind','published_revision__public_member_status').annotate(count=Count('pk',distinct=True)))
    return {'members':{'total':people.count(),'composition':[{'kind':r['published_revision__member_kind'],'status':r['published_revision__public_member_status'],'count':r['count']} for r in groups]},'content':[{'kind':r['kind'],'count':r['total'],'unknown_date':r['unknown_date']} for r in annual(f)],'notes':['团队人数为当前已公开成员，不是历史年度人数。','未知日期计入总量，不进入已知年份序列。','共同成果全站计一次；各成员参与数量之和可能大于全站。']}

def review_metrics(f):
    from apps.workflow.models import RevisionSubmission,ReviewDecision
    begin=datetime(f['year_from'],1,1,tzinfo=ZoneInfo('Asia/Shanghai'));end=datetime(f['year_to']+1,1,1,tzinfo=ZoneInfo('Asia/Shanghai'))
    decisions=ReviewDecision.objects.filter(content_revision__isnull=False,created_at__gte=begin,created_at__lt=end)
    submissions=RevisionSubmission.objects.filter(content_revision__isnull=False,created_at__gte=begin,created_at__lt=end)
    if f.get('kind'):decisions=decisions.filter(content_revision__item__kind=f['kind']);submissions=submissions.filter(content_revision__item__kind=f['kind'])
    if f.get('category'):
        c=f['category']
        condition=Q(content_revision__paper__category=c)|Q(content_revision__award__category=c)|Q(content_revision__news__category=c)|Q(content_revision__blog__category=c)
        decisions=decisions.filter(condition);submissions=submissions.filter(condition)
    # Percentiles computed in PostgreSQL; no row-by-row query or unbounded Python materialization.
    from django.db import connection
    pairs=decisions.annotate(duration=ExpressionWrapper(F('created_at')-F('content_revision__submission__created_at'),output_field=DurationField())).exclude(duration__lt=timezone.timedelta(0))
    sql,params=pairs.values('duration').query.sql_with_params()
    with connection.cursor() as cursor:
        cursor.execute('SELECT count(*), percentile_cont(0.5) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM duration)), percentile_cont(0.95) WITHIN GROUP (ORDER BY EXTRACT(EPOCH FROM duration)) FROM ('+sql+') AS samples',params)
        count,median,p95=cursor.fetchone()
    return {'submitted_events':submissions.count(),'decisions':list(decisions.values('decision').annotate(count=Count('pk'))),'sample_size':count,'median_seconds':median,'p95_seconds':p95,'definition':'提交至最终内容审核事件；撤回和未决不进入耗时样本。'}
