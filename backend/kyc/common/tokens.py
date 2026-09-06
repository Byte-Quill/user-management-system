"""Stateless signed tokens for document downloads (HMAC via TimestampSigner)."""
from django.core.signing import TimestampSigner


DOWNLOAD_TOKEN_SALT = "kyc.document-download"


DOWNLOAD_TOKEN_MAX_AGE = 900


def document_download_token(doc_id) -> str:
    """Return a time-limited signed token authorising download of a document."""
    return TimestampSigner(salt=DOWNLOAD_TOKEN_SALT).sign(str(doc_id))
