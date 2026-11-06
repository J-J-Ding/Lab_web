import hashlib,json
from django.conf import settings
from django.db import transaction,IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied,ValidationError,Throttled,NotFound
from apps.workflow.permissions import actor_for,can_submit,visible_items,selectable_contributors
from apps.workflow.audit import record
from apps.members.services import VersionConflict
from apps.assets.models import AssetFile
from .models import AIImportJob,AIConsent,AICandidate,AIUsageLedger,ACTIVE_STATES
from . import quota
from .schemas import normalize_fields,validate_candidate,paths,TARGET_TYPES

def digest(value):return hashlib.sha256(value.encode()).hexdigest()
def eligible(actor,target):
    if target not in TARGET_TYPES:raise ValidationError({'target_type':'Unsupported target.'})
    if target!='MEMBER' and not can_submit(actor):raise PermissionDenied('正式成员或管理者才可导入内容草稿。')
def own(actor,pk):return get_object_or_404(AIImportJob.objects.select_for_update(),pk=pk,owner=actor,deleted_at__isnull=True)
def version(job,n):
    if job.lock_version!=n:raise VersionConflict('候选或任务已更新，请重新读取。')
def bump(job):job.lock_version+=1;job.save()

@transaction.atomic
def create(request,data,summary=False):
    actor=actor_for(request);quota.require_enabled();eligible(actor,data['target_type'])
    if AIImportJob.objects.filter(owner=actor,state__in=ACTIVE_STATES,deleted_at__isnull=True).exists():raise VersionConflict('请先完成或取消当前 AI 任务。')
    asset=None;values={};pages=[];text=''
    if summary:
        values=normalize_fields(data['verified_fields'],data['target_type'])
        text=json.dumps(values,ensure_ascii=False,sort_keys=True)
        if len(text)>20000:raise ValidationError('已确认字段过长。')
        from .extractors import redact
        text=redact(text);pages=[{'page':1,'text':text}]
    else:
        asset=get_object_or_404(AssetFile.objects.select_for_update(),pk=data['asset'],owner=actor,purpose='ai_source',scan_status='CLEAN',visibility='PRIVATE',deletion_requested_at__isnull=True)
        if asset.expires_at and asset.expires_at<=timezone.now():raise ValidationError({'asset':'Source expired.'})
    try:
        with transaction.atomic():job=AIImportJob.objects.create(owner=actor,asset=asset,target_type=data['target_type'],mode='SUMMARY' if summary else 'IMPORT',model_name=settings.DEEPSEEK_MODEL,source_pages=pages,source_preview=text,selected_text=text,input_digest=digest(text) if text else '',expires_at=timezone.now()+timezone.timedelta(days=settings.AI_CANDIDATE_RETENTION_DAYS))
    except IntegrityError:raise VersionConflict('当前账号已有活动任务。') from None
    AIConsent.objects.create(job=job,owner=actor,version='deepseek-text-v1' if summary else 'local-v1',scopes=['verified_fields'] if summary else ['local_extraction'],text_digest=job.input_digest)
    quota.reserve(actor,job);record(actor,job,'ai.job.create',('mode','target_type','consent'))
    return job

@transaction.atomic
def consent(request,pk,data):
    actor=actor_for(request);quota.require_enabled();job=own(actor,pk);eligible(actor,job.target_type);version(job,data['lock_version'])
    if job.state!='AWAITING_CONSENT' or not job.source_preview:raise VersionConflict('当前任务不能授权发送。')
    if job.asset_id and job.asset.expires_at and job.asset.expires_at<=timezone.now():raise VersionConflict('原件已到期，请重新上传。')
    if data['text_digest']!=digest(job.source_preview):raise VersionConflict('脱敏预览已变更。')
    selected=data['selected_text'].strip()
    if not selected or selected not in job.source_preview:raise ValidationError({'selected_text':'仅选择脱敏原文的连续片段，不可改写原文。'})
    # Byte count is a conservative token bound; includes schema/system overhead.
    from .schemas import prompt_schema
    if len(selected.encode())+len(json.dumps(prompt_schema(job.target_type),ensure_ascii=False).encode())+2500>settings.AI_MAX_INPUT_TOKENS:raise ValidationError({'selected_text':'文本过长，请选择更小的连续片段分批处理。'})
    AIConsent.objects.create(job=job,owner=actor,version='deepseek-text-v1',scopes=['redacted_selected_text'],text_digest=digest(selected))
    job.selected_text=selected;job.input_digest=digest(selected);job.state='QUEUED';bump(job);record(actor,job,'ai.consent.granted',('selected_text',));return job

@transaction.atomic
def cancel(request,pk,delete=False):
    actor=actor_for(request);job=own(actor,pk)
    running=job.state in ('CALLING','VALIDATING')
    if job.state not in ('APPLIED','EXPIRED'):
        if not running:quota.settle(job,release=True)
        job.state='CANCELLED';job.finished_at=timezone.now()
    job.consents.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
    if delete:
        job.deleted_at=timezone.now();job.source_pages=[];job.source_preview='';job.selected_text=''
        AICandidate.objects.filter(job=job).update(data={})
        if job.asset_id and job.asset.purpose=='ai_source':
            job.asset.deletion_requested_at=timezone.now();job.asset.expires_at=timezone.now();job.asset.save(update_fields=['deletion_requested_at','expires_at'])
    bump(job);record(actor,job,'ai.job.delete' if delete else 'ai.job.cancel',('state',));return job

