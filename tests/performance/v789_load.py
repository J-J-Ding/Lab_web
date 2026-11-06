"""Synthetic real-HTTP load; guarded isolated DB only, never production. Run from repository root."""
import sys,os,time,json,threading,concurrent.futures,urllib.request,urllib.error,http.cookiejar,secrets,statistics
from pathlib import Path
sys.path.insert(0,'tests/browser');sys.path.insert(0,'tests/support');os.environ['LAB_TEST_STAGE']='v7'
from v4_environment import guarded
os.environ['LAB_BROWSER_COMPOSE']=json.dumps(guarded())
from support import Environment
DURATION=int(os.environ.get('LAB_LOAD_SECONDS','600'))
if DURATION < 1: raise ValueError('Duration must be positive')
env=Environment().start();counts={'read':[],'write':[]};errors=[];endpoint_counts={};lock=threading.Lock()
try:
 # The independent DB starts with the full synthetic scale, never touches production.
 env.orm("""
from django.db import transaction
from apps.accounts.models import User
from apps.content.models import ContentItem,ContentRevision,BlogDetail,Contributor,RevisionContribution
import uuid
u=User.objects.create(username='load-owner',role='TEACHER')
with transaction.atomic():
 items=[ContentItem(id=uuid.uuid4(),kind='BLOG',created_by=u) for _ in range(10000)];ContentItem.objects.bulk_create(items)
 revs=[ContentRevision(id=uuid.uuid4(),item=i,number=1,title='Load example '+str(n),edited_by=u) for n,i in enumerate(items)];ContentRevision.objects.bulk_create(revs)
 BlogDetail.objects.bulk_create([BlogDetail(revision=r,body='Synthetic load test',event_date='2026-01-01') for r in revs])
 people=[Contributor(display_name='Example '+str(n)) for n in range(5)];Contributor.objects.bulk_create(people)
 RevisionContribution.objects.bulk_create([RevisionContribution(revision=r,contributor=c,contribution_role='AUTHOR',position=n+1,approved_display_name=c.display_name) for r in revs for n,c in enumerate(people)],batch_size=1000)
 ContentRevision.objects.all().update(state='PUBLISHED')
 for i,r in zip(items,revs):i.published_revision=r
 ContentItem.objects.bulk_update(items,['published_revision'],batch_size=1000)
result={}
""",{})
 writers=[]
 for n in range(5):
  username='writer-'+str(n);password=secrets.token_urlsafe(18)+'!A4';env.seed(username,password,'TEACHER',False)
  jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
  opener.open(env.url+'/api/auth/csrf/').read();csrf=next(c.value for c in jar if c.name=='csrftoken')
  opener.open(urllib.request.Request(env.url+'/api/auth/login/',data=json.dumps({'username':username,'password':password}).encode(),headers={'Content-Type':'application/json','X-CSRFToken':csrf})).read();csrf=next(c.value for c in jar if c.name=='csrftoken');writers.append((opener,csrf))
 start=time.monotonic();deadline=start+DURATION
 paths=['/api/public/content/?kind=BLOG&page_size=20','/api/public/stats/overview/','/api/public/stats/annual/','/api/public/content/?q=example&page_size=20']
 def reader(n):
  opener=urllib.request.build_opener();i=0
  while time.monotonic()<deadline:
   begin=time.monotonic();path=paths[(n+i)%len(paths)]
   try:
    response=opener.open(env.url+path,timeout=30);response.read();assert response.status==200
   except Exception as exc:
    with lock:errors.append({'type':'read','path':path,'code':getattr(exc,'code',type(exc).__name__)})
   with lock:
    elapsed=(time.monotonic()-begin)*1000;counts['read'].append(elapsed);endpoint_counts.setdefault(path,[]).append(elapsed)
   i+=1;time.sleep(.5)
 def writer(n):
  opener,csrf=writers[n];i=0
  while time.monotonic()<deadline:
   begin=time.monotonic()
   try:
    body=json.dumps({'kind':'BLOG','title':f'Synthetic writer {n}-{i}','detail':{'body':'Private load fixture'}}).encode();r=opener.open(urllib.request.Request(env.url+'/api/content/items/',data=body,headers={'Content-Type':'application/json','X-CSRFToken':csrf}),timeout=30);r.read();assert r.status==201
   except Exception as exc:
    with lock:errors.append({'type':'write','code':getattr(exc,'code',type(exc).__name__)})
   with lock:
    elapsed=(time.monotonic()-begin)*1000;counts['write'].append(elapsed);endpoint_counts.setdefault('POST /api/content/items/',[]).append(elapsed)
   i+=1;time.sleep(5)
 with concurrent.futures.ThreadPoolExecutor(max_workers=35) as pool:
  futures=[pool.submit(reader,n) for n in range(30)]+[pool.submit(writer,n) for n in range(5)]
  for f in futures:f.result()
 def metric(rows):
  rows=sorted(rows);return {'samples':len(rows),'min_ms':round(rows[0],2),'mean_ms':round(statistics.mean(rows),2),'p50_ms':round(statistics.median(rows),2),'p90_ms':round(rows[int((len(rows)-1)*.90)],2),'p99_ms':round(rows[int((len(rows)-1)*.99)],2),'p95_ms':round(rows[int((len(rows)-1)*.95)],2),'max_ms':round(max(rows),2)}
 result={'duration_seconds':round(time.monotonic()-start,2),'read_concurrency':30,'write_concurrency':5,'initial_items':10000,'initial_relations':50000,'read':metric(counts['read']),'write':metric(counts['write']),'by_endpoint':{path:metric(rows) for path,rows in endpoint_counts.items()},'errors':errors,'error_rate':len(errors)/sum(map(len,counts.values())),'environment':'isolated ECS 2 vCPU; real HTTP via test proxy; production not loaded'}
 Path(os.environ.get('LAB_LOAD_RESULT','.browser-artifacts/v789/load-result.json')).write_text(json.dumps(result,indent=2));print(json.dumps(result))
finally:env.close()

assert result['error_rate'] < .01, 'Error-rate acceptance failed; inspect recorded errors'
for endpoint, values in result['by_endpoint'].items():
    target_ms = 2000 if '/stats/' in endpoint else 1000
    assert values['p95_ms'] <= target_ms, (endpoint, values['p95_ms'], target_ms)
