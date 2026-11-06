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
    allowed['resume']=allowed['attachment']
    ext=Path(file.name).suffix.lower()
    if ext not in allowed[purpose] or file.content_type not in (allowed[purpose][ext],'application/octet-stream',''):raise ValidationError({'file':'文件类型不支持，请选择PDF或DOCX，确认扩展名与文件内容一致。'})
    if file.size<=0 or file.size>limit:raise ValidationError({'file':f'文件大小须大于0且不超过{limit//(1024*1024)}MiB。'})
    if AssetFile.objects.filter(owner=actor,created_at__gte=timezone.now()-timezone.timedelta(hours=1)).count()>=20:raise Throttled(wait=3600)
    raw=file.read(limit+1)
    magic={'.png':b'\x89PNG\r\n\x1a\n','.jpg':b'\xff\xd8\xff','.jpeg':b'\xff\xd8\xff','.pdf':b'%PDF-','.webp':b'RIFF','.docx':b'PK\x03\x04'}[ext]
    if len(raw)>limit or not raw.startswith(magic) or (ext=='.webp' and raw[8:12]!=b'WEBP'):raise ValidationError({'file':'文件内容与扩展名不一致，请选择真实PDF/DOCX文件。'})
    try:
        result=subprocess.run([sys.executable,'-m','apps.assets.inspect_file','avatar' if purpose in ('avatar','image') else 'docx' if ext=='.docx' else 'proof'],input=raw,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=8,env={'PATH':os.defpath,'PYTHONPATH':str(settings.BASE_DIR),'PYTHONDONTWRITEBYTECODE':'1'})
    except (OSError,subprocess.TimeoutExpired):raise ValidationError({'file':'文件校验失败或超时，请重新导出较小的标准文件后上传。'}) from None
    if result.returncode or not result.stdout or len(result.stdout)>limit:
        import json
        try:message=json.loads(result.stderr[:1000]).get('message')
        except (ValueError,TypeError):message=None
        raise ValidationError({'file':message or '文件解析失败或超过限制，请重新导出PDF/DOCX后上传。'})
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
    asset=AssetFile.objects.filter(pk=pk,scan_status='CLEAN',deletion_requested_at__isnull=True).first()
    if not asset or (asset.expires_at and asset.expires_at<=timezone.now()):raise NotFound()
    if asset.owner_id!=actor.pk and asset.purpose=='resume' and not actor.is_superuser:raise NotFound()
    if asset.owner_id!=actor.pk and not actor.is_superuser:
        from apps.workflow.permissions import visible_items
        from django.db.models import F
        content_reference=asset.purpose in ('image','attachment') and asset.revisionasset_set.filter(revision__item__in=visible_items(actor),revision_id=F('revision__item__published_revision_id'),revision__item__visibility_gate=True,revision__item__archived_at__isnull=True).exists()
        if not content_reference:
            if not is_manager(actor):raise NotFound()
            # Current business avatar access only; retired review status grants no access.
            from apps.members.models import MemberProfile
            candidates=MemberProfile.objects.filter(published_revision__avatar_asset=asset,merged_into__isnull=True,user__is_active=True,user__role__in=['TEACHER','STUDENT'],user__is_superuser=False)
            if not (asset.purpose=='avatar' and candidates.exists()):raise NotFound()
    root=Path(settings.PRIVATE_MEDIA_ROOT).resolve();original=root/asset.storage_key
    if original.is_symlink():raise NotFound()
    path=original.resolve()
    if path.parent!=root or not path.is_file() or path.is_symlink():raise NotFound()
    return asset,path
