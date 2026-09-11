"""DRF throttles: atomic fixed-window counters and scoped rate limits."""

import hashlib
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


def credential_throttle_key(prefix: str, email: str, ident: str) -> str:
    """Build a fixed-length throttle cache key.

    A valid email can be up to 254 chars and an IPv6 address up to 45, so the
    naive ``f"{prefix}:{email}:{ident}"`` key can exceed the cache table's
    ``varchar(255)`` key column. The resulting ``DataError`` is swallowed by
    the cache backend (fail-closed), permanently locking that email + IP out.
    Hashing the email keeps the key well under the limit for any input.
    """
    digest = hashlib.sha256(email.encode("utf-8")).hexdigest()[:32]
    return f"{prefix}:{digest}:{ident}"


class FixedWindowThrottle(BaseThrottle):
    """Shared atomic fixed-window counter for credential/OTP endpoints."""

    timer = time.time

    def _allow(self, key_prefix: str, max_attempts: int, window_seconds: int) -> bool:
        now = self.timer()
        bucket = int(now // window_seconds)
        key = f"{key_prefix}:{bucket}"

        self.reset_at = (bucket + 1) * window_seconds
        try:
            if cache.add(key, 1, window_seconds):
                count = 1
            else:
                count = cache.incr(key)
        except (ValueError, DatabaseError):
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
    """Per-credential login throttle (email + IP) to stop stuffing one account."""

    def allow_request(self, request, view):
        ident = self.get_ident(request)

        data = request.data
        email = (data.get("email") or "").strip().lower() if hasattr(data, "get") else ""
        return self._allow(
            credential_throttle_key("login-throttle", email, ident),
            settings.LOGIN_THROTTLE_MAX_ATTEMPTS,
            settings.LOGIN_THROTTLE_WINDOW_SECONDS,
        )


class LoginIPThrottle(AnonRateThrottle):
    """Per-IP login cap: bounds credential stuffing across many accounts."""

    scope = "login_ip"


class RegisterThrottle(AnonRateThrottle):
    scope = "register"


class GoogleLoginThrottle(AnonRateThrottle):
    """Per-IP cap on Google Sign-In attempts."""

    scope = "google_login"


class OTPRequestThrottle(FixedWindowThrottle):
    """Per (email + IP) cap on OTP email requests (verify resend, reset request)."""

    def allow_request(self, request, view):
        ident = self.get_ident(request)
        data = request.data
        email = (data.get("email") or "").strip().lower() if hasattr(data, "get") else ""
        return self._allow(
            credential_throttle_key("otp-request-throttle", email, ident),
            settings.OTP_REQUEST_MAX,
            settings.OTP_REQUEST_WINDOW_SECONDS,
        )


class OTPIPRequestThrottle(AnonRateThrottle):
    """Per-IP cap on OTP email sends, complementing OTPRequestThrottle."""

    scope = "otp_request_ip"


class OTPVerifyThrottle(AnonRateThrottle):
    """Per-IP cap on OTP verification attempts."""

    scope = "otp_verify"


class DownloadThrottle(ScopedRateThrottle):
    """Per-IP cap on signed document downloads (unauthenticated endpoint)."""

    def get_cache_key(self, request, view):
        return f"download-throttle:anon:{self.get_ident(request)}"


class WriteThrottle(ScopedRateThrottle):
    """User-scoped throttle for state-changing endpoints (uploads, submit, review)."""

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return f"write-throttle:{request.user.pk}:{self.scope}"

        ident = self.get_ident(request)
        return f"write-throttle:anon:{ident}:{self.scope}"


def throttled_exception_handler(exc, context):
    """DRF exception handler that adds Retry-After to throttled (429) responses."""
    response = exception_handler(exc, context)
    if isinstance(exc, Throttled) and response is not None and exc.wait:
        response["Retry-After"] = str(math.ceil(exc.wait))
    return response
