from pathlib import Path
from django.conf import settings
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q,F
from apps.content.public_views import PublicView
from apps.content.public_selectors import content_queryset,member_queryset
from rest_framework.exceptions import NotFound
from .models import AssetFile


class PublicAsset(PublicView):
    def get(self,request,pk):
        asset=get_object_or_404(AssetFile,pk=pk,scan_status='CLEAN',deletion_requested_at__isnull=True,purpose__in=['avatar','image','attachment'])
        if asset.expires_at and asset.expires_at<=timezone.now():raise NotFound()
        member=member_queryset().filter(published_revision__avatar_asset=asset).exists()
        content=content_queryset().filter(published_revision__assets__asset=asset).exists() if asset.purpose in ('image','attachment') else False
        if not member and not content:raise NotFound()
        root=Path(settings.PRIVATE_MEDIA_ROOT).resolve();source=root/asset.storage_key
        if source.is_symlink():raise NotFound()
        path=source.resolve()
        if path.parent!=root or not path.is_file():raise NotFound()
        extension='png' if asset.mime_type.startswith('image/') else 'pdf' if asset.mime_type=='application/pdf' else 'docx'
        response=FileResponse(path.open('rb'),as_attachment=extension!='png',filename='document.'+extension,content_type=asset.mime_type)
        response['Content-Security-Policy']="default-src 'none'; sandbox"
        return response
