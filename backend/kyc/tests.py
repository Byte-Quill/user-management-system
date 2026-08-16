import os
import threading
import time
from unittest import mock

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialLogin
from allauth.socialaccount.providers.oauth2.client import OAuth2Error
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from rest_framework import status
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory, APITestCase

from .access import GoogleLoginThrottle, LoginIPThrottle
from .models import AuditLog, Document, KYCApplication

User = get_user_model()

# PBKDF2 hashing dominates the suite's runtime (every user create/login).
# Tests never verify hashing strength, so use the fast MD5 hasher there.
FAST_PASSWORD_HASHERS = override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"]
)

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


class LightweightCacheTests(TestCase):
    """Regression tests for kyc.cache.LightweightDatabaseCache.

    ``add()`` is security-critical: allauth's JWT ``jti`` replay guard calls
    it on every Google login. ``BaseDatabaseCache`` leaves ``add``/``touch``
    abstract, so if this backend ever stops implementing them, every social
    login crashes with NotImplementedError — and the Google tests below would
    not catch it because they mock token verification.
    """

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

    def test_jti_replay_guard(self):
        """The real allauth replay check must accept a first use and reject a
        replayed jti."""
        from allauth.socialaccount.internal import jwtkit

        claims = {
            "iss": "https://accounts.google.com",
            "exp": int(time.time()) + 300,
            "jti": "replay-guard-jti",
        }
        jwtkit.verify_jti(claims)  # first use: no exception
        with self.assertRaises(OAuth2Error):
            jwtkit.verify_jti(claims)


