"""Domain-focused tests: auth."""
from unittest import mock
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from rest_framework import status
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, APITestCase
from kyc.common.throttles import LoginIPThrottle

from kyc.tests.utils import FAST_PASSWORD_HASHERS, last_otp_code, make_user, register_payload, verify_via_api

User = get_user_model()

@FAST_PASSWORD_HASHERS
class AuthTests(APITestCase):
    def setUp(self):
        cache.clear()

    def test_names_are_capitalized(self):
        """first/middle/last names are stored with an initial capital."""
        res = self.client.post(
            "/api/auth/register/",
            register_payload(
                "caps@kyc.local",
                phone="+919876543297",
                first_name="jane",
                middle_name="q",
                last_name="doe",
            ),
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="caps@kyc.local")
        self.assertEqual(user.first_name, "Jane")
        self.assertEqual(user.middle_name, "Q")
        self.assertEqual(user.last_name, "Doe")

    def test_register_and_login(self):
        res = self.client.post(
            "/api/auth/register/",
            register_payload("new@kyc.local"),
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        res = self.client.post(
            "/api/auth/token/", {"email": "new@kyc.local", "password": "Str0ngPass!"}
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(res.data.get("code"), "email_not_verified")

        verify_via_api(self.client, "new@kyc.local")

        res = self.client.post(
            "/api/auth/token/", {"email": "new@kyc.local", "password": "Str0ngPass!"}
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("access", res.data)

    def test_register_phone_only_and_login_with_phone(self):
        """A phone-only account (no email) is created and can log in immediately."""
        payload = register_payload("ignored@kyc.local", phone="+919876500099")
        payload.pop("email")
        res = self.client.post("/api/auth/register/", payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(res.data["email"])

        user = User.objects.get(phone="+919876500099")
        self.assertIsNone(user.email)

        self.assertEqual(len(mail.outbox), 0)

        res = self.client.post(
            "/api/auth/token/", {"email": "+919876500099", "password": "Str0ngPass!"}
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("access", res.data)

    def test_register_email_only_and_login(self):
        """An email-only account (no phone) still requires OTP verification."""
        payload = register_payload("emailonly@kyc.local")
        payload.pop("phone")
        res = self.client.post("/api/auth/register/", payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(res.data["phone"])

        res = self.client.post(
            "/api/auth/token/", {"email": "emailonly@kyc.local", "password": "Str0ngPass!"}
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(res.data.get("code"), "email_not_verified")

        verify_via_api(self.client, "emailonly@kyc.local")
        res = self.client.post(
            "/api/auth/token/", {"email": "emailonly@kyc.local", "password": "Str0ngPass!"}
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_register_requires_email_or_phone(self):
        """At least one contact method is required."""
        payload = register_payload("neither@kyc.local")
        payload.pop("email")
        payload.pop("phone")
        res = self.client.post("/api/auth/register/", payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("non_field_errors", res.data)

    def test_register_generates_user_id_and_ignores_client_username(self):
        """The User ID is server-generated; a client-supplied username is dropped."""
        res = self.client.post(
            "/api/auth/register/",
            register_payload("uid@kyc.local", username="squatted"),
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertRegex(res.data["username"], r"^PHIN-[A-Z2-9]{8}$")
        self.assertNotEqual(res.data["username"], "squatted")
        user = User.objects.get(email="uid@kyc.local")
        self.assertEqual(user.username, res.data["username"])
        self.assertEqual(user.gender, "female")
        self.assertEqual(user.phone, "+919876500001")

    def test_register_rejects_duplicate_phone_including_format_variants(self):
        self.client.post("/api/auth/register/", register_payload("p1@kyc.local"))

        res = self.client.post(
            "/api/auth/register/",
            register_payload("p2@kyc.local", phone="+91 98765 00001"),
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone", res.data)

    def test_register_rejects_invalid_fields(self):
        cases = {
            "phone": register_payload("bad1@kyc.local", phone="123"),
            "gender": register_payload("bad2@kyc.local", gender="robot"),
            "first_name": register_payload("bad3@kyc.local", first_name="Jane123"),
            "last_name": register_payload("bad4@kyc.local", last_name=""),
        }
        for field, payload in cases.items():
            res = self.client.post("/api/auth/register/", payload)
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, field)
            self.assertIn(field, res.data, field)

    def test_register_rejects_disposable_email(self):
        """Temp/burner mail providers are blocked at signup (KYC needs a."""
        cases = [
            ("user@mailinator.com", "+919876500011"),
            ("user@YOPMAIL.com", "+919876500012"),
            ("x@10minutemail.com", "+919876500013"),
        ]
        for email, phone in cases:
            res = self.client.post(
                "/api/auth/register/", register_payload(email, phone=phone)
            )
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, email)
            self.assertIn("email", res.data, email)
            self.assertFalse(User.objects.filter(email__iexact=email).exists(), email)

    def test_register_allows_normal_email(self):
        """A regular provider domain must not be caught by the blocklist."""
        res = self.client.post(
            "/api/auth/register/", register_payload("real.user@gmail.com")
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="real.user@gmail.com").exists())

    def test_is_disposable_email_helper(self):
        from kyc.common.email_domains import is_disposable_email

        self.assertTrue(is_disposable_email("a@mailinator.com"))
        self.assertTrue(is_disposable_email("a@GuerrillaMail.NET"))
        self.assertFalse(is_disposable_email("a@gmail.com"))
        self.assertFalse(is_disposable_email("a@kyc.local"))

        self.assertFalse(is_disposable_email("not-an-email"))

    def test_register_accepts_optional_profile_fields(self):
        """DOB/nationality/address are optional but stored when provided."""
        res = self.client.post(
            "/api/auth/register/",
            register_payload(
                "profile@kyc.local",
                date_of_birth="1992-05-20",
                nationality="Indian",
                address_line1="1 Main Street",
                city="Pune",
                state="Maharashtra",
                postal_code="411001",
                country="India",
            ),
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="profile@kyc.local")
        self.assertEqual(str(user.date_of_birth), "1992-05-20")
        self.assertEqual(user.nationality, "Indian")
        self.assertEqual(user.address_line1, "1 Main Street")
        self.assertEqual(user.city, "Pune")
        self.assertEqual(user.country, "India")

        verify_via_api(self.client, "profile@kyc.local")
        res = self.client.post(
            "/api/auth/token/", {"email": "profile@kyc.local", "password": "Str0ngPass!"}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        me = self.client.get("/api/auth/me/")
        self.assertEqual(me.data["date_of_birth"], "1992-05-20")
        self.assertEqual(me.data["nationality"], "Indian")

    def test_register_optional_profile_fields_default_blank(self):
        res = self.client.post("/api/auth/register/", register_payload("minimal@kyc.local"))
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="minimal@kyc.local")
        self.assertIsNone(user.date_of_birth)
        self.assertEqual(user.nationality, "")
        self.assertEqual(user.address_line1, "")
        self.assertEqual(user.country, "")

    def test_register_rejects_invalid_date_of_birth(self):
        cases = {
            "future": register_payload("dob1@kyc.local", date_of_birth="2999-01-01"),
            "too_old": register_payload("dob2@kyc.local", date_of_birth="1850-01-01"),
            "malformed": register_payload("dob3@kyc.local", date_of_birth="20/05/1992"),
        }
        for label, payload in cases.items():
            res = self.client.post("/api/auth/register/", payload)
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, label)
            self.assertIn("date_of_birth", res.data, label)

    def test_login_with_phone(self):
        self.client.post("/api/auth/register/", register_payload("phone@kyc.local"))
        verify_via_api(self.client, "phone@kyc.local")
        res = self.client.post(
            "/api/auth/token/", {"email": "+91 98765 00001", "password": "Str0ngPass!"}
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("access", res.data)

    def test_login_with_phone_blocked_until_verified(self):
        """The verification gate applies to the phone-login path too."""
        self.client.post("/api/auth/register/", register_payload("phone2@kyc.local"))
        res = self.client.post(
            "/api/auth/token/", {"email": "+919876500001", "password": "Str0ngPass!"}
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(res.data.get("code"), "email_not_verified")

    def test_login_with_unknown_phone_is_generic_401(self):
        res = self.client.post(
            "/api/auth/token/", {"email": "+919999999999", "password": "whatever123"}
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

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
                register_payload(f"spam{i}@kyc.local", phone=f"+9198765001{i:02d}"),
            )
            self.assertIn(
                res.status_code,
                (status.HTTP_201_CREATED, status.HTTP_429_TOO_MANY_REQUESTS),
            )
        res = self.client.post(
            "/api/auth/register/",
            register_payload("spam6@kyc.local", phone="+919876500199"),
        )
        self.assertEqual(res.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_register_unique_constraint_race_returns_400_not_500(self):
        """A concurrent registration can pass the serializer's existence."""
        from django.db import IntegrityError

        with mock.patch.object(
            User.objects, "create_user", side_effect=IntegrityError("race")
        ):
            res = self.client.post(
                "/api/auth/register/", register_payload("race@kyc.local")
            )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_lowercases_email(self):
        """Login/Google matching is case-insensitive, so stored emails must."""
        res = self.client.post(
            "/api/auth/register/",
            register_payload("MiXeD@KYC.local", phone="+919876509991"),
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertTrue(User.objects.filter(email="mixed@kyc.local").exists())

    def test_register_rejects_weak_passwords(self):
        """AUTH_PASSWORD_VALIDATORS must be enforced server-side, not just in the SPA."""
        weak_passwords = [
            "12345678",
            "password",
            "short",
        ]
        for i, weak in enumerate(weak_passwords):
            res = self.client.post(
                "/api/auth/register/",
                register_payload(f"weak{i}@kyc.local", password=weak),
            )
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, weak)
            self.assertIn("password", res.data)

    def test_register_rejects_password_similar_to_email(self):
        res = self.client.post(
            "/api/auth/register/",
            register_payload(
                "janedoe@kyc.local",
                password="Janedoe2026",
            ),
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
        """Login CSRF: a cross-site form must not be able to log the victim."""
        make_user("new@kyc.local", User.Role.APPLICANT)
        res = self.client.post(
            "/api/auth/token/",
            {"email": "new@kyc.local", "password": "Passw0rd!"},
            HTTP_ORIGIN="https://evil.example.com",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn("refresh_token", res.cookies)
    def test_throttle_ident_uses_last_xff_entry(self):
        """NUM_PROXIES=1: the trusted proxy appends the real client IP last,."""
        factory = APIRequestFactory()
        throttle = LoginIPThrottle()
        spoofed = throttle.get_ident(
            Request(factory.get("/", HTTP_X_FORWARDED_FOR="1.2.3.4, 10.0.0.1"))
        )
        clean = throttle.get_ident(Request(factory.get("/", REMOTE_ADDR="10.0.0.1")))
        self.assertEqual(spoofed, clean)
    def test_refresh_allows_same_origin_on_non_standard_port(self):
        """Browsers include non-standard ports in Origin. With the port."""
        make_user("new@kyc.local", User.Role.APPLICANT)
        self.client.post(
            "/api/auth/token/",
            {"email": "new@kyc.local", "password": "Passw0rd!"},
        )

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

        res = self.client.post("/api/auth/token/refresh/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_rejects_disallowed_origin(self):
        """Logout CSRF: a cross-site POST must not blacklist the victim's."""
        make_user("new@kyc.local", User.Role.APPLICANT)
        self.client.post(
            "/api/auth/token/",
            {"email": "new@kyc.local", "password": "Passw0rd!"},
        )
        res = self.client.post("/api/auth/logout/", HTTP_ORIGIN="https://evil.example.com")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        res = self.client.post("/api/auth/token/refresh/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_blacklisted_refresh_token_cannot_be_reused(self):
        """A refresh token captured before logout (e.g. exfiltrated via logs."""
        make_user("new@kyc.local", User.Role.APPLICANT)
        self.client.post(
            "/api/auth/token/",
            {"email": "new@kyc.local", "password": "Passw0rd!"},
        )
        stolen = self.client.cookies["refresh_token"].value
        self.client.post("/api/auth/logout/")

        res = self.client.post("/api/auth/token/refresh/", {"refresh": stolen})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rotated_refresh_token_is_blacklisted(self):
        """BLACKLIST_AFTER_ROTATION: after a refresh rotates the token, the."""
        make_user("new@kyc.local", User.Role.APPLICANT)
        self.client.post(
            "/api/auth/token/",
            {"email": "new@kyc.local", "password": "Passw0rd!"},
        )
        old = self.client.cookies["refresh_token"].value
        res = self.client.post("/api/auth/token/refresh/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertNotEqual(self.client.cookies["refresh_token"].value, old)

        del self.client.cookies["refresh_token"]

        res = self.client.post("/api/auth/token/refresh/", {"refresh": old})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


@FAST_PASSWORD_HASHERS
class TokenRevocationTests(APITestCase):
    """CHECK_REVOKE_TOKEN: a password change invalidates every issued token."""

    def setUp(self):
        cache.clear()

    def test_password_reset_revokes_existing_tokens(self):
        make_user("revoke@kyc.local", User.Role.APPLICANT)
        res = self.client.post(
            "/api/auth/token/", {"email": "revoke@kyc.local", "password": "Passw0rd!"}
        )
        old_access = res.data["access"]
        res = self.client.get(
            "/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {old_access}"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.client.post("/api/auth/password-reset/request/", {"email": "revoke@kyc.local"})
        res = self.client.post(
            "/api/auth/password-reset/confirm/",
            {
                "email": "revoke@kyc.local",
                "code": last_otp_code(),
                "new_password": "N3wSecret!",
            },
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        res = self.client.get(
            "/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {old_access}"
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        res = self.client.post("/api/auth/token/refresh/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        res = self.client.post(
            "/api/auth/token/", {"email": "revoke@kyc.local", "password": "N3wSecret!"}
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)


@FAST_PASSWORD_HASHERS
class UserIDCollisionRetryTests(APITestCase):
    """A public-ID collision retries instead of returning a "duplicate" error."""

    def setUp(self):
        cache.clear()

    def test_username_collision_retries_with_new_id(self):

        make_user("taken@kyc.local", User.Role.APPLICANT)
        with mock.patch(
            "kyc.serializers.auth.generate_user_id",
            side_effect=["taken", "FRESHID99"],
        ):
            res = self.client.post(
                "/api/auth/register/", register_payload("fresh@kyc.local", phone="+919876543299")
            )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.get(email="fresh@kyc.local").username, "FRESHID99")

    def test_non_username_integrity_error_still_maps_to_400(self):
        """Email duplicates that beat the pre-check still return the friendly 400."""
        make_user("dupe@kyc.local", User.Role.APPLICANT)
        res = self.client.post(
            "/api/auth/register/", register_payload("dupe@kyc.local", phone="+919876543298")
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already exists", str(res.data))
