"""Access control for the KYC API: role/ownership permissions and throttles."""
import math
import time

from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import Throttled
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.throttling import AnonRateThrottle, BaseThrottle, ScopedRateThrottle
from rest_framework.views import exception_handler

# --- Permissions -----------------------------------------------------------


class IsReviewer(BasePermission):
    """Allow access only to reviewers/admins."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_reviewer)


class IsOwnerOrReviewer(BasePermission):
    """Applicants can access their own applications; reviewers can access all (read-only)."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        # Reviewers are read-only on application resources
        if request.user.is_reviewer and request.method not in SAFE_METHODS:
            return False
        return True

    def has_object_permission(self, request, view, obj):
        if request.user.is_reviewer:
            # Reviewers can only read (has_permission already blocks writes)
            return request.method in SAFE_METHODS
        return obj.applicant_id == request.user.id


# --- Throttles -------------------------------------------------------------

# Login attempts are bounded two ways: per credential (email + IP) to stop a
# single account being stuffed, and per IP ("login_ip" scope) to stop a single
# address rotating through many accounts. Counters live in the Postgres-backed
# cache, so they are shared across all gunicorn workers.


class LoginThrottle(BaseThrottle):
    """Per-credential login throttle (email + IP) to stop stuffing one account.

    Keying on email alone would let an attacker distribute attempts across
    many accounts; keying on IP alone would poison a shared proxy/NAT address
    for everyone behind it. Using both bounds both attacks. Fixed window of
    LOGIN_THROTTLE_MAX_ATTEMPTS per LOGIN_THROTTLE_WINDOW_SECONDS.
    """

    timer = time.time

    def allow_request(self, request, view):
        ident = self.get_ident(request)
        # request.data may be a dict (JSON) or a QueryDict (form/multipart).
        data = request.data
        email = (data.get("email") or "").strip().lower() if hasattr(data, "get") else ""
        self.key = f"login-throttle:{email}:{ident}"
        now = self.timer()
        entry = cache.get(self.key)
        # Guard against legacy/foreign cache values (older code stored a bare
        # int); treat anything unexpected as a fresh window.
        if not isinstance(entry, dict) or entry.get("reset", 0) <= now:
            entry = {"count": 0, "reset": now + settings.LOGIN_THROTTLE_WINDOW_SECONDS}
        self.reset_at = entry["reset"]
        if entry["count"] >= settings.LOGIN_THROTTLE_MAX_ATTEMPTS:
            return False
        entry["count"] += 1
        cache.set(self.key, entry, settings.LOGIN_THROTTLE_WINDOW_SECONDS)
        return True

    def wait(self):
        """Seconds until the window resets (surfaced in the Retry-After header)."""
        reset_at = getattr(self, "reset_at", None)
        if reset_at is None:
            return None
        return max(0.0, reset_at - self.timer())


class LoginIPThrottle(AnonRateThrottle):
    """Per-IP login cap: bounds credential stuffing across many accounts."""

    scope = "login_ip"


class RegisterThrottle(AnonRateThrottle):
    scope = "register"


class DownloadThrottle(ScopedRateThrottle):
    """Per-IP cap on signed document downloads (unauthenticated endpoint).

    Generous enough for a reviewer opening many files, but bounds scraping /
    DoS of the file-serving path. Keyed by IP since downloads carry no JWT.
    """

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return f"download-throttle:{request.user.pk}"
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


# --- 429 handling -----------------------------------------------------------


def throttled_exception_handler(exc, context):
    """DRF exception handler that adds Retry-After to throttled (429) responses.

    RFC 6585: clients can use the header to schedule a retry instead of
    hammering an endpoint that is still throttled.
    """
    response = exception_handler(exc, context)
    if isinstance(exc, Throttled) and response is not None and exc.wait:
        response["Retry-After"] = str(math.ceil(exc.wait))
    return response