@transaction.atomic
def update_candidate(request,pk,data):
    actor=actor_for(request);job=own(actor,pk);version(job,data['lock_version'])
    if job.state!='READY':raise VersionConflict()
    candidate=AICandidate.objects.select_for_update().get(job=job)
    if candidate.applied:raise VersionConflict('已应用部分候选，不再改写此批候选。')
    candidate.data=validate_candidate(data['candidate'],job.target_type,job.source_pages,job.selected_text,human=True,summary=job.mode=='SUMMARY');candidate.save(update_fields=['data'])
    bump(job);record(actor,job,'ai.candidate.edit',('candidate',));return job

def selected_fields(fields,confirmed):
    if not confirmed or len(set(confirmed))!=len(confirmed) or set(confirmed)-set(paths(fields)):raise ValidationError({'confirmed_fields':'逐项确认有效字段。'})
    out={}
    for key in confirmed:
        if key.startswith('detail.'):out.setdefault('detail',{})[key.split('.',1)[1]]=fields['detail'][key.split('.',1)[1]]
        else:out[key]=fields[key]
    return out

@transaction.atomic
def apply(request,pk,data):
    actor=actor_for(request);job=own(actor,pk);eligible(actor,job.target_type)
    if job.state not in ('READY','APPLIED') or job.expires_at<=timezone.now():raise VersionConflict('候选不可应用或已到期。')
    candidate=AICandidate.objects.select_for_update().get(job=job);index=data['record_index'];key=str(index)
    fingerprint=digest(json.dumps(data,sort_keys=True,default=str))
    if key in candidate.applied:
        saved=candidate.applied[key]
        if saved['request_digest']!=fingerprint:raise VersionConflict('该候选已应用到其他请求。')
        return saved
    version(job,data['lock_version'])
    if index>=len(candidate.data['records']):raise ValidationError({'record_index':'Invalid record.'})
    fields=selected_fields(candidate.data['records'][index]['fields'],data['confirmed_fields'])
    if job.target_type=='MEMBER':
        from apps.members import services as members
        from apps.members.models import MemberProfile
        profile=MemberProfile.objects.filter(user=actor,merged_into__isnull=True).first()
        if data.get('target_id') and (not profile or str(profile.pk)!=str(data['target_id'])):raise NotFound()
        if profile and profile.draft_revision_id:
            if data.get('target_lock_version')!=profile.lock_version:raise VersionConflict('本人档案已变化。')
        else:
            if data.get('target_lock_version') not in (None,profile.lock_version if profile else None):raise VersionConflict()
            profile,rev,_=members.initialize_draft(actor)
        profile,rev=members.update_draft(actor,{'lock_version':profile.lock_version,**fields})
        result={'target_id':str(profile.pk),'revision_id':str(rev.pk),'kind':'MEMBER','request_digest':fingerprint}
        candidate.applied_member_revision=rev
    else:
        from apps.workflow import content_services as content
        from apps.workflow.serializers import ContentCreateInput,ContentUpdateInput
        authors=fields.pop('authors',None);matches=data.get('contributor_matches',[])
        if authors is not None:
            if len(matches)!=len(authors) or {m['index'] for m in matches}!=set(range(len(authors))):raise ValidationError({'contributor_matches':'每位作者需人工明确匹配贡献者；不按姓名自动绑定。'})
            fields['contributions']=[{k:v for k,v in m.items() if k!='index'} for m in matches]
        elif matches:raise ValidationError({'contributor_matches':'请先确认作者字段。'})
        if data.get('target_id'):
            from apps.content.models import ContentItem
            item=get_object_or_404(visible_items(actor).select_for_update(),pk=data['target_id'],kind=job.target_type)
            if not item.working_revision_id or data.get('target_lock_version')!=item.lock_version:raise VersionConflict('目标草稿已变化。')
            serializer=ContentUpdateInput(data={'lock_version':item.lock_version,**fields});serializer.is_valid(raise_exception=True)
            item=content.edit(request,item.working_revision_id,serializer.validated_data)
        else:
            if job.mode=='SUMMARY':raise ValidationError('摘要应应用到明确的已有草稿。')
            serializer=ContentCreateInput(data={'kind':job.target_type,**fields});serializer.is_valid(raise_exception=True)
            item=content.create(request,serializer.validated_data)
        rev=item.working_revision;result={'target_id':str(item.pk),'revision_id':str(rev.pk),'kind':item.kind,'request_digest':fingerprint};candidate.applied_revision=rev
    candidate.applied[key]=result;candidate.confirmed_at=timezone.now();candidate.save()
    job.state='APPLIED' if len(candidate.applied)==len(candidate.data['records']) else 'READY';bump(job)
    record(actor,job,'ai.candidate.apply',tuple(data['confirmed_fields']),rev);return result
