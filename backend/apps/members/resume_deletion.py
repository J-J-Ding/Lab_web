"""Owner-only resume removal; withdraw access atomically, then remove unused bytes."""
import logging
from pathlib import Path
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from apps.accounts.services import locked_users
from apps.assets.models import AssetFile
from apps.workflow.audit import record
from .models import Resume,ResumeSubmission,SubmissionNotification
from .services import VersionConflict

logger=logging.getLogger(__name__)


def has_retained_reference(asset):
    if Resume.objects.filter(asset=asset,deleted_at__isnull=True).exists():return True
    if ResumeSubmission.objects.filter(asset=asset,resume__deleted_at__isnull=True).exists():return True
    return any(getattr(asset,name).exists() for name in ('ai_import_jobs','memberrevision_set','revisionasset_set','memberrevisionasset_set','membershipapplication_set'))


def purge_resume_file(pk):
    """Retryable after commit: deleted metadata/submission history does not retain bytes."""
    try:
        with transaction.atomic():
            asset=AssetFile.objects.select_for_update().filter(pk=pk,purpose='resume',deletion_requested_at__isnull=False).first()
            if not asset or has_retained_reference(asset):return False
            root=Path(settings.PRIVATE_MEDIA_ROOT).resolve();path=root/asset.storage_key
            if path.is_symlink() or path.resolve().parent!=root:
                logger.error('Unsafe resume storage key for asset %s',pk);return False
            path.unlink(missing_ok=True)
            if asset.scan_status!='REJECTED':
                asset.scan_status='REJECTED';asset.save(update_fields=['scan_status'])
                if asset.owner_id:record(asset.owner,asset,'resume.file.deleted',('file',))
        return True
    except Exception:
        logger.exception('Resume file cleanup pending for asset %s',pk)
        return False


@transaction.atomic
def delete_resume(request,pk,lock_version):
    actor,_=locked_users(request)
    resume=get_object_or_404(Resume.objects.select_for_update(),pk=pk,owner=actor,deleted_at__isnull=True)
    if resume.lock_version!=lock_version:raise VersionConflict()
    now=timezone.now()
    rows=list(ResumeSubmission.objects.select_for_update().filter(resume=resume).order_by('pk'))
    asset_ids={row.asset_id for row in rows}
    if resume.asset_id:asset_ids.add(resume.asset_id)
    for row in rows:
        if row.state=='SUBMITTED':
            row.state='WITHDRAWN';row.withdrawn_at=now;row.save(update_fields=['state','withdrawn_at'])
            record(actor,row,'resume.withdrawn',('state',))
    SubmissionNotification.objects.filter(submission__in=rows,read_at__isnull=True).update(read_at=now)
    resume.deleted_at=now;resume.lock_version+=1;resume.save(update_fields=['deleted_at','lock_version','updated_at'])
    record(actor,resume,'resume.deleted',('deleted_at',))
    for asset in AssetFile.objects.select_for_update().filter(pk__in=asset_ids,owner=actor,purpose='resume').order_by('pk'):
        if has_retained_reference(asset):continue
        asset.deletion_requested_at=now;asset.expires_at=now;asset.save(update_fields=['deletion_requested_at','expires_at'])
        record(actor,asset,'asset.delete.request',('deletion_requested_at',))
        transaction.on_commit(lambda pk=asset.pk:purge_resume_file(pk))
    return {'detail':'简历已删除，相关投递已撤回；不再被其他简历使用的文件已安排清理。'}
