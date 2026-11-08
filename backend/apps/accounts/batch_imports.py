"""Root import queue: sanitized DB records, encrypted expiring private payloads."""
import json,os,secrets,sys,subprocess
from pathlib import Path
from datetime import timedelta
from cryptography.fernet import Fernet,InvalidToken
from django.conf import settings
from django.db import transaction,IntegrityError
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from rest_framework.exceptions import ValidationError,PermissionDenied
from .models import User,AccountImportBatch
from .serializers import RegisterSerializer,check_password
from .services import audit,locked_users


def cipher():
    try:return Fernet(settings.ACCOUNT_IMPORT_KEY.encode())
    except (ValueError,TypeError,AttributeError):raise ValidationError('批量导入尚未配置，请联系管理员。') from None


def payload_path(key):
    if not key or len(key)!=48 or any(c not in '0123456789abcdef' for c in key):raise ValueError('Invalid import key')
    root=Path(settings.ACCOUNT_IMPORT_ROOT).resolve();path=root/key
    if path.is_symlink():raise ValueError('Invalid import path')
    return path


def purge(key):
    if key:
        try:payload_path(key).unlink(missing_ok=True)
        except (ValueError,OSError):pass


def summary(batch):
    return {'id':str(batch.pk),'state':batch.state,'expires_at':batch.expires_at,'count':len(batch.rows),'rows':batch.rows,'errors':batch.errors,'can_confirm':batch.state=='PREVIEW' and not batch.errors,'created_count':len(batch.created_ids)}


def validate_rows(rows):
    seen=set();errors=[];safe=[];default=settings.INITIAL_ACCOUNT_PASSWORD
    for row in rows:
        messages=list(row.pop('errors',[]));name=User.normalize_username(row['username'].strip());row['username']=name
        row['role']={'Teacher':'TEACHER','Student':'STUDENT','Customer':'CUSTOMER'}.get(row['role'].strip(),'')
        row['is_active']={'正常':True,'已注销':False}.get(row.pop('status').strip())
        row['name']=row['name'].strip();row['password']=row['password'] if row['password'].strip() else default
        if not row['role']:messages.append('账号身份仅支持Teacher/Student/Customer，请注意大小写。')
        if row['is_active'] is None:messages.append('是否启用请选择正常或已注销。')
        if name in seen:messages.append('文件内用户名重复。')
        seen.add(name)
        try:RegisterSerializer().validate_username(name)
        except Exception:messages.append('用户名无效或已被使用（含已注销账号）。')
        try:check_password(row['password'],User(username=name))
        except Exception:messages.append('初始密码不符合规则，请使用至少6位英文字母与数字；留空须已配置默认密码。')
        safe.append({k:row[k] for k in ('row','serial','username','role','is_active','name')})
        for message in dict.fromkeys(messages):errors.append({'row':row['row'],'username':name,'message':message})
    return safe,errors


def preview(request,file):
    cipher_instance=cipher()
    if not file.name.lower().endswith('.xlsx') or file.size>2*1024*1024:raise ValidationError('请选择不超过2 MiB的xlsx文件。')
    try:
        result=subprocess.run([sys.executable,'-m','apps.accounts.import_excel'],input=file.read(2*1024*1024+1),capture_output=True,timeout=12,env={'PATH':os.defpath,'PYTHONPATH':str(settings.BASE_DIR),'PYTHONDONTWRITEBYTECODE':'1'})
        parsed=json.loads(result.stdout)
    except (OSError,subprocess.TimeoutExpired,ValueError):raise ValidationError('Excel解析失败或超时，请使用系统模板。') from None
    if result.returncode:raise ValidationError(parsed.get('error','Excel解析失败。'))
    rows=parsed['rows'];safe,errors=validate_rows(rows);key=''
    if not errors:
        key=secrets.token_hex(24);path=payload_path(key);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        encrypted=cipher_instance.encrypt(json.dumps(rows,ensure_ascii=False).encode())
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as out:out.write(encrypted)
    try:
        with transaction.atomic():
            actor,_=locked_users(request)
            if not actor.is_superuser:raise PermissionDenied()
            if AccountImportBatch.objects.filter(owner=actor,state__in=['PREVIEW','QUEUED','RUNNING'],expires_at__gt=timezone.now()).count()>=10:raise ValidationError('待处理批次过多，请稍后重试。')
            batch=AccountImportBatch.objects.create(owner=actor,storage_key=key,rows=safe,errors=errors,expires_at=timezone.now()+timedelta(minutes=15))
            audit('account_import.preview',actor=actor,fields=['batch'],changes={'batch_id':str(batch.pk),'count':len(rows),'errors':len(errors)})
    except BaseException:purge(key);raise
    return batch


