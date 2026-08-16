import os

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from .models import AuditLog, Document, KYCApplication

User = get_user_model()

APP_PAYLOAD = {
    "full_name": "Jane Doe",
    "date_of_birth": "1992-05-20",
    "nationality": "Indian",
    "phone": "+91-9000000000",
    "address_line1": "1 Main Street",
    "address_line2": "",
    "city": "Pune",
    "state": "Maharashtra",
    "postal_code": "411001",
    "country": "India",
    "id_type": "passport",
    "id_number": "B7654321",
    "id_expiry": "2031-01-01",
}


def make_user(email, role, password="Passw0rd!"):
    return User.objects.create_user(
        email=email, username=email.split("@")[0], password=password, role=role
    )


class AuthTests(APITestCase):
    def setUp(self):
        cache.clear()

    def test_register_and_login(self):
        res = self.client.post(
            "/api/auth/register/",
            {"email": "new@kyc.local", "username": "newbie", "password": "Str0ngPass!"},
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        res = self.client.post(
            "/api/auth/token/", {"email": "new@kyc.local", "password": "Str0ngPass!"}
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("access", res.data)

    def test_login_is_rate_limited(self):
        for _ in range(10):
            res = self.client.post(
                "/api/auth/token/",
                {"email": "unknown@kyc.local", "password": "wrong-password"},
            )
            self.assertIn(
                res.status_code,
                (status.HTTP_401_UNAUTHORIZED, status.HTTP_429_TOO_MANY_REQUESTS),
            )

        res = self.client.post(
            "/api/auth/token/",
            {"email": "unknown@kyc.local", "password": "wrong-password"},
        )
        self.assertEqual(res.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_register_is_rate_limited(self):
        for i in range(5):
            res = self.client.post(
                "/api/auth/register/",
                {"email": f"spam{i}@kyc.local", "username": f"spam{i}", "password": "Str0ngPass!"},
            )
            self.assertIn(
                res.status_code,
                (status.HTTP_201_CREATED, status.HTTP_429_TOO_MANY_REQUESTS),
            )
        res = self.client.post(
            "/api/auth/register/",
            {"email": "spam6@kyc.local", "username": "spam6", "password": "Str0ngPass!"},
        )
        self.assertEqual(res.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_me_requires_auth(self):
        self.assertEqual(self.client.get("/api/auth/me/").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_sets_httponly_refresh_cookie(self):
        make_user("new@kyc.local", User.Role.APPLICANT)
        res = self.client.post(
            "/api/auth/token/",
            {"email": "new@kyc.local", "password": "Passw0rd!"},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # Refresh token must NOT be exposed in the response body.
        self.assertNotIn("refresh", res.data)
        self.assertIn("refresh_token", res.cookies)
        cookie = res.cookies["refresh_token"]
        self.assertTrue(cookie["httponly"])

    def test_refresh_with_cookie_rotates_token(self):
        make_user("new@kyc.local", User.Role.APPLICANT)
        self.client.post(
            "/api/auth/token/",
            {"email": "new@kyc.local", "password": "Passw0rd!"},
        )
        old_cookie = self.client.cookies["refresh_token"].value

        res = self.client.post("/api/auth/token/refresh/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("access", res.data)
        # Rotation: the cookie value must change.
        new_cookie = self.client.cookies["refresh_token"].value
        self.assertNotEqual(old_cookie, new_cookie)

    def test_refresh_rejects_disallowed_origin(self):
        make_user("new@kyc.local", User.Role.APPLICANT)
        self.client.post(
            "/api/auth/token/",
            {"email": "new@kyc.local", "password": "Passw0rd!"},
        )
        res = self.client.post(
            "/api/auth/token/refresh/",
            HTTP_ORIGIN="https://evil.example.com",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_logout_clears_cookie(self):
        make_user("new@kyc.local", User.Role.APPLICANT)
        self.client.post(
            "/api/auth/token/",
            {"email": "new@kyc.local", "password": "Passw0rd!"},
        )
        res = self.client.post("/api/auth/logout/")
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        # Cookie cleared -> refresh must now fail.
        res = self.client.post("/api/auth/token/refresh/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class ApplicationFlowTests(APITestCase):
    def setUp(self):
        cache.clear()  # keep user-scoped write throttles deterministic per test
        self.applicant = make_user("user@kyc.local", User.Role.APPLICANT)
        self.other = make_user("other@kyc.local", User.Role.APPLICANT)
        self.reviewer = make_user("rev@kyc.local", User.Role.REVIEWER)

    def auth(self, user, password="Passw0rd!"):
        res = self.client.post("/api/auth/token/", {"email": user.email, "password": password})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    def create_app(self):
        res = self.client.post("/api/applications/", APP_PAYLOAD)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        return res.data["id"]

    def upload_doc(self, app_id):
        file = SimpleUploadedFile(
            "passport.pdf",
            b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
            content_type="application/pdf",
        )
        return self.client.post(
            f"/api/applications/{app_id}/documents/",
            {"doc_type": "id_proof", "file": file},
            format="multipart",
        )

    def test_full_approval_flow(self):
        self.auth(self.applicant)
        app_id = self.create_app()

        res = self.client.post(f"/api/applications/{app_id}/submit/")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        res = self.upload_doc(app_id)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        res = self.client.post(f"/api/applications/{app_id}/submit/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], "submitted")

        res = self.client.post(f"/api/applications/{app_id}/review/", {"decision": "approve"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        self.auth(self.reviewer)
        res = self.client.post(f"/api/applications/{app_id}/review/", {"decision": "approve"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], "approved")

        res = self.client.get(f"/api/applications/{app_id}/audit/")
        actions = [entry["action"] for entry in res.data["results"]]
        self.assertEqual(
            actions,
            ["approved", "submitted", "document_uploaded", "created"],
        )

    def test_rejection_requires_notes(self):
        self.auth(self.applicant)
        app_id = self.create_app()
        self.upload_doc(app_id)
        self.client.post(f"/api/applications/{app_id}/submit/")

        self.auth(self.reviewer)
        res = self.client.post(f"/api/applications/{app_id}/review/", {"decision": "reject"})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        res = self.client.post(
            f"/api/applications/{app_id}/review/",
            {"decision": "reject", "notes": "Blurry ID scan"},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], "rejected")

    def test_applicant_cannot_see_others_applications(self):
        self.auth(self.applicant)
        app_id = self.create_app()

        self.auth(self.other)
        res = self.client.get(f"/api/applications/{app_id}/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        res = self.client.get("/api/applications/")
        self.assertEqual(len(res.data["results"]), 0)

    def test_list_is_paginated(self):
        self.auth(self.applicant)
        for _ in range(25):
            self.create_app()
        res = self.client.get("/api/applications/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 25)
        self.assertEqual(len(res.data["results"]), 20)
        self.assertIsNotNone(res.data["next"])
        res2 = self.client.get("/api/applications/?page=2")
        self.assertEqual(len(res2.data["results"]), 5)

    def test_reviewer_cannot_patch_applicant_fields(self):
        self.auth(self.applicant)
        app_id = self.create_app()
        self.auth(self.reviewer)
        res = self.client.patch(
            f"/api/applications/{app_id}/",
            {"full_name": "Tampered Name"},
        )
        # Permission layer now blocks reviewers from any write operations
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_review_queue_only_for_reviewers(self):
        self.auth(self.applicant)
        self.create_app()
        res = self.client.get("/api/review-queue/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        self.auth(self.reviewer)
        res = self.client.get("/api/review-queue/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_invalid_file_type_rejected(self):
        self.auth(self.applicant)
        app_id = self.create_app()
        file = SimpleUploadedFile("malware.exe", b"MZ", content_type="application/octet-stream")
        res = self.client.post(
            f"/api/applications/{app_id}/documents/",
            {"doc_type": "id_proof", "file": file},
            format="multipart",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_remove_document(self):
        self.auth(self.applicant)
        app_id = self.create_app()
        res = self.upload_doc(app_id)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        doc_id = res.data["id"]

        # Only removable while editable, and only by the owner.
        self.client.post(f"/api/applications/{app_id}/submit/")
        res = self.client.delete(f"/api/applications/{app_id}/documents/{doc_id}/")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Non-owner gets 404: the queryset is owner-scoped, so the app is
        # invisible to them (no existence leak).
        self.auth(self.other)
        res = self.client.delete(f"/api/applications/{app_id}/documents/{doc_id}/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        # Owner removes it from a draft and it is logged.
        self.auth(self.applicant)
        app_id = self.create_app()
        res = self.upload_doc(app_id)
        doc_id = res.data["id"]
        # Capture the on-disk path before deletion so we can assert cleanup.
        file_path = Document.objects.get(pk=doc_id).file.path
        self.assertTrue(os.path.exists(file_path))
        res = self.client.delete(f"/api/applications/{app_id}/documents/{doc_id}/")
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(
            Document.objects.filter(pk=doc_id).exists(),
            False,
        )
        # Django does not delete FileField files on model deletion; the
        # post_delete signal must remove the PII file from disk.
        self.assertFalse(os.path.exists(file_path))
        res = self.client.get(f"/api/applications/{app_id}/audit/")
        actions = [entry["action"] for entry in res.data["results"]]
        self.assertEqual(actions[0], "document_removed")

        # Unknown document id -> 404.
        res = self.client.delete(f"/api/applications/{app_id}/documents/does-not-exist/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_content_mismatch_rejected(self):
        """An executable renamed to .pdf must be rejected by content sniffing."""
        self.auth(self.applicant)
        app_id = self.create_app()
        file = SimpleUploadedFile(
            "fake.pdf", b"MZ\x90\x00 executable", content_type="application/pdf"
        )
        res = self.client.post(
            f"/api/applications/{app_id}/documents/",
            {"doc_type": "id_proof", "file": file},
            format="multipart",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_oversized_upload_rejected(self):
        self.auth(self.applicant)
        app_id = self.create_app()
        big = SimpleUploadedFile(
            "big.pdf", b"%PDF-1.4 " + b"0" * (6 * 1024 * 1024), content_type="application/pdf"
        )
        res = self.client.post(
            f"/api/applications/{app_id}/documents/",
            {"doc_type": "id_proof", "file": big},
            format="multipart",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_document_download_signed_url(self):
        """Detail responses carry a signed download URL that serves the file."""
        self.auth(self.applicant)
        app_id = self.create_app()
        res = self.upload_doc(app_id)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        doc_id = res.data["id"]

        # The upload response and detail view expose a signed URL.
        self.assertIn("token=", res.data["file"])
        res = self.client.get(f"/api/applications/{app_id}/")
        doc_url = res.data["documents"][0]["file"]
        self.assertIn(f"/api/documents/{doc_id}/download/?token=", doc_url)

        # The URL works WITHOUT the JWT (browser new-tab semantics)...
        self.client.credentials()
        res = self.client.get(doc_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["Content-Type"], "application/pdf")
        content = b"".join(res.streaming_content)
        self.assertTrue(content.startswith(b"%PDF-1.4"))

        # ...but a missing, forged, or mismatched token is rejected.
        res = self.client.get(f"/api/documents/{doc_id}/download/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        res = self.client.get(f"/api/documents/{doc_id}/download/?token=forged")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        # A valid token for another document must not grant access.
        from kyc.models import document_download_token

        other_token = document_download_token("00000000-0000-0000-0000-000000000000")
        res = self.client.get(f"/api/documents/{doc_id}/download/?token={other_token}")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_download_url_omitted_in_list_views(self):
        """List payloads stay lean: no per-document download URLs."""
        self.auth(self.applicant)
        app_id = self.create_app()
        self.upload_doc(app_id)
        res = self.client.get("/api/applications/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIsNone(res.data["results"][0]["documents"][0]["file"])


# The admin templates reference static assets. The production storage backend
# (CompressedManifestStaticFilesStorage) needs a collectstatic manifest, which
# the test runner does not build (and DEBUG is forced off, so the manifest
# lookup is not skipped). Use the plain storage so admin pages render.
@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class AdminTests(TestCase):
    """Regression tests for the Django admin customizations."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="boss@kyc.local", username="boss", password="Passw0rd!"
        )
        self.client.force_login(self.admin)

    def test_user_add_form_includes_email(self):
        # USERNAME_FIELD is email, so the stock add form (username only)
        # would create users that can never log in.
        res = self.client.post(
            "/admin/kyc/user/add/",
            {
                "username": "newuser",
                "usable_password": "true",
                "password1": "Str0ngPass!2026",
                "password2": "Str0ngPass!2026",
                "email": "newuser@kyc.local",
            },
        )
        self.assertEqual(res.status_code, 302)  # success redirects to change page
        user = User.objects.get(email="newuser@kyc.local")
        self.assertEqual(user.username, "newuser")
        self.assertTrue(user.check_password("Str0ngPass!2026"))

    def test_admin_status_change_is_audited(self):
        applicant = User.objects.create_user(
            email="user@kyc.local", username="user", password="Passw0rd!"
        )
        app = KYCApplication.objects.create(
            applicant=applicant,
            full_name="Jane Doe",
            date_of_birth="1992-05-20",
            nationality="Indian",
            phone="+91-9000000000",
            address_line1="1 Main Street",
            city="Pune",
            state="Maharashtra",
            postal_code="411001",
            country="India",
            id_type=KYCApplication.IDType.PASSPORT,
            id_number="B7654321",
        )
        res = self.client.post(
            f"/admin/kyc/kycapplication/{app.pk}/change/",
            {
                "applicant": applicant.pk,
                "status": KYCApplication.Status.APPROVED,
                "full_name": "Jane Doe",
                "date_of_birth": "1992-05-20",
                "nationality": "Indian",
                "phone": "+91-9000000000",
                "address_line1": "1 Main Street",
                "address_line2": "",
                "city": "Pune",
                "state": "Maharashtra",
                "postal_code": "411001",
                "country": "India",
                "id_type": KYCApplication.IDType.PASSPORT,
                "id_number": "B7654321",
                "review_notes": "",
                "documents-TOTAL_FORMS": "0",
                "documents-INITIAL_FORMS": "0",
                "documents-MIN_NUM_FORMS": "0",
                "documents-MAX_NUM_FORMS": "1000",
            },
        )
        self.assertEqual(res.status_code, 302)
        app.refresh_from_db()
        self.assertEqual(app.status, KYCApplication.Status.APPROVED)
        entry = AuditLog.objects.filter(application=app).first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.action, AuditLog.Action.UPDATED)
        self.assertEqual(entry.actor, self.admin)
        self.assertIn("draft -> approved", entry.detail)

    def test_auditlog_is_view_only(self):
        applicant = User.objects.create_user(
            email="user2@kyc.local", username="user2", password="Passw0rd!"
        )
        app = KYCApplication.objects.create(
            applicant=applicant,
            full_name="X",
            date_of_birth="1990-01-01",
            nationality="Indian",
            phone="+91",
            address_line1="a",
            city="c",
            state="s",
            postal_code="1",
            country="India",
            id_type=KYCApplication.IDType.PASSPORT,
            id_number="Z1",
        )
        entry = AuditLog.objects.create(
            application=app, actor=applicant, action=AuditLog.Action.CREATED
        )
        # No add form, and the detail page is view-only (no change permission).
        self.assertEqual(self.client.get("/admin/kyc/auditlog/add/").status_code, 403)
        res = self.client.get(f"/admin/kyc/auditlog/{entry.pk}/change/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "View audit log")
        delete_url = f"/admin/kyc/auditlog/{entry.pk}/delete/"
        self.assertEqual(self.client.get(delete_url).status_code, 403)

    def test_reviewer_dropdown_excludes_applicants(self):
        applicant = User.objects.create_user(
            email="user3@kyc.local", username="user3", password="Passw0rd!"
        )
        reviewer = User.objects.create_user(
            email="rev@kyc.local", username="rev", password="Passw0rd!", role=User.Role.REVIEWER
        )
        app = KYCApplication.objects.create(
            applicant=applicant,
            full_name="X",
            date_of_birth="1990-01-01",
            nationality="Indian",
            phone="+91",
            address_line1="a",
            city="c",
            state="s",
            postal_code="1",
            country="India",
            id_type=KYCApplication.IDType.PASSPORT,
            id_number="Z2",
        )
        res = self.client.get(f"/admin/kyc/kycapplication/{app.pk}/change/")
        self.assertEqual(res.status_code, 200)
        options = set(res.context["adminform"].form.fields["reviewer"].queryset)
        self.assertIn(reviewer, options)
        self.assertNotIn(applicant, options)
