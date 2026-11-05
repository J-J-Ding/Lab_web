from unittest.mock import patch

from django.db import InterfaceError, OperationalError
from django.test import TestCase
from rest_framework.test import APIClient


class HealthTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_anonymous_get_checks_database_each_time(self):
        for _ in range(2):
            with self.assertNumQueries(1):
                response = self.client.get("/api/health/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {
                "status": "ok", "backend": "running", "database": "connected",
            })
            self.assertNotIn("sessionid", response.cookies)

    def test_database_failure_returns_sanitized_503(self):
        # The only mocked dependency is database I/O; routing and response are real.
        for error in (OperationalError, InterfaceError):
            with self.subTest(error=error.__name__):
                with patch("django.db.connection.cursor", side_effect=error("private-db-password")):
                    response = self.client.get("/api/health/")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json(), {
                    "status": "degraded", "backend": "running", "database": "unavailable",
                })
                self.assertNotIn(b"private-db-password", response.content)

    def test_other_methods_are_not_allowed(self):
        for method in ("head", "options", "post", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)("/api/health/")
                self.assertEqual(response.status_code, 405)

    def test_no_admin_or_authentication_routes_are_exposed(self):
        for path in ("/admin/", "/api/login/", "/api/register/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)
