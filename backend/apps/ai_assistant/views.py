from decimal import Decimal
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from apps.accounts.views import validated
from apps.workflow.api import BusinessAPIView
from apps.workflow.serializers import VersionInput
from .models import AIImportJob,AICandidate,AIQuotaBucket,AIUsageLedger
from .serializers import ImportInput,SummaryInput,ConsentInput,CandidateInput,ApplyInput
from . import services,quota

ERRORS={'ocr_required':'该文件没有可用文本层，需要 OCR 或人工录入。','empty_document':'文档没有可提取文本。','invalid_document':'文件结构损坏或不受支持。','text_too_large':'提取文本过长，请拆分文档。','source_expired':'原件已到期，请重新上传。','unknown_usage':'请求结果或计费不确定，已停止自动重试，预留预算等待核对。','candidate_validation_failed':'模型输出未通过字段或来源校验，请人工录入或重新提交。','provider_access_denied':'模型服务未授权或余额不足，请联系管理员。','input_too_large':'选中内容过长，请拆分。'}
def serialize(job,detail=False):
    usage=job.usage
    out={'id':str(job.pk),'target_type':job.target_type,'mode':job.mode,'state':job.state,'lock_version':job.lock_version,'error_code':job.error_code,'message':ERRORS.get(job.error_code,'任务暂不可用，请稍后查看或联系管理员。') if job.error_code else '',
        'created_at':job.created_at,'expires_at':job.expires_at,'model':job.model_name,
        'usage':{'state':usage.state,'reserved_cny':str(usage.reserved_cny),'actual_cny':str(usage.actual_cny) if usage.actual_cny is not None else None,'input_tokens':usage.input_tokens,'output_tokens':usage.output_tokens}}
    if detail:
        candidate=getattr(job,'candidate',None)
        out.update(preview=job.source_preview,text_digest=services.digest(job.source_preview),candidate=candidate.data if candidate else None,applied=candidate.applied if candidate else {})
    return out

def owner_job(user,pk):return get_object_or_404(AIImportJob.objects.select_related('usage','candidate'),pk=pk,owner=user,deleted_at__isnull=True)

class ImportsView(BusinessAPIView):
    http_method_names=['get','post']
    def get(self,request):
        from apps.workflow.views import page,filters
        filters(request,set());return page(request,AIImportJob.objects.filter(owner=request.user,deleted_at__isnull=True).select_related('usage').order_by('-created_at','pk'),serialize)
    def post(self,request):return Response(serialize(services.create(request,validated(ImportInput,request)),True),status=202)
class SummaryView(BusinessAPIView):
    http_method_names=['post']
    def post(self,request):return Response(serialize(services.create(request,validated(SummaryInput,request),summary=True),True),status=202)
class JobView(BusinessAPIView):
    http_method_names=['get','delete']
    def get(self,request,pk):return Response(serialize(owner_job(request.user,pk),True))
    def delete(self,request,pk):services.cancel(request,pk,delete=True);return Response(status=204)
class CancelView(BusinessAPIView):
    http_method_names=['post']
    def post(self,request,pk):return Response(serialize(services.cancel(request,pk),True))
class ConsentView(BusinessAPIView):
    http_method_names=['post']
    def post(self,request,pk):return Response(serialize(services.consent(request,pk,validated(ConsentInput,request)),True))
class CandidateView(BusinessAPIView):
    http_method_names=['patch']
    def patch(self,request,pk):return Response(serialize(services.update_candidate(request,pk,validated(CandidateInput,request)),True))
class ApplyView(BusinessAPIView):
    http_method_names=['post']
    def post(self,request,pk):
        data=services.apply(request,pk,validated(ApplyInput,request));return Response({k:v for k,v in data.items() if k!='request_digest'})
class QuotaView(BusinessAPIView):
    http_method_names=['get']
    def get(self,request):
        enabled=True
        try:quota.require_enabled()
        except quota.AIUnavailable:enabled=False
        day=timezone.localdate();user=AIQuotaBucket.objects.filter(scope='USER',owner_key=request.user.pk,day=day).first();global_bucket=AIQuotaBucket.objects.filter(scope='GLOBAL',owner_key=0,day=day).first()
        return Response({'enabled':enabled,'provider':'deepseek','model':settings.DEEPSEEK_MODEL,'consent_version':'deepseek-text-v1','local_consent_version':'local-v1','user_daily_limit':settings.AI_USER_DAILY_LIMIT,'user_remaining':max(0,settings.AI_USER_DAILY_LIMIT-(user.count if user else 0)),
            'global_remaining':max(0,settings.AI_GLOBAL_DAILY_LIMIT-(global_bucket.count if global_bucket else 0)),'daily_budget_cny':settings.AI_GLOBAL_DAILY_BUDGET_CNY,'reserved_cny':str(user.reserved_cny) if user else '0','spent_cny':str(user.spent_cny) if user else '0','notice':'原件留在本服务器；只有确认后的脱敏文本发送至 DeepSeek。候选须人工确认，应用仅保存草稿。'})
class MatchesView(BusinessAPIView):
    http_method_names=['get']
    def get(self,request,pk):
        from apps.workflow.permissions import selectable_contributors,visible_items
        from apps.content.models import ContentIdentifier
        from django.db.models import Q
        from apps.content.services import normalize_identifier
        job=owner_job(request.user,pk);candidate=getattr(job,'candidate',None);results=[]
        if not candidate:return Response({'records':[]})
        for index,r in enumerate(candidate.data.get('records',[])):
            fields=r['fields'];matches=[];duplicates=[]
            for i,author in enumerate(fields.get('authors',[])):
                choices=selectable_contributors(request.user).filter(safe_name__icontains=author['name'])
                matches.append({'author_index':i,'options':[{'id':str(c.pk),'name':c.safe_name,'affiliation':c.safe_affiliation} for c in list(choices)[:20]]})
            for field,scheme in [('doi','DOI'),('project_number','PROJECT'),('isbn','ISBN')]:
                value=fields.get('detail',{}).get(field)
                if value:
                    try:normalized=normalize_identifier(scheme,value)
                    except Exception:continue
                    for identifier in ContentIdentifier.objects.filter(scheme=scheme,value=normalized).filter(Q(item__in=visible_items(request.user))|Q(item__visibility_gate=True,item__visibility_scope='PUBLIC',item__archived_at__isnull=True,item__deleted_at__isnull=True,item__published_revision__state='PUBLISHED')).select_related('item__working_revision','item__published_revision')[:10]:
                        item=identifier.item;private=visible_items(request.user).filter(pk=item.pk).exists()
                        revision=(item.working_revision or item.published_revision) if private else item.published_revision
                        duplicates.append({'id':str(item.pk),'title':revision.title if revision else '', 'public_only':not private})
            results.append({'record_index':index,'authors':matches,'duplicates':duplicates})
        return Response({'records':results})
