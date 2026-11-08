from django.http import HttpResponse
from rest_framework.response import Response
from rest_framework.parsers import JSONParser,MultiPartParser,FormParser
from rest_framework.exceptions import ValidationError
from apps.workflow.api import BusinessAPIView
from . import batch_services as service


class BatchView(BusinessAPIView):
 def initial(self,request,*args,**kwargs):
  super().initial(request,*args,**kwargs);service.eligible(request.user)


class Template(BatchView):
 def get(self,request):
  from .batch_excel import template
  response=HttpResponse(template(),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');response['Content-Disposition']='attachment; filename="research-content-template.xlsx"';return response


class Batches(BatchView):
 parser_classes=[JSONParser,MultiPartParser,FormParser]
 def get(self,request):
  from .public_views import paged
  return paged(request,service.ContentImportBatch.objects.filter(owner=request.user).order_by('-created_at'),lambda b:{'id':str(b.pk),'source':b.source,'state':b.state,'created_at':b.created_at})
 def post(self,request):
  from apps.accounts.throttling import consume
  consume('content_import',str(request.user.pk),20)
  if 'file' in request.FILES:
   if set(request.data)!={'file'}:raise ValidationError('仅上传模板文件。')
   batch=service.create_template(request,request.FILES['file'])
  else:
   if set(request.data)!={'asset','source'} or request.data['source']!='AI':raise ValidationError('请选择模板或AI原件。')
   from uuid import UUID
   try:aid=UUID(str(request.data['asset']))
   except ValueError:raise ValidationError('原件标识无效。')
   batch=service.create_ai(request,aid)
  return Response(service.serialize(batch),status=201)


class Item(BatchView):
 def get(self,request,pk):
  from .batch_tasks import cleanup
  cleanup();return Response(service.serialize(service.owned(request.user,pk)))
 def patch(self,request,pk):
  if set(request.data)!={'lock_version','records'}:raise ValidationError('仅允许更新候选卡片。')
  return Response(service.serialize(service.edit(request,pk,request.data)))


class Consent(BatchView):
 def post(self,request,pk):
  if set(request.data)!={'lock_version','selected_text','text_digest','confirm'}:raise ValidationError('授权字段无效。')
  return Response(service.serialize(service.consent(request,pk,request.data)))


class Confirm(BatchView):
 def post(self,request,pk):
  if set(request.data)!={'lock_version','confirm'}:raise ValidationError('确认字段无效。')
  return Response(service.serialize(service.confirm(request,pk,request.data)),status=202)


class Cancel(BatchView):
 def post(self,request,pk):return Response(service.serialize(service.cancel(request,pk)))
