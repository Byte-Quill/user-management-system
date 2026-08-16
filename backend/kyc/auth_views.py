"""JWT auth views that store the refresh token in an HttpOnly cookie.

Why: keeping refresh tokens in `localStorage` (the previous design) exposes
them to any XSS payload. Access tokens stay in memory on the client; the
long-lived refresh token lives in an HttpOnly, SameSite-protected cookie that
JavaScript cannot read.

CSRF mitigation: endpoints that authenticate via the cookie validate the
`Origin` header against the configured CORS origins. A cross-site request from
an attacker's page sends the cookie but fails the Origin check.
"""
import logging
import re
from urllib.parse import urlparse

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import EmailTokenObtainPairSerializer
from .throttles import LoginThrottle

logger = logging.getLogger("kyc.auth")

COOKIE_NAME = getattr(settings, "JWT_AUTH_COOKIE", "refresh_token")


def _cookie_kwargs() -> dict:
    return {
        "httponly": True,
        "secure": getattr(settings, "JWT_AUTH_COOKIE_SECURE", not settings.DEBUG),
        "samesite": getattr(settings, "JWT_AUTH_COOKIE_SAMESITE", "Lax"),
        "path": getattr(settings, "JWT_AUTH_COOKIE_PATH", "/"),
        "max_age": getattr(settings, "JWT_AUTH_COOKIE_MAX_AGE", None),
    }


def _set_refresh_cookie(response: Response, refresh: str) -> None:
    response.set_cookie(COOKIE_NAME, refresh, **_cookie_kwargs())


def _delete_refresh_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path=getattr(settings, "JWT_AUTH_COOKIE_PATH", "/"))


def origin_allowed(request) -> bool:
    """Return True when the request Origin (if any) is safe for cookie auth.

    Allowed: no Origin header (non-browser clients), same-origin requests
    (inherently not a CSRF vector — the Origin matches the request's own
    Host), and explicitly configured CORS origins.
    """
    origin = request.headers.get("Origin")
    if not origin:
        # Non-browser client (curl, mobile). Not a CSRF vector.
        return True
    # Same-origin: the SPA and API share a host (e.g. nginx proxying /api).
    parsed = urlparse(origin)
    if parsed.netloc == request.get_host():
        return True
    allowed = set(getattr(settings, "CORS_ALLOWED_ORIGINS", []))
    if origin in allowed:
        return True
    for pattern in getattr(settings, "CORS_ALLOWED_ORIGIN_REGEXES", []):
        if re.match(pattern, origin):
            return True
    return False


class CookieTokenObtainPairView(TokenObtainPairView):
    """Login: return the access token in the body, refresh token in a cookie."""

    serializer_class = EmailTokenObtainPairSerializer
    throttle_classes = [LoginThrottle]

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            refresh = response.data.pop("refresh", None)
            if refresh:
                _set_refresh_cookie(response, refresh)
        return response


class CookieTokenRefreshView(TokenRefreshView):
    """Refresh: read the refresh token from the cookie (body as fallback)."""

    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        if not origin_allowed(request):
            logger.warning("Refresh rejected: disallowed Origin %s", request.headers.get("Origin"))
            return Response(
                {"detail": "Cross-origin refresh is not allowed."},
                status=status.HTTP_403_FORBIDDEN,
            )
        # Fall back to the body token when the cookie is absent (API clients).
        refresh = request.COOKIES.get(COOKIE_NAME) or request.data.get("refresh")
        if not refresh:
            # No token anywhere: treat as unauthenticated, not a validation error.
            return Response(
                {"detail": "No refresh token provided."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if request.COOKIES.get(COOKIE_NAME):
            data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
            data["refresh"] = request.COOKIES[COOKIE_NAME]
            request._full_data = data
        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            new_refresh = response.data.pop("refresh", None)
            if new_refresh:
                _set_refresh_cookie(response, new_refresh)
        elif response.status_code == status.HTTP_401_UNAUTHORIZED:
            # Rotated/expired token: clear the stale cookie.
            _delete_refresh_cookie(response)
        return response


class LogoutView(APIView):
    """Blacklist the refresh token and clear the auth cookie."""

    permission_classes = (AllowAny,)

    def post(self, request):
        refresh = request.COOKIES.get(COOKIE_NAME) or request.data.get("refresh")
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except TokenError as exc:
                logger.info("Logout with invalid/expired token: %s", exc)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        _delete_refresh_cookie(response)
        return response
