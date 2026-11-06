import logging,time,uuid,ipaddress
from django.conf import settings
from django.http import JsonResponse
logger=logging.getLogger('lab.requests')
class RequestContextMiddleware:
    def __init__(self,get_response):self.get_response=get_response
    def __call__(self,request):
        request_id=uuid.uuid4().hex;request.request_id=request_id;start=time.monotonic()
        trusted=False
        try:trusted=any(ipaddress.ip_address(request.META.get('REMOTE_ADDR','')) in ipaddress.ip_network(n) for n in settings.TRUSTED_PROXY_NETWORKS)
        except ValueError:pass
        if trusted:
            real=request.META.get('HTTP_X_LAB_CLIENT_IP','')
            try:request.META['REMOTE_ADDR']=str(ipaddress.ip_address(real))
            except ValueError:pass
        # Never trust forwarded headers on an untrusted connection.
        if not trusted:
            request.META.pop('HTTP_X_FORWARDED_PROTO',None);request.META.pop('HTTP_X_LAB_CLIENT_IP',None)
        response=self.get_response(request);response['X-Request-ID']=request_id
        logger.info('request id=%s method=%s status=%s duration_ms=%.2f',request_id,request.method,response.status_code,(time.monotonic()-start)*1000)
        return response
