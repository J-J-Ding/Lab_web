from apps.workflow.api import BusinessAPIView as AccountAPIView
from django.http import FileResponse
from rest_framework.parsers import MultiPartParser,FormParser
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from . import services


class UploadView(AccountAPIView):
    parser_classes=[MultiPartParser,FormParser]
    http_method_names=['post']
    def post(self,request):
        from apps.accounts.throttling import consume
        consume('asset_user', str(request.user.pk), 20)
        if set(request.data)-{'file','purpose'} or request.data.get('purpose') not in ('avatar','proof','image','attachment','ai_source','resume') or 'file' not in request.FILES:
            raise ValidationError({'detail':'Expected a file and supported purpose only.'})
        asset=services.upload(request,request.FILES['file'],request.data['purpose'])
        return Response({'id':str(asset.pk),'mime_type':asset.mime_type,'size':asset.size,'visibility':'PRIVATE','expires_at':asset.expires_at,'download_url':f'/api/assets/{asset.pk}/download/'},status=201)


class DownloadView(AccountAPIView):
    http_method_names=['get']
    def get(self,request,pk):
        asset,path=services.permitted_asset(request.user,pk)
        response=FileResponse(path.open('rb'),as_attachment=True,filename='document.docx' if asset.mime_type.endswith('document') else 'document.pdf' if asset.mime_type=='application/pdf' else 'image.png',content_type=asset.mime_type)
        response['X-Content-Type-Options']='nosniff';response['Cache-Control']='no-store'
        return response


class DeleteView(AccountAPIView):
    http_method_names=['post']
    def post(self,request,pk):
        from django.db import transaction
        from django.utils import timezone
        from django.shortcuts import get_object_or_404
        from .models import AssetFile
        from apps.workflow.permissions import actor_for
        from apps.workflow.audit import record
        with transaction.atomic():
            actor=actor_for(request)
            asset=get_object_or_404(AssetFile.objects.select_for_update(),pk=pk,owner=actor)
            asset.deletion_requested_at=timezone.now()
            asset.save(update_fields=['deletion_requested_at'])
            record(actor,asset,'asset.delete.request',('deletion_requested_at',))
        return Response({'detail':'Deletion requested. Referenced files are retained.'})
