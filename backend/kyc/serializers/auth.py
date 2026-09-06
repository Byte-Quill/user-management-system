"""Auth and account serializers: login, registration, own profile."""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from kyc.common.email_domains import is_disposable_email
from kyc.models import generate_user_id
from kyc.serializers.fields import (
    PasswordField,
    normalize_phone,
    validate_dob,
    validate_person_name,
)

User = get_user_model()

class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """JWT serializer that authenticates with email (or phone) + password."""

    username_field = "email"

    def validate(self, attrs):
        data = super().validate(attrs)

        if self.user.email and not self.user.email_verified:
            raise PermissionDenied(
                {"detail": "Verify your email to sign in.", "code": "email_not_verified"}
            )
        return data


class RegisterSerializer(serializers.ModelSerializer):
    """Account creation: email + phone + password + name + gender."""

    password = PasswordField()
    role = serializers.CharField(read_only=True)
    username = serializers.CharField(read_only=True)

    email = serializers.EmailField(
        required=False, allow_blank=True, allow_null=True, default=None
    )

    def validate_email(self, value):

        if not value:
            return None
        value = value.strip().lower()

        if is_disposable_email(value):
            raise serializers.ValidationError(
                "Disposable or temporary email addresses are not allowed. "
                "Please use a permanent email address."
            )
        return value

    first_name = serializers.CharField(max_length=150)
    middle_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True, default=""
    )
    last_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(
        max_length=30, required=False, allow_blank=True, allow_null=True, default=None
    )
    gender = serializers.ChoiceField(choices=User.Gender.choices)

    date_of_birth = serializers.DateField(required=False, allow_null=True, default=None)
    nationality = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default=""
    )
    address_line1 = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
    address_line2 = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )
    city = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    state = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    postal_code = serializers.CharField(
        max_length=20, required=False, allow_blank=True, default=""
    )
    country = serializers.CharField(
        max_length=100, required=False, allow_blank=True, default=""
    )

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "password",
            "first_name",
            "middle_name",
            "last_name",
            "phone",
            "gender",
            "date_of_birth",
            "nationality",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "role",
        )
    def validate_first_name(self, value):
        return validate_person_name(value, "First name")

    def validate_middle_name(self, value):
        return validate_person_name(value, "Middle name", required=False)

    def validate_last_name(self, value):
        return validate_person_name(value, "Last name")

    def validate_date_of_birth(self, value):
        if value is None:
            return None
        return validate_dob(value)

    def validate_phone(self, value):

        if not value:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        try:
            normalized = normalize_phone(trimmed)
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
            middle_name=attrs.get("middle_name", ""),
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
                        middle_name=validated_data.get("middle_name", ""),
                        last_name=validated_data["last_name"],
                        phone=validated_data.get("phone"),
                        gender=validated_data["gender"],
                        date_of_birth=validated_data.get("date_of_birth"),
                        nationality=validated_data.get("nationality", ""),
                        address_line1=validated_data.get("address_line1", ""),
                        address_line2=validated_data.get("address_line2", ""),
                        city=validated_data.get("city", ""),
                        state=validated_data.get("state", ""),
                        postal_code=validated_data.get("postal_code", ""),
                        country=validated_data.get("country", ""),
                        role=User.Role.APPLICANT,
                    )
            except IntegrityError as exc:
                if "username" in str(exc) and attempt < 2:
                    continue
                raise


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "first_name",
            "middle_name",
            "last_name",
            "phone",
            "gender",
            "date_of_birth",
            "nationality",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "role",
            "email_verified",
        )
        read_only_fields = fields