@FAST_PASSWORD_HASHERS
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
        # RFC 6585: throttled responses tell clients when they can retry.
        self.assertGreater(int(res.headers["Retry-After"]), 0)

    @mock.patch.object(LoginIPThrottle, "THROTTLE_RATES", {"login_ip": "3/hour"})
    def test_login_ip_throttle_caps_credential_stuffing(self):
        """One IP rotating through many emails is still capped (per-IP scope)."""
        for i in range(3):
            res = self.client.post(
                "/api/auth/token/",
                {"email": f"victim{i}@kyc.local", "password": "wrong-password"},
            )
            self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        res = self.client.post(
            "/api/auth/token/",
            {"email": "victim3@kyc.local", "password": "wrong-password"},
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

    def test_register_rejects_weak_passwords(self):
        """AUTH_PASSWORD_VALIDATORS must be enforced server-side, not just in the SPA."""
        weak_passwords = [
            "12345678",       # all-numeric (NumericPasswordValidator)
            "password",       # too common (CommonPasswordValidator)
            "short",          # below min length
        ]
        for i, weak in enumerate(weak_passwords):
            res = self.client.post(
                "/api/auth/register/",
                {"email": f"weak{i}@kyc.local", "username": f"weak{i}", "password": weak},
            )
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, weak)
            self.assertIn("password", res.data)

    def test_register_rejects_password_similar_to_email(self):
        res = self.client.post(
            "/api/auth/register/",
            {
                "email": "janedoe@kyc.local",
                "username": "janedoe",
                "password": "Janedoe2026",  # too similar to email/username
            },
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", res.data)

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

    def test_login_rejects_disallowed_origin(self):
        """Login CSRF: a cross-site form must not be able to log the victim
        into an attacker's account (the response SETS the refresh cookie)."""
        make_user("new@kyc.local", User.Role.APPLICANT)
        res = self.client.post(
            "/api/auth/token/",
            {"email": "new@kyc.local", "password": "Passw0rd!"},
            HTTP_ORIGIN="https://evil.example.com",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn("refresh_token", res.cookies)
    def test_throttle_ident_uses_last_xff_entry(self):
        """NUM_PROXIES=1: the trusted proxy appends the real client IP last,
        so a spoofed leading entry must not change the throttle identity."""
        factory = APIRequestFactory()
        throttle = LoginIPThrottle()
        spoofed = throttle.get_ident(
            Request(factory.get("/", HTTP_X_FORWARDED_FOR="1.2.3.4, 10.0.0.1"))
        )
        clean = throttle.get_ident(Request(factory.get("/", REMOTE_ADDR="10.0.0.1")))
        self.assertEqual(spoofed, clean)
    def test_refresh_allows_same_origin_on_non_standard_port(self):
        """Browsers include non-standard ports in Origin. With the port
        preserved in the Host header (nginx $http_host), the same-origin
        refresh must be accepted."""
        make_user("new@kyc.local", User.Role.APPLICANT)
        self.client.post(
            "/api/auth/token/",
            {"email": "new@kyc.local", "password": "Passw0rd!"},
        )
        # SERVER_PORT makes the test client send Host: testserver:8080, so
        # Origin and Host both carry the non-standard port.
        res = self.client.post(
            "/api/auth/token/refresh/",
            HTTP_ORIGIN="http://testserver:8080",
            SERVER_PORT="8080",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

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

    def test_logout_rejects_disallowed_origin(self):
        """Logout CSRF: a cross-site POST must not blacklist the victim's
        refresh token (forced logout / session destruction)."""
        make_user("new@kyc.local", User.Role.APPLICANT)
        self.client.post(
            "/api/auth/token/",
            {"email": "new@kyc.local", "password": "Passw0rd!"},
        )
        res = self.client.post("/api/auth/logout/", HTTP_ORIGIN="https://evil.example.com")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        # Session must still be alive.
        res = self.client.post("/api/auth/token/refresh/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_blacklisted_refresh_token_cannot_be_reused(self):
        """A refresh token captured before logout (e.g. exfiltrated via logs
        or a compromised client) must stop working once the session is
        blacklisted — replay after logout is a session-hijack vector."""
        make_user("new@kyc.local", User.Role.APPLICANT)
        self.client.post(
            "/api/auth/token/",
            {"email": "new@kyc.local", "password": "Passw0rd!"},
        )
        stolen = self.client.cookies["refresh_token"].value
        self.client.post("/api/auth/logout/")

        # Replay the pre-logout token directly in the body.
        res = self.client.post("/api/auth/token/refresh/", {"refresh": stolen})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rotated_refresh_token_is_blacklisted(self):
        """BLACKLIST_AFTER_ROTATION: after a refresh rotates the token, the
        old value must be unusable. If it were not, a stolen refresh token
        would stay valid for its full 7-day lifetime despite rotation."""
        make_user("new@kyc.local", User.Role.APPLICANT)
        self.client.post(
            "/api/auth/token/",
            {"email": "new@kyc.local", "password": "Passw0rd!"},
        )
        old = self.client.cookies["refresh_token"].value
        res = self.client.post("/api/auth/token/refresh/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertNotEqual(self.client.cookies["refresh_token"].value, old)

        # Drop the rotated cookie so the replay goes through the body
        # fallback (the view prefers the cookie when present).
        del self.client.cookies["refresh_token"]
        # The pre-rotation token must now be rejected.
        res = self.client.post("/api/auth/token/refresh/", {"refresh": old})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


def _google_sociallogin(email="guser@gmail.com", uid="google-uid-1", verified=True):
    """Build an unsaved SocialLogin shaped like allauth's Google provider output."""
    user = User(
        email=email,
        first_name="Google",
        last_name="User",
        username="",
    )
    account = SocialAccount(provider="google", uid=uid, extra_data={"email": email})
    sociallogin = SocialLogin(user=user, account=account, provider="google")
    if verified:
        sociallogin.email_addresses = [
            EmailAddress(email=email, verified=True, primary=True)
        ]
    return sociallogin


@override_settings(GOOGLE_CLIENT_ID="test-client-id")
@FAST_PASSWORD_HASHERS
class GoogleAuthTests(APITestCase):
    """Google Sign-In: the ID-token verification step is mocked (no network /
    no Google keys in CI); provisioning, linking, and session issuance are real."""

    URL = "/api/auth/google/"

    def setUp(self):
        cache.clear()

    def _mock_verification(self, sociallogin=None, exc=None):
        """Patch the socialaccount adapter so provider.verify_token returns our
        fake sociallogin (or raises, simulating a bad/forged ID token)."""
        provider = mock.Mock()
        provider.verify_token.side_effect = exc if exc else lambda request, token: sociallogin
        adapter = mock.Mock()
        adapter.get_provider.return_value = provider
        patcher = mock.patch("kyc.auth_views.get_socialaccount_adapter", return_value=adapter)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_google_login_creates_applicant(self):
        self._mock_verification(_google_sociallogin())
        res = self.client.post(self.URL, {"credential": "fake-id-token"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("access", res.data)
        # Same session model as password login: refresh in HttpOnly cookie only.
        self.assertNotIn("refresh", res.data)
        self.assertTrue(res.cookies["refresh_token"]["httponly"])

        user = User.objects.get(email="guser@gmail.com")
        self.assertEqual(user.role, User.Role.APPLICANT)
        self.assertFalse(user.has_usable_password())
        self.assertTrue(
            SocialAccount.objects.filter(user=user, provider="google", uid="google-uid-1").exists()
        )
        self.assertTrue(
            EmailAddress.objects.filter(user=user, email="guser@gmail.com", verified=True).exists()
        )

    def test_google_login_reuses_linked_account(self):
        self._mock_verification(_google_sociallogin())
        self.client.post(self.URL, {"credential": "fake-id-token"})
        first_id = User.objects.get(email="guser@gmail.com").id

        self._mock_verification(_google_sociallogin())
        res = self.client.post(self.URL, {"credential": "fake-id-token"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(User.objects.filter(email="guser@gmail.com").count(), 1)
        self.assertEqual(User.objects.get(email="guser@gmail.com").id, first_id)

    def test_google_login_links_existing_password_user_by_email(self):
        """Google proved ownership of the email, so linking is safe."""
        existing = make_user("guser@gmail.com", User.Role.APPLICANT)
        self._mock_verification(_google_sociallogin())
        res = self.client.post(self.URL, {"credential": "fake-id-token"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(User.objects.filter(email="guser@gmail.com").count(), 1)
        self.assertTrue(
            SocialAccount.objects.filter(user=existing, provider="google").exists()
        )
        # The password credential must keep working after linking.
        res = self.client.post(
            "/api/auth/token/", {"email": "guser@gmail.com", "password": "Passw0rd!"}
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_google_login_rejects_second_google_identity(self):
        existing = make_user("guser@gmail.com", User.Role.APPLICANT)
        SocialAccount.objects.create(user=existing, provider="google", uid="other-uid")
        self._mock_verification(_google_sociallogin())
        res = self.client.post(self.URL, {"credential": "fake-id-token"})
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(
            SocialAccount.objects.filter(user=existing, provider="google").count(), 1
        )

    def test_google_login_requires_verified_email(self):
        self._mock_verification(_google_sociallogin(verified=False))
        res = self.client.post(self.URL, {"credential": "fake-id-token"})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(User.objects.filter(email="guser@gmail.com").exists())

    def test_google_login_rejects_invalid_credential(self):
        self._mock_verification(exc=OAuth2Error("Invalid id_token"))
        res = self.client.post(self.URL, {"credential": "forged-token"})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_google_login_requires_credential(self):
        res = self.client.post(self.URL, {})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(GOOGLE_CLIENT_ID="")
    def test_google_login_disabled_when_unconfigured(self):
        res = self.client.post(self.URL, {"credential": "fake-id-token"})
        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_google_login_rejects_disallowed_origin(self):
        """Login CSRF: a cross-site POST must not set the victim's refresh cookie."""
        self._mock_verification(_google_sociallogin())
        res = self.client.post(
            self.URL, {"credential": "fake-id-token"}, HTTP_ORIGIN="https://evil.example.com"
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn("refresh_token", res.cookies)

    def test_google_login_rejects_inactive_user(self):
        user = make_user("guser@gmail.com", User.Role.APPLICANT)
        user.is_active = False
        user.save()
        SocialAccount.objects.create(user=user, provider="google", uid="google-uid-1")
        self._mock_verification(_google_sociallogin())
        res = self.client.post(self.URL, {"credential": "fake-id-token"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    @mock.patch.object(GoogleLoginThrottle, "THROTTLE_RATES", {"google_login": "2/hour"})
    def test_google_login_is_rate_limited(self):
        """Per-IP cap bounds the CPU/network cost of token verification."""
        self._mock_verification(exc=OAuth2Error("Invalid id_token"))
        for _ in range(2):
            res = self.client.post(self.URL, {"credential": "forged"})
            self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        res = self.client.post(self.URL, {"credential": "forged"})
        self.assertEqual(res.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertGreater(int(res.headers["Retry-After"]), 0)


@FAST_PASSWORD_HASHERS
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
        # attachment (not inline): documents are served on the app origin,
        # so in-browser PDF JavaScript would run with the viewer's session.
        self.assertIn("attachment", res["Content-Disposition"])
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


@FAST_PASSWORD_HASHERS
@skipUnlessDBFeature("has_select_for_update")
class ConcurrencyTests(TransactionTestCase):
    """Race conditions on state transitions (needs real row locks: Postgres)."""

    def setUp(self):
        cache.clear()
        self.applicant = make_user("user@kyc.local", User.Role.APPLICANT)

    def test_concurrent_submits_transition_once(self):
        """Two parallel submits must not both pass the draft-status check."""
        client = APIClient()
        res = client.post(
            "/api/auth/token/", {"email": "user@kyc.local", "password": "Passw0rd!"}
        )
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


# The admin templates reference static assets. The production storage backend
# (CompressedManifestStaticFilesStorage) needs a collectstatic manifest, which
# the test runner does not build (and DEBUG is forced off, so the manifest
# lookup is not skipped). Use the plain storage so admin pages render.
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
