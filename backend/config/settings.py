"""Django settings for the KYC-V3 backend."""
import os
import sys
import urllib.parse
from datetime import timedelta
from pathlib import Path

from django.utils.csp import CSP
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

_BUILD_TIME_SENTINEL = "django-insecure-build-time-only-key-not-for-production"
_KNOWN_WEAK_SECRETS = {
    _BUILD_TIME_SENTINEL,
    "change-me-in-production",
    "change-me",
    "secret",
    "django-insecure",
}
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or _BUILD_TIME_SENTINEL
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"

if not DEBUG and (
    SECRET_KEY in _KNOWN_WEAK_SECRETS or len(SECRET_KEY) < 50
):
    raise RuntimeError(
        "DJANGO_SECRET_KEY must be a strong, unique value (50+ chars) when "
        "DJANGO_DEBUG=false. Refusing to start with a known-weak or short key: "
        "JWTs and signed download tokens would be forgeable."
    )
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
if DEBUG:
    CSRF_TRUSTED_ORIGINS += ["http://localhost:5173", "http://127.0.0.1:5173"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # `sites` is required by allauth.socialaccount (SocialApp.sites M2M).
    "django.contrib.sites",
    # Required by GinIndex/gin_trgm_ops on User (postgres.E005 system check).
    "django.contrib.postgres",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "kyc",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Sets up the per-request allauth context; near the bottom per Django docs.
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "kyc.common.middleware.RequestIDMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# PostgreSQL only (any instance).
# Parse DATABASE_URL with stdlib only (no dj-database-url dependency).
def _parse_database_url(url: str) -> dict:
    """Parse a postgres:// URL into a Django database config dict.

    Replicates the conn_max_age and conn_health_checks behaviour that
    dj-database-url provided, using only the stdlib urllib.parse.
    """
    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lstrip("/")
    if "?" in path:
        path = path.split("?")[0]
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": path,
        "USER": parsed.username or "",
        "PASSWORD": parsed.password or "",
        "HOST": parsed.hostname or "",
        "PORT": parsed.port or "",
        "CONN_MAX_AGE": 600,
        "CONN_HEALTH_CHECKS": True,
    }


if not os.environ.get("DATABASE_URL", ""):
    raise RuntimeError(
        "DATABASE_URL is required. Point it at PostgreSQL, e.g. "
        "postgres://kyc:***@localhost:5432/kyc"
    )
DATABASES = {"default": _parse_database_url(os.environ["DATABASE_URL"])}

# Postgres-backed cache shared across workers; no extra service needed.
CACHES = {
    "default": {
        "BACKEND": "kyc.common.cache.LightweightDatabaseCache",
        "LOCATION": "kyc_cache",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Argon2id first for all new hashes (memory-hard, GPU-resistant — see
# argon2-cffi in requirements.txt). The PBKDF2/Scrypt entries keep every
# existing hash verifiable; Django re-hashes to the first entry
# automatically on the next successful login.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "kyc.User"

# Lets the login identifier resolve against both email and phone columns.
AUTHENTICATION_BACKENDS = [
    "kyc.common.backends.EmailOrPhoneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    # Safety-net throttles; stricter views override these.
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "120/hour",      # any unauthenticated request, per IP
        "user": "600/hour",      # any authenticated request, per user
        "register": "5/hour",    # account creation, per IP
        "login_ip": "60/hour",   # login attempts per IP, across all emails
        "google_login": "60/hour",  # Google Sign-In attempts, per IP
        "otp_verify": "10/hour",   # OTP verification attempts, per IP
        "download": "300/hour",  # signed document downloads, per IP
        "submit": "10/hour",
        "documents": "30/hour",
        "review": "60/hour",
    },
    # Adds a Retry-After header to 429 responses (RFC 6585).
    "EXCEPTION_HANDLER": "kyc.common.throttles.throttled_exception_handler",
    # Trusted proxy hops; raise when behind an extra load balancer.
    "NUM_PROXIES": int(os.environ.get("DJANGO_NUM_PROXIES", "1")),
}

# Fixed window for the per-credential login throttle.
LOGIN_THROTTLE_MAX_ATTEMPTS = 10
LOGIN_THROTTLE_WINDOW_SECONDS = 10 * 60

# Fixed window for the per-(email + IP) OTP request throttle.
OTP_REQUEST_MAX = 5
OTP_REQUEST_WINDOW_SECONDS = 60 * 60

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    # Revoke ALL tokens (access + refresh) when the password changes: each
    # token carries a hash of the password it was issued with, and
    # JWTAuthentication rejects tokens whose hash no longer matches. Without
    # this, a stolen refresh token would survive a password reset for its
    # full 7-day lifetime.
    "CHECK_REVOKE_TOKEN": True,
}

# Transactional email (OTP codes) via Django's built-in SMTP backend.
# Resend is the default provider; SMTP settings work out of the box:
#   smtp.resend.com:587, user "resend", password = API key (re_...).
# In DEBUG, emails are written to the console instead of sent.
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend"
    if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.resend.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "resend")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "10"))
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Login Portal <onboarding@resend.dev>")

