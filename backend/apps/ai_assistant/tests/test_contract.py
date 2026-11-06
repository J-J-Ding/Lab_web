from django.test import override_settings
from django.utils import timezone
from apps.accounts.tests.helpers import AccountFixtures,login_as,write

class AIContractTests(AccountFixtures):
    def test_quota_safe_and_disabled_rejects_creation(self):
        c=login_as(self.customer);r=c.get('/api/ai/quota/')
        self.assertEqual(r.status_code,200,r.content);self.assertFalse(r.json()['enabled'])
        self.assertNotIn('key',r.json());self.assertNotIn('DEEPSEEK',str(r.json()))
        r=write(c,'post','/api/ai/imports/',{'asset':'00000000-0000-0000-0000-000000000000','target_type':'MEMBER','consent_version':'local-v1'})
        self.assertEqual(r.status_code,503,r.content)
    def test_anonymous_and_csrf_enforced(self):
        self.assertEqual(self.client.get('/api/ai/imports/').status_code,403)
        c=login_as(self.customer)
        self.assertEqual(c.post('/api/ai/imports/',{},format='json').status_code,403)
