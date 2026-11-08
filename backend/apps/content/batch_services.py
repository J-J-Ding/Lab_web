"""Shared candidates and atomic creation for template and AI imports."""
import json,hashlib,os,subprocess,sys
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.db import transaction,IntegrityError
from django.db.models import Sum
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError,PermissionDenied
from apps.accounts.models import User
from apps.accounts.services import locked_users
from apps.assets.models import AssetFile
from apps.members.services import VersionConflict
from apps.workflow.audit import record
from .models import ContentImportBatch,ContentImportCall,ContentItem,ContentIdentifier,PatentDetail,DETAIL_MODELS
from .batch_excel import KINDS
from .direct_services import team,directory,name_for
from .serializers import validate_detail
from .services import normalize_identifier


def eligible(user):
 if not team(user):raise PermissionDenied('仅团队成员可批量创建科研内容。')


def owned(user,pk,lock=False):
 eligible(user);qs=ContentImportBatch.objects
 if lock:qs=qs.select_for_update()
 return get_object_or_404(qs,pk=pk,owner=user)


def version(batch,value):
 if type(value) is not int or batch.lock_version!=value:raise VersionConflict()
 if batch.expires_at<=timezone.now():raise ValidationError('批次已过期，请重新导入。')


def bump(batch):batch.lock_version+=1;batch.save()


def identifier(r):
 fields={'PAPER':('DOI','doi'),'PROJECT':('PROJECT','project_number'),'PUBLICATION':('ISBN','isbn'),'PATENT':('PATENT','patent_number')}
 scheme,key=fields.get(r.get('kind'),('',''));value=r.get('detail',{}).get(key,'')
 if not value:return None
 return (scheme,''.join(value.split()).upper() if scheme=='PATENT' else normalize_identifier(scheme,value))


