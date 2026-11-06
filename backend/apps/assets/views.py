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
        if set(request.data)-{'file','purpose'} or request.data.get('purpose') not in ('avatar','proof') or 'file' not in request.FILES:
            raise ValidationError({'detail':'Expected a file and avatar/proof purpose only.'})
        asset=services.upload(request,request.FILES['file'],request.data['purpose'])
        return Response({'id':str(asset.pk),'mime_type':asset.mime_type,'size':asset.size,'visibility':'PRIVATE','expires_at':asset.expires_at,'download_url':f'/api/assets/{asset.pk}/download/'},status=201)


class DownloadView(AccountAPIView):
    http_method_names=['get']
    def get(self,request,pk):
        asset,path=services.permitted_asset(request.user,pk)
        response=FileResponse(path.open('rb'),as_attachment=True,filename='document.pdf' if asset.mime_type=='application/pdf' else 'avatar.png',content_type=asset.mime_type)
        response['X-Content-Type-Options']='nosniff';response['Cache-Control']='no-store'
        return response
