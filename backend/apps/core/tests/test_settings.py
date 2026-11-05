import json
import os
from pathlib import Path
import subprocess
import sys

from django.test import SimpleTestCase


class SettingsTests(SimpleTestCase):
    def load_settings(self, changes):
        env = os.environ.copy()
        env.update(changes)
        return subprocess.run(
            [sys.executable, "-c", (
                "import json; from config import settings as s; "
                "print(json.dumps({'debug': s.DEBUG, 'engine': s.DATABASES['default']['ENGINE']}))"
            )],
            cwd=Path(__file__).resolve().parents[3],
            env=env, capture_output=True, text=True, timeout=10,
        )

    def test_false_is_parsed_and_database_is_postgresql(self):
        result = self.load_settings({"DJANGO_DEBUG": "False"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            "debug": False, "engine": "django.db.backends.postgresql",
        })

    def test_missing_secrets_fail_startup_without_leaking_values(self):
        for key in ("DJANGO_SECRET_KEY", "POSTGRES_PASSWORD"):
            with self.subTest(key=key):
                result = self.load_settings({key: ""})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(key, result.stderr)
                self.assertNotIn(os.environ["POSTGRES_PASSWORD"], result.stderr)
