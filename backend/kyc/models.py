import os
import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.core.signing import TimestampSigner
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone


def validate_file_content(file_obj: UploadedFile):
    """Validate the file's content matches its extension (magic-byte sniff).

    Extension checks alone are bypassed by renaming an executable to .pdf, so
    we inspect actual bytes: start-of-file signatures plus, where cheap,
    end-of-file markers (JPEG EOI, PDF %%EOF) to catch truncated/polyglot files.
    """
    ext = os.path.splitext(file_obj.name)[1].lower()
    head = file_obj.read(16)
    file_obj.seek(0)

    if ext in (".jpg", ".jpeg"):
        # SOI marker at start; EOI marker must appear within the last 4 KB.
        if not head.startswith(b"\xff\xd8\xff"):
            raise ValidationError("File content does not match the '.jpg/.jpeg' extension.")
        file_obj.seek(max(0, file_obj.size - 4096))
        tail = file_obj.read()
        file_obj.seek(0)
        if b"\xff\xd9" not in tail:
            raise ValidationError("Image file appears truncated (missing end marker).")

    elif ext == ".png":
        if not head.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValidationError("File content does not match the '.png' extension.")

    elif ext == ".pdf":
        # %PDF- at the start and %%EOF within the last 1 KB are required by the
        # spec. A real PDF always ends with %%EOF; executables do not.
        if not head.startswith(b"%PDF-"):
            raise ValidationError("File content does not match the '.pdf' extension.")
        file_obj.seek(max(0, file_obj.size - 1024))
        tail = file_obj.read()
        file_obj.seek(0)
        if b"%%EOF" not in tail:
            raise ValidationError("PDF file appears truncated or malformed.")


class User(AbstractUser):
    """Custom user with a role for the KYC workflow."""

    class Role(models.TextChoices):
        APPLICANT = "applicant", "Applicant"
        REVIEWER = "reviewer", "Reviewer"
        ADMIN = "admin", "Admin"

    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=20, choices=Role.choices, default=Role.APPLICANT
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return f"{self.email} ({self.role})"

    @property
    def is_reviewer(self):
        return self.role in (self.Role.REVIEWER, self.Role.ADMIN)


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
            # Review queue: status-filtered list ordered by -created_at.
            models.Index(fields=["status", "-created_at"], name="kyc_app_status_created_idx"),
        ]

    def __str__(self):
        return f"KYC {self.id} — {self.full_name} [{self.status}]"

    def submit(self):
        # Note: callers must fetch this row via select_for_update() inside a
        # transaction so concurrent submits cannot both pass the status check.
        if self.status not in (self.Status.DRAFT, self.Status.RESUBMISSION_REQUESTED):
            raise ValidationError(
                "Only draft or resubmission-requested applications can be submitted."
            )
        self.status = self.Status.SUBMITTED
        self.submitted_at = timezone.now()
        self.save(update_fields=["status", "submitted_at", "updated_at"])

    def apply_review(self, *, reviewer: User, decision: str, notes: str = ""):
        """Apply a reviewer decision and record audit metadata."""
        # Note: callers must fetch this row via select_for_update() inside a
        # transaction so two concurrent reviews cannot both pass the check.
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
        self.save(
            update_fields=["status", "reviewer", "review_notes", "reviewed_at", "updated_at"]
        )


def document_upload_path(instance: "Document", filename: str):
    ext = os.path.splitext(filename)[1].lower()
    return f"documents/{instance.application_id}/{uuid.uuid4().hex}{ext}"


class Document(models.Model):
    """A file uploaded in support of a KYC application."""

    class DocType(models.TextChoices):
        ID_PROOF = "id_proof", "ID Proof"
        ADDRESS_PROOF = "address_proof", "Address Proof"
        SELFIE = "selfie", "Selfie"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        KYCApplication, on_delete=models.CASCADE, related_name="documents"
    )
    doc_type = models.CharField(max_length=30, choices=DocType.choices)
    file = models.FileField(upload_to=document_upload_path)
    original_filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.doc_type}: {self.original_filename}"

    def clean(self):
        ext = os.path.splitext(self.original_filename)[1].lower()
        allowed = getattr(settings, "ALLOWED_UPLOAD_EXTENSIONS", [])
        if allowed and ext not in allowed:
            raise ValidationError(f"File type '{ext}' is not allowed.")
        max_bytes = getattr(settings, "MAX_UPLOAD_SIZE_MB", 5) * 1024 * 1024
        if self.file and self.file.size > max_bytes:
            raise ValidationError("File exceeds the maximum allowed size.")
        if self.file:
            validate_file_content(self.file)


@receiver(post_delete, sender=Document)
def cleanup_document_files(sender, instance, **kwargs):
    """Remove backing files whenever a Document row is deleted.

    Django never deletes FileField files on model deletion, and the admin's
    bulk-delete and cascade-delete paths bypass any custom ``Model.delete()``
    override while still emitting ``post_delete`` signals. Centralising the
    cleanup in a signal therefore covers every deletion path (API delete,
    admin single/bulk delete, and application cascade) so identity documents
    are never left orphaned on disk.
    """
    if instance.file:
        instance.file.delete(save=False)


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

    def __str__(self):
        # application_id is the FK column name; Pylance only knows the `application` field.
        return f"{self.action} on {self.application_id} by {self.actor}"  # type: ignore


def log_action(application, actor, action, detail=""):
    """Append an immutable audit entry for an application action."""
    AuditLog.objects.create(
        application=application, actor=actor, action=action, detail=detail
    )


# Signed download tokens are HMAC'd with SECRET_KEY, so they can be verified
# statelessly (no DB lookup, no cache) and forged only by someone who holds
# the secret key. Tokens are issued only to users who already passed the
# API's ownership/role permission checks; anyone holding a valid token can
# view the file until it expires (same semantics as object-storage signed
# URLs).
DOWNLOAD_TOKEN_SALT = "kyc.document-download"
# Short TTL: tokens are minted on detail-view load and used immediately.
# They travel in URLs (access logs, browser history), so keep the replay
# window small.
DOWNLOAD_TOKEN_MAX_AGE = 900


def document_download_token(doc_id) -> str:
    """Return a time-limited signed token authorising download of a document."""
    return TimestampSigner(salt=DOWNLOAD_TOKEN_SALT).sign(str(doc_id))
