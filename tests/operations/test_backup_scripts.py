"""Backup guards must reject unsafe requests before touching Docker."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import json,unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('lab_backup',Path(__file__).resolve().parents[2]/'deploy/scripts/backup_restore.py')
backup=importlib.util.module_from_spec(spec);spec.loader.exec_module(backup)

class BackupGuardTests(unittest.TestCase):
 def test_production_target_rejected_without_any_command(self):
  with patch.object(backup,'run') as mutate,patch.object(backup,'output') as query:
   with self.assertRaises(SystemExit):backup.restore('/missing','lab-web')
   mutate.assert_not_called();query.assert_not_called()
 def test_existing_resources_rejected_without_cleanup(self):
  with patch.object(backup,'output',return_value='already-owned'),patch.object(backup,'run') as mutate:
   with self.assertRaises(SystemExit):backup.restore('/missing','lab-web-restore-example')
   mutate.assert_not_called()
 def test_existing_backup_never_overwritten(self):
  with TemporaryDirectory() as root,patch.object(backup,'run') as mutate:
   with self.assertRaises(SystemExit):backup.backup(root)
   mutate.assert_not_called()
 def test_corrupt_backup_rejected_before_container_creation(self):
  with TemporaryDirectory() as root,patch.object(backup,'output',return_value=''),patch.object(backup,'run') as mutate:
   p=Path(root);(p/'COMPLETE').write_text('complete');(p/'database.dump').write_bytes(b'corrupt');(p/'media.tar').write_bytes(b'corrupt')
   (p/'manifest.json').write_text(json.dumps({'files':{'database.dump':'0'*64,'media.tar':'0'*64}}))
   with self.assertRaises(AssertionError):backup.restore(root,'lab-web-restore-hash')
   mutate.assert_not_called()
 def test_incomplete_manifest_rejected_before_container_creation(self):
  with TemporaryDirectory() as root,patch.object(backup,'output',return_value=''),patch.object(backup,'run') as mutate:
   p=Path(root);(p/'COMPLETE').write_text('complete');(p/'manifest.json').write_text('{"files":{}}')
   with self.assertRaises(SystemExit):backup.restore(root,'lab-web-restore-incomplete')
   mutate.assert_not_called()
