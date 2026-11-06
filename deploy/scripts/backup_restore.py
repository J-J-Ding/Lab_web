"""Consistent local backup and isolated restoration. Never restores into production."""
import subprocess,sys,os,json,hashlib,tempfile,time,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.chdir(ROOT);os.umask(0o077)
BASE=['sudo','-n','docker','compose']
def run(args,**kwargs):return subprocess.run(args,check=True,**kwargs)
def output(args):return subprocess.check_output(args,text=True).strip()
def hashfile(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def backup(destination):
 target=Path(destination).resolve()
 if not target.is_absolute() or target.exists() or target.is_relative_to(ROOT/'frontend'):raise SystemExit('Use a new private directory outside frontend')
 target.parent.mkdir(parents=True,exist_ok=True,mode=0o700);stage=Path(tempfile.mkdtemp(prefix='.lab-backup-',dir=target.parent));services=[]
 try:
  ps=output(BASE+['--profile','ai','ps','--services','--status','running']).splitlines()
  services=[s for s in ('worker','backend') if s in ps]
  if services:run(BASE+['--profile','ai','stop',*services])
  image=output(['sudo','-n','docker','inspect','lab-web-backend-1','--format','{{.Config.Image}}'])
  with (stage/'database.dump').open('wb') as f:run(BASE+['exec','-T','db','sh','-c','pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc'],stdout=f)
  mounts=json.loads(output(['sudo','-n','docker','inspect','lab-web-backend-1','--format','{{json .Mounts}}']))
  volume=next(m['Name'] for m in mounts if m['Destination']=='/app/private_media')
  with (stage/'media.tar').open('wb') as f:run(['sudo','-n','docker','run','--rm','--user','0','--entrypoint','tar','--mount',f'type=volume,src={volume},dst=/media,readonly',image,'-C','/media','-cf','-','.'],stdout=f)
  with (stage/'database.dump').open('rb') as f:run(BASE+['exec','-T','db','pg_restore','--list'],stdin=f,stdout=subprocess.DEVNULL)
  tables=output(BASE+['exec','-T','db','sh','-c','psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "$1"','tables',"SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;"]).splitlines()
  table_checks={}
  for table in tables:
   if not table.replace('_','').isalnum():raise ValueError('Unsafe table name')
   query="SELECT count(*),md5(COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text)::text,'[]')) FROM \"{}\" t;".format(table)
   table_checks[table]=output(BASE+['exec','-T','db','sh','-c','psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -c "$1"','check',query])
  manifest={'table_checks':table_checks,'version':1,'created_utc':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),'image':image,'commit':output(['git','rev-parse','HEAD']),'files':{name:hashfile(stage/name) for name in ('database.dump','media.tar')}}
  (stage/'manifest.json').write_text(json.dumps(manifest,indent=2));(stage/'COMPLETE').write_text('complete\n');stage.rename(target);print('Backup complete:',target)
 finally:
  if services:run(BASE+['--profile','ai','start',*reversed(services)])
  if stage.exists():shutil.rmtree(stage)
