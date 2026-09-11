"""JWT auth views that store the refresh token in an HttpOnly cookie."""
import logging
import re

import requests
from allauth.account.models import EmailAddress
from allauth.socialaccount.adapter import get_adapter as get_socialaccount_adapter
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.providers.oauth2.client import OAuth2Error
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.utils import get_md5_hash_password
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from kyc.common.throttles import (
    GoogleLoginThrottle,
    LoginIPThrottle,
    LoginThrottle,
    OTPIPRequestThrottle,
    OTPRequestThrottle,
    OTPVerifyThrottle,
    RegisterThrottle,
)
from kyc.common.tokens import revoke_user_sessions
from kyc.models import EmailOTP, generate_user_id
from kyc.serializers import EmailTokenObtainPairSerializer, RegisterSerializer
from kyc.services.otp import issue_otp, request_otp, verify_otp

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


def _reject_cross_origin(request, action: str) -> Response | None:
    """403 for disallowed Origins on cookie-setting/-sending endpoints, else None."""
    if origin_allowed(request):
        return None
    logger.warning("%s rejected: disallowed Origin %s", action, request.headers.get("Origin"))
    return Response(
        {"detail": f"Cross-origin {action} is not allowed."},
        status=status.HTTP_403_FORBIDDEN,
    )


def origin_allowed(request) -> bool:
    """Return True when the request Origin (if any) is safe for cookie auth."""
    origin = request.headers.get("Origin")
    if not origin:

        return True

    if origin == f"{request.scheme}://{request.get_host()}":
        return True
    allowed = set(getattr(settings, "CORS_ALLOWED_ORIGINS", []))
    if origin in allowed:
        return True
    for pattern in getattr(settings, "CORS_ALLOWED_ORIGIN_REGEXES", []):

        if re.fullmatch(pattern, origin):
            return True
    return False


