"""Application endpoints: CRUD, submit, documents, review, audit, download."""
import logging
import mimetypes
from datetime import date
from urllib.parse import quote

from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.signing import TimestampSigner
from django.db import transaction
from django.http import FileResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from kyc.common.permissions import IsOwnerOrReviewer, IsReviewer
from kyc.common.throttles import DownloadThrottle, WriteThrottle
from kyc.common.tokens import DOWNLOAD_TOKEN_MAX_AGE, DOWNLOAD_TOKEN_SALT
from kyc.models import AuditLog, Document, KYCApplication, log_action
from kyc.serializers import (
    AuditLogSerializer,
    DocumentSerializer,
    KYCApplicationSerializer,
    ReviewSerializer,
)

logger = logging.getLogger("kyc.views")


REVIEW_ACTION_MAP = {
    KYCApplication.Decision.APPROVE: AuditLog.Action.APPROVED,
    KYCApplication.Decision.REJECT: AuditLog.Action.REJECTED,
    KYCApplication.Decision.REQUEST_RESUBMISSION: AuditLog.Action.RESUBMISSION_REQUESTED,
}

class KYCApplicationViewSet(viewsets.ModelViewSet):
    serializer_class = KYCApplicationSerializer
    permission_classes = (IsAuthenticated, IsOwnerOrReviewer)
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def destroy(self, request, *args, **kwargs):

        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    THROTTLE_SCOPES = {
        "submit": "submit",
        "documents": "documents",
        "review": "review",
    }

    def get_throttles(self):
        scope = self.THROTTLE_SCOPES.get(self.action)
        if scope:
            self.throttle_scope = scope

            return [WriteThrottle(), *super().get_throttles()]
        return super().get_throttles()

    def get_serializer_context(self):

        context = super().get_serializer_context()
        context["include_document_url"] = self.action != "list"
        return context

    def get_queryset(self):
        qs = (
            KYCApplication.objects.select_related("applicant", "reviewer")
            .prefetch_related("documents")
        )
        user = self.request.user
        if user.is_reviewer:
            status_filter = self.request.query_params.get("status")
            if status_filter:
                if status_filter not in KYCApplication.Status.values:
                    raise ValidationError(f"Invalid status: {status_filter}")
                qs = qs.filter(status=status_filter)
            return qs
        return qs.filter(applicant=user)

    def _locked_editable(self, application, verb: str) -> KYCApplication:
        """Lock the row and verify it is still editable."""
        locked = KYCApplication.objects.select_for_update().get(pk=application.pk)
        if locked.applicant_id != self.request.user.id:
            raise ValidationError(f"Only the applicant can {verb}.")
        if locked.status not in KYCApplication.EDITABLE_STATUSES:
            raise ValidationError("This application can no longer be edited.")
        return locked

    def perform_create(self, serializer):

        with transaction.atomic():
            application = serializer.save(applicant=self.request.user)
            log_action(application, self.request.user, AuditLog.Action.CREATED)

    def perform_update(self, serializer):
        with transaction.atomic():
            self._locked_editable(serializer.instance, "edit")
            application = serializer.save()
            log_action(application, self.request.user, AuditLog.Action.UPDATED)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        with transaction.atomic():
            application = self.get_object()

            application = KYCApplication.objects.select_for_update().get(pk=application.pk)
            if application.applicant_id != request.user.id:
                raise ValidationError("Only the applicant can submit this application.")
            if not application.documents.exists():
                raise ValidationError(
                    "At least one supporting document is required before submission."
                )

            if application.id_expiry and application.id_expiry < date.today():
                raise ValidationError(
                    "The ID document has expired. Update the ID details before submitting."
                )
            try:
                application.submit()
            except DjangoValidationError as exc:
                raise ValidationError(exc.message) from exc
            log_action(application, request.user, AuditLog.Action.SUBMITTED)
        return Response(self.get_serializer(application).data)

    @action(
        detail=True,
        methods=["post"],
        parser_classes=(MultiPartParser, FormParser),
    )
    def documents(self, request, pk=None):
        application = self.get_object()

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
            raise ValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            ) from exc

        try:
            with transaction.atomic():
                application = self._locked_editable(application, "upload documents")

                cap = getattr(settings, "MAX_DOCUMENTS_PER_APPLICATION", 10)
                if application.documents.count() >= cap:
                    raise ValidationError(
                        f"At most {cap} documents can be attached to an application."
                    )
                document.save()
                log_action(
                    application,
                    request.user,
                    AuditLog.Action.DOCUMENT_UPLOADED,
                    detail=f"{doc_type}: {file_obj.name}",
                )
        except Exception:

            try:
                if document.file.name and document.file.name != file_obj.name:
                    document.file.delete(save=False)
            except Exception:
                logger.exception("Failed to clean up orphaned document upload")
            raise

        return Response(
            DocumentSerializer(document, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["delete"], url_path=r"documents/(?P<doc_id>[^/.]+)")
    def remove_document(self, request, pk=None, doc_id=None):
        """Remove one document while the application is still editable."""
        application = self.get_object()
        with transaction.atomic():
            application = self._locked_editable(application, "remove documents")

            try:
                document = application.documents.get(pk=doc_id)
            except (Document.DoesNotExist, ValueError, DjangoValidationError) as exc:

                raise NotFound("Document not found.") from exc

            doc_type = document.doc_type
            original_filename = document.original_filename
            document.delete()
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

            application = KYCApplication.objects.select_for_update().get(pk=application.pk)

            if application.applicant_id == request.user.id:
                raise ValidationError("You cannot review your own application.")
            try:
                application.apply_review(reviewer=request.user, decision=decision, notes=notes)
            except DjangoValidationError as exc:
                raise ValidationError(exc.message) from exc
            log_action(application, request.user, REVIEW_ACTION_MAP[decision], detail=notes)
        return Response(self.get_serializer(application).data)

    @action(detail=True, methods=["get"])
    def audit(self, request, pk=None):
        application = self.get_object()
        logs = application.audit_logs.select_related("actor").order_by("-created_at")
        page = self.paginate_queryset(logs)
        serializer = AuditLogSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

class DocumentDownloadView(APIView):
    """Serve a document behind a time-limited signed token."""

    authentication_classes = ()
    permission_classes = (AllowAny,)

    throttle_scope = "download"
    throttle_classes = (DownloadThrottle,)

    def get(self, request, doc_id):
        token = request.query_params.get("token", "")
        try:
            signed_id = TimestampSigner(salt=DOWNLOAD_TOKEN_SALT).unsign(
                token, max_age=DOWNLOAD_TOKEN_MAX_AGE
            )
        except signing.BadSignature as exc:

            raise NotFound("Document not found.") from exc
        if signed_id != str(doc_id):

            raise NotFound("Document not found.")
        try:
            document = Document.objects.get(pk=doc_id)
        except (Document.DoesNotExist, ValueError, DjangoValidationError) as exc:
            raise NotFound("Document not found.") from exc
        if not document.file:
            raise NotFound("Document not found.")
        try:
            handle = document.file.open("rb")
        except (FileNotFoundError, ValueError) as exc:
            raise NotFound("Document not found.") from exc
        content_type = (
            mimetypes.guess_type(document.original_filename)[0]
            or "application/octet-stream"
        )
        response = FileResponse(handle, content_type=content_type)

        response["Content-Disposition"] = (
            f"attachment; filename*=UTF-8''{quote(document.original_filename)}"
        )
        return response
