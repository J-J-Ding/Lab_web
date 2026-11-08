import csv,io
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.parsers import MultiPartParser,FormParser
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from apps.workflow.api import BusinessAPIView
from .permissions import IsRoot
from .models import AccountImportBatch
from . import batch_imports


class RootImportView(BusinessAPIView):
    permission_classes=[IsRoot]


class Template(RootImportView):
    http_method_names=['get']
    def get(self,request):
        from .import_excel import template
        response=HttpResponse(template(),content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');response['Content-Disposition']='attachment; filename="account-import-template.xlsx"';response['Cache-Control']='no-store';return response


class Preview(RootImportView):
    http_method_names=['post']
    parser_classes=[MultiPartParser,FormParser]
    def post(self,request):
        if set(request.data)!={'file'} or 'file' not in request.FILES:raise ValidationError('请选择Excel文件。')
        from .throttling import consume
        consume('import_user',str(request.user.pk),10)
        batch_imports.cleanup()
        return Response(batch_imports.summary(batch_imports.preview(request,request.FILES['file'])),status=201)


class Batch(RootImportView):
    http_method_names=['get','post']
    def get(self,request,pk):
        batch_imports.cleanup()
        return Response(batch_imports.summary(get_object_or_404(AccountImportBatch,pk=pk,owner=request.user)))
    def post(self,request,pk):
        if request.data:raise ValidationError('确认请求不接受额外字段。')
        return Response(batch_imports.summary(batch_imports.confirm(request,pk)),status=202)


class Errors(RootImportView):
    http_method_names=['get']
    def get(self,request,pk):
        batch=get_object_or_404(AccountImportBatch,pk=pk,owner=request.user)
        output=io.StringIO();writer=csv.writer(output);writer.writerow(['Excel行号','用户名','错误'])
        for row in batch.errors:
            # CSV opened in Excel must not evaluate attacker-controlled usernames.
            name=row.get('username','');name="'"+name if name.startswith(('=','+','-','@','\t','\r')) else name
            writer.writerow([row.get('row',''),name,row['message']])
        response=HttpResponse('\ufeff'+output.getvalue(),content_type='text/csv; charset=utf-8');response['Content-Disposition']='attachment; filename="account-import-errors.csv"';response['Cache-Control']='no-store';return response
