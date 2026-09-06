"""Domain-focused tests: cache."""
import time
from allauth.socialaccount.providers.oauth2.client import OAuth2Error
from django.core.cache import cache
from django.test import TestCase

class LightweightCacheTests(TestCase):
    """Regression tests for kyc.common.cache.LightweightDatabaseCache."""

    def setUp(self):
        cache.clear()

    def test_add_is_set_if_absent(self):
        self.assertTrue(cache.add("k", "v1", timeout=60))
        self.assertFalse(cache.add("k", "v2", timeout=60))
        self.assertEqual(cache.get("k"), "v1")

    def test_add_after_expiry_succeeds(self):
        self.assertTrue(cache.add("k", "v1", timeout=1))
        time.sleep(1.1)
        self.assertTrue(cache.add("k", "v2", timeout=60))
        self.assertEqual(cache.get("k"), "v2")

    def test_touch_updates_expiry(self):
        cache.set("k", "v", timeout=60)
        self.assertTrue(cache.touch("k", timeout=120))
        self.assertFalse(cache.touch("missing", timeout=120))

    def test_incr_is_atomic_integer_counter(self):
        self.assertTrue(cache.add("n", 0, timeout=60))
        self.assertEqual(cache.incr("n"), 1)
        self.assertEqual(cache.incr("n", 4), 5)
        self.assertEqual(cache.get("n"), 5)

    def test_incr_missing_or_non_integer_raises(self):
        with self.assertRaises(ValueError):
            cache.incr("missing")
        cache.set("s", "not-an-int", timeout=60)
        with self.assertRaises(ValueError):
            cache.incr("s")

    def test_jti_replay_guard(self):
        """The real allauth replay check must accept a first use and reject a."""
        from allauth.socialaccount.internal import jwtkit

        claims = {
            "iss": "https://accounts.google.com",
            "exp": int(time.time()) + 300,
            "jti": "replay-guard-jti",
        }
        jwtkit.verify_jti(claims)
        with self.assertRaises(OAuth2Error):
            jwtkit.verify_jti(claims)
