"""Domain-focused tests: admin."""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from kyc.models import AuditLog, KYCApplication
from kyc.tests.utils import FAST_PASSWORD_HASHERS

User = get_user_model()


@FAST_PASSWORD_HASHERS
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
        self.assertEqual(res.status_code, 302)
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
            email="rev@kyc.local", username="rev", password="Passw0rd!", role=User.Role.ADMIN
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
