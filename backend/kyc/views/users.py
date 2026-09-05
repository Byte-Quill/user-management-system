"""Own-profile and SUPER_ADMIN user-management endpoints."""
from django.contrib.auth import get_user_model
from django.db import IntegrityError, models, transaction
from rest_framework import generics, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from kyc.common.permissions import IsSuperAdmin
from kyc.serializers import (
    AdminUserCreateSerializer,
    AdminUserSerializer,
    AdminUserUpdateSerializer,
    SetPasswordSerializer,
    UserSerializer,
)

User = get_user_model()

class MeView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        return self.request.user


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

    def perform_create(self, serializer):
        try:
            serializer.save()
        except IntegrityError as exc:
            # Concurrent creates can pass the serializer's existence checks
            # and lose to the DB unique constraints (email/phone/username).
            raise ValidationError(
                "An account with these details already exists."
            ) from exc

    def perform_update(self, serializer):
        if serializer.instance.pk == self.request.user.pk:
            raise ValidationError("You cannot change your own role or status.")
        with transaction.atomic():
            # Lock the active-super-admin set for the check-and-change, so
            # two concurrent mutual demotions cannot both commit and leave
            # the deployment with zero active super admins (only reachable
            # via that race: single actors can never target themselves, and
            # the actor is always one remaining active super admin).
            list(
                User.objects.select_for_update()
                .filter(role=User.Role.SUPER_ADMIN, is_active=True)
                .order_by("pk")
                .values_list("pk", flat=True)
            )
            serializer.save()
            if not User.objects.filter(
                role=User.Role.SUPER_ADMIN, is_active=True
            ).exists():
                raise ValidationError(
                    "Cannot demote or deactivate the last active super admin."
                )

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
