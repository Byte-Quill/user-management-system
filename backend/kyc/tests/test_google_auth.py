"""Domain-focused tests: google auth."""

from unittest import mock

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialLogin
from allauth.socialaccount.providers.oauth2.client import OAuth2Error
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from kyc.common.throttles import GoogleLoginThrottle
from kyc.tests.utils import FAST_PASSWORD_HASHERS, make_user

User = get_user_model()


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
        sociallogin.email_addresses = [EmailAddress(email=email, verified=True, primary=True)]
    return sociallogin


@override_settings(GOOGLE_CLIENT_ID="test-client-id")
@FAST_PASSWORD_HASHERS
class GoogleAuthTests(APITestCase):
    """Google Sign-In with token verification mocked; provisioning/linking real."""

    URL = "/api/auth/google/"

    def setUp(self):
        cache.clear()

    def _mock_verification(self, sociallogin=None, exc=None):
        """Patch the adapter so verify_token returns our fake sociallogin."""
        provider = mock.Mock()
        provider.verify_token.side_effect = exc if exc else lambda request, token: sociallogin
        adapter = mock.Mock()
        adapter.get_provider.return_value = provider
        patcher = mock.patch("kyc.views.auth.get_socialaccount_adapter", return_value=adapter)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_google_login_creates_applicant(self):
        self._mock_verification(_google_sociallogin())
        res = self.client.post(self.URL, {"credential": "fake-id-token"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("access", res.data)

        self.assertNotIn("refresh", res.data)
        self.assertTrue(res.cookies["refresh_token"]["httponly"])

        user = User.objects.get(email="guser@gmail.com")
        self.assertEqual(user.role, User.Role.APPLICANT)
        self.assertFalse(user.has_usable_password())

        self.assertRegex(user.username, r"^PHIN-[A-Z2-9]{8}$")
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
        self.assertTrue(SocialAccount.objects.filter(user=existing, provider="google").exists())

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
        self.assertEqual(SocialAccount.objects.filter(user=existing, provider="google").count(), 1)

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
