"""Append-only record of transactional emails sent (verification, reset)."""

import uuid

from django.conf import settings
from django.db import models


class EmailLog(models.Model):
    """Append-only record of transactional emails sent (verification, reset)."""

    class Purpose(models.TextChoices):
        VERIFY_EMAIL = "verify_email", "Verify Email"
        RESET_PASSWORD = "reset_password", "Reset Password"

    class Status(models.TextChoices):
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="email_logs",
    )
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=Status.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["-created_at"], name="kyc_emaillo_created_idx")]

    def __str__(self):
        return f"EmailLog({self.purpose}, {self.status}, {self.recipient})"
