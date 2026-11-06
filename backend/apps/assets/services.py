import hashlib
from pathlib import Path
import os
import secrets
import subprocess
import sys
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError,NotFound,Throttled
from apps.accounts.permissions import can_manage,is_manager
from apps.workflow.permissions import actor_for
from apps.workflow.audit import record
from .models import AssetFile


@transaction.atomic
def upload(request,file,purpose):
    actor=actor_for(request)
    limit=(5 if purpose in ('avatar','image') else 10 if purpose=='proof' else 20)*1024*1024
    allowed={'avatar':{'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp'},'proof':{'.pdf':'application/pdf'}}
    allowed['image']=allowed['avatar']
    allowed['attachment']={'.pdf':'application/pdf','.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
    allowed['ai_source']=allowed['attachment']
    ext=Path(file.name).suffix.lower()
    if ext not in allowed[purpose] or file.content_type!=allowed[purpose][ext]:raise ValidationError({'file':'Unsupported extension or MIME type.'})
    if file.size<=0 or file.size>limit:raise ValidationError({'file':'File exceeds the allowed size.'})
    if AssetFile.objects.filter(owner=actor,created_at__gte=timezone.now()-timezone.timedelta(hours=1)).count()>=20:raise Throttled(wait=3600)
    raw=file.read(limit+1)
    magic={'.png':b'\x89PNG\r\n\x1a\n','.jpg':b'\xff\xd8\xff','.jpeg':b'\xff\xd8\xff','.pdf':b'%PDF-','.webp':b'RIFF','.docx':b'PK\x03\x04'}[ext]
    if len(raw)>limit or not raw.startswith(magic) or (ext=='.webp' and raw[8:12]!=b'WEBP'):raise ValidationError({'file':'File signature does not match its declared type.'})
    try:
        result=subprocess.run([sys.executable,'-m','apps.assets.inspect_file','avatar' if purpose in ('avatar','image') else 'docx' if ext=='.docx' else 'proof'],input=raw,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=8,env={'PATH':os.defpath,'PYTHONPATH':str(settings.BASE_DIR),'PYTHONDONTWRITEBYTECODE':'1'})
    except (OSError,subprocess.TimeoutExpired):raise ValidationError({'file':'File validation failed or timed out.'}) from None
    if result.returncode or not result.stdout or len(result.stdout)>limit:raise ValidationError({'file':'Malformed, unsafe or oversized decoded file.'})
    cleaned=result.stdout
    from .scanner import check_bytes
    check_bytes(raw);check_bytes(cleaned)
    root=Path(settings.PRIVATE_MEDIA_ROOT).resolve();root.mkdir(mode=0o700,parents=True,exist_ok=True)
    output_ext='.png' if purpose in ('avatar','image') else ext
    output_mime='image/png' if purpose in ('avatar','image') else allowed[purpose][ext]
    key=secrets.token_hex(24)+output_ext;target=root/key
    try:
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as handle:handle.write(cleaned)
        asset=AssetFile.objects.create(owner=actor,purpose=purpose,storage_key=key,original_filename=Path(file.name).name[:255],mime_type=output_mime,size=len(cleaned),sha256=hashlib.sha256(cleaned).hexdigest(),visibility='PRIVATE',scan_status='CLEAN',expires_at=timezone.now()+timezone.timedelta(days=settings.AI_SOURCE_RETENTION_DAYS if purpose=='ai_source' else 30))
        record(actor,asset,'asset.upload',('file',))
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return asset


def permitted_asset(actor,pk):
    asset=AssetFile.objects.filter(pk=pk,scan_status='CLEAN').first()
    if not asset or (asset.expires_at and asset.expires_at<=timezone.now()):raise NotFound()
    if asset.owner_id!=actor.pk:
        from apps.workflow.permissions import visible_items
        content_reference=asset.purpose in ('image','attachment') and asset.revisionasset_set.filter(revision__item__in=visible_items(actor)).exists()
        if not content_reference:
            if not is_manager(actor):raise NotFound()
            applications=asset.membershipapplication_set.select_related('applicant')
            from django.db.models import F
            avatar_candidates=asset.memberrevision_set.filter(state='SUBMITTED',profile__draft_revision_id=F('id'))
            if not actor.is_superuser:avatar_candidates=avatar_candidates.filter(profile__user__is_superuser=False,profile__user__role__in=['CUSTOMER','STUDENT','TEACHER'])
            reviewing_avatar=asset.mime_type.startswith('image/') and avatar_candidates.exists()
            if not reviewing_avatar and not any(can_manage(actor,a.applicant) for a in applications):raise NotFound()
    root=Path(settings.PRIVATE_MEDIA_ROOT).resolve();original=root/asset.storage_key
    if original.is_symlink():raise NotFound()
    path=original.resolve()
    if path.parent!=root or not path.is_file() or path.is_symlink():raise NotFound()
    return asset,path
