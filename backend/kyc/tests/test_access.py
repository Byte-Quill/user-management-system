"""Domain-focused tests: access."""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from kyc.models import KYCApplication

from kyc.tests.utils import APP_PAYLOAD, FAST_PASSWORD_HASHERS, make_user

User = get_user_model()

@FAST_PASSWORD_HASHERS
class RoleAccessTests(APITestCase):
    """Each role reaches only its own surface: review queue, user management,."""

    def setUp(self):
        cache.clear()
        self.applicant = make_user("app@kyc.local", User.Role.APPLICANT)
        self.admin = make_user("admin@kyc.local", User.Role.ADMIN)
        self.super_admin = make_user("super@kyc.local", User.Role.SUPER_ADMIN)
        self.ceo = make_user("ceo@kyc.local", User.Role.CEO)

    def auth(self, user):
        res = self.client.post(
            "/api/auth/token/", {"email": user.email, "password": "Passw0rd!"}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    def statuses(self, url):
        """(applicant, admin, super_admin, ceo) response codes for a GET."""
        codes = []
        for user in (self.applicant, self.admin, self.super_admin, self.ceo):
            self.auth(user)
            codes.append(self.client.get(url).status_code)
        return tuple(codes)

    def test_review_queue_is_admin_and_super_admin_only(self):
        self.assertEqual(
            self.statuses("/api/review-queue/"),
            (
                status.HTTP_403_FORBIDDEN,
                status.HTTP_200_OK,
                status.HTTP_200_OK,
                status.HTTP_403_FORBIDDEN,
            ),
        )

    def test_user_management_is_super_admin_only(self):
        self.assertEqual(
            self.statuses("/api/users/"),
            (
                status.HTTP_403_FORBIDDEN,
                status.HTTP_403_FORBIDDEN,
                status.HTTP_200_OK,
                status.HTTP_403_FORBIDDEN,
            ),
        )

    def test_analytics_is_ceo_only(self):
        self.assertEqual(
            self.statuses("/api/analytics/"),
            (
                status.HTTP_403_FORBIDDEN,
                status.HTTP_403_FORBIDDEN,
                status.HTTP_403_FORBIDDEN,
                status.HTTP_200_OK,
            ),
        )

    def test_ceo_cannot_review(self):
        app = KYCApplication.objects.create(
            applicant=self.applicant,
            status=KYCApplication.Status.SUBMITTED,
            submitted_at=timezone.now(),
            **{k: v for k, v in APP_PAYLOAD.items() if k != "address_line2"},
        )
        self.auth(self.ceo)
        res = self.client.post(f"/api/applications/{app.pk}/review/", {"decision": "approve"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_is_rejected(self):
        self.client.credentials()
        for url in ("/api/users/", "/api/analytics/", "/api/review-queue/"):
            self.assertEqual(
                self.client.get(url).status_code, status.HTTP_401_UNAUTHORIZED, url
            )
