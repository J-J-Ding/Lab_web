"""Minimized retention, never cascades into applied business drafts."""
from pathlib import Path
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from .models import AIImportJob,AICandidate
from . import quota

def cleanup(apply=False):
    now=timezone.now();stats={'jobs':0,'sources':0,'metadata':0}
    for pk in AIImportJob.objects.filter(Q(expires_at__lte=now)|Q(deleted_at__isnull=False)|Q(asset__expires_at__lte=now,state__in=['QUEUED','EXTRACTING','AWAITING_CONSENT'])).values_list('pk',flat=True).iterator():
        with transaction.atomic():
            job=AIImportJob.objects.select_for_update().get(pk=pk)
            if job.state in ('EXTRACTING','CALLING','VALIDATING') and job.lease_expires_at and job.lease_expires_at>now:continue
            stats['jobs']+=1
            if apply:
                if job.state not in ('APPLIED','EXPIRED'):
                    # Calling leases cannot be proven unbilled, even after expiry.
                    quota.settle(job,unknown=job.state in ('CALLING','VALIDATING'),release=job.state not in ('CALLING','VALIDATING'))
                    job.state='EXPIRED'
                job.source_pages=[];job.source_preview='';job.selected_text='';job.save(update_fields=['source_pages','source_preview','selected_text','state'])
                AICandidate.objects.filter(job=job).update(data={})
    from apps.assets.models import AssetFile
    root=Path(settings.PRIVATE_MEDIA_ROOT).resolve()
    for pk in AssetFile.objects.filter(purpose='ai_source',expires_at__lte=now,scan_status='CLEAN').values_list('pk',flat=True).iterator():
        with transaction.atomic():
            asset=AssetFile.objects.select_for_update().get(pk=pk)
            if asset.ai_import_jobs.filter(state__in=['EXTRACTING','CALLING','VALIDATING'],lease_expires_at__gt=now).exists():continue
            if asset.revisionasset_set.exists() or asset.memberrevisionasset_set.exists() or asset.membershipapplication_set.exists() or asset.memberrevision_set.exists():continue
            stats['sources']+=1
            if apply:
                path=(root/asset.storage_key).resolve()
                if path.parent!=root or path.is_symlink():continue
                path.unlink(missing_ok=True);asset.scan_status='REJECTED';asset.original_filename='expired-ai-source';asset.save(update_fields=['scan_status','original_filename'])
    # Usage/account references remain as minimal accounting evidence; no document payload.
    cutoff=now-timezone.timedelta(days=180)
    for pk in AIImportJob.objects.filter(created_at__lt=cutoff,source_preview='').values_list('pk',flat=True).iterator():
        stats['metadata']+=1
        if apply:
            with transaction.atomic():
                job=AIImportJob.objects.select_for_update().get(pk=pk)
                if job.usage.state in ('RESERVED','UNKNOWN'):continue
                job.consents.all().delete();AICandidate.objects.filter(job=job).delete();job.usage.delete();job.delete()
    from .models import AIQuotaBucket
    old=AIQuotaBucket.objects.filter(day__lt=cutoff.date(),reserved_cny=0).exclude(scope__in=['DISPATCH','CIRCUIT'])
    stats['quota_buckets']=old.count()
    if apply:old.delete()
    return stats
