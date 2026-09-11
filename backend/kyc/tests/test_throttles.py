"""Domain-focused tests: throttles."""

from contextlib import ExitStack
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import DatabaseError
from rest_framework import status
from rest_framework.test import APITestCase

from kyc.tests.utils import FAST_PASSWORD_HASHERS, make_user

User = get_user_model()


@FAST_PASSWORD_HASHERS
class ThrottleFailureTests(APITestCase):
    """Auth throttles must fail CLOSED when the cache cannot be written."""

    def setUp(self):
        cache.clear()

    def _simulate_cache_outage(self) -> ExitStack:

        stack = ExitStack()
        stack.enter_context(mock.patch("kyc.common.throttles.cache.add", return_value=False))
        stack.enter_context(
            mock.patch("kyc.common.throttles.cache.incr", side_effect=DatabaseError("cache down"))
        )
        return stack

    def test_login_denied_when_cache_write_fails(self):
        make_user("throttle@kyc.local", User.Role.APPLICANT)
        with self._simulate_cache_outage():
            res = self.client.post(
                "/api/auth/token/",
                {"email": "throttle@kyc.local", "password": "Passw0rd!"},
            )

        self.assertEqual(res.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_otp_request_denied_when_cache_write_fails(self):
        with self._simulate_cache_outage():
            res = self.client.post(
                "/api/auth/password-reset/request/", {"email": "ghost@kyc.local"}
            )
        self.assertEqual(res.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


@FAST_PASSWORD_HASHERS
class ThrottleKeyLengthTests(APITestCase):
    """Throttle cache keys must never exceed the cache table's varchar(255).

    Regression for the long-email lockout: a max-length email (254 chars) plus
    an IPv6 ident used to produce keys > 255 chars, whose insert failed with a
    DataError the fail-closed throttle turned into a permanent 429.
    """

    def test_key_builder_bounded_for_worst_case_input(self):
        from kyc.common.throttles import credential_throttle_key

        email = "a" * 242 + "@example.com"  # 254 chars, accepted by EmailField
        ident = "2001:0db8:85a3:0000:0000:8a2e:0370:7334"  # 39 chars IPv6
        key = credential_throttle_key("login-throttle", email, ident)
        self.assertLessEqual(len(key), 255)
        self.assertIn("login-throttle", key)
        self.assertIn(ident, key)

    def test_same_email_maps_to_same_key(self):
        from kyc.common.throttles import credential_throttle_key

        email = "LongLocalPart" * 18 + "@example.com"
        self.assertEqual(
            credential_throttle_key("login-throttle", email, "1.2.3.4"),
            credential_throttle_key("login-throttle", email, "1.2.3.4"),
        )
        self.assertNotEqual(
            credential_throttle_key("login-throttle", email, "1.2.3.4"),
            credential_throttle_key("login-throttle", "other@example.com", "1.2.3.4"),
        )

    def test_long_email_login_is_not_locked_out(self):
        """A max-length email + IPv6 client gets 401, not a 500 or 429 lockout."""
        long_email = "user" * 50 + "@example.com"  # 204 chars
        self.client.post(
            "/api/auth/token/",
            {"email": long_email, "password": "Whatever1!"},
            REMOTE_ADDR="2001:db8::1",
        )
        res = self.client.post(
            "/api/auth/token/",
            {"email": long_email, "password": "Whatever1!"},
            REMOTE_ADDR="2001:db8::1",
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


@FAST_PASSWORD_HASHERS
class OTPPerIPThrottleTests(APITestCase):
    """Rotating victim emails must not evade the per-(email + IP) OTP cap."""

    def setUp(self):
        cache.clear()

    def test_otp_requests_bounded_per_ip(self):
        """OTP requests stay bounded per IP across many victim emails."""
        for i in range(20):
            res = self.client.post(
                "/api/auth/password-reset/request/",
                {"email": f"victim{i}@kyc.local"},
            )
            self.assertEqual(res.status_code, status.HTTP_200_OK)
        res = self.client.post("/api/auth/password-reset/request/", {"email": "victim20@kyc.local"})
        self.assertEqual(res.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
