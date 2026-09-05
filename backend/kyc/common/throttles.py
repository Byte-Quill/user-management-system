"""DRF throttles: atomic fixed-window counters and scoped rate limits."""
import logging
import math
import time

from django.conf import settings
from django.core.cache import cache
from django.db import DatabaseError
from rest_framework.exceptions import Throttled
from rest_framework.throttling import AnonRateThrottle, BaseThrottle, ScopedRateThrottle
from rest_framework.views import exception_handler

logger = logging.getLogger("kyc.access")

class FixedWindowThrottle(BaseThrottle):
    """Shared atomic fixed-window counter for credential/OTP endpoints.

    The counter is a single integer per (bucket, identifier). ``cache.add()``
    creates the slot race-free and ``cache.incr()`` bumps it under a row lock
    (see ``kyc.common.cache.LightweightDatabaseCache.incr``), so concurrent workers
    cannot overshoot the cap the way a get-then-set window can. Windows are
    deterministic clock buckets, so no per-client reset bookkeeping is needed.
    """

    timer = time.time

    def _allow(self, key_prefix: str, max_attempts: int, window_seconds: int) -> bool:
        now = self.timer()
        bucket = int(now // window_seconds)
        key = f"{key_prefix}:{bucket}"
        # Absolute epoch time the current bucket rolls over (Retry-After).
        self.reset_at = (bucket + 1) * window_seconds
        try:
            # Seed the counter at 1 so the first attempt counts — seeding at 0
            # would let max_attempts+1 requests through per window.
            if cache.add(key, 1, window_seconds):
                count = 1  # this request opened the window
            else:
                count = cache.incr(key)
        except (ValueError, DatabaseError):
            # The slot expired/vanished between add() and incr(), or cache
            # writes are failing (DB outage). Retry the add: if it still
            # fails, fail CLOSED — an uncounted login/OTP endpoint is an
            # unbounded brute-force/email-bomb surface exactly when the
            # system is degraded.
            logger.warning("%s throttle counter unavailable; denying request", key_prefix)
            if not cache.add(key, 1, window_seconds):
                return False
            count = 1
        return count <= max_attempts

    def wait(self):
        """Seconds until the window resets (surfaced in the Retry-After header)."""
        reset_at = getattr(self, "reset_at", None)
        if reset_at is None:
            return None
        return max(0.0, reset_at - self.timer())


class LoginThrottle(FixedWindowThrottle):
    """Per-credential login throttle (email + IP) to stop stuffing one account.

    Keying on email alone lets an attacker distribute attempts across many
    accounts; keying on IP alone poisons a shared proxy/NAT address. Fixed
    window of LOGIN_THROTTLE_MAX_ATTEMPTS per LOGIN_THROTTLE_WINDOW_SECONDS;
    every attempt counts, successful logins included.
    """

    def allow_request(self, request, view):
        ident = self.get_ident(request)
        # request.data may be a dict (JSON) or a QueryDict (form/multipart).
        data = request.data
        email = (data.get("email") or "").strip().lower() if hasattr(data, "get") else ""
        return self._allow(
            f"login-throttle:{email}:{ident}",
            settings.LOGIN_THROTTLE_MAX_ATTEMPTS,
            settings.LOGIN_THROTTLE_WINDOW_SECONDS,
        )


class LoginIPThrottle(AnonRateThrottle):
    """Per-IP login cap: bounds credential stuffing across many accounts."""

    scope = "login_ip"


class RegisterThrottle(AnonRateThrottle):
    scope = "register"


class GoogleLoginThrottle(AnonRateThrottle):
    """Per-IP cap on Google Sign-In attempts.

    Every attempt costs an RSA signature verification plus a fetch of
    Google's public keys, so the endpoint is bounded per IP.
    """

    scope = "google_login"


class OTPRequestThrottle(FixedWindowThrottle):
    """Per (email + IP) cap on OTP email requests (verify resend, reset request).

    Email sending costs money, so an unbounded endpoint would be an email
    bomb aimed at arbitrary inboxes. Fixed window of OTP_REQUEST_MAX per
    OTP_REQUEST_WINDOW_SECONDS.
    """

    def allow_request(self, request, view):
        ident = self.get_ident(request)
        data = request.data
        email = (data.get("email") or "").strip().lower() if hasattr(data, "get") else ""
        return self._allow(
            f"otp-request-throttle:{email}:{ident}",
            settings.OTP_REQUEST_MAX,
            settings.OTP_REQUEST_WINDOW_SECONDS,
        )


class OTPVerifyThrottle(AnonRateThrottle):
    """Per-IP cap on OTP verification attempts.

    The per-OTP attempt counter (5) already bounds brute force of one code;
    this additionally bounds rotation across many OTPs/emails from one IP.
    """

    scope = "otp_verify"


class DownloadThrottle(ScopedRateThrottle):
    """Per-IP cap on signed document downloads (unauthenticated endpoint).

    Generous enough for a reviewer opening many files, but bounds scraping /
    DoS of the file-serving path; requests are always anonymous, so the
    counter is keyed by IP.
    """

    def get_cache_key(self, request, view):
        return f"download-throttle:anon:{self.get_ident(request)}"


class WriteThrottle(ScopedRateThrottle):
    """User-scoped throttle for state-changing endpoints (uploads, submit, review)."""

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            # Key per user, not per IP: NAT/proxy users should not be pooled.
            return f"write-throttle:{request.user.pk}:{self.scope}"
        # Anonymous fallback: throttle by IP to prevent unauthenticated DoS.
        ident = self.get_ident(request)
        return f"write-throttle:anon:{ident}:{self.scope}"


def throttled_exception_handler(exc, context):
    """DRF exception handler that adds Retry-After to throttled (429) responses."""
    response = exception_handler(exc, context)
    if isinstance(exc, Throttled) and response is not None and exc.wait:
        response["Retry-After"] = str(math.ceil(exc.wait))
    return response