def validate_records(records,actor):
 if not isinstance(records,list) or len(records)>200:raise ValidationError('最多200条记录。')
 if len(json.dumps(records,ensure_ascii=False).encode())>2*1024*1024:raise ValidationError('候选数据超过2 MiB。')
 seen=set();ids=set();all_projects=set();out=[]
 for r in records:
  if not isinstance(r,dict) or not isinstance(r.get('kind',''),str) or not isinstance(r.get('detail',{}),dict):raise ValidationError('卡片格式无效。')
  for key in ('authors','author_order','project_numbers','project_ids'):
   if not isinstance(r.get(key,[]),list) or any(not isinstance(v,str) for v in r.get(key,[])):raise ValidationError('关联字段须为文字列表。')
  number=str(r.get('id',''))
  if not number or number in ids:raise ValidationError('卡片编号重复或缺失。')
  ids.add(number)
  if r.get('kind')=='PROJECT' and isinstance(r.get('detail'),dict) and r['detail'].get('project_number'):
   try:all_projects.add(normalize_identifier('PROJECT',r['detail']['project_number']))
   except ValidationError:pass
 for source in records:
  r=dict(source);r.setdefault('project_ids',[]);errors=[];warnings=list(r.get('warnings',[])) if isinstance(r.get('warnings',[]),list) else []
  if set(r)-{'id','kind','title','summary','body','authors','author_order','project_numbers','project_ids','visibility_scope','detail','evidence','warnings','source_label','reviewed','selected','errors','item_id'}:errors.append('卡片包含未知字段。')
  if r.get('kind') not in KINDS:errors.append('请选择论文、专利、科研项目、竞赛荣誉或著作。')
  for key,limit in [('title',500),('summary',10000),('body',50000)]:
   if not isinstance(r.get(key,''),str) or len(r.get(key,''))>limit:errors.append(key+'字段格式或长度无效。')
  if not str(r.get('title','')).strip():errors.append('标题必填。')
  if r.get('visibility_scope','TEAM') not in ('TEAM','PUBLIC'):errors.append('展示范围无效。')
  try:
   d=validate_detail(r['kind'],r.get('detail',{}));instance=DETAIL_MODELS[r['kind']](**d);instance.full_clean(exclude=['revision']);r['detail']=json.loads(json.dumps(d,cls=DjangoJSONEncoder))
  except Exception:errors.append('类型字段有误，请检查日期、状态、链接及数值。')
  names=r.get('authors',[]);order=r.get('author_order',[]);projects=r.get('project_numbers',[])
  for values,label in [(names,'关联成员'),(order,'成员顺序'),(projects,'关联项目')]:
   if not isinstance(values,list) or len(values)>100 or any(not isinstance(n,str) or not n.strip() or len(n)>150 for n in values):errors.append(label+'格式无效。')
  if not any('格式无效' in e for e in errors):
   names=[n.strip() for n in names];order=[n.strip() for n in order]
   if len(names)!=len(set(names)):errors.append('关联成员重复。')
   if order and (len(order)!=len(names) or set(order)!=set(names)):errors.append('成员顺序须是关联成员的完整排列。')
   profiles={p.user.username:p for p in directory().filter(user__username__in=names)}
   if len(profiles)!=len(names) or any(not name_for(p) for p in profiles.values()):errors.append('关联用户名不存在、已注销、身份不符或未填写姓名。')
   r['authors']=order or names;r['author_order']=order
   normalized=[]
   for number in projects:
    try:
     number=normalize_identifier('PROJECT',number);normalized.append(number)
     own_num=r.get('detail',{}).get('project_number') if r.get('kind')=='PROJECT' else None
     if own_num and normalize_identifier('PROJECT',own_num)==number:errors.append('项目不能关联自身。')
     if number not in all_projects and not ContentIdentifier.objects.filter(scheme='PROJECT',value=number,item__deleted_at__isnull=True,item__archived_at__isnull=True,item__published_revision__isnull=False).exists():errors.append('关联项目编号不存在。')
    except ValidationError:errors.append('项目编号无效。')
   if len(normalized)!=len(set(normalized)):errors.append('关联项目重复。')
   r['project_numbers']=normalized
   try:
    if len(r['project_ids'])>30 or len(set(r['project_ids']))!=len(r['project_ids']) or ContentItem.objects.filter(pk__in=r['project_ids'],kind='PROJECT',deleted_at__isnull=True,archived_at__isnull=True,published_revision__isnull=False).count()!=len(r['project_ids']):errors.append('所选关联项目已失效或重复。')
   except Exception:errors.append('关联项目标识无效。')
  try:
   ident=identifier(r)
   if ident:
    if ident in seen:errors.append('本批标识符重复。')
    seen.add(ident)
    if ident[0]=='PATENT':
     if any(''.join(n.split()).upper()==ident[1] for n in PatentDetail.objects.exclude(patent_number='').values_list('patent_number',flat=True)):errors.append('专利号已存在，请核对。')
    elif ContentIdentifier.objects.filter(scheme=ident[0],value=ident[1]).exists():errors.append('标识符已存在或被历史记录预留。')
   if r.get('title') and ContentItem.objects.filter(published_revision__title__iexact=r['title'],deleted_at__isnull=True).exists():warnings.append('已有同名内容，请核对是否重复。')
  except Exception:errors.append('DOI、ISBN、专利号或项目编号无效。')
  r.update(errors=list(dict.fromkeys(errors)),warnings=list(dict.fromkeys(str(w)[:500] for w in warnings)),selected=r.get('selected') is True,reviewed=r.get('reviewed') is True,visibility_scope=r.get('visibility_scope','TEAM'));out.append(r)
 # Reject same-batch project cycles before any write.
 graph={r.get('detail',{}).get('project_number'):r.get('project_numbers',[]) for r in out if r.get('kind')=='PROJECT' and r.get('detail',{}).get('project_number')}
 colors={};cyclic=set()
 def visit(n,path):
  if colors.get(n)==1:cyclic.update(path[path.index(n):]);return
  if colors.get(n)==2:return
  colors[n]=1
  for x in graph.get(n,[]):
   if x in graph:visit(x,path+[n])
  colors[n]=2
 for n in graph:visit(n,[])
 for r in out:
  if r.get('kind')=='PROJECT' and r.get('detail',{}).get('project_number') in cyclic:r['errors'].append('同批项目关联存在循环。')
 return out


def serialize(batch):
 calls=list(batch.calls.all());used=sum((c.actual if c.state=='SETTLED' else c.reserved for c in calls),Decimal(0))
 return {'id':str(batch.pk),'source':batch.source,'state':batch.state,'records':batch.records,'warnings':batch.warnings,'errors':batch.errors,'lock_version':batch.lock_version,'created':batch.created,'preview':batch.selected_text if batch.state=='AWAITING_CONSENT' else '', 'text_digest':hashlib.sha256(batch.selected_text.encode()).hexdigest() if batch.state=='AWAITING_CONSENT' else '', 'processed_segments':batch.processed,'total_segments':len(batch.segments),'calls':len(calls),'cost_cny':str(used),'single_call_cap':'0.10','document_cap':'0.50','max_calls':5}


