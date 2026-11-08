"""Local queue for parsing, bounded AI calls and atomic content application."""
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from .models import ContentImportBatch
from .batch_services import bump,apply_batch,eligible


def cleanup():
 from .models import ContentImportCall
 from .batch_ai import settle
 now=timezone.now()
 with transaction.atomic():
  for batch in ContentImportBatch.objects.select_for_update(skip_locked=True).exclude(state__in=['EXPIRED','CANCELLED']).filter(expires_at__lte=now):
   for call in batch.calls.filter(state='RESERVED'):settle(call.pk,unknown=True)
   batch.state='EXPIRED';batch.records=[];batch.errors=[];batch.pages=[];batch.selected_text='';batch.segments=[];bump(batch)
  for batch in ContentImportBatch.objects.select_for_update(skip_locked=True).filter(state__in=['CALLING','APPLYING','PARSING'],lease_at__lt=now-timedelta(minutes=5)):
   for call in batch.calls.filter(state='RESERVED'):settle(call.pk,unknown=True)
   batch.state='READY';batch.errors=['处理已中断；没有自动重试收费请求。请核对已有候选后继续。'];batch.lease_at=None;bump(batch)


def run_once(send=None):
 cleanup()
 with transaction.atomic():
  batch=ContentImportBatch.objects.select_for_update(skip_locked=True).filter(state__in=['EXTRACTING','QUEUED_AI','QUEUED_APPLY']).order_by('created_at').first()
  if not batch:return False
  try:eligible(batch.owner)
  except Exception:batch.state='CANCELLED';bump(batch);return True
  operation=batch.state;batch.state={'EXTRACTING':'PARSING','QUEUED_AI':'CALLING','QUEUED_APPLY':'APPLYING'}[operation];batch.lease_at=timezone.now();bump(batch);pk=batch.pk
 if operation=='QUEUED_APPLY':apply_batch(pk)
 elif operation=='QUEUED_AI':
  from .batch_ai import extract_one
  extract_one(pk,send)
 else:
  from apps.ai_assistant.extractors import extract_asset,ExtractionError
  try:
   asset=batch.asset
   if not asset or asset.deletion_requested_at or asset.scan_status!='CLEAN' or (asset.expires_at and asset.expires_at<=timezone.now()):raise ExtractionError('source_expired')
   pages=extract_asset(asset)
   with transaction.atomic():
    batch=ContentImportBatch.objects.select_for_update().get(pk=pk)
    if batch.state=='PARSING':batch.pages=pages;batch.selected_text='\n\n'.join('[PAGE '+str(p['page'])+']\n'+p['text'] for p in pages);batch.state='AWAITING_CONSENT';batch.lease_at=None;bump(batch)
  except Exception as exc:
   with transaction.atomic():
    batch=ContentImportBatch.objects.select_for_update().get(pk=pk)
    if batch.state=='PARSING':batch.state='READY';batch.errors=['文档提取失败：'+(exc.code if isinstance(exc,ExtractionError) else 'parser_failure')+'；扫描件需要OCR，请使用文本型PDF或DOCX。'];bump(batch)
 return True
