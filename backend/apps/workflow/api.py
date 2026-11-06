import uuid
from django.db import DatabaseError
from django.http import Http404
from rest_framework.exceptions import ValidationError,PermissionDenied,NotFound
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.accounts.views import AccountAPIView
from .models import BusinessAuditLog


class BusinessAPIView(AccountAPIView):
    """V5 errors/audits use UUID business targets, never V2's integer account path."""
    def handle_exception(self,exc):
        try:
            target=self.kwargs.get('pk')
            if isinstance(target,uuid.UUID) and self.request.method!='GET' and self.request.user.is_authenticated and isinstance(exc,(PermissionDenied,NotFound,Http404)):
                BusinessAuditLog.objects.create(actor=self.request.user,actor_snapshot=self.request.user.pk,target_id=target,action='business.denied',outcome='denied')
            response=Response({'detail':'Service temporarily unavailable.'},status=503) if isinstance(exc,DatabaseError) else APIView.handle_exception(self,exc)
        except DatabaseError:
            response=Response({'detail':'Service temporarily unavailable.'},status=503)
        if response.status_code>=400:
            original=response.data
            fields=original if isinstance(exc,ValidationError) and isinstance(original,dict) else {}
            detail=original.get('detail') if isinstance(original,dict) else None
            response.data={'code':'service_unavailable' if response.status_code==503 else getattr(exc,'default_code','request_failed'),
                           'detail':str(detail) if detail is not None else '输入信息有误，请检查字段。','fields':fields}
        return response
