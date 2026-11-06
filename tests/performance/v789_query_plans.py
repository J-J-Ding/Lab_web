"""Isolated synthetic query plans. BLOG has 10k rows; other kinds/member plans have zero rows. Not a load acceptance test."""
import os,sys,subprocess,json,secrets
from pathlib import Path
os.environ['LAB_TEST_STAGE']='v7';sys.path.insert(0,'tests/support');from v4_environment import guarded
prefix=guarded();db='test_lab_web_perf_'+secrets.token_hex(4)
subprocess.run(prefix+['exec','-T','db','sh','-c','createdb -U "$POSTGRES_USER" "$1"','perf',db],check=True)
code='''
import os,django,time,json,statistics,uuid
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');django.setup()
from django.core.management import call_command
from django.db import transaction,connection
from django.test import Client
from apps.accounts.models import User
from apps.content.models import ContentItem,ContentRevision,BlogDetail,Contributor,RevisionContribution
call_command('migrate',verbosity=0,interactive=False)
u=User.objects.create(username='performance-synthetic',role='TEACHER')
with transaction.atomic():
 items=[ContentItem(id=uuid.uuid4(),kind='BLOG',created_by=u) for _ in range(10000)];ContentItem.objects.bulk_create(items)
 revisions=[ContentRevision(id=uuid.uuid4(),item=i,number=1,title='Synthetic '+str(n),edited_by=u) for n,i in enumerate(items)];ContentRevision.objects.bulk_create(revisions)
 BlogDetail.objects.bulk_create([BlogDetail(revision=r,body='Synthetic benchmark',event_date='2026-01-01') for r in revisions])
 contributors=[Contributor(display_name='Author '+str(n)) for n in range(5)];Contributor.objects.bulk_create(contributors)
 RevisionContribution.objects.bulk_create([RevisionContribution(revision=r,contributor=c,contribution_role='AUTHOR',position=n+1,approved_display_name=c.display_name) for r in revisions for n,c in enumerate(contributors)],batch_size=1000)
 ContentRevision.objects.all().update(state='PUBLISHED')
 for i,r in zip(items,revisions):i.published_revision=r
 ContentItem.objects.bulk_update(items,['published_revision'],batch_size=1000)
client=Client();results={}
for path in ['/api/public/stats/overview/','/api/public/stats/annual/','/api/public/content/?kind=BLOG&page_size=20']:
 samples=[]
 for _ in range(20):
  start=time.perf_counter();response=client.get(path);samples.append((time.perf_counter()-start)*1000);assert response.status_code==200,response.content[:100]
 results[path]={'samples':len(samples),'p50_ms':round(statistics.median(samples),2),'p95_ms':round(sorted(samples)[18],2),'max_ms':round(max(samples),2)}
with connection.cursor() as c:c.execute('EXPLAIN (ANALYZE, FORMAT TEXT) SELECT count(*) FROM content_contentitem WHERE visibility_gate AND published_revision_id IS NOT NULL');plan='\\n'.join(r[0] for r in c.fetchall())
from apps.content.public_selectors import content_queryset,member_queryset
from apps.content.public_views import content_filter
plans={name:query.explain(analyze=True,buffers=True) for name,query in {'blog':content_queryset().filter(kind='BLOG')[:20],'search':content_filter(content_queryset(),{'q':'Synthetic'})[:20],'paper':content_queryset().filter(kind='PAPER')[:20],'project':content_queryset().filter(kind='PROJECT')[:20],'members':member_queryset()[:20]}.items()}
print('PERFORMANCE_RESULT '+json.dumps({'items':10000,'relations':50000,'results':results,'explain':plan,'plans':plans,'production_load_test':False}))
'''
try:
 r=subprocess.run(prefix+['run','--rm','--no-deps','-T','-e','POSTGRES_DB='+db,'backend','python','-c',code],capture_output=True,text=True,timeout=300)
 lines=[l for l in r.stdout.splitlines() if l.startswith('PERFORMANCE_RESULT ')]
 if r.returncode or not lines:print(r.stderr[-2500:]);raise RuntimeError('Performance rehearsal failed')
 result=json.loads(lines[-1][19:]);Path('.browser-artifacts/v789/query-plans.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
finally:subprocess.run(prefix+['exec','-T','db','sh','-c','dropdb -U "$POSTGRES_USER" "$1"','perf',db],check=True)