# allauth verifies the Google ID token; SimpleJWT still issues the session.
SITE_ID = 1

# OAuth "Web application" client ID; leave unset to disable Google Sign-In.
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")

ACCOUNT_EMAIL_VERIFICATION = "none"
# ID-token flow only: never persist Google access tokens (less PII at rest).
SOCIALACCOUNT_STORE_TOKENS = False
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        # Settings-backed app: no SocialApp DB row required.
        "APP": {"client_id": GOOGLE_CLIENT_ID},
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    }
}

# Refresh token lives in an HttpOnly cookie so XSS cannot read it.
SSL_ENABLED = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "true").lower() == "true"
JWT_AUTH_COOKIE = "refresh_token"
# Only the refresh/logout endpoints consume it, so scope it to /api/.
JWT_AUTH_COOKIE_PATH = "/api/"
JWT_AUTH_COOKIE_MAX_AGE = int(timedelta(days=7).total_seconds())
JWT_AUTH_COOKIE_SECURE = not DEBUG and SSL_ENABLED
# None requires the Secure flag, so fall back to Lax without HTTPS.
JWT_AUTH_COOKIE_SAMESITE = "None" if (not DEBUG and SSL_ENABLED) else "Lax"

CORS_ALLOWED_ORIGINS: list[str] = []
if DEBUG:
    # Vite dev server only.
    CORS_ALLOWED_ORIGINS += ["http://localhost:5173", "http://127.0.0.1:5173"]
# Required so the refresh cookie can be sent cross-origin.
CORS_ALLOW_CREDENTIALS = True

if not DEBUG:
    # Same-origin deployments need no CORS entries; split-origin setups list
    # frontend origins explicitly via env (no vendor wildcard allowlists).
    custom_domain = os.environ.get("CUSTOM_DOMAIN")
    if custom_domain:
        CORS_ALLOWED_ORIGINS.append(f"https://{custom_domain}")

extra_cors = os.environ.get("CORS_ALLOWED_ORIGINS", "")
if extra_cors:
    CORS_ALLOWED_ORIGINS.extend([o.strip() for o in extra_cors.split(",") if o.strip()])

MAX_UPLOAD_SIZE_MB = 5
ALLOWED_UPLOAD_EXTENSIONS = [".jpg", ".jpeg", ".png", ".pdf"]
# Reject oversized request bodies before DRF buffers them into memory.
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024 + 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024

LOGGING: dict[str, object] = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {
            "()": "kyc.common.middleware.RequestIDFilter",
        },
    },
    "formatters": {
        "json": {
            "()": "kyc.common.logging.JSONFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(request_id)s %(message)s",
        },
        "plain": {
            "format": "[%(asctime)s] %(levelname)s %(name)s %(request_id)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "json" if not DEBUG else "plain",
            "filters": ["request_id"],
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
    "loggers": {
        "django": {"level": "INFO", "handlers": ["console"], "propagate": False},
        "kyc": {"level": "DEBUG" if DEBUG else "INFO", "handlers": ["console"], "propagate": False},
        "kyc.request": {"level": "INFO", "handlers": ["console"], "propagate": False},
    },
}

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
# STATICFILES_STORAGE was removed in Django 5.1; use the STORAGES dict instead.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

if not DEBUG:
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    # HSTS and Secure cookies only make sense when HTTPS is actually in play.
    if SSL_ENABLED:
        SECURE_HSTS_SECONDS = 31536000
        SECURE_HSTS_INCLUDE_SUBDOMAINS = True
        SECURE_HSTS_PRELOAD = True
        SESSION_COOKIE_SECURE = True
        CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = SSL_ENABLED
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # Content Security Policy (Django 6 native, enforced by
    # ContentSecurityPolicyMiddleware). Restrictive, but allows inline styles
    # for Tailwind.
    SECURE_CSP = {
        "default-src": [CSP.SELF],
        "script-src": [CSP.SELF],
        "style-src": [CSP.SELF, "'unsafe-inline'"],  # Tailwind uses inline styles
        "img-src": [CSP.SELF, "data:", "https:"],
        "font-src": [CSP.SELF, "data:"],
        "connect-src": [CSP.SELF],
        "frame-ancestors": [CSP.NONE],
        "form-action": [CSP.SELF],
        "base-uri": [CSP.SELF],
    }
