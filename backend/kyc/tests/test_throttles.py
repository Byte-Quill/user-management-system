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
        stack.enter_context(
            mock.patch("kyc.common.throttles.cache.add", return_value=False)
        )
        stack.enter_context(
            mock.patch(
                "kyc.common.throttles.cache.incr", side_effect=DatabaseError("cache down")
            )
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
        res = self.client.post(
            "/api/auth/password-reset/request/", {"email": "victim20@kyc.local"}
        )
        self.assertEqual(res.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
