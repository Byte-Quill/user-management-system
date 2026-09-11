"""KYC application aggregate: identity data, statuses and review workflow."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from kyc.models.user import User


class KYCApplication(models.Model):
    """A single KYC verification application submitted by an applicant."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        RESUBMISSION_REQUESTED = "resubmission_requested", "Resubmission Requested"

    class IDType(models.TextChoices):
        PASSPORT = "passport", "Passport"
        NATIONAL_ID = "national_id", "National ID"
        DRIVERS_LICENSE = "drivers_license", "Driver's License"

    class Decision(models.TextChoices):
        APPROVE = "approve", "Approve"
        REJECT = "reject", "Reject"
        REQUEST_RESUBMISSION = "request_resubmission", "Request Resubmission"

    EDITABLE_STATUSES = (Status.DRAFT, Status.RESUBMISSION_REQUESTED)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="applications",
        db_index=True,
    )
    status = models.CharField(
        max_length=30, choices=Status.choices, default=Status.DRAFT, db_index=True
    )

    full_name = models.CharField(max_length=255)
    date_of_birth = models.DateField()
    nationality = models.CharField(max_length=100)
    phone = models.CharField(max_length=30)

    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=100)

    id_type = models.CharField(max_length=30, choices=IDType.choices)
    id_number = models.CharField(max_length=100)
    id_expiry = models.DateField(null=True, blank=True)

    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_applications",
    )
    review_notes = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["applicant", "status"], name="kyc_app_applicant_status_idx"),
            models.Index(fields=["status", "-created_at"], name="kyc_app_status_created_idx"),
        ]

    def __str__(self):
        return f"KYC {self.id} — {self.full_name} [{self.status}]"

    def submit(self):

        if self.status not in (self.Status.DRAFT, self.Status.RESUBMISSION_REQUESTED):
            raise ValidationError(
                "Only draft or resubmission-requested applications can be submitted."
            )
        self.status = self.Status.SUBMITTED
        self.submitted_at = timezone.now()
        self.save(update_fields=["status", "submitted_at", "updated_at"])

    def apply_review(self, *, reviewer: User, decision: str, notes: str = ""):
        """Apply a reviewer decision and record audit metadata."""

        if self.status != self.Status.SUBMITTED:
            raise ValidationError("Application is not in a reviewable state.")
        mapping = {
            self.Decision.APPROVE: self.Status.APPROVED,
            self.Decision.REJECT: self.Status.REJECTED,
            self.Decision.REQUEST_RESUBMISSION: self.Status.RESUBMISSION_REQUESTED,
        }
        if decision not in mapping:
            raise ValidationError(f"Invalid decision: {decision}")
        self.status = mapping[decision]
        self.reviewer = reviewer
        self.review_notes = notes
        self.reviewed_at = timezone.now()
        self.save(update_fields=["status", "reviewer", "review_notes", "reviewed_at", "updated_at"])
