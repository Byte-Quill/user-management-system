"""One-time email codes for signup verification and password reset."""
from django.conf import settings
from django.db import models

class EmailOTP(models.Model):
    """One-time email codes for signup verification and password reset.

    Security properties (enforced by kyc/otp.py): codes are stored as
    HMAC-SHA256 keyed with SECRET_KEY, single-use with a bounded attempt
    counter, short TTL, and only the latest OTP per (user, purpose) is valid.
    """

    class Purpose(models.TextChoices):
        VERIFY_EMAIL = "verify_email", "Verify email"
        RESET_PASSWORD = "reset_password", "Reset password"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="email_otps"
    )
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "purpose"]),
        ]

    def __str__(self):
        return f"EmailOTP({self.purpose}, user={self.user_id})"
