"""Stateless signed tokens for document downloads (HMAC via TimestampSigner)."""
from django.core.signing import TimestampSigner

# statelessly (no DB/cache lookup) and forgeable only by the secret holder.
DOWNLOAD_TOKEN_SALT = "kyc.document-download"
# Short TTL: tokens travel in URLs (logs, browser history), so keep the
# replay window small.
DOWNLOAD_TOKEN_MAX_AGE = 900


def document_download_token(doc_id) -> str:
    """Return a time-limited signed token authorising download of a document."""
    return TimestampSigner(salt=DOWNLOAD_TOKEN_SALT).sign(str(doc_id))
