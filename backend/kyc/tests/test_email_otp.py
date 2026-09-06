"""Domain-focused tests: email otp."""
import threading
from datetime import timedelta
from unittest import mock
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from kyc.models import EmailOTP

from kyc.tests.utils import FAST_PASSWORD_HASHERS, last_otp_code, make_user, register_payload, verify_via_api

User = get_user_model()

@FAST_PASSWORD_HASHERS
class EmailOTPTests(APITestCase):
    """Signup verification + password reset OTP flows."""

    def setUp(self):
        cache.clear()

    def register(self, email="otp@kyc.local", phone="+919876500001"):
        res = self.client.post("/api/auth/register/", register_payload(email, phone=phone))
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        return res

    def test_registration_sends_verification_email(self):
        self.register()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("verification code", mail.outbox[0].body)
        self.assertFalse(User.objects.get(email="otp@kyc.local").email_verified)

    def test_verify_email_unlocks_login(self):
        self.register()
        res = self.client.post(
            "/api/auth/verify-email/", {"email": "otp@kyc.local", "code": last_otp_code()}
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(User.objects.get(email="otp@kyc.local").email_verified)

    def test_verify_email_rejects_wrong_or_expired_code(self):
        self.register()
        code = last_otp_code()
        wrong = ("0" if code[0] != "0" else "1") * 6
        res = self.client.post(
            "/api/auth/verify-email/", {"email": "otp@kyc.local", "code": wrong}
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        self.register("otp2@kyc.local", phone="+919876500002")
        code = last_otp_code()

        EmailOTP.objects.filter(user__email="otp2@kyc.local").update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        res = self.client.post(
            "/api/auth/verify-email/", {"email": "otp2@kyc.local", "code": code}
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_otp_is_single_use_and_predecessor_invalidated(self):
        self.register()
        first_code = last_otp_code()

        EmailOTP.objects.filter(user__email="otp@kyc.local").update(last_sent_at=None)
        self.client.post("/api/auth/verify-email/resend/", {"email": "otp@kyc.local"})
        second_code = last_otp_code()

        res = self.client.post(
            "/api/auth/verify-email/", {"email": "otp@kyc.local", "code": first_code}
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        res = self.client.post(
            "/api/auth/verify-email/", {"email": "otp@kyc.local", "code": second_code}
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        res = self.client.post(
            "/api/auth/verify-email/", {"email": "otp@kyc.local", "code": second_code}
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_attempt_cap_invalidates_otp(self):
        self.register()
        code = last_otp_code()
        wrong = ("0" if code[0] != "0" else "1") * 6
        for _ in range(5):
            self.client.post(
                "/api/auth/verify-email/", {"email": "otp@kyc.local", "code": wrong}
            )

        res = self.client.post(
            "/api/auth/verify-email/", {"email": "otp@kyc.local", "code": code}
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resend_is_enumeration_safe_and_cooldown_enforced(self):

        res = self.client.post("/api/auth/verify-email/resend/", {"email": "ghost@kyc.local"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 0)

        self.register()
        self.assertEqual(len(mail.outbox), 1)

        res = self.client.post("/api/auth/verify-email/resend/", {"email": "otp@kyc.local"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_skips_already_verified_users(self):
        self.register()
        verify_via_api(self.client, "otp@kyc.local")
        sent = len(mail.outbox)
        self.client.post("/api/auth/verify-email/resend/", {"email": "otp@kyc.local"})
        self.assertEqual(len(mail.outbox), sent)

    def test_password_reset_flow(self):
        user = make_user("reset@kyc.local", User.Role.APPLICANT)
        res = self.client.post(
            "/api/auth/password-reset/request/", {"email": "reset@kyc.local"}
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

        res = self.client.post(
            "/api/auth/password-reset/confirm/",
            {
                "email": "reset@kyc.local",
                "code": last_otp_code(),
                "new_password": "N3wSecret!",
            },
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.check_password("N3wSecret!"))

        res = self.client.post(
            "/api/auth/token/", {"email": "reset@kyc.local", "password": "N3wSecret!"}
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_password_reset_request_is_enumeration_safe(self):
        res = self.client.post(
            "/api/auth/password-reset/request/", {"email": "ghost@kyc.local"}
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_confirm_rejects_bad_code_and_weak_password(self):
        make_user("reset2@kyc.local", User.Role.APPLICANT)
        self.client.post("/api/auth/password-reset/request/", {"email": "reset2@kyc.local"})
        res = self.client.post(
            "/api/auth/password-reset/confirm/",
            {"email": "reset2@kyc.local", "code": "123456", "new_password": "N3wSecret!"},
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        res = self.client.post(
            "/api/auth/password-reset/confirm/",
            {"email": "reset2@kyc.local", "code": last_otp_code(), "new_password": "12345678"},
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("new_password", res.data)

    def test_password_reset_verifies_email_and_unblocks_login(self):
        """An unverified signup whose only recovery path is the reset flow:."""
        self.register()
        self.client.post("/api/auth/password-reset/request/", {"email": "otp@kyc.local"})
        res = self.client.post(
            "/api/auth/password-reset/confirm/",
            {"email": "otp@kyc.local", "code": last_otp_code(), "new_password": "N3wSecret!"},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        user = User.objects.get(email="otp@kyc.local")
        self.assertTrue(user.email_verified)
        res = self.client.post(
            "/api/auth/token/", {"email": "otp@kyc.local", "password": "N3wSecret!"}
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_password_reset_works_for_google_only_accounts(self):
        """Google users have no password; the reset flow lets them set one."""
        user = User.objects.create_user(
            email="google-only@kyc.local",
            username="PHIN-GOOGLE01",
            password=None,
            role=User.Role.APPLICANT,
            email_verified=True,
        )
        self.client.post(
            "/api/auth/password-reset/request/", {"email": "google-only@kyc.local"}
        )
        res = self.client.post(
            "/api/auth/password-reset/confirm/",
            {
                "email": "google-only@kyc.local",
                "code": last_otp_code(),
                "new_password": "N3wSecret!",
            },
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.check_password("N3wSecret!"))

    @mock.patch("kyc.common.throttles.OTPRequestThrottle.allow_request", return_value=False)
    def test_otp_request_throttle_returns_429(self, _mock):
        res = self.client.post(
            "/api/auth/password-reset/request/", {"email": "otp@kyc.local"}
        )
        self.assertEqual(res.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    @mock.patch("kyc.views.auth.issue_otp", side_effect=RuntimeError("smtp down"))
    def test_register_survives_email_send_failure(self, _mock):
        """An email outage must not turn signup into a 500: the account is."""
        res = self.client.post(
            "/api/auth/register/", register_payload("outage@kyc.local")
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="outage@kyc.local")
        self.assertFalse(user.email_verified)

        res = self.client.post(
            "/api/auth/token/",
            {"email": "outage@kyc.local", "password": "Str0ngPass!"},
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    @mock.patch("kyc.views.auth.request_otp", side_effect=RuntimeError("smtp down"))
    def test_resend_and_reset_request_survive_email_send_failure(self, _mock):
        """Send failures keep the generic 200 (enumeration safety) instead of."""
        self.register()
        res = self.client.post(
            "/api/auth/verify-email/resend/", {"email": "otp@kyc.local"}
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        res = self.client.post(
            "/api/auth/password-reset/request/", {"email": "otp@kyc.local"}
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)


@FAST_PASSWORD_HASHERS
@skipUnlessDBFeature("has_select_for_update")
class OTPResendConcurrencyTests(TransactionTestCase):
    """Concurrent resend requests must not double-send (needs real row locks)."""

    def test_concurrent_resends_send_one_email(self):
        client = APIClient()
        res = client.post(
            "/api/auth/register/", register_payload("race@kyc.local")
        )
        assert res.status_code == 201, res.content

        EmailOTP.objects.filter(user__email="race@kyc.local").update(last_sent_at=None)
        sent_before = len(mail.outbox)

        barrier = threading.Barrier(2)

        def resend():
            barrier.wait()
            client.post("/api/auth/verify-email/resend/", {"email": "race@kyc.local"})

        threads = [threading.Thread(target=resend) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(mail.outbox), sent_before + 1)

        self.assertEqual(
            EmailOTP.objects.filter(
                user__email="race@kyc.local", consumed_at__isnull=True
            ).count(),
            1,
        )