@transaction.atomic
def confirm(request,pk):
    actor,_=locked_users(request)
    if not actor.is_superuser:raise PermissionDenied()
    from django.shortcuts import get_object_or_404
    batch=get_object_or_404(AccountImportBatch.objects.select_for_update(),pk=pk,owner=actor)
    if batch.state in ('QUEUED','RUNNING','DONE'):return batch
    if batch.state!='PREVIEW' or batch.errors or batch.expires_at<=timezone.now():raise ValidationError('批次有错误或已过期，请重新上传预览。')
    conflicts=list(User.objects.filter(username__in=[r['username'] for r in batch.rows]).values_list('username',flat=True))
    if conflicts:raise ValidationError('用户名已被使用，请重新预览：'+ '、'.join(conflicts[:10]))
    batch.state='QUEUED';batch.save(update_fields=['state']);audit('account_import.queued',actor=actor,changes={'batch_id':str(batch.pk)})
    return batch


def cleanup():
    now=timezone.now()
    with transaction.atomic():
        for batch in AccountImportBatch.objects.select_for_update(skip_locked=True).filter(state__in=['PREVIEW','QUEUED','RUNNING']):
            if batch.state=='RUNNING' and batch.started_at and batch.started_at>now-timedelta(minutes=10):continue
            if batch.expires_at>now and batch.state!='RUNNING':continue
            key=batch.storage_key;batch.storage_key='';batch.state='EXPIRED';batch.errors=[{'message':'批次已过期或处理已中断，请重新上传。'}];batch.finished_at=now;batch.save();transaction.on_commit(lambda key=key:purge(key))
    root=Path(settings.ACCOUNT_IMPORT_ROOT)
    if root.is_dir():
        retained=set(AccountImportBatch.objects.exclude(storage_key='').values_list('storage_key',flat=True))
        for path in root.iterdir():
            try:
                if path.name not in retained and not path.is_symlink() and path.is_file() and path.stat().st_mtime<now.timestamp()-900:purge(path.name)
            except OSError:continue


def process_one():
    cleanup()
    with transaction.atomic():
        batch=AccountImportBatch.objects.select_for_update(skip_locked=True).filter(state='QUEUED').order_by('created_at').first()
        if not batch:return False
        batch.state='RUNNING';batch.started_at=timezone.now();batch.save(update_fields=['state','started_at']);pk=batch.pk;owner_id=batch.owner_id;key=batch.storage_key
    try:
        raw=cipher().decrypt(payload_path(key).read_bytes(),ttl=900);rows=json.loads(raw);del raw
        # Hashing is outside the write transaction and never in the HTTP request.
        for row in rows:
            row['password_hash']=make_password(row.pop('password'))
        with transaction.atomic():
            owner=User.objects.select_for_update().get(pk=owner_id)
            batch=AccountImportBatch.objects.select_for_update().get(pk=pk)
            if batch.state!='RUNNING':return True
            if not owner.is_active or not owner.is_superuser or batch.expires_at<=timezone.now():raise PermissionDenied()
            if User.objects.filter(username__in=[r['username'] for r in rows]).exists():raise ValidationError('用户名在确认后被占用，请重新上传预览。')
            created=[]
            from apps.members.direct import save_profile
            from apps.members.models import MemberProfile
            from types import SimpleNamespace
            from django.contrib.auth import HASH_SESSION_KEY
            from .authentication import SESSION_VERSION_KEY
            request=SimpleNamespace(user=owner,session={SESSION_VERSION_KEY:owner.session_version,HASH_SESSION_KEY:owner.get_session_auth_hash()})
            for row in rows:
                u=User.objects.create(username=row['username'],password=row['password_hash'],role=row['role'],is_active=row['is_active'])
                audit('user.created',actor=owner,target=u,fields=['username','role','is_active'],changes={'batch_id':str(pk)})
                if row['name']:
                    profile=MemberProfile.objects.create(user=u,created_by=owner,updated_by=owner)
                    save_profile(request,{'lock_version':0,'display_name':row['name']},profile.pk)
                created.append(u.pk)
            batch.created_ids=created;batch.rows=[{**r,'user_id':uid} for r,uid in zip(batch.rows,created)];batch.state='DONE';batch.finished_at=timezone.now();batch.storage_key='';batch.save();audit('account_import.completed',actor=owner,changes={'batch_id':str(pk),'count':len(created)})
            transaction.on_commit(lambda:purge(key))
    except Exception as exc:
        # Never write raw exception text: DB/validation errors can contain credentials.
        with transaction.atomic():
            batch=AccountImportBatch.objects.select_for_update().get(pk=pk)
            if batch.state=='RUNNING':
                batch.state='FAILED';batch.errors=[{'message':'整批创建失败，未创建账号；请重新预览并检查用户名、配置或联系管理员。'}];batch.finished_at=timezone.now();batch.storage_key='';batch.save();audit('account_import.failed',actor_snapshot=owner_id,changes={'batch_id':str(pk)})
                transaction.on_commit(lambda:purge(key))
    return True
