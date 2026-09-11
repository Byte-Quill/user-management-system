"""Domain-focused tests: applications."""

import os
import threading
import time
from datetime import date, timedelta
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from kyc.models import Document, KYCApplication
from kyc.tests.utils import APP_PAYLOAD, FAST_PASSWORD_HASHERS, make_user

User = get_user_model()


@FAST_PASSWORD_HASHERS
class ApplicationFlowTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.applicant = make_user("user@kyc.local", User.Role.APPLICANT)
        self.other = make_user("other@kyc.local", User.Role.APPLICANT)
        self.reviewer = make_user("rev@kyc.local", User.Role.ADMIN)

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

    def test_future_date_of_birth_rejected(self):
        """The API (not just the SPA) must enforce the DOB business rule."""
        self.auth(self.applicant)
        payload = {**APP_PAYLOAD, "date_of_birth": "2999-01-01"}
        res = self.client.post("/api/applications/", payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("date_of_birth", res.data)

    def test_invalid_phone_rejected(self):
        self.auth(self.applicant)
        for bad_phone in ("abc", "12", "12345678901234567890"):
            payload = {**APP_PAYLOAD, "phone": bad_phone}
            res = self.client.post("/api/applications/", payload)
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, bad_phone)
            self.assertIn("phone", res.data)

    def test_remove_document(self):
        self.auth(self.applicant)
        app_id = self.create_app()
        res = self.upload_doc(app_id)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        doc_id = res.data["id"]

        self.client.post(f"/api/applications/{app_id}/submit/")
        res = self.client.delete(f"/api/applications/{app_id}/documents/{doc_id}/")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        self.auth(self.other)
        res = self.client.delete(f"/api/applications/{app_id}/documents/{doc_id}/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

        self.auth(self.applicant)
        app_id = self.create_app()
        res = self.upload_doc(app_id)
        doc_id = res.data["id"]

        file_path = Document.objects.get(pk=doc_id).file.path
        self.assertTrue(os.path.exists(file_path))

        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.delete(f"/api/applications/{app_id}/documents/{doc_id}/")
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(
            Document.objects.filter(pk=doc_id).exists(),
            False,
        )

        self.assertFalse(os.path.exists(file_path))
        res = self.client.get(f"/api/applications/{app_id}/audit/")
        actions = [entry["action"] for entry in res.data["results"]]
        self.assertEqual(actions[0], "document_removed")

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

        self.assertIn("token=", res.data["file"])
        res = self.client.get(f"/api/applications/{app_id}/")
        doc_url = res.data["documents"][0]["file"]
        self.assertIn(f"/api/documents/{doc_id}/download/?token=", doc_url)

        self.client.credentials()
        res = self.client.get(doc_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res["Content-Type"], "application/pdf")

        self.assertIn("attachment", res["Content-Disposition"])
        content = b"".join(res.streaming_content)
        self.assertTrue(content.startswith(b"%PDF-1.4"))

        res = self.client.get(f"/api/documents/{doc_id}/download/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        res = self.client.get(f"/api/documents/{doc_id}/download/?token=forged")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

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

    def test_download_token_expires(self):
        """Tokens travel in URLs (logs, history) — the replay window is short."""
        from kyc.models import DOWNLOAD_TOKEN_MAX_AGE, document_download_token

        self.auth(self.applicant)
        app_id = self.create_app()
        res = self.upload_doc(app_id)
        doc_id = res.data["id"]
        token = document_download_token(doc_id)

        with mock.patch(
            "django.core.signing.time.time",
            return_value=time.time() + DOWNLOAD_TOKEN_MAX_AGE + 1,
        ):
            res = self.client.get(f"/api/documents/{doc_id}/download/?token={token}")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_patch_rejected_after_submit(self):
        """The editable-status check and the write happen under one row lock,."""
        self.auth(self.applicant)
        app_id = self.create_app()
        self.upload_doc(app_id)
        self.client.post(f"/api/applications/{app_id}/submit/")
        res = self.client.patch(
            f"/api/applications/{app_id}/", {"full_name": "Changed After Submit"}
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(KYCApplication.objects.get(pk=app_id).full_name, "Jane Doe")

    def test_upload_rolls_back_file_on_audit_failure(self):
        """If anything after the storage write fails, the transaction rolls."""
        self.auth(self.applicant)
        app_id = self.create_app()
        file = SimpleUploadedFile(
            "passport.pdf",
            b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
            content_type="application/pdf",
        )
        with mock.patch(
            "kyc.views.applications.log_action", side_effect=RuntimeError("audit down")
        ):
            self.client.raise_request_exception = False
            try:
                res = self.client.post(
                    f"/api/applications/{app_id}/documents/",
                    {"doc_type": "id_proof", "file": file},
                    format="multipart",
                )
            finally:
                self.client.raise_request_exception = True
        self.assertEqual(res.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

        self.assertEqual(Document.objects.filter(application_id=app_id).count(), 0)

        app_dir = os.path.join(settings.MEDIA_ROOT, "documents", str(app_id))
        self.assertFalse(
            os.path.isdir(app_dir) and os.listdir(app_dir),
            f"orphaned upload left in {app_dir}",
        )

    def test_create_rejects_expired_id_expiry(self):
        """An already-expired ID is refused at creation, not at review time."""
        self.auth(self.applicant)
        payload = {**APP_PAYLOAD, "id_expiry": (date.today() - timedelta(days=1)).isoformat()}
        res = self.client.post("/api/applications/", payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("expired", str(res.data))

    def test_expired_id_blocks_submission(self):
        """An ID that expires while a draft sits around still blocks submission."""
        self.auth(self.applicant)
        app_id = self.create_app()
        self.upload_doc(app_id)
        KYCApplication.objects.filter(pk=app_id).update(id_expiry=date.today() - timedelta(days=1))
        res = self.client.post(f"/api/applications/{app_id}/submit/")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("expired", str(res.data))
        self.assertEqual(KYCApplication.objects.get(pk=app_id).status, KYCApplication.Status.DRAFT)

    def test_reviewer_cannot_review_own_application(self):
        """A reviewer must not decide their own submitted application."""
        reviewer = make_user("owner@kyc.local", User.Role.ADMIN)
        app = KYCApplication.objects.create(
            applicant=reviewer,
            full_name="Owner Applicant",
            date_of_birth=date(1992, 5, 20),
            nationality="Indian",
            phone="+919000000099",
            address_line1="1 Main Street",
            city="Pune",
            state="Maharashtra",
            postal_code="411001",
            country="India",
            id_type=KYCApplication.IDType.PASSPORT,
            id_number="B7654321",
            status=KYCApplication.Status.SUBMITTED,
            submitted_at=timezone.now(),
        )
        self.auth(reviewer)
        res = self.client.post(f"/api/applications/{app.pk}/review/", {"decision": "approve"})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        app.refresh_from_db()
        self.assertEqual(app.status, KYCApplication.Status.SUBMITTED)
        self.assertIsNone(app.reviewer)

    def test_document_count_is_capped(self):
        """Storage bound: a draft cannot accumulate unbounded 5 MB files."""
        self.auth(self.applicant)
        app_id = self.create_app()
        cap = settings.MAX_DOCUMENTS_PER_APPLICATION
        for _ in range(cap):
            res = self.upload_doc(app_id)
            self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        res = self.upload_doc(app_id)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("At most", str(res.data))


@FAST_PASSWORD_HASHERS
@skipUnlessDBFeature("has_select_for_update")
class ConcurrencyTests(TransactionTestCase):
    """Race conditions on state transitions (needs real row locks: Postgres)."""

    def setUp(self):
        cache.clear()
        self.applicant = make_user("user@kyc.local", User.Role.APPLICANT)
        self.super_admin = make_user("super@kyc.local", User.Role.SUPER_ADMIN)

    def test_concurrent_submits_transition_once(self):
        """Two parallel submits must not both pass the draft-status check."""
        client = APIClient()
        res = client.post("/api/auth/token/", {"email": "user@kyc.local", "password": "Passw0rd!"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        res = client.post("/api/applications/", APP_PAYLOAD)
        app_id = res.data["id"]
        file = SimpleUploadedFile(
            "passport.pdf",
            b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
            content_type="application/pdf",
        )
        client.post(
            f"/api/applications/{app_id}/documents/",
            {"doc_type": "id_proof", "file": file},
            format="multipart",
        )

        results = []
        barrier = threading.Barrier(2)

        def submit():
            barrier.wait()
            results.append(client.post(f"/api/applications/{app_id}/submit/").status_code)

        threads = [threading.Thread(target=submit) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(sorted(results), [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])
        self.assertEqual(
            KYCApplication.objects.get(pk=app_id).status,
            KYCApplication.Status.SUBMITTED,
        )

    def test_concurrent_mutual_demote_keeps_one_super_admin(self):
        """Two super admins demoting each other simultaneously must not leave."""
        other = make_user("super2@kyc.local", User.Role.SUPER_ADMIN)

        def demote(actor_email, target_pk, results):
            client = APIClient()
            res = client.post("/api/auth/token/", {"email": actor_email, "password": "Passw0rd!"})
            client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
            barrier.wait()
            results.append(
                client.patch(
                    f"/api/users/{target_pk}/",
                    {"role": User.Role.APPLICANT},
                    format="json",
                ).status_code
            )

        barrier = threading.Barrier(2)
        results = []
        threads = [
            threading.Thread(target=demote, args=("super@kyc.local", other.pk, results)),
            threading.Thread(
                target=demote, args=("super2@kyc.local", self.super_admin.pk, results)
            ),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertIn(status.HTTP_400_BAD_REQUEST, results)
        self.assertTrue(User.objects.filter(role=User.Role.SUPER_ADMIN, is_active=True).exists())
