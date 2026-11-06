from django.test import SimpleTestCase,override_settings
from rest_framework.exceptions import ValidationError
from unittest.mock import patch,MagicMock
from apps.assets.scanner import check_bytes
class ScannerTests(SimpleTestCase):
 @override_settings(FILE_SCAN_REQUIRED=False)
 def test_optional_mode_does_not_claim_antivirus(self):self.assertEqual(check_bytes(b'example'),'structural_only')
 @override_settings(FILE_SCAN_REQUIRED=True,CLAMAV_SOCKET='/nonexistent/clamd.sock')
 def test_required_scanner_unavailable_fails_closed(self):
  with self.assertRaises(ValidationError):check_bytes(b'example')
 @override_settings(FILE_SCAN_REQUIRED=True,CLAMAV_SOCKET='/run/clamd.sock')
 def test_detected_file_rejected(self):
  with patch('apps.assets.scanner.socket.socket') as factory:
   connection=factory.return_value.__enter__.return_value;connection.recv.return_value=b'stream: Eicar-Test-Signature FOUND\0'
   with self.assertRaises(ValidationError):check_bytes(b'test-fixture')
