"""Own-profile and SUPER_ADMIN user-management endpoints."""

from django.contrib.auth import get_user_model
from django.db import IntegrityError, models, transaction
from rest_framework import generics, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from kyc.common.permissions import IsSuperAdmin
from kyc.common.tokens import revoke_user_sessions
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
    """SUPER_ADMIN user management: list, create, change roles, reset passwords."""

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
            raise ValidationError("An account with these details already exists.") from exc

    def perform_update(self, serializer):
        if serializer.instance.pk == self.request.user.pk:
            raise ValidationError("You cannot change your own role or status.")
        with transaction.atomic():
            list(
                User.objects.select_for_update()
                .filter(role=User.Role.SUPER_ADMIN, is_active=True)
                .order_by("pk")
                .values_list("pk", flat=True)
            )
            serializer.save()
            if not User.objects.filter(role=User.Role.SUPER_ADMIN, is_active=True).exists():
                raise ValidationError("Cannot demote or deactivate the last active super admin.")

    @action(detail=True, methods=["post"])
    def set_password(self, request, pk=None):
        user = self.get_object()
        if user.pk == request.user.pk:
            raise ValidationError("You cannot reset your own password here.")
        serializer = SetPasswordSerializer(data=request.data, context={"user": user})
        serializer.is_valid(raise_exception=True)

        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        # The admin-console copy promises that this revokes active sessions:
        # blacklist refresh tokens issued before the reset to make it true.
        revoke_user_sessions(user)
        return Response({"detail": "Password updated."})
