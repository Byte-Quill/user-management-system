"""Security-contract tests for settings-derived configuration (issue #24)."""

from django.test import SimpleTestCase
from django.utils.csp import CSP

from config.settings import build_secure_csp


class SecureCspTests(SimpleTestCase):
    """Production CSP must allow Google Sign-In only when it is enabled."""

    def test_csp_allows_google_sources_when_configured(self):
        csp = build_secure_csp("test-client-id")
        self.assertIn("https://accounts.google.com", csp["script-src"])
        self.assertIn("https://accounts.google.com", csp["style-src"])
        self.assertIn("https://accounts.google.com", csp["connect-src"])
        self.assertEqual(csp["frame-src"], ["https://accounts.google.com"])

    def test_csp_stays_self_only_without_google_client_id(self):
        csp = build_secure_csp("")
        self.assertNotIn("https://accounts.google.com", csp["script-src"])
        self.assertNotIn("https://accounts.google.com", csp["style-src"])
        self.assertNotIn("https://accounts.google.com", csp["connect-src"])
        self.assertNotIn("frame-src", csp)

    def test_csp_keeps_existing_hardening_directives(self):
        csp = build_secure_csp("")
        self.assertEqual(csp["frame-ancestors"], [CSP.NONE])
        self.assertEqual(csp["base-uri"], [CSP.SELF])
        self.assertEqual(csp["form-action"], [CSP.SELF])
