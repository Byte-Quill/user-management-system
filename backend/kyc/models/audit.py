"""Immutable audit trail for every application action."""
import uuid

from django.conf import settings
from django.db import models

from kyc.models.application import KYCApplication

class AuditLog(models.Model):
    """Immutable record of every action taken on an application."""

    class Action(models.TextChoices):
        CREATED = "created", "Created"
        UPDATED = "updated", "Updated"
        SUBMITTED = "submitted", "Submitted"
        DOCUMENT_UPLOADED = "document_uploaded", "Document Uploaded"
        DOCUMENT_REMOVED = "document_removed", "Document Removed"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        RESUBMISSION_REQUESTED = "resubmission_requested", "Resubmission Requested"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        KYCApplication, on_delete=models.CASCADE, related_name="audit_logs"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="audit_events",
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        # Paginated per-application history: /applications/{id}/audit/.
        indexes = [
            models.Index(
                fields=["application", "-created_at"],
                name="kyc_audit_app_created_idx",
            ),
        ]

    def __str__(self):
        # application_id is the FK column name; Pylance only knows the `application` field.
        return f"{self.action} on {self.application_id} by {self.actor}"  # type: ignore


def log_action(application, actor, action, detail=""):
    """Append an immutable audit entry for an application action."""
    AuditLog.objects.create(
        application=application, actor=actor, action=action, detail=detail
    )

