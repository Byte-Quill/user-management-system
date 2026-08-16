import logging
import os

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from . import supabase_client
from .models import AuditLog, Document, KYCApplication
from .permissions import IsOwnerOrReviewer, IsReviewer
from .serializers import (
    AuditLogSerializer,
    DocumentSerializer,
    KYCApplicationSerializer,
    RegisterSerializer,
    ReviewSerializer,
    UserSerializer,
)
from .services import log_action
from .throttles import RegisterThrottle, WriteThrottle

User = get_user_model()
logger = logging.getLogger("kyc")


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = (AllowAny,)
    throttle_classes = (RegisterThrottle,)


class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        return self.request.user


class KYCApplicationViewSet(viewsets.ModelViewSet):
    serializer_class = KYCApplicationSerializer
    permission_classes = (IsAuthenticated, IsOwnerOrReviewer)
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def destroy(self, request, *args, **kwargs):
        # Application deletion is not part of the KYC flow; DELETE is only
        # used by the dedicated document-removal action.
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    # User-scoped write throttles keyed by DRF action name.
    THROTTLE_SCOPES = {
        "submit": "submit",
        "documents": "documents",
        "review": "review",
    }

    def get_throttles(self):
        scope = self.THROTTLE_SCOPES.get(self.action)
        if scope:
            self.throttle_scope = scope
            return [WriteThrottle()]
        return super().get_throttles()

    def get_serializer_context(self):
        # List views only need document metadata (e.g. doc count); generating
        # signed URLs is a Supabase network round-trip per document, so skip it.
        context = super().get_serializer_context()
        context["include_signed_url"] = self.action != "list"
        return context

    def get_queryset(self):
        qs = KYCApplication.objects.select_related("applicant", "reviewer").prefetch_related("documents")
        user = self.request.user
        if user.is_reviewer:
            status_filter = self.request.query_params.get("status")
            if status_filter:
                if status_filter not in KYCApplication.Status.values:
                    raise ValidationError(f"Invalid status: {status_filter}")
                qs = qs.filter(status=status_filter)
            return qs
        return qs.filter(applicant=user)

    def perform_create(self, serializer):
        application = serializer.save(applicant=self.request.user)
        log_action(application, self.request.user, AuditLog.Action.CREATED)

    def perform_update(self, serializer):
        application = serializer.save()
        log_action(application, self.request.user, AuditLog.Action.UPDATED)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        with transaction.atomic():
            application = self.get_object()
            # Row lock: two concurrent submits cannot both pass the status check.
            application = KYCApplication.objects.select_for_update().get(pk=application.pk)
            if application.applicant_id != request.user.id:
                raise ValidationError("Only the applicant can submit this application.")
            if not application.documents.exists():
                raise ValidationError("At least one supporting document is required before submission.")
            try:
                application.submit()
            except DjangoValidationError as exc:
                raise ValidationError(exc.message)
            log_action(application, request.user, AuditLog.Action.SUBMITTED)
        return Response(self.get_serializer(application).data)

    @action(
        detail=True,
        methods=["post"],
        parser_classes=(MultiPartParser, FormParser),
    )
    def documents(self, request, pk=None):
        application = self.get_object()
        if application.applicant_id != request.user.id:
            raise ValidationError("Only the applicant can upload documents.")
        if application.status not in (
            KYCApplication.Status.DRAFT,
            KYCApplication.Status.RESUBMISSION_REQUESTED,
        ):
            raise ValidationError("Documents can only be uploaded while the application is editable.")

        file_obj = request.FILES.get("file")
        doc_type = request.data.get("doc_type")
        if not file_obj:
            raise ValidationError({"file": "No file provided."})
        if doc_type not in Document.DocType.values:
            raise ValidationError({"doc_type": f"Must be one of {list(Document.DocType.values)}."})

        document = Document(
            application=application,
            doc_type=doc_type,
            file=file_obj,
            original_filename=file_obj.name,
        )
        try:
            document.full_clean()
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)
        document.save()

        # Mirror the file to Supabase Storage when configured. In production the
        # local copy is NOT served (WhiteNoise only serves static files), so a
        # failed mirror means the document is unreachable: fail loudly and roll
        # back rather than report a success that nobody can see.
        if supabase_client.is_configured():
            file_obj.seek(0)
            ext = os.path.splitext(file_obj.name)[1].lower()
            storage_path = f"{application.id}/{document.id}{ext}"
            uploaded = supabase_client.upload_document(
                storage_path, file_obj.read(), file_obj.content_type or "application/octet-stream"
            )
            if not uploaded:
                document.delete()  # post_delete signal removes the file from disk
                logger.error(
                    "Document upload failed: Supabase mirror unavailable (application=%s)", application.id
                )
                return Response(
                    {"detail": "Document storage is temporarily unavailable. Please retry."},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            document.storage_path = uploaded
            document.save(update_fields=["storage_path"])

        log_action(
            application,
            request.user,
            AuditLog.Action.DOCUMENT_UPLOADED,
            detail=f"{doc_type}: {file_obj.name}",
        )
        return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"documents/(?P<doc_id>[^/.]+)")
    def remove_document(self, request, pk=None, doc_id=None):
        """Remove one document while the application is still editable.

        The Supabase mirror is deleted first; on failure the local row is kept
        so a half-deleted document never leaves a dangling DB record.
        """
        application = self.get_object()
        if application.applicant_id != request.user.id:
            raise ValidationError("Only the applicant can remove documents.")
        if application.status not in (
            KYCApplication.Status.DRAFT,
            KYCApplication.Status.RESUBMISSION_REQUESTED,
        ):
            raise ValidationError("Documents can only be removed while the application is editable.")

        try:
            document = application.documents.get(pk=doc_id)
        except (Document.DoesNotExist, ValueError, DjangoValidationError):
            # ValueError/ValidationError: malformed UUID in the URL -> 404, never 500.
            raise NotFound("Document not found.")

        if supabase_client.is_configured() and document.storage_path:
            if not supabase_client.delete_document(document.storage_path):
                logger.error(
                    "Document removal failed: Supabase delete unavailable (application=%s, doc=%s)",
                    application.id,
                    document.id,
                )
                return Response(
                    {"detail": "Document storage is temporarily unavailable. Please retry."},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            # Mirror removed; clear the path so the post_delete cleanup signal
            # does not attempt a redundant Supabase delete.
            document.storage_path = ""
            document.save(update_fields=["storage_path"])

        doc_type = document.doc_type
        original_filename = document.original_filename
        document.delete()  # post_delete signal removes the file from disk
        log_action(
            application,
            request.user,
            AuditLog.Action.DOCUMENT_REMOVED,
            detail=f"{doc_type}: {original_filename}",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=(IsAuthenticated, IsReviewer),
    )
    def review(self, request, pk=None):
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decision = serializer.validated_data["decision"]
        notes = serializer.validated_data["notes"]
        with transaction.atomic():
            application = self.get_object()
            # Row lock: two concurrent reviews cannot both pass the status check.
            application = KYCApplication.objects.select_for_update().get(pk=application.pk)
            try:
                application.apply_review(reviewer=request.user, decision=decision, notes=notes)
            except DjangoValidationError as exc:
                raise ValidationError(exc.message)
            action_map = {
                KYCApplication.Decision.APPROVE: AuditLog.Action.APPROVED,
                KYCApplication.Decision.REJECT: AuditLog.Action.REJECTED,
                KYCApplication.Decision.REQUEST_RESUBMISSION: AuditLog.Action.RESUBMISSION_REQUESTED,
            }
            log_action(application, request.user, action_map[decision], detail=notes)
        return Response(self.get_serializer(application).data)

    @action(detail=True, methods=["get"])
    def audit(self, request, pk=None):
        application = self.get_object()
        logs = application.audit_logs.select_related("actor").order_by("-created_at")
        page = self.paginate_queryset(logs)
        serializer = AuditLogSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)


class ReviewQueueView(generics.ListAPIView):
    """Reviewer-facing queue of applications awaiting a decision."""

    serializer_class = KYCApplicationSerializer
    permission_classes = (IsAuthenticated, IsReviewer)

    def get_serializer_context(self):
        # Queue rows only need document metadata (doc count); skip the
        # per-document Supabase signed-URL round-trip like the list views.
        context = super().get_serializer_context()
        context["include_signed_url"] = False
        return context

    def get_queryset(self):
        return (
            KYCApplication.objects.filter(status=KYCApplication.Status.SUBMITTED)
            .select_related("applicant")
            .prefetch_related("documents")
        )
