from django.db import DatabaseError, InterfaceError, connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    http_method_names = ["get"]

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                if cursor.fetchone() != (1,):
                    raise DatabaseError("Unexpected health query result")
        except (DatabaseError, InterfaceError):
            return Response(
                {"status": "degraded", "backend": "running", "database": "unavailable"},
                status=503,
                headers={"Cache-Control": "no-store"},
            )
        return Response(
            {"status": "ok", "backend": "running", "database": "connected"},
            headers={"Cache-Control": "no-store"},
        )

class ReadinessView(HealthView):
    def get(self,request):
        response=super().get(request)
        if response.status_code!=200:return response
        from django.conf import settings
        import os
        from pathlib import Path
        root=Path(settings.PRIVATE_MEDIA_ROOT)
        if not root.is_dir() or not os.access(root,os.R_OK|os.W_OK):
            return Response({'status':'degraded','storage':'unavailable'},status=503,headers={'Cache-Control':'no-store'})
        return Response({'status':'ready','database':'connected','storage':'available'},headers={'Cache-Control':'no-store'})
