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

import requests
from allauth.account.models import EmailAddress
from allauth.socialaccount.adapter import get_adapter as get_socialaccount_adapter
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.providers.oauth2.client import OAuth2Error
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .access import GoogleLoginThrottle, LoginIPThrottle, LoginThrottle
from .models import generate_user_id
from .serializers import EmailTokenObtainPairSerializer

logger = logging.getLogger("kyc.auth")

User = get_user_model()

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
    host), and explicitly configured CORS origins.
    """
    origin = request.headers.get("Origin")
    if not origin:
        # Non-browser client (curl, mobile). Not a CSRF vector.
        return True
    # Same-origin: the SPA and API share an origin (e.g. nginx proxying
    # /api). Rebuild the request's own origin from scheme + host (incl.
    # port, honoring SECURE_PROXY_SSL_HEADER) instead of comparing the
    # Origin's netloc to the Host header: browsers include non-standard
    # ports in Origin ("http://host:8080") while a proxy may forward the
    # Host header without one, and netloc equality would then reject a
    # legitimate same-origin refresh.
    if origin == f"{request.scheme}://{request.get_host()}":
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
    # Per-credential window (email + IP) plus a per-IP cap that bounds
    # credential stuffing across many accounts from one address.
    throttle_classes = [LoginThrottle, LoginIPThrottle]

    def post(self, request, *args, **kwargs):
        # Login CSRF: DRF views are csrf_exempt, and a successful login SETS
        # the refresh cookie (SameSite never blocks setting). Without an Origin
        # check, an attacker's auto-submitting form could silently log a victim
        # into an attacker-controlled account and harvest their KYC uploads.
        if not origin_allowed(request):
            logger.warning("Login rejected: disallowed Origin %s", request.headers.get("Origin"))
            return Response(
                {"detail": "Cross-origin login is not allowed."},
                status=status.HTTP_403_FORBIDDEN,
            )
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
        # Logout CSRF: with SameSite=None (HTTPS deploys) a cross-site POST
        # would send the victim's cookie and blacklist their refresh token.
        if not origin_allowed(request):
            logger.warning("Logout rejected: disallowed Origin %s", request.headers.get("Origin"))
            return Response(
                {"detail": "Cross-origin logout is not allowed."},
                status=status.HTTP_403_FORBIDDEN,
            )
        refresh = request.COOKIES.get(COOKIE_NAME) or request.data.get("refresh")
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except TokenError as exc:
                logger.info("Logout with invalid/expired token: %s", exc)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        _delete_refresh_cookie(response)
        return response


def _resolve_google_user(request, sociallogin):
    """Return the local user for a verified Google login, creating/linking as needed.

    Resolution order:
      1. An existing SocialAccount for (google, uid) -> its user.
      2. An existing local user with the same (Google-verified) email -> link.
         Google proved ownership of the email, so linking is safe. Refuse if
         that user already has a *different* Google account linked.
      3. Otherwise create a new applicant with an unusable password.

    Callers retry on IntegrityError to absorb create/link races.
    """
    provider = sociallogin.account.provider
    uid = sociallogin.account.uid

    existing = (
        SocialAccount.objects.filter(provider=provider, uid=uid)
        .select_related("user")
        .first()
    )
    if existing:
        return existing.user

    email = sociallogin.user.email
    user = User.objects.filter(email__iexact=email).first()
    if user:
        other_google = SocialAccount.objects.filter(user=user, provider=provider).exists()
        if other_google:
            raise DjangoValidationError(
                "This account is already linked to a different Google identity."
            )
        with transaction.atomic():
            SocialAccount.objects.create(
                user=user, provider=provider, uid=uid,
                extra_data=sociallogin.account.extra_data,
            )
        return user

    # New applicant. Auto-generate the public User ID (users never pick one).
    with transaction.atomic():
        user = User.objects.create_user(
            email=email,
            username=generate_user_id(),
            password=None,  # unusable: Google is the credential
            first_name=sociallogin.user.first_name,
            last_name=sociallogin.user.last_name,
            role=User.Role.APPLICANT,
        )
        SocialAccount.objects.create(
            user=user, provider=provider, uid=uid,
            extra_data=sociallogin.account.extra_data,
        )
        # Record the Google-verified address so allauth's email bookkeeping
        # (and future email-based lookups) sees it as verified + primary.
        has_primary = EmailAddress.objects.filter(user=user, primary=True).exists()
        EmailAddress.objects.get_or_create(
            user=user, email=email.lower(),
            defaults={"verified": True, "primary": not has_primary},
        )
    return user


class GoogleAuthView(APIView):
    """Google Sign-In: exchange a Google ID token for our JWT session.

    The SPA's Google button posts the OIDC ``credential`` (ID token). allauth's
    Google provider verifies it (signature against Google's public keys, issuer,
    audience = GOOGLE_CLIENT_ID, expiry, and jti replay via the cache), then we
    resolve or provision the local user and issue the same SimpleJWT pair used
    by password login: access token in the body, refresh token in the HttpOnly
    cookie. No Django session is created; the session model is unchanged.
    """

    permission_classes = (AllowAny,)
    throttle_classes = [GoogleLoginThrottle]

    def post(self, request, *args, **kwargs):
        # Login CSRF: this endpoint SETS the refresh cookie. Without an Origin
        # check an attacker's page could silently log a victim into an
        # attacker-controlled account. Same policy as password login.
        if not origin_allowed(request):
            logger.warning(
                "Google login rejected: disallowed Origin %s", request.headers.get("Origin")
            )
            return Response(
                {"detail": "Cross-origin login is not allowed."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not getattr(settings, "GOOGLE_CLIENT_ID", ""):
            logger.error("Google login attempted but GOOGLE_CLIENT_ID is not configured")
            return Response(
                {"detail": "Google Sign-In is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        credential = request.data.get("credential")
        if not credential or not isinstance(credential, str):
            return Response(
                {"detail": "Missing Google credential."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            provider = get_socialaccount_adapter().get_provider(request, "google")
            sociallogin = provider.verify_token(request, {"id_token": credential})
        except (OAuth2Error, DjangoValidationError, requests.RequestException, ValueError) as exc:
            logger.info("Google ID token verification failed: %s", exc)
            return Response(
                {"detail": "Invalid Google credential."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Require a Google-verified email before trusting it for linking.
        verified = [ea for ea in sociallogin.email_addresses if ea.verified]
        email = sociallogin.user.email
        if not email or not any(ea.email.lower() == email.lower() for ea in verified):
            return Response(
                {"detail": "Google account has no verified email."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = None
        for _ in range(2):
            try:
                with transaction.atomic():
                    user = _resolve_google_user(request, sociallogin)
                break
            except IntegrityError:
                # Concurrent first-login/link race: retry the lookup.
                continue
            except DjangoValidationError as exc:
                return Response({"detail": exc.messages[0]}, status=status.HTTP_409_CONFLICT)
        if user is None:
            return Response(
                {"detail": "Could not sign in with Google."},
                status=status.HTTP_409_CONFLICT,
            )

        if not user.is_active:
            return Response(
                {"detail": "This account is disabled."},
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)
        response = Response({"access": str(refresh.access_token)})
        _set_refresh_cookie(response, str(refresh))
        return response
