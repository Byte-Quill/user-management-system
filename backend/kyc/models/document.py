"""Identity documents attached to applications, with storage cleanup."""

import os
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from kyc.common.validators import validate_file_content
from kyc.models.application import KYCApplication


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
    """Remove backing files whenever a Document row is deleted."""
    if instance.file:
        storage = instance.file.storage
        name = instance.file.name
        transaction.on_commit(lambda: storage.delete(name))
