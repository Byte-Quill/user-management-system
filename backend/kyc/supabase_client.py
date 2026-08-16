"""Thin Supabase Storage client via plain REST.

Uses the service-role key directly instead of the full `supabase` SDK
(which drags in pydantic/httpx/websockets) to keep the backend install
lightweight. All helpers degrade to no-ops when Supabase is unconfigured.
"""
import logging
import time
from collections.abc import Callable

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Shared session: keeps TCP/TLS connections to Supabase alive across calls
# instead of paying a fresh handshake on every request.
_session = requests.Session()

# Retry configuration for idempotent Supabase operations
_MAX_RETRIES = 2
_BASE_BACKOFF = 0.5  # seconds

# Signed URLs are valid for 1h; cache them a bit shorter so callers never
# receive a URL that expires mid-use.
_SIGNED_URL_TTL = 55 * 60


def _retry_idempotent[T](func: Callable[[], T], operation: str) -> T | None:
    """Execute an idempotent operation with exponential backoff retries."""
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return func()
        except Exception as exc:  # noqa: BLE001
            if attempt < _MAX_RETRIES:
                backoff = _BASE_BACKOFF * (2**attempt)
                logger.warning(
                    "%s failed (attempt %d/%d), retrying in %.1fs: %s",
                    operation,
                    attempt + 1,
                    _MAX_RETRIES + 1,
                    backoff,
                    exc,
                )
                time.sleep(backoff)
            else:
                logger.error("%s failed after %d attempts: %s", operation, _MAX_RETRIES + 1, exc)
    return None


def is_configured() -> bool:
    """True when the minimum Supabase settings are present."""
    return bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY)


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
    }


def supabase_storage_ping() -> bool:
    """Return True if the storage API is reachable. Used by the readiness probe."""
    if not is_configured():
        # Nothing configured: treat as healthy so /readyz does not block deploys.
        return True
    try:
        url = (
            f"{settings.SUPABASE_URL}/storage/v1/bucket/"
            f"{settings.SUPABASE_STORAGE_BUCKET}"
        )
        res = _session.get(url, headers=_headers(), timeout=10)
        return res.status_code in (200, 404)  # 404 = bucket listing endpoint differs
    except Exception as exc:  # noqa: BLE001
        logger.warning("Supabase storage ping failed: %s", exc)
        return False


def upload_document(path: str, data: bytes, content_type: str) -> str | None:
    """Upload bytes to the configured bucket. Returns the storage path or None."""
    if not is_configured():
        return None

    def _do_upload() -> str:
        url = (
            f"{settings.SUPABASE_URL}/storage/v1/object/"
            f"{settings.SUPABASE_STORAGE_BUCKET}/{path}"
        )
        headers = _headers()
        headers["Content-Type"] = content_type
        headers["x-upsert"] = "true"
        res = _session.post(url, data=data, headers=headers, timeout=30)
        res.raise_for_status()
        return path

    return _retry_idempotent(_do_upload, "Supabase storage upload")


def delete_document(path: str) -> bool:
    """Delete an object from the configured bucket. Returns True on success."""
    if not is_configured():
        return False

    def _do_delete() -> bool:
        url = (
            f"{settings.SUPABASE_URL}/storage/v1/object/"
            f"{settings.SUPABASE_STORAGE_BUCKET}/{path}"
        )
        res = _session.delete(url, headers=_headers(), timeout=30)
        res.raise_for_status()
        return True

    result = _retry_idempotent(_do_delete, "Supabase storage delete")
    if result:
        # Drop any cached signed URL so a removed object can't be re-shared.
        cache.delete(f"supabase-signed-url:{path}")
    return result is True


def create_signed_url(path: str, expires_in: int = 3600) -> str | None:
    """Return a time-limited signed URL for a private object.

    Signed URLs are cached (keyed by storage path) so detail views don't pay
    one Supabase round-trip per document on every request.
    """
    if not is_configured():
        return None
    cache_key = f"supabase-signed-url:{path}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    try:
        url = (
            f"{settings.SUPABASE_URL}/storage/v1/object/sign/"
            f"{settings.SUPABASE_STORAGE_BUCKET}/{path}"
        )
        res = _session.post(
            url, json={"expiresIn": expires_in}, headers=_headers(), timeout=10
        )
        res.raise_for_status()
        signed = res.json().get("signedURL")
        if not signed:
            return None
        full_url = f"{settings.SUPABASE_URL}{signed}"
        # Never cache longer than the URL's remaining validity.
        ttl = max(60, min(_SIGNED_URL_TTL, expires_in - 300))
        cache.set(cache_key, full_url, ttl)
        return full_url
    except Exception as exc:  # noqa: BLE001
        logger.warning("Supabase create_signed_url failed: %s", exc)
        return None