def create_template(request,file):
 eligible(request.user)
 if not file.name.lower().endswith('.xlsx') or file.size>2*1024*1024:raise ValidationError('请选择不超过2 MiB的xlsx文件。')
 try:
  result=subprocess.run([sys.executable,'-m','apps.content.batch_excel'],input=file.read(2*1024*1024+1),capture_output=True,timeout=12,env={'PATH':os.defpath,'PYTHONPATH':str(settings.BASE_DIR),'PYTHONDONTWRITEBYTECODE':'1'});data=json.loads(result.stdout)
 except Exception:raise ValidationError('文件解析失败或超时。') from None
 if result.returncode:raise ValidationError(data.get('error','模板解析失败。'))
 with transaction.atomic():
  actor,_=locked_users(request);eligible(actor)
  batch=ContentImportBatch.objects.create(owner=actor,source='TEMPLATE',records=validate_records(data['records'],actor),expires_at=timezone.now()+timedelta(days=7));record(actor,batch,'content_import.preview',('records',));return batch


@transaction.atomic
def create_ai(request,asset_id):
 actor,_=locked_users(request);eligible(actor)
 from apps.ai_assistant.quota import require_enabled
 require_enabled()
 if ContentImportBatch.objects.filter(owner=actor,state__in=['EXTRACTING','QUEUED_AI','CALLING','AWAITING_CONSENT'],expires_at__gt=timezone.now()).exists():raise ValidationError('已有AI文档正在处理，请先完成或取消。')
 asset=get_object_or_404(AssetFile.objects.select_for_update(),pk=asset_id,owner=actor,purpose='ai_source',scan_status='CLEAN',deletion_requested_at__isnull=True)
 if asset.expires_at and asset.expires_at<=timezone.now():raise ValidationError('文件已过期。')
 batch=ContentImportBatch.objects.create(owner=actor,source='AI',asset=asset,state='EXTRACTING',expires_at=timezone.now()+timedelta(days=7));record(actor,batch,'content_import.ai_created',('asset',));return batch


@transaction.atomic
def edit(request,pk,data):
 actor,_=locked_users(request);batch=owned(actor,pk,True);version(batch,data.get('lock_version'))
 if batch.state!='READY':raise ValidationError('当前状态不可修改。')
 incoming=data.get('records')
 if not isinstance(incoming,list):raise ValidationError('缺少候选卡片。')
 old={str(r['id']):r for r in batch.records};updated=[]
 for r in incoming:
  if not isinstance(r,dict) or str(r.get('id')) not in old:raise ValidationError('未知候选卡片。')
  original=old[str(r['id'])];r={**r,'evidence':original.get('evidence',[]),'source_label':original.get('source_label','')}
  # Review must occur after editing, in a separate save.
  compare=lambda x:{k:v for k,v in x.items() if k not in ['reviewed','selected','errors','warnings','evidence']}
  if compare(r)!=compare(original):r['reviewed']=False
  updated.append(r)
 batch.records=validate_records(updated,actor);batch.errors=[];bump(batch);return batch


@transaction.atomic
def consent(request,pk,data):
 actor,_=locked_users(request);batch=owned(actor,pk,True);version(batch,data.get('lock_version'))
 if batch.state!='AWAITING_CONSENT' or data.get('confirm') is not True:raise ValidationError('请确认发送所选脱敏文本。')
 text=data.get('selected_text','')
 if data.get('text_digest')!=hashlib.sha256(batch.selected_text.encode()).hexdigest() or not isinstance(text,str) or not text.strip() or text not in batch.selected_text:raise ValidationError('请选择预览中的连续文本，不可改写原文。')
 batch.selected_text=text;batch.segments=[text[i:i+2200] for i in range(0,len(text),2200)]
 batch.consent_at=timezone.now();batch.state='QUEUED_AI';bump(batch);record(actor,batch,'content_import.consent',('selected_text',));return batch


