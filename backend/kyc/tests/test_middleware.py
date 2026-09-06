"""Domain-focused tests: middleware."""
from django.test import TestCase

class RequestIDMiddlewareTests(TestCase):
    def test_malicious_request_id_is_replaced(self):
        res = self.client.get("/healthz", HTTP_X_REQUEST_ID="evil\ninjected: yes")
        self.assertRegex(res.headers["X-Request-ID"], r"^[0-9a-f]{32}$")

    def test_oversized_request_id_is_replaced(self):
        res = self.client.get("/healthz", HTTP_X_REQUEST_ID="x" * 65)
        self.assertRegex(res.headers["X-Request-ID"], r"^[0-9a-f]{32}$")

    def test_valid_request_id_is_preserved(self):
        res = self.client.get("/healthz", HTTP_X_REQUEST_ID="req-123.abc_XYZ")
        self.assertEqual(res.headers["X-Request-ID"], "req-123.abc_XYZ")
