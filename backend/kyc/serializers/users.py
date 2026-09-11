"""User-management serializers (SUPER_ADMIN console)."""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers

from kyc.common.email_domains import is_disposable_email
from kyc.models import generate_user_id
from kyc.serializers.fields import PasswordField, normalize_phone, validate_person_name

User = get_user_model()

class AdminUserSerializer(serializers.ModelSerializer):
    """Read representation of a user for the management console."""

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "phone",
            "role",
            "email_verified",
            "is_active",
            "date_joined",
        )
        read_only_fields = fields


class AdminUserCreateSerializer(serializers.ModelSerializer):
    """SUPER_ADMIN account creation: contact + password + role."""

    password = PasswordField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "password",
            "first_name",
            "last_name",
            "phone",
            "role",
        )
        read_only_fields = ("id", "username")

    def validate_email(self, value):

        if not value:
            return value
        value = value.strip().lower()
        # Same rule as self-registration (RegisterSerializer): keep burner
        # domains out of every account-creation path.
        if is_disposable_email(value):
            raise serializers.ValidationError(
                "Disposable or temporary email addresses are not allowed."
            )
        return value

    def validate_first_name(self, value):
        return validate_person_name(value, "First name")

    def validate_last_name(self, value):
        return validate_person_name(value, "Last name")

    def validate_phone(self, value):
        if not value:
            return None
        try:
            normalized = normalize_phone(value.strip())
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        if User.objects.filter(phone=normalized).exists():
            raise serializers.ValidationError("This phone number is already registered.")
        return normalized

    def validate(self, attrs):
        if not attrs.get("email") and not attrs.get("phone"):
            raise serializers.ValidationError(
                "Provide an email address or a phone number (at least one is required)."
            )
        user = User(
            email=attrs.get("email"),
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
            phone=attrs.get("phone"),
        )
        try:
            validate_password(attrs["password"], user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": exc.messages}) from exc
        return attrs

    def create(self, validated_data):

        for attempt in range(3):
            try:
                with transaction.atomic():
                    return User.objects.create_user(
                        email=validated_data.get("email"),
                        username=generate_user_id(),
                        password=validated_data["password"],
                        first_name=validated_data["first_name"],
                        last_name=validated_data["last_name"],
                        phone=validated_data.get("phone"),
                        role=validated_data.get("role", User.Role.APPLICANT),
                        email_verified=True,
                    )
            except IntegrityError as exc:
                if "username" in str(exc) and attempt < 2:
                    continue
                raise


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    """Role / active-status changes. Self-modification is blocked in the view."""

    class Meta:
        model = User
        fields = ("role", "is_active")


class SetPasswordSerializer(serializers.Serializer):
    """Direct password reset by a SUPER_ADMIN."""

    new_password = PasswordField()

    def validate_new_password(self, value):
        user = self.context.get("user")
        try:
            validate_password(value, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return value
