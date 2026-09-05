"""Django email backend that sends through the Resend HTTP API.

The HTTP API is faster than SMTP (no handshake, port 25/587 not needed). The
backend implements ``BaseEmailBackend``, so ``send_mail`` and the test
runner's automatic locmem swap work unchanged — tests never touch the network.

Configuration: RESEND_API_KEY and DEFAULT_FROM_EMAIL env vars. With an
*unverified* domain Resend only allows sending from ``onboarding@resend.dev``
to the account owner's own inbox.
"""
import logging

import resend
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger("kyc.email")

try:
    # Pluggable sync HTTP client (requests-backed) available since the SDK
    # grew one; guarded so an SDK upgrade never breaks email at startup.
    from resend.http_client_requests import RequestsClient
except ImportError:  # pragma: no cover
    RequestsClient = None

# The Resend call runs inside the request path (registration, resend, reset).
# A tight timeout keeps a degraded Resend API from occupying gunicorn sync
# workers until the 30s worker timeout kills the request.
RESEND_TIMEOUT_SECONDS = int(getattr(settings, "RESEND_TIMEOUT_SECONDS", 10))


class ResendEmailBackend(BaseEmailBackend):
    """Send EmailMessages via ``resend.Emails.send``.

    Failures raise unless ``fail_silently=True`` (Django contract), in which
    case they are logged and counted as unsent.
    """

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        self.api_key = getattr(settings, "RESEND_API_KEY", "")
        if not self.api_key and not fail_silently:
            # Fail loudly on misconfiguration at first send, not as a vague
            # 401 from the API.
            raise RuntimeError("RESEND_API_KEY is not configured.")
        if RequestsClient is not None:
            # Process-global client; RequestsClient is stateless per request
            # (it builds a fresh requests call each time), so sharing it
            # across threads is safe. The SDK's default is 30s — far too
            # long to hold a sync worker for an email that should take <1s.
            resend.default_http_client = RequestsClient(
                timeout=RESEND_TIMEOUT_SECONDS
            )

    def send_messages(self, email_messages):
        sent = 0
        # Set the key per call: gunicorn workers are threaded and the SDK
        # reads a module-level value at request time, so a per-instance
        # attribute avoids cross-thread races.
        resend.api_key = self.api_key
        for message in email_messages:
            try:
                resend.Emails.send(
                    {
                        "from": message.from_email,
                        "to": list(message.to),
                        "subject": message.subject,
                        # Resend requires an html body; fall back to a
                        # <pre>-wrapped plain-text version.
                        "html": (
                            message.body
                            if getattr(message, "content_subtype", "plain") == "html"
                            else f"<pre>{message.body}</pre>"
                        ),
                        "text": message.body,
                    }
                )
                sent += 1
            except Exception:
                logger.exception("Resend send failed (to=%s)", message.to)
                if not self.fail_silently:
                    raise
        return sent
