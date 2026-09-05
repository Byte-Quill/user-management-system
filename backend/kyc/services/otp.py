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
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from kyc.models import EmailLog, EmailOTP

logger = logging.getLogger("kyc.otp")

User = get_user_model()

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
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email])
    except Exception:
        # Record the failure for the CEO email-activity panel, then re-raise
        # so the caller's existing outage handling (log + generic response)
        # still applies.
        _log_email(user, purpose, subject, EmailLog.Status.FAILED)
        raise
    _log_email(user, purpose, subject, EmailLog.Status.SENT)


def _log_email(user, purpose: str, subject: str, status: str) -> None:
    """Append to EmailLog; a logging failure must never break the send path."""
    try:
        EmailLog.objects.create(
            user=user, purpose=purpose, recipient=user.email, subject=subject, status=status
        )
    except Exception:
        logger.exception("Failed to write EmailLog entry")


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


def _issue_otp_db(user, purpose: str):
    """DB-only issuance: invalidate predecessors and create the new row.

    Returns ``(otp, code)``. Callers must hold the per-user lock (see
    ``issue_otp`` / ``request_otp``) and send the email only after the
    transaction commits, so an HTTP send never holds a DB connection or lock.
    """
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
    return otp, code


def issue_otp(user, purpose: str) -> EmailOTP:
    """Create a fresh OTP, send it, and invalidate any predecessor."""
    with transaction.atomic():
        # Row lock on the user: concurrent issuances for the same user
        # serialize, so they cannot both invalidate each other's predecessor.
        User.objects.select_for_update().get(pk=user.pk)
        otp, code = _issue_otp_db(user, purpose)
    _send_otp_email(user, purpose, code)
    _purge_old()
    return otp


def request_otp(user, purpose: str) -> bool:
    """Send an OTP unless the resend cooldown is still active.

    Returns True when an email was sent. Callers must return a generic
    response either way (enumeration safety).
    """
    code = None
    with transaction.atomic():
        # Row lock on the user: the cooldown check and the issuance happen
        # atomically, so two concurrent resend requests cannot both pass the
        # check and double-send.
        User.objects.select_for_update().get(pk=user.pk)
        existing = latest_active(user, purpose)
        if (
            existing
            and existing.last_sent_at
            and timezone.now() - existing.last_sent_at < OTP_RESEND_COOLDOWN
        ):
            return False
        _, code = _issue_otp_db(user, purpose)
    # Send outside the transaction/lock (see _issue_otp_db).
    _send_otp_email(user, purpose, code)
    _purge_old()
    return True


def verify_otp(user, purpose: str, code: str) -> bool:
    """Constant-time compare against the active OTP; consume on success.

    Every attempt — including the successful one — claims a slot from the
    attempt counter with a conditional atomic UPDATE, so the cap check is
    part of the write itself and N concurrent wrong guesses cannot overshoot
    OTP_MAX_ATTEMPTS via a stale read. Consumption is an atomic UPDATE
    guarded on ``consumed_at IS NULL``, so single-use holds under concurrency.
    """
    code = (code or "").strip()
    otp = latest_active(user, purpose)
    if otp is None or not code:
        return False
    # Claim an attempt slot atomically: the attempts__lt guard makes the cap
    # check and the increment a single statement, so racing verifications
    # cannot all pass the old read-then-increment check.
    claimed = EmailOTP.objects.filter(
        pk=otp.pk, consumed_at__isnull=True, attempts__lt=OTP_MAX_ATTEMPTS
    ).update(attempts=F("attempts") + 1)
    if not claimed:
        return False
    if not hmac.compare_digest(otp.code_hash, _hash_code(code)):
        return False
    consumed = EmailOTP.objects.filter(pk=otp.pk, consumed_at__isnull=True).update(
        consumed_at=timezone.now()
    )
    return consumed == 1
