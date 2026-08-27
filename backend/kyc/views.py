import logging
import mimetypes
from datetime import timedelta
from urllib.parse import quote

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.signing import TimestampSigner
from django.db import models, transaction
from django.db.models import Count
from django.http import FileResponse
from django.utils import timezone
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .access import (
    DownloadThrottle,
    IsCEO,
    IsOwnerOrReviewer,
    IsReviewer,
    IsSuperAdmin,
    RegisterThrottle,
    WriteThrottle,
)
from .models import (
    DOWNLOAD_TOKEN_MAX_AGE,
    DOWNLOAD_TOKEN_SALT,
    AuditLog,
    Document,
    EmailLog,
    EmailOTP,
    KYCApplication,
    log_action,
)
from .otp import issue_otp
from .serializers import (
    AdminUserCreateSerializer,
    AdminUserSerializer,
    AdminUserUpdateSerializer,
    AuditLogSerializer,
    DocumentSerializer,
    EmailLogSerializer,
    KYCApplicationSerializer,
    RegisterSerializer,
    ReviewSerializer,
    SetPasswordSerializer,
    UserSerializer,
)

logger = logging.getLogger("kyc.views")

User = get_user_model()

# Reviewer decision -> audit action (static; shared by the review endpoint).
REVIEW_ACTION_MAP = {
    KYCApplication.Decision.APPROVE: AuditLog.Action.APPROVED,
    KYCApplication.Decision.REJECT: AuditLog.Action.REJECTED,
    KYCApplication.Decision.REQUEST_RESUBMISSION: AuditLog.Action.RESUBMISSION_REQUESTED,
}


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = (AllowAny,)
    throttle_classes = (RegisterThrottle,)

    def perform_create(self, serializer):
        # Create the user, then issue the OTP — deliberately outside a
        # transaction so the external HTTP send never holds a DB connection.
        user = serializer.save()
        # Phone-only accounts have no email to verify, so skip the OTP.
        if not user.email:
            return
        try:
            issue_otp(user, EmailOTP.Purpose.VERIFY_EMAIL)
        except Exception:
            # An email outage must not turn signup into a 500 (the client
            # would retry into "email already registered"); the account stays
            # unverified and recovers via the resend endpoint.
            logger.exception("Failed to send verification email to %s", user.email)


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
            # Scoped write limit plus the global anon/user safety nets.
            return [WriteThrottle(), *super().get_throttles()]
        return super().get_throttles()

    def get_serializer_context(self):
        # List views skip signed download URLs to keep payloads lean.
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
        """Lock the row and verify it is still editable.

        Callers must run this inside ``transaction.atomic()``: the row lock
        stops a concurrent submit/review from flipping the status between the
        editable check and the caller's write. ``verb`` names the blocked
        action for the ownership error ("edit", "upload documents", ...).
        """
        locked = KYCApplication.objects.select_for_update().get(pk=application.pk)
        if locked.applicant_id != self.request.user.id:
            raise ValidationError(f"Only the applicant can {verb}.")
        if locked.status not in KYCApplication.EDITABLE_STATUSES:
            raise ValidationError("This application can no longer be edited.")
        return locked

    def perform_create(self, serializer):
        # Atomic so the application row and its audit entry commit together.
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
            # Row lock: two concurrent submits cannot both pass the status check.
            application = KYCApplication.objects.select_for_update().get(pk=application.pk)
            if application.applicant_id != request.user.id:
                raise ValidationError("Only the applicant can submit this application.")
            if not application.documents.exists():
                raise ValidationError(
                    "At least one supporting document is required before submission."
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
                document.save()
                log_action(
                    application,
                    request.user,
                    AuditLog.Action.DOCUMENT_UPLOADED,
                    detail=f"{doc_type}: {file_obj.name}",
                )
        except Exception:
            # document.save() writes the file to storage before the row is
            # inserted; if anything after that fails (row insert, audit log),
            # the transaction rolls back but the file would remain on disk.
            # Once the storage write completes, file.name holds the generated
            # storage path (documents/...) rather than the original upload
            # name, so delete it to avoid orphaning PII.
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
        """Remove one document while the application is still editable.

        The post_delete signal removes the file from disk, so the row and the
        PII file always disappear together.
        """
        application = self.get_object()
        with transaction.atomic():
            application = self._locked_editable(application, "remove documents")

            try:
                document = application.documents.get(pk=doc_id)
            except (Document.DoesNotExist, ValueError, DjangoValidationError) as exc:
                # ValueError/ValidationError: malformed UUID in the URL -> 404, never 500.
                raise NotFound("Document not found.") from exc

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


class ReviewQueueView(generics.ListAPIView):
    """Reviewer-facing queue of applications awaiting a decision."""

    serializer_class = KYCApplicationSerializer
    permission_classes = (IsAuthenticated, IsReviewer)

    def get_serializer_context(self):
        # Queue rows need document metadata only, so skip the signed URLs.
        context = super().get_serializer_context()
        context["include_document_url"] = False
        return context

    def get_queryset(self):
        return (
            KYCApplication.objects.filter(status=KYCApplication.Status.SUBMITTED)
            .select_related("applicant")
            .prefetch_related("documents")
        )


class UserManagementViewSet(viewsets.ModelViewSet):
    """SUPER_ADMIN user management: list, create, change roles, reset passwords.

    Self-modification is blocked on update/delete/set-password: an operator
    must not be able to lock themselves out or silently change their own
    role. Deactivation is used instead of deletion so the audit trail and
    application history stay intact.
    """

    serializer_class = AdminUserSerializer
    permission_classes = (IsAuthenticated, IsSuperAdmin)
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = User.objects.all().order_by("-date_joined")
        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                models.Q(email__icontains=search)
                | models.Q(username__icontains=search)
                | models.Q(first_name__icontains=search)
                | models.Q(last_name__icontains=search)
            )
        role = self.request.query_params.get("role", "").strip()
        if role:
            if role not in User.Role.values:
                raise ValidationError(f"Invalid role: {role}")
            qs = qs.filter(role=role)
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return AdminUserCreateSerializer
        if self.action in ("partial_update", "update"):
            return AdminUserUpdateSerializer
        return AdminUserSerializer

    def perform_update(self, serializer):
        if serializer.instance.pk == self.request.user.pk:
            raise ValidationError("You cannot change your own role or status.")
        serializer.save()

    @action(detail=True, methods=["post"])
    def set_password(self, request, pk=None):
        user = self.get_object()
        if user.pk == request.user.pk:
            raise ValidationError("You cannot reset your own password here.")
        serializer = SetPasswordSerializer(
            data=request.data, context={"user": user}
        )
        serializer.is_valid(raise_exception=True)
        # set_password() changes the password hash, which also revokes all
        # existing JWTs for the user (CHECK_REVOKE_TOKEN compares the hash).
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        return Response({"detail": "Password updated."})


