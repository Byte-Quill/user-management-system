"""Stateless signed tokens for document downloads (HMAC via TimestampSigner)."""
from django.core.signing import TimestampSigner


DOWNLOAD_TOKEN_SALT = "kyc.document-download"


DOWNLOAD_TOKEN_MAX_AGE = 900


def document_download_token(doc_id) -> str:
    """Return a time-limited signed token authorising download of a document."""
    return TimestampSigner(salt=DOWNLOAD_TOKEN_SALT).sign(str(doc_id))


def revoke_user_sessions(user) -> int:
    """Blacklist every outstanding refresh token for ``user``.

    Used on password change/reset so that refresh cookies issued before the
    change stop working immediately (access tokens remain valid until their
    short TTL expires). Returns the number of tokens blacklisted.
    """
    from django.utils import timezone
    from rest_framework_simplejwt.exceptions import TokenError
    from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
    from rest_framework_simplejwt.tokens import RefreshToken

    revoked = 0
    outstanding = OutstandingToken.objects.filter(
        user=user, expires_at__gt=timezone.now()
    )
    for token in outstanding:
        try:
            RefreshToken(token.token).blacklist()
            revoked += 1
        except TokenError:
            # Already blacklisted or malformed — nothing to do.
            pass
    return revoked
