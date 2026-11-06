from django.test import TestCase,override_settings,RequestFactory
from django.http import HttpResponse
from apps.core.middleware import RequestContextMiddleware

class OperationsTests(TestCase):
    @override_settings(TRUSTED_PROXY_NETWORKS=[])
    def test_untrusted_forwarded_protocol_removed_and_request_id_generated(self):
        r=RequestFactory().get('/',HTTP_X_FORWARDED_PROTO='https',HTTP_X_LAB_CLIENT_IP='1.2.3.4',REMOTE_ADDR='8.8.8.8')
        response=RequestContextMiddleware(lambda req:HttpResponse(str(req.is_secure())))(r)
        self.assertEqual(response.content,b'False');self.assertEqual(len(response['X-Request-ID']),32);self.assertEqual(r.META['REMOTE_ADDR'],'8.8.8.8')
    @override_settings(TRUSTED_PROXY_NETWORKS=['127.0.0.0/8'])
    def test_trusted_proxy_accepts_single_valid_client_ip(self):
        r=RequestFactory().get('/',HTTP_X_LAB_CLIENT_IP='1.2.3.4',REMOTE_ADDR='127.0.0.1')
        RequestContextMiddleware(lambda req:HttpResponse())(r);self.assertEqual(r.META['REMOTE_ADDR'],'1.2.3.4')
    def test_readiness_reports_no_sensitive_details(self):
        response=self.client.get('/api/ready/');self.assertIn(response.status_code,(200,503));self.assertNotIn('PASSWORD',str(response.content));self.assertEqual(response['Cache-Control'],'no-store')