class AnalyticsView(APIView):
    """CEO analytics: KPIs, approval rate, pipeline breakdown, email activity."""

    permission_classes = (IsAuthenticated, IsCEO)

    def get(self, request):
        now = timezone.now()
        last_30 = now - timedelta(days=30)

        total = KYCApplication.objects.count()
        by_status = dict(
            KYCApplication.objects.values_list("status").annotate(count=Count("id"))
        )
        approved = by_status.get(KYCApplication.Status.APPROVED, 0)
        rejected = by_status.get(KYCApplication.Status.REJECTED, 0)
        decided = approved + rejected
        approval_rate = round(approved / decided * 100, 1) if decided else None

        recent = KYCApplication.objects.filter(created_at__gte=last_30).count()

        emails = EmailLog.objects.filter(created_at__gte=last_30)
        email_counts = dict(emails.values_list("status").annotate(count=Count("id")))
        recent_emails = EmailLog.objects.select_related("user").order_by("-created_at")[:20]

        return Response(
            {
                "kpis": {
                    "total_applications": total,
                    "submitted_last_30_days": recent,
                    "users": User.objects.count(),
                    "pending_review": by_status.get(KYCApplication.Status.SUBMITTED, 0),
                },
                "approval_rate": approval_rate,
                "pipeline": {s: by_status.get(s, 0) for s in KYCApplication.Status.values},
                "email_activity": {
                    "sent_last_30_days": email_counts.get(EmailLog.Status.SENT, 0),
                    "failed_last_30_days": email_counts.get(EmailLog.Status.FAILED, 0),
                    "recent": EmailLogSerializer(recent_emails, many=True).data,
                },
            }
        )


class DocumentDownloadView(APIView):
    """Serve a document behind a time-limited signed token.

    Tokens are issued by the API only after the ownership/role checks pass,
    and verified here statelessly via Django's ``TimestampSigner`` — letting
    browsers open the file without sending the JWT.
    """

    authentication_classes = ()
    permission_classes = (AllowAny,)
    # Unauthenticated endpoint: bound downloads per IP so the file-serving
    # path cannot be scraped or used for DoS.
    throttle_scope = "download"
    throttle_classes = (DownloadThrottle,)

    def get(self, request, doc_id):
        token = request.query_params.get("token", "")
        try:
            signed_id = TimestampSigner(salt=DOWNLOAD_TOKEN_SALT).unsign(
                token, max_age=DOWNLOAD_TOKEN_MAX_AGE
            )
        except signing.BadSignature as exc:
            # Covers forged tokens, tampered ids, and expired timestamps.
            # 404 (not 403) so an invalid token leaks nothing about the id.
            raise NotFound("Document not found.") from exc
        if signed_id != str(doc_id):
            # A valid token for a *different* document must not grant access.
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
        # attachment (not inline): in-browser PDF viewers execute embedded
        # JavaScript in the app origin's context, so a malicious PDF could
        # act with the viewer's session — forcing a download removes that
        # XSS surface. RFC 5987 filename* for non-ASCII names.
        response["Content-Disposition"] = (
            f"attachment; filename*=UTF-8''{quote(document.original_filename)}"
        )
        return response