def restore(source,project):
 import secrets,tarfile
 if not project.startswith('lab-web-restore-') or not all(c.isalnum() or c=='-' for c in project):raise SystemExit('Unsafe restore target')
 # Each invocation owns an unguessable project; never reuses user-supplied project volumes.
 requested_project=project
 project=project+'-'+secrets.token_hex(6)
 for resource in ('ps','volume','network'):
  cmd=['sudo','-n','docker',resource,'ls','-q','--filter','label=com.docker.compose.project='+project] if resource!='ps' else ['sudo','-n','docker','ps','-aq','--filter','label=com.docker.compose.project='+project]
  if output(cmd):raise SystemExit('Restore target already exists; refusing reuse')
 src=Path(source).resolve();manifest=json.loads((src/'manifest.json').read_text());assert (src/'COMPLETE').is_file()
 if set(manifest['files'])!={'database.dump','media.tar'}:raise SystemExit('Incomplete backup manifest')
 for name,digest in manifest['files'].items():assert name in ('database.dump','media.tar') and hashfile(src/name)==digest,'Backup hash mismatch'
 runtime=Path(tempfile.mkdtemp(prefix=project+'-'));media=runtime/'media';media.mkdir();start=time.monotonic()
 restore_password=secrets.token_hex(24)
 cfg=runtime/'compose.yml';cfg.write_text('services:\n  db:\n    image: postgres:16-bookworm\n    environment:\n      POSTGRES_USER: restore_test\n      POSTGRES_DB: restore_test\n      POSTGRES_PASSWORD: '+restore_password+'\n    volumes: ["restore_data:/var/lib/postgresql/data"]\n    healthcheck:\n      test: ["CMD-SHELL", "pg_isready -h 127.0.0.1 -U restore_test"]\n      interval: 1s\n      timeout: 3s\n      retries: 30\nvolumes:\n  restore_data:\n')
 prefix=['sudo','-n','docker','compose','-p',project,'-f',str(cfg)]
 try:
  run(prefix+['up','-d','--wait'])
  with (src/'database.dump').open('rb') as f:run(prefix+['exec','-T','db','pg_restore','-h','127.0.0.1','-U','restore_test','-d','restore_test','--no-owner','--no-acl','--exit-on-error'],stdin=f)
  with tarfile.open(src/'media.tar') as tar:
   for member in tar.getmembers():
    p=(media/member.name).resolve()
    if not p.is_relative_to(media) or member.issym() or member.islnk():raise ValueError('Unsafe archive entry')
   tar.extractall(media,filter='data')
  for table,expected in manifest.get('table_checks',{}).items():
   if not table.replace('_','').isalnum():raise ValueError('Unsafe table name')
   query="SELECT count(*),md5(COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text)::text,'[]')) FROM \"{}\" t;".format(table)
   actual=output(prefix+['exec','-T','db','psql','-h','127.0.0.1','-U','restore_test','-d','restore_test','-At','-c',query])
   assert actual==expected,'Restored table digest mismatch: '+table
  count=output(prefix+['exec','-T','db','psql','-h','127.0.0.1','-U','restore_test','-d','restore_test','-At','-c',"SELECT count(*) FROM information_schema.tables WHERE table_schema='public';"])
  assert int(count)>0
  app_env=runtime/'app.env'
  app_env.write_text('DJANGO_SECRET_KEY='+secrets.token_hex(32)+'\nDJANGO_ALLOWED_HOSTS=testserver,localhost,127.0.0.1\nPOSTGRES_USER=restore_test\nPOSTGRES_PASSWORD='+restore_password+'\nPOSTGRES_DB=restore_test\nPOSTGRES_HOST='+project+'-db-1\nAI_ENABLED=False\n')
  app_image=os.environ.get('LAB_RESTORE_APP_IMAGE',manifest['image'])
  probe="""import os,django,secrets; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); django.setup()
from django.core.management import call_command
from django.test import Client
from apps.accounts.models import User
from apps.assets.models import AssetFile
from pathlib import Path
import hashlib
for asset in AssetFile.objects.filter(scan_status='CLEAN'):
 source=Path('/app/private_media')/asset.storage_key
 if source.is_file():assert hashlib.sha256(source.read_bytes()).hexdigest()==asset.sha256
call_command('migrate',verbosity=0,interactive=False)
call_command('check',verbosity=0)
password=secrets.token_urlsafe(24)+'!A4'; username='restore_probe_'+secrets.token_hex(5)
u=User.objects.create_user(username=username,password=password)
c=Client(enforce_csrf_checks=True); assert c.get('/api/health/').status_code==200
assert c.get('/api/auth/me/').status_code==403
assert c.get('/api/public/content/').status_code==200
c.get('/api/auth/csrf/'); token=c.cookies['csrftoken'].value
r=c.post('/api/auth/login/',{'username':username,'password':password},content_type='application/json',HTTP_X_CSRFTOKEN=token); assert r.status_code==200
assert c.get('/api/auth/me/').status_code==200
assert c.post('/api/auth/logout/',{},content_type='application/json').status_code==403
print('PASS: restored isolated app migrations/health/public/private/login/CSRF')
"""
  run(['sudo','-n','docker','run','--rm','--user',str(os.getuid())+':'+str(os.getgid()),'--env-file',str(app_env),'--network',project+'_default','--mount','type=bind,src='+str(media)+',dst=/app/private_media,readonly',app_image,'python','-c',probe])
  print(json.dumps({'restored_tables':int(count),'media_files':sum(p.is_file() for p in media.rglob('*')),'elapsed_seconds':round(time.monotonic()-start,2),'production_overwritten':False}))
 finally:
  run(prefix+['down','--volumes']);shutil.rmtree(runtime)
if __name__=='__main__':
 if sys.argv[1]=='backup':backup(sys.argv[2])
 elif sys.argv[1]=='restore':restore(sys.argv[2],sys.argv[3])
 else:raise SystemExit('Unknown action')