class CookieTokenObtainPairView(TokenObtainPairView):
    """Login: return the access token in the body, refresh token in a cookie."""

    serializer_class = EmailTokenObtainPairSerializer

    throttle_classes = [LoginThrottle, LoginIPThrottle]

    def post(self, request, *args, **kwargs):

        if (rejected := _reject_cross_origin(request, "login")) is not None:
            return rejected
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
        if (rejected := _reject_cross_origin(request, "refresh")) is not None:
            return rejected

        refresh = request.COOKIES.get(COOKIE_NAME) or request.data.get("refresh")
        if not refresh:

            return Response(
                {"detail": "No refresh token provided."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if request.COOKIES.get(COOKIE_NAME):
            data = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
            data["refresh"] = request.COOKIES[COOKIE_NAME]
            request._full_data = data

        if jwt_settings.CHECK_REVOKE_TOKEN and request.data.get("refresh"):
            try:
                token = RefreshToken(request.data["refresh"])
            except TokenError:
                token = None
            if token is not None:
                user = User.objects.filter(pk=token["user_id"]).first()
                if (
                    user is None
                    or token.get(jwt_settings.REVOKE_TOKEN_CLAIM)
                    != get_md5_hash_password(user.password)
                ):
                    logger.warning(
                        "Refresh rejected after password change for user %s",
                        token["user_id"],
                    )
                    response = Response(
                        {"detail": "Token is invalid or expired"},
                        status=status.HTTP_401_UNAUTHORIZED,
                    )
                    _delete_refresh_cookie(response)
                    return response
        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            new_refresh = response.data.pop("refresh", None)
            if new_refresh:
                _set_refresh_cookie(response, new_refresh)
        elif response.status_code == status.HTTP_401_UNAUTHORIZED:

            _delete_refresh_cookie(response)
        return response


class LogoutView(APIView):
    """Blacklist the refresh token and clear the auth cookie."""

    permission_classes = (AllowAny,)

    def post(self, request):

        if (rejected := _reject_cross_origin(request, "logout")) is not None:
            return rejected
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
    """Return the local user for a verified Google login, creating/linking as needed."""
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

            if not user.email_verified:
                user.email_verified = True
                user.save(update_fields=["email_verified"])
        return user

    with transaction.atomic():
        user = User.objects.create_user(
            email=email,
            username=generate_user_id(),
            password=None,
            first_name=sociallogin.user.first_name,
            last_name=sociallogin.user.last_name,
            role=User.Role.APPLICANT,

            email_verified=True,
        )
        SocialAccount.objects.create(
            user=user, provider=provider, uid=uid,
            extra_data=sociallogin.account.extra_data,
        )

        has_primary = EmailAddress.objects.filter(user=user, primary=True).exists()
        EmailAddress.objects.get_or_create(
            user=user, email=email.lower(),
            defaults={"verified": True, "primary": not has_primary},
        )
    return user


class GoogleAuthView(APIView):
    """Google Sign-In: exchange a Google ID token for our JWT session."""

    permission_classes = (AllowAny,)
    throttle_classes = [GoogleLoginThrottle]

    def post(self, request, *args, **kwargs):

        if (rejected := _reject_cross_origin(request, "login")) is not None:
            return rejected

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


def _find_user_by_email(email: str):
    email = (email or "").strip().lower()
    if not email:
        return None
    return User.objects.filter(email__iexact=email).first()


class VerifyEmailView(APIView):
    """Verify the signup OTP and unlock the account for password login."""

    permission_classes = (AllowAny,)
    throttle_classes = [OTPVerifyThrottle]

    def post(self, request):
        email = (request.data.get("email") or "").strip()
        code = (request.data.get("code") or "").strip()
        if not email or not code:
            return Response(
                {"detail": "Email and code are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = _find_user_by_email(email)
        if user is None or not verify_otp(
            user, EmailOTP.Purpose.VERIFY_EMAIL, code
        ):
            return Response(
                {"detail": "Invalid or expired code."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not user.email_verified:
            user.email_verified = True
            user.save(update_fields=["email_verified"])
        return Response({"detail": "Email verified. You can sign in now."})


class ResendVerificationView(APIView):
    """Resend the signup OTP (generic 200; cooldown enforced server-side)."""

    permission_classes = (AllowAny,)

    throttle_classes = [OTPRequestThrottle, OTPIPRequestThrottle]

    def post(self, request):
        user = _find_user_by_email(request.data.get("email"))
        if user is not None and not user.email_verified:
            try:
                request_otp(user, EmailOTP.Purpose.VERIFY_EMAIL)
            except Exception:

                logger.exception("Verification resend failed for user %s", user.pk)
        return Response({"detail": "If the account needs verification, a code was sent."})


class PasswordResetRequestView(APIView):
    """Send a password-reset OTP (generic 200; works for Google-only users)."""

    permission_classes = (AllowAny,)
    throttle_classes = [OTPRequestThrottle, OTPIPRequestThrottle]

    def post(self, request):
        user = _find_user_by_email(request.data.get("email"))
        if user is not None:
            try:
                request_otp(user, EmailOTP.Purpose.RESET_PASSWORD)
            except Exception:

                logger.exception("Password-reset OTP send failed for user %s", user.pk)
        return Response(
            {"detail": "If an account exists for that email, a reset code was sent."}
        )


class PasswordResetConfirmView(APIView):
    """Consume the reset OTP and set a new password."""

    permission_classes = (AllowAny,)
    throttle_classes = [OTPVerifyThrottle]

    def post(self, request):
        email = (request.data.get("email") or "").strip()
        code = (request.data.get("code") or "").strip()
        password = request.data.get("new_password") or ""
        if not email or not code or not password:
            return Response(
                {"detail": "Email, code and new password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = _find_user_by_email(email)
        if user is None or not verify_otp(
            user, EmailOTP.Purpose.RESET_PASSWORD, code
        ):
            return Response(
                {"detail": "Invalid or expired code."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            validate_password(password, user=user)
        except DjangoValidationError as exc:
            return Response(
                {"new_password": exc.messages}, status=status.HTTP_400_BAD_REQUEST
            )
        user.set_password(password)
        if not user.email_verified:
            user.email_verified = True
        user.save(update_fields=["password", "email_verified"])
        # Invalidate refresh tokens issued before the reset so a captured
        # refresh cookie cannot outlive the password change.
        revoke_user_sessions(user)
        return Response({"detail": "Password updated. You can sign in now."})


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = (AllowAny,)
    throttle_classes = (RegisterThrottle,)

    def perform_create(self, serializer):

        try:
            user = serializer.save()
        except IntegrityError as exc:

            raise ValidationError(
                "An account with these details already exists."
            ) from exc

        if not user.email:
            return
        try:
            issue_otp(user, EmailOTP.Purpose.VERIFY_EMAIL)
        except Exception:

            logger.exception("Failed to send verification email to %s", user.email)
