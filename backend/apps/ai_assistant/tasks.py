"""PostgreSQL leased worker. No database transaction is held during parsing/network I/O."""
import uuid
from datetime import date
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from apps.accounts.models import User
from apps.workflow.permissions import can_submit
from .models import AIImportJob,AIConsent,AICandidate,ACTIVE_STATES
from . import quota
from .extractors import extract_asset,ExtractionError
from .providers.deepseek import DeepSeekProvider,ProviderError
from .schemas import validate_candidate


def eligible(actor,job):return actor.is_active and (job.target_type=='MEMBER' or can_submit(actor))

@transaction.atomic
def recover_leases():
    now=timezone.now()
    for ref in AIImportJob.objects.filter(state__in=['EXTRACTING','CALLING','VALIDATING'],lease_expires_at__lt=now).values('id','owner_id')[:100]:
        actor=User.objects.select_for_update(skip_locked=True).filter(pk=ref['owner_id']).first()
        if not actor:continue
        job=AIImportJob.objects.select_for_update(skip_locked=True).filter(pk=ref['id'],lease_expires_at__lt=now).first()
        if not job:continue
        if job.state=='EXTRACTING' and job.attempts<3 and eligible(actor,job):job.state='QUEUED';job.error_code=''
        else:
            unknown=job.state in ('CALLING','VALIDATING')
            quota.settle(job,unknown=unknown,release=not unknown)
            job.state='FAILED';job.error_code='unknown_usage' if unknown else 'worker_recovery_failed';job.finished_at=now
        job.lease_token=None;job.lease_expires_at=None;job.lock_version+=1;job.save()

@transaction.atomic
def claim_job():
    if not settings.AI_ENABLED:return None
    ref=AIImportJob.objects.filter(state='QUEUED',deleted_at__isnull=True).order_by('created_at','pk').values('id','owner_id').first()
    if not ref:return None
    actor=User.objects.select_for_update(skip_locked=True).filter(pk=ref['owner_id']).first()
    if not actor:return None
    dispatch=quota.bucket('DISPATCH',0,date(1970,1,1));guard=quota.circuit()
    if guard.blocked_until and guard.blocked_until>timezone.now():return None
    if AIImportJob.objects.filter(state__in=['EXTRACTING','CALLING','VALIDATING'],lease_expires_at__gt=timezone.now()).count()>=2:return None
    job=AIImportJob.objects.select_for_update(skip_locked=True).filter(pk=ref['id'],state='QUEUED').first()
    if not job:return None
    if not eligible(actor,job) or job.expires_at<=timezone.now():
        quota.settle(job,release=True);job.state='FAILED';job.error_code='account_or_job_unavailable';job.finished_at=timezone.now();job.lock_version+=1;job.save();return None
    calling=bool(job.source_pages)
    if calling and not job.consents.filter(version='deepseek-text-v1',revoked_at__isnull=True,text_digest=job.input_digest).exists():
        quota.settle(job,release=True);job.state='FAILED';job.error_code='consent_required';job.save();return None
    if (not calling and not job.asset_id) or (job.asset_id and (job.asset.scan_status!='CLEAN' or (job.asset.expires_at and job.asset.expires_at<=timezone.now()))):
        quota.settle(job,release=True);job.state='FAILED';job.error_code='source_expired';job.save();return None
    if calling:
        try:current_prices,_=quota.require_enabled()
        except quota.AIUnavailable:
            quota.settle(job,release=True);job.state='FAILED';job.error_code='provider_configuration';job.save();return None
        if current_prices!=job.usage.price_snapshot:
            quota.settle(job,release=True);job.state='FAILED';job.error_code='price_changed';job.save();return None
        ledger=job.usage;ledger.sent_at=timezone.now();ledger.save(update_fields=['sent_at'])
    job.state='CALLING' if calling else 'EXTRACTING';job.lease_token=uuid.uuid4();job.lease_expires_at=timezone.now()+timezone.timedelta(seconds=max(settings.AI_LEASE_SECONDS,240));job.heartbeat_at=timezone.now();job.attempts+=1;job.lock_version+=1;job.save()
    return job

@transaction.atomic
def finish_extract(ref,pages=None,error=''):
    job=AIImportJob.objects.select_for_update().get(pk=ref.pk)
    if job.lease_token!=ref.lease_token or job.state!='EXTRACTING':return
    if error:
        job.state='FAILED';job.error_code=error;job.finished_at=timezone.now();quota.settle(job,release=True)
    else:
        job.source_pages=pages;job.source_preview='\n\n'.join('[PAGE '+str(p['page'])+']\n'+p['text'] for p in pages);job.state='AWAITING_CONSENT'
    job.lease_token=None;job.lease_expires_at=None;job.heartbeat_at=timezone.now();job.lock_version+=1;job.save()

@transaction.atomic
def finish_call(ref,result=None,error=None):
    job=AIImportJob.objects.select_for_update().get(pk=ref.pk)
    guard=quota.circuit()
    if error:
        quota.settle(job,unknown=error.unknown,release=not error.unknown,known_not_billed=not error.unknown)
        guard.failures+=1
        if error.code=='provider_access_denied' or guard.failures>=3:guard.blocked_until=timezone.now()+timezone.timedelta(seconds=300)
        guard.save()
    else:
        quota.settle(job,input_tokens=result.input_tokens,output_tokens=result.output_tokens,request_id=result.request_id)
        guard.failures=0;guard.blocked_until=None;guard.save()
    if job.lease_token!=ref.lease_token or job.state!='CALLING':return
    if error:job.state='FAILED';job.error_code='unknown_usage' if error.unknown else error.code
    else:
        job.state='VALIDATING';job.heartbeat_at=timezone.now();job.save(update_fields=['state','heartbeat_at'])
        try:
            data=validate_candidate(result.data,job.target_type,job.source_pages,job.selected_text,summary=job.mode=='SUMMARY')
            AICandidate.objects.create(job=job,data=data,expires_at=job.expires_at);job.state='READY'
        except Exception:job.state='FAILED';job.error_code='candidate_validation_failed'
    job.finished_at=timezone.now();job.lease_token=None;job.lease_expires_at=None;job.lock_version+=1;job.save()


def run_once(provider=None):
    recover_leases();job=claim_job()
    if not job:return False
    if job.state=='EXTRACTING':
        try:finish_extract(job,extract_asset(job.asset))
        except ExtractionError as exc:finish_extract(job,error=exc.code)
        return True
    try:
        provider=provider or DeepSeekProvider()
        context={'request_digest':job.usage.request_digest,'summary':job.mode=='SUMMARY'}
        result=provider.extract_fields(job.selected_text,job.target_type,context)
        finish_call(job,result=result)
    except ProviderError as exc:finish_call(job,error=exc)
    except Exception:finish_call(job,error=ProviderError('worker_network_unknown',unknown=True))
    return True
