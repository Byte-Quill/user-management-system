"""Domain-focused tests: users."""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase

from kyc.tests.utils import FAST_PASSWORD_HASHERS, make_user

User = get_user_model()

@FAST_PASSWORD_HASHERS
class UserManagementTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.super_admin = make_user("super@kyc.local", User.Role.SUPER_ADMIN)
        self.applicant = make_user("app@kyc.local", User.Role.APPLICANT)
        res = self.client.post(
            "/api/auth/token/", {"email": self.super_admin.email, "password": "Passw0rd!"}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    def test_create_user_with_role(self):
        res = self.client.post(
            "/api/users/",
            {
                "email": "new.admin@kyc.local",
                "password": "Str0ngPass!",
                "first_name": "New",
                "last_name": "Admin",
                "role": User.Role.ADMIN,
            },
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        created = User.objects.get(email="new.admin@kyc.local")
        self.assertEqual(created.role, User.Role.ADMIN)

        self.assertTrue(created.email_verified)
        self.assertTrue(created.check_password("Str0ngPass!"))
        self.assertNotIn("password", res.data)

    def test_create_user_rejects_weak_password(self):
        res = self.client.post(
            "/api/users/",
            {
                "email": "weak@kyc.local",
                "password": "password",
                "first_name": "W",
                "last_name": "K",
                "role": User.Role.APPLICANT,
            },
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", res.data)

    def test_change_role(self):
        res = self.client.patch(
            f"/api/users/{self.applicant.pk}/", {"role": User.Role.ADMIN}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.applicant.refresh_from_db()
        self.assertEqual(self.applicant.role, User.Role.ADMIN)

    def test_cannot_change_own_role(self):
        res = self.client.patch(
            f"/api/users/{self.super_admin.pk}/", {"role": User.Role.APPLICANT}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.super_admin.refresh_from_db()
        self.assertEqual(self.super_admin.role, User.Role.SUPER_ADMIN)

    def test_set_password(self):
        res = self.client.post(
            f"/api/users/{self.applicant.pk}/set_password/", {"new_password": "An0therPass!"}
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.applicant.refresh_from_db()
        self.assertTrue(self.applicant.check_password("An0therPass!"))

    def test_set_password_rejects_weak_and_self(self):
        res = self.client.post(
            f"/api/users/{self.applicant.pk}/set_password/", {"new_password": "12345678"}
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        res = self.client.post(
            f"/api/users/{self.super_admin.pk}/set_password/", {"new_password": "An0therPass!"}
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.super_admin.refresh_from_db()
        self.assertTrue(self.super_admin.check_password("Passw0rd!"))

    def test_filters(self):
        res = self.client.get("/api/users/", {"role": User.Role.APPLICANT})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        emails = [row["email"] for row in res.data["results"]]
        self.assertEqual(emails, [self.applicant.email])

        res = self.client.get("/api/users/", {"role": "bogus"})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        res = self.client.get("/api/users/", {"search": "super"})
        self.assertEqual(
            [row["email"] for row in res.data["results"]], [self.super_admin.email]
        )

    def test_delete_is_not_allowed(self):
        res = self.client.delete(f"/api/users/{self.applicant.pk}/")
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
