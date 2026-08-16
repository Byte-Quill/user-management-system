from django.core.signing import TimestampSigner

from .models import AuditLog

# Signed download tokens are HMAC'd with SECRET_KEY, so they can be verified
# statelessly (no DB lookup, no cache) and forged only by someone who holds
# the secret key. Tokens are issued only to users who already passed the
# API's ownership/role permission checks; anyone holding a valid token can
# view the file until it expires (same semantics as object-storage signed
# URLs). One hour matches the previous Supabase signed-URL validity.
DOWNLOAD_TOKEN_SALT = "kyc.document-download"
DOWNLOAD_TOKEN_MAX_AGE = 3600


def log_action(application, actor, action, detail=""):
    AuditLog.objects.create(
        application=application, actor=actor, action=action, detail=detail
    )


def document_download_token(doc_id) -> str:
    """Return a time-limited signed token authorising download of a document."""
    return TimestampSigner(salt=DOWNLOAD_TOKEN_SALT).sign(str(doc_id))
