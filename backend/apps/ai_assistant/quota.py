from datetime import date,datetime,timezone as utc
from decimal import Decimal,InvalidOperation,ROUND_CEILING
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException,Throttled
from .models import AIQuotaBucket,AIUsageLedger,ACTIVE_STATES,AIImportJob

class AIUnavailable(APIException):
    status_code=503
    default_detail='AI 功能关闭或模型、价格配置尚未就绪；仍可使用手工录入。'
    default_code='ai_unavailable'

def pricing():
    try:
        day=date.fromisoformat(settings.AI_PRICE_EFFECTIVE_DATE);today=timezone.localdate()
        a=Decimal(settings.AI_PRICE_INPUT_CNY_PER_MILLION);b=Decimal(settings.AI_PRICE_OUTPUT_CNY_PER_MILLION);budget=Decimal(settings.AI_GLOBAL_DAILY_BUDGET_CNY)
        if day>today or (today-day).days>30 or not all(x.is_finite() and x>0 for x in (a,b,budget)):raise ValueError()
        if not 1<=settings.AI_MAX_INPUT_TOKENS<=24000 or not 1<=settings.AI_MAX_OUTPUT_TOKENS<=4000:raise ValueError()
        return {'input':str(a),'output':str(b),'effective_date':str(day),'model':settings.DEEPSEEK_MODEL},budget
    except (ValueError,TypeError,InvalidOperation):raise AIUnavailable() from None

def require_enabled():
    if not settings.AI_ENABLED or settings.AI_PROVIDER!='deepseek' or settings.DEEPSEEK_MODEL!='deepseek-flash' or settings.DEEPSEEK_BASE_URL.rstrip('/') not in ('https://api.deepseek.com','https://api.deepseek.com/v1') or not settings.DEEPSEEK_API_KEY:raise AIUnavailable()
    return pricing()

def amount(a,b,prices):return ((Decimal(a)*Decimal(prices['input'])+Decimal(b)*Decimal(prices['output']))/Decimal(1000000)).quantize(Decimal('.000001'),rounding=ROUND_CEILING)

def bucket(scope,key,day):
    obj,_=AIQuotaBucket.objects.get_or_create(scope=scope,owner_key=key,day=day)
    return AIQuotaBucket.objects.select_for_update().get(pk=obj.pk)

def reserve(owner,job):
    prices,budget=require_enabled();day=timezone.localdate();cost=amount(settings.AI_MAX_INPUT_TOKENS,settings.AI_MAX_OUTPUT_TOKENS,prices)
    global_bucket=bucket('GLOBAL',0,day);user_bucket=bucket('USER',owner.pk,day)
    if global_bucket.count>=settings.AI_GLOBAL_DAILY_LIMIT or user_bucket.count>=settings.AI_USER_DAILY_LIMIT or global_bucket.reserved_cny+global_bucket.spent_cny+cost>budget or AIImportJob.objects.filter(state__in=ACTIVE_STATES,deleted_at__isnull=True).count()>100:raise Throttled(detail='AI 每日次数、预算或队列已达上限。',wait=3600)
    for obj in (global_bucket,user_bucket):
        obj.count+=1;obj.reserved_cny+=cost;obj.save(update_fields=['count','reserved_cny'])
    return AIUsageLedger.objects.create(job=job,owner=owner,request_digest=__import__('hashlib').sha256(('ai-v1:'+str(job.pk)).encode()).hexdigest(),reserved_cny=cost,price_snapshot=prices,business_day=day,billing_day_utc=datetime.now(utc.utc).date())

def settle(job,input_tokens=0,output_tokens=0,unknown=False,release=False,request_id='',known_not_billed=False):
    ledger=AIUsageLedger.objects.select_for_update().get(job=job)
    if ledger.state in ('SETTLED','RELEASED'):return ledger
    if unknown or (release and ledger.sent_at and not known_not_billed):
        ledger.state='UNKNOWN';ledger.save(update_fields=['state']);return ledger
    global_bucket=bucket('GLOBAL',0,ledger.business_day);user_bucket=bucket('USER',ledger.owner_id,ledger.business_day)
    actual=Decimal(0) if release else amount(input_tokens,output_tokens,ledger.price_snapshot)
    for obj in (global_bucket,user_bucket):
        obj.reserved_cny=max(Decimal(0),obj.reserved_cny-ledger.reserved_cny);obj.spent_cny+=actual;obj.save(update_fields=['reserved_cny','spent_cny'])
    ledger.state='RELEASED' if release else 'SETTLED';ledger.actual_cny=actual;ledger.input_tokens=input_tokens;ledger.output_tokens=output_tokens;ledger.settled_at=timezone.now()
    ledger.request_id_digest=__import__('hashlib').sha256(request_id.encode()).hexdigest() if request_id else ''
    ledger.save();return ledger

def circuit():return bucket('CIRCUIT',0,date(1970,1,1))
