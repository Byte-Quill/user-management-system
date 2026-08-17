"""Email OTP issuance and verification (signup verification + password reset).

Codes are 6 digits from ``secrets``, stored only as HMAC-SHA256 keyed with
SECRET_KEY; single-use with a bounded attempt counter, a 10-minute TTL, a
60-second resend cooldown, and only the latest code per (user, purpose) is
valid.
"""
import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import F
from django.utils import timezone

from .models import EmailOTP

logger = logging.getLogger("kyc.otp")

OTP_LENGTH = 6
OTP_TTL = timedelta(minutes=10)
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN = timedelta(seconds=60)
# Rows are purged a day after expiry.
OTP_PURGE_AFTER = timedelta(days=1)


def _hash_code(code: str) -> str:
    """Keyed hash (HMAC-SHA256 with SECRET_KEY), not plain SHA-256.

    A 6-digit code has only 10^6 possibilities — plain SHA-256 could be
    brute-forced offline from a database leak alone.
    """
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"), code.encode("utf-8"), hashlib.sha256
    ).hexdigest()


def generate_code() -> str:
    """Uniform 6-digit code; zero-padded so '000042' is as likely as any other."""
    return f"{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}"


def _purge_old() -> None:
    """Delete long-expired rows, amortized across issuances (1-in-10)."""
    if secrets.randbelow(10) != 0:
        return
    EmailOTP.objects.filter(expires_at__lt=timezone.now() - OTP_PURGE_AFTER).delete()
    if secrets.randbelow(10) != 0:
        return
    EmailOTP.objects.filter(expires_at__lt=timezone.now() - OTP_PURGE_AFTER).delete()


def _send_otp_email(user, purpose: str, code: str) -> None:
    if purpose == EmailOTP.Purpose.VERIFY_EMAIL:
        subject = "Verify your email — Login Portal"
        body = (
            f"Hi {user.first_name or 'there'},\n\n"
            f"Your Login Portal verification code is: {code}\n\n"
            f"It expires in {OTP_TTL.seconds // 60} minutes. If you did not "
            "create an account, you can ignore this email.\n\n"
            "— Login Portal"
        )
    else:
        subject = "Reset your password — Login Portal"
        body = (
            f"Hi {user.first_name or 'there'},\n\n"
            f"Your Login Portal password reset code is: {code}\n\n"
            f"It expires in {OTP_TTL.seconds // 60} minutes. If you did not "
            "request a password reset, you can ignore this email — your "
            "password stays unchanged.\n\n"
            "— Login Portal"
        )
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email])


def latest_active(user, purpose: str):
    """The newest unconsumed, unexpired OTP for (user, purpose), or None."""
    return (
        EmailOTP.objects.filter(
            user=user,
            purpose=purpose,
            consumed_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        .order_by("-created_at", "-id")
        .first()
    )


def issue_otp(user, purpose: str) -> EmailOTP:
    """Create a fresh OTP, send it, and invalidate any predecessor."""
    now = timezone.now()
    # Only the latest code may work: mark unconsumed predecessors consumed.
    EmailOTP.objects.filter(
        user=user, purpose=purpose, consumed_at__isnull=True
    ).update(consumed_at=now)
    code = generate_code()
    otp = EmailOTP.objects.create(
        user=user,
        purpose=purpose,
        code_hash=_hash_code(code),
        expires_at=now + OTP_TTL,
        last_sent_at=now,
    )
    _send_otp_email(user, purpose, code)
    _purge_old()
    return otp


def request_otp(user, purpose: str) -> bool:
    """Send an OTP unless the resend cooldown is still active.

    Returns True when an email was sent. Callers must return a generic
    response either way (enumeration safety).
    """
    existing = latest_active(user, purpose)
    if (
        existing
        and existing.last_sent_at
        and timezone.now() - existing.last_sent_at < OTP_RESEND_COOLDOWN
    ):
        return False
    issue_otp(user, purpose)
    return True


def verify_otp(user, purpose: str, code: str) -> bool:
    """Constant-time compare against the active OTP; consume on success.

    Wrong guesses increment the attempt counter atomically; after
    OTP_MAX_ATTEMPTS the OTP is dead. Consumption is an atomic UPDATE guarded
    on ``consumed_at IS NULL``, so single-use holds under concurrency.
    """
    code = (code or "").strip()
    otp = latest_active(user, purpose)
    if otp is None or otp.attempts >= OTP_MAX_ATTEMPTS or not code:
        return False
    if not hmac.compare_digest(otp.code_hash, _hash_code(code)):
        EmailOTP.objects.filter(pk=otp.pk, consumed_at__isnull=True).update(
            attempts=F("attempts") + 1
        )
        return False
    consumed = EmailOTP.objects.filter(pk=otp.pk, consumed_at__isnull=True).update(
        consumed_at=timezone.now()
    )
    return consumed == 1
