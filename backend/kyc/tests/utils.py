"""Shared fixtures and helpers for the kyc test-suite."""

import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings

User = get_user_model()


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
        email=email,
        username=email.split("@")[0],
        password=password,
        role=role,
        email_verified=True,
    )


OTP_CODE_RE = re.compile(r"\b(\d{6})\b")


def last_otp_code():
    """Extract the 6-digit code from the most recent test-outbox email."""
    match = OTP_CODE_RE.search(mail.outbox[-1].body)
    assert match, f"no OTP code found in email body: {mail.outbox[-1].body!r}"
    return match.group(1)


def verify_via_api(client, email):
    """Complete the signup OTP flow for a freshly registered account."""
    res = client.post("/api/auth/verify-email/", {"email": email, "code": last_otp_code()})
    assert res.status_code == 200, res.content
    return res


def register_payload(email, phone="+919876500001", **overrides):
    """Valid registration body; each call needs a unique email AND phone."""
    payload = {
        "email": email,
        "password": "Str0ngPass!",
        "first_name": "Jane",
        "last_name": "Doe",
        "phone": phone,
        "gender": "female",
    }
    payload.update(overrides)
    return payload
