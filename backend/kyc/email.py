"""Django email backend that sends through the Resend HTTP API.

Why a custom backend instead of Resend's SMTP relay: the HTTP API is faster
(no SMTP handshake), works where outbound port 25/587 is blocked, and the
official SDK gives typed errors. The backend implements Django's standard
``BaseEmailBackend`` interface, so ``django.core.mail.send_mail`` and the
test runner's automatic locmem swap work unchanged — tests never touch the
network.

Configuration (settings / env):
  RESEND_API_KEY      API key from resend.com (required in production).
  DEFAULT_FROM_EMAIL  Verified sender, e.g. "Login Portal <noreply@yourdomain.com>".

Note: with an *unverified* domain Resend only allows sending from
``onboarding@resend.dev`` to the account owner's own inbox — verify a domain
before real production sending.
"""
import logging

import resend
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger("kyc.email")


class ResendEmailBackend(BaseEmailBackend):
    """Send EmailMessages via ``resend.Emails.send``.

    Failures raise unless ``fail_silently=True`` (Django contract), in which
    case they are logged and counted as unsent.
    """

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        api_key = getattr(settings, "RESEND_API_KEY", "")
        if not api_key and not fail_silently:
            # Surface misconfiguration loudly at first send, not as a vague
            # 401 from the API.
            raise RuntimeError("RESEND_API_KEY is not configured.")
        # The SDK reads the module-level key at call time.
        resend.api_key = api_key

    def send_messages(self, email_messages):
        sent = 0
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
