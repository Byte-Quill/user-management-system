"""Django settings for the KYC-V3 backend."""
import os
import sys
from datetime import timedelta
from pathlib import Path

import dj_database_url
from django.utils.csp import CSP
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

_BUILD_TIME_SENTINEL = "django-insecure-build-time-only-key-not-for-production"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or _BUILD_TIME_SENTINEL
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"

if not DEBUG and SECRET_KEY == _BUILD_TIME_SENTINEL:
    raise RuntimeError(
        "DJANGO_SECRET_KEY must be set when DJANGO_DEBUG=false. "
        "Refusing to start with the insecure build-time fallback."
    )
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "DJANGO_CSRF_TRUSTED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
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
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Django 6's built-in CSP middleware (configured via SECURE_CSP below).
    # Docs recommend placing it near the bottom of the stack.
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "kyc.middleware.RequestIDMiddleware",
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

# Database: PostgreSQL (Supabase) via DATABASE_URL.
# Set DATABASE_URL to your Supabase Postgres connection string, e.g.
#   postgres://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
DATABASES = {
    "default": dj_database_url.config(
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Rate-limit counters and sessions. In production use Redis so throttling is
# shared across gunicorn workers/processes (LocMemCache is per-process and
# gets wiped on restart). Redis is mandatory when DEBUG=false.
_REDIS_URL = os.environ.get("REDIS_URL", "").strip()
if not DEBUG and not _REDIS_URL:
    raise RuntimeError(
        "REDIS_URL must be set when DJANGO_DEBUG=false. "
        "Redis is required for shared throttling and token blacklist across workers."
    )
if _REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": _REDIS_URL,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "kyc-default",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "kyc.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_RATES": {
        "submit": "10/hour",
        "documents": "30/hour",
        "review": "60/hour",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

# Refresh token lives in an HttpOnly cookie (not localStorage) so XSS cannot
# steal it. The access token is kept in memory on the client.
JWT_AUTH_COOKIE = "refresh_token"
JWT_AUTH_COOKIE_PATH = "/"
JWT_AUTH_COOKIE_MAX_AGE = int(timedelta(days=7).total_seconds())
JWT_AUTH_COOKIE_SECURE = not DEBUG
JWT_AUTH_COOKIE_SAMESITE = "None" if not DEBUG else "Lax"

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
# Required so the refresh-token cookie can be sent cross-origin from the SPA.
CORS_ALLOW_CREDENTIALS = True

if not DEBUG:
    CORS_ALLOWED_ORIGIN_REGEXES = [
        r"^https://.*\.onrender\.com$",
        r"^https://.*\.up\.railway\.app$",
        r"^https://.*\.vercel\.app$",
    ]
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

# --- Logging ---

LOGGING: dict[str, object] = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {
            "()": "kyc.middleware.RequestIDFilter",
        },
    },
    "formatters": {
        "json": {
            # python-json-logger >= 3.1 moved JsonFormatter to pythonjsonlogger.json
            "()": "pythonjsonlogger.json.JsonFormatter",
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
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
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

# Project URL and keys from the Supabase dashboard (Settings > API).
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
# Storage bucket for KYC documents (created via the Supabase dashboard or CLI).
SUPABASE_STORAGE_BUCKET = os.environ.get("SUPABASE_STORAGE_BUCKET", "kyc-documents")
USE_SUPABASE_STORAGE = bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)
