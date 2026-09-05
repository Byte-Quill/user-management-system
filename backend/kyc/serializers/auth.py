"""Auth and account serializers: login, registration, own profile."""
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
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
    """JWT serializer that authenticates with email (or phone) + password.

    The identifier is passed through unchanged and resolved by
    ``EmailOrPhoneBackend`` against both unique columns.
    """

    username_field = "email"

    def validate(self, attrs):
        data = super().validate(attrs)
        # The password was right, but the account stays locked until the
        # signup OTP proves inbox ownership (phone-only accounts have
        # nothing to verify). Only the password holder ever sees this code,
        # so it cannot enumerate other accounts.
        if self.user.email and not self.user.email_verified:
            raise PermissionDenied(
                {"detail": "Verify your email to sign in.", "code": "email_not_verified"}
            )
        return data


class RegisterSerializer(serializers.ModelSerializer):
    """Account creation: email + phone + password + name + gender.

    The public User ID (``username``) is auto-generated server-side — it is
    never accepted from the client, so it cannot be squatted or probed.
    """

    password = PasswordField()
    role = serializers.CharField(read_only=True)
    username = serializers.CharField(read_only=True)
    # Email and phone are each optional, but at least one is required
    # (enforced in validate()). This lets users sign up with just a phone.
    email = serializers.EmailField(
        required=False, allow_blank=True, allow_null=True, default=None
    )

    def validate_email(self, value):
        # Canonical lowercase form: login and Google linking match
        # case-insensitively, so storing mixed case would create accounts
        # that differ only by email case. Email is optional (a phone alone
        # is enough), so empty input normalizes to None.
        if not value:
            return None
        value = value.strip().lower()
        # Disposable / temp-mail providers are rejected at signup so KYC
        # accounts stay reachable long-term.
        if is_disposable_email(value):
            raise serializers.ValidationError(
                "Disposable or temporary email addresses are not allowed. "
                "Please use a permanent email address."
            )
        return value

    # AbstractUser's name fields are blank=True, which DRF would make
    # optional; registration requires first and last names.
    first_name = serializers.CharField(max_length=150)
    middle_name = serializers.CharField(
        max_length=150, required=False, allow_blank=True, default=""
    )
    last_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(
        max_length=30, required=False, allow_blank=True, allow_null=True, default=None
    )
    gender = serializers.ChoiceField(choices=User.Gender.choices)
    # Optional profile details — blankable so minimal signups and
    # Google-provisioned accounts stay valid. Limits mirror KYCApplication
    # so the application form can prefill from the profile 1:1.
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
        # Phone is optional (an email alone is enough); normalize empty to None.
        if not value:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        try:
            normalized = normalize_phone(trimmed)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        # Explicitly declared fields skip the ModelSerializer's UniqueValidator;
        # enforce uniqueness here or duplicates 500 on the DB constraint.
        if User.objects.filter(phone=normalized).exists():
            raise serializers.ValidationError("This phone number is already registered.")
        return normalized

    def validate(self, attrs):
        # At least one contact method is required: email OR phone.
        if not attrs.get("email") and not attrs.get("phone"):
            raise serializers.ValidationError(
                "Provide an email address or a phone number (at least one is required)."
            )
        # create_user() does not run Django's password validators, so enforce
        # AUTH_PASSWORD_VALIDATORS here. Passing an (unsaved) user lets the
        # attribute-similarity validator compare against email/names/phone.
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
