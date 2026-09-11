"""Domain-focused tests: analytics."""

from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from kyc.models import EmailLog, EmailOTP, KYCApplication
from kyc.services.otp import issue_otp
from kyc.tests.utils import APP_PAYLOAD, FAST_PASSWORD_HASHERS, make_user, register_payload

User = get_user_model()


@FAST_PASSWORD_HASHERS
class AnalyticsTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.ceo = make_user("ceo@kyc.local", User.Role.CEO)
        self.applicant = make_user("app@kyc.local", User.Role.APPLICANT)
        res = self.client.post(
            "/api/auth/token/", {"email": self.ceo.email, "password": "Passw0rd!"}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    def make_app(self, status_value):
        app = KYCApplication.objects.create(
            applicant=self.applicant,
            status=status_value,
            **{k: v for k, v in APP_PAYLOAD.items() if k != "address_line2"},
        )
        # Anything past DRAFT must have been submitted to get there, so
        # backfill submitted_at: the 30-day submission KPI (computed on
        # submitted_at, not created_at) would otherwise ignore these apps.
        if status_value != KYCApplication.Status.DRAFT:
            KYCApplication.objects.filter(pk=app.pk).update(submitted_at=timezone.now())
            app.refresh_from_db()
        return app

    def test_payload_shape_and_approval_rate(self):
        self.make_app(KYCApplication.Status.APPROVED)
        self.make_app(KYCApplication.Status.APPROVED)
        self.make_app(KYCApplication.Status.APPROVED)
        self.make_app(KYCApplication.Status.REJECTED)
        self.make_app(KYCApplication.Status.SUBMITTED)
        EmailLog.objects.create(
            user=self.applicant,
            purpose=EmailLog.Purpose.VERIFY_EMAIL,
            recipient=self.applicant.email,
            subject="Verify",
            status=EmailLog.Status.SENT,
        )
        EmailLog.objects.create(
            user=self.applicant,
            purpose=EmailLog.Purpose.RESET_PASSWORD,
            recipient=self.applicant.email,
            subject="Reset",
            status=EmailLog.Status.FAILED,
        )

        res = self.client.get("/api/analytics/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["kpis"]["total_applications"], 5)
        self.assertEqual(res.data["kpis"]["submitted_last_30_days"], 5)
        self.assertEqual(res.data["kpis"]["users"], 2)
        self.assertEqual(res.data["kpis"]["pending_review"], 1)
        self.assertEqual(res.data["approval_rate"], 75.0)
        self.assertEqual(res.data["pipeline"]["approved"], 3)
        self.assertEqual(res.data["pipeline"]["draft"], 0)
        self.assertEqual(set(res.data["pipeline"]), set(KYCApplication.Status.values))
        emails = res.data["email_activity"]
        self.assertEqual(emails["sent_last_30_days"], 1)
        self.assertEqual(emails["failed_last_30_days"], 1)
        self.assertEqual(len(emails["recent"]), 2)

    def test_approval_rate_is_none_without_decisions(self):
        self.make_app(KYCApplication.Status.SUBMITTED)
        res = self.client.get("/api/analytics/")
        self.assertIsNone(res.data["approval_rate"])
        self.assertEqual(res.data["kpis"]["total_applications"], 1)

    def test_submitted_kpi_counts_submissions_not_creations(self):
        """The 30-day KPI is on submitted_at, not created_at (GH issue 32)."""
        # Submitted yesterday, but created 40 days ago: counts.
        submitted_old = self.make_app(KYCApplication.Status.SUBMITTED)
        KYCApplication.objects.filter(pk=submitted_old.pk).update(
            created_at=timezone.now() - timedelta(days=40),
            submitted_at=timezone.now() - timedelta(days=1),
        )
        # Draft created today, never submitted: does not count.
        self.make_app(KYCApplication.Status.DRAFT)
        # Submitted long ago but created today: does not count.
        submitted_long_ago = self.make_app(KYCApplication.Status.SUBMITTED)
        KYCApplication.objects.filter(pk=submitted_long_ago.pk).update(
            submitted_at=timezone.now() - timedelta(days=40)
        )

        res = self.client.get("/api/analytics/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["kpis"]["submitted_last_30_days"], 1)


@FAST_PASSWORD_HASHERS
class EmailLogTests(APITestCase):
    def test_registration_verification_email_is_logged(self):
        res = self.client.post("/api/auth/register/", register_payload("logme@kyc.local"))
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.content)
        log = EmailLog.objects.get()
        self.assertEqual(log.purpose, EmailLog.Purpose.VERIFY_EMAIL)
        self.assertEqual(log.status, EmailLog.Status.SENT)
        self.assertEqual(log.recipient, "logme@kyc.local")

    def test_send_failure_is_logged_as_failed(self):
        user = make_user("boom@kyc.local", User.Role.APPLICANT)
        with mock.patch("kyc.services.otp.send_mail", side_effect=RuntimeError("smtp down")):
            with self.assertRaises(RuntimeError):
                issue_otp(user, EmailOTP.Purpose.RESET_PASSWORD)
        log = EmailLog.objects.get()
        self.assertEqual(log.status, EmailLog.Status.FAILED)
        self.assertEqual(log.purpose, EmailLog.Purpose.RESET_PASSWORD)