@transaction.atomic
def confirm(request,pk,data):
 actor,_=locked_users(request);batch=owned(actor,pk,True)
 if batch.state in ['QUEUED_APPLY','APPLYING','DONE']:return batch
 version(batch,data.get('lock_version'))
 if batch.state!='READY' or data.get('confirm') is not True:raise ValidationError('请核验后明确确认创建。')
 selected=[r for r in batch.records if r.get('selected')]
 if not selected or any(not r.get('reviewed') for r in selected):raise ValidationError('请先逐项核验并选择要创建的卡片。')
 checked=validate_records(selected,actor)
 if any(r['errors'] for r in checked):raise ValidationError({'records':[{r['id']:r['errors']} for r in checked if r['errors']]})
 batch.selected=[r['id'] for r in checked];batch.state='QUEUED_APPLY';bump(batch);record(actor,batch,'content_import.confirmed',('selected',));return batch


@transaction.atomic
def cancel(request,pk):
 actor,_=locked_users(request);batch=owned(actor,pk,True)
 if batch.state=='DONE':raise ValidationError('已创建内容请使用回收站处理。')
 batch.state='CANCELLED';batch.records=[];batch.pages=[];batch.selected_text='';batch.segments=[];bump(batch);record(actor,batch,'content_import.cancelled',());return batch


def apply_batch(pk):
 try:
  with transaction.atomic():
   ref=ContentImportBatch.objects.get(pk=pk);actor=User.objects.select_for_update().get(pk=ref.owner_id);eligible(actor);batch=ContentImportBatch.objects.select_for_update().get(pk=pk)
   if batch.state!='APPLYING' or batch.expires_at<=timezone.now():return
   records=validate_records([r for r in batch.records if r['id'] in batch.selected],actor)
   if any(r['errors'] or not r['reviewed'] for r in records):raise ValidationError('所选内容需要重新核验。')
   from types import SimpleNamespace
   from django.contrib.auth import HASH_SESSION_KEY
   from apps.accounts.authentication import SESSION_VERSION_KEY
   from . import direct_services
   request=SimpleNamespace(user=actor,session={SESSION_VERSION_KEY:actor.session_version,HASH_SESSION_KEY:actor.get_session_auth_hash()})
   project_map={};created={}
   projects={normalize_identifier('PROJECT',r['detail']['project_number']):r for r in records if r['kind']=='PROJECT' and r.get('detail',{}).get('project_number')}
   ordered=[];visited=set()
   def visit(r):
    if r['id'] in visited:return
    visited.add(r['id'])
    for number in r.get('project_numbers',[]):
     if number in projects:visit(projects[number])
    ordered.append(r)
   for r in records:visit(r)
   for r in ordered:
    authors=list(User.objects.filter(username__in=r.get('authors',[])).values_list('username','id'));ids=dict(authors)
    payload={'kind':r['kind'],'title':r['title'],'summary':r.get('summary',''),'detail':r.get('detail',{}),'visibility_scope':r['visibility_scope'],'authors':[ids[n] for n in r.get('authors',[])],'authors_ordered':True,'assets':[],'project_links':[]}
    if r.get('body'):payload['rich_body']={'version':1,'type':'doc','content':[{'type':'paragraph','content':[{'type':'text','text':line}]} if line else {'type':'paragraph'} for line in r['body'].splitlines()]}
    from uuid import UUID
    payload['project_links']=[UUID(value) for value in r.get('project_ids',[])]
    for number in r.get('project_numbers',[]):
     project=project_map.get(number)
     if project is None:project=ContentIdentifier.objects.get(scheme='PROJECT',value=number,item__deleted_at__isnull=True,item__archived_at__isnull=True).item
     payload['project_links'].append(project.pk)
    item=direct_services.save(request,payload);created[r['id']]=str(item.pk)
    if r['kind']=='PROJECT' and r.get('detail',{}).get('project_number'):project_map[normalize_identifier('PROJECT',r['detail']['project_number'])]=item
   batch.created=created;batch.state='DONE';bump(batch);record(actor,batch,'content_import.created',('created',))
 except Exception:
  with transaction.atomic():
   batch=ContentImportBatch.objects.select_for_update().get(pk=pk)
   if batch.state=='APPLYING':batch.state='READY';batch.errors=['创建失败，所选内容均未写入。请重新校验标识符、关联成员与项目后重试。'];bump(batch)
