import re
from datetime import date

import phonenumbers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from phonenumbers import NumberParseException
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .email_domains import is_disposable_email
from .models import AuditLog, Document, KYCApplication, generate_user_id

User = get_user_model()

# Mirrors the SPA's validation.ts so the API is the source of truth:
# direct API clients cannot bypass the business rules.
DOB_MIN = date(1900, 1, 1)

# Person names: Unicode letters plus spaces, hyphens, apostrophes, periods
# ("O'Brien", "Anne-Marie", "M. K. Gandhi"). Digits and other symbols rejected.
NAME_CHARS_RE = re.compile(r"^(?:[^\W\d_]|[ \-'.])+$", re.UNICODE)

# Phone numbers are validated and normalised with libphonenumber (the
# ``phonenumbers`` package) — the same metadata the SPA's country-code picker
# uses, so client and server agree on what counts as a valid number. Input in
# national format (no leading '+') is interpreted against this default region;
# E164 input carries its own country code, so the region is only a fallback.
DEFAULT_PHONE_REGION = "IN"


def normalize_phone(value: str) -> str:
    """Canonical E164 form (e.g. "+919876543210") via libphonenumber.

    Storing one canonical form is what makes the unique constraint actually
    catch duplicates entered as "+91 98765 43210" vs "9876543210" vs
    "(98765) 432-10". Raises ``ValueError`` when the input is not a valid
    number for the default region.
    """
    try:
        parsed = phonenumbers.parse(value.strip(), DEFAULT_PHONE_REGION)
    except NumberParseException as exc:
        raise ValueError("Enter a valid phone number.") from exc
    if not phonenumbers.is_valid_number(parsed):
        raise ValueError("Enter a valid phone number for the selected country.")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def legacy_phone_key(value: str) -> str:
    """Pre-libphonenumber canonical form, kept for backwards-compatible lookups.

    Rows created before the libphonenumber switch may store national-format
    numbers as bare digits ("9876543210") rather than E164. Login still
    resolves those so existing accounts are never locked out by the stricter
    normalisation.
    """
    digits = re.sub(r"\D", "", value)
    return f"+{digits}" if value.strip().startswith("+") else digits


def validate_person_name(value: str, label: str, required: bool = True) -> str:
    value = value.strip()
    if not value:
        if required:
            raise serializers.ValidationError(f"{label} is required.")
        return ""
    if len(value) > 150:
        raise serializers.ValidationError(f"{label} must be at most 150 characters.")
    if not NAME_CHARS_RE.match(value):
        raise serializers.ValidationError(
            f"{label} may only contain letters, spaces, hyphens, apostrophes and periods."
        )
    return value


class PasswordField(serializers.CharField):
    """Write-only password field for registration.

    The full AUTH_PASSWORD_VALIDATORS policy is applied in
    ``RegisterSerializer.validate`` (with a user instance, so the
    attribute-similarity validator can compare against email/username).
    """

    def __init__(self, **kwargs):
        kwargs.setdefault("write_only", True)
        kwargs.setdefault("min_length", 8)
        super().__init__(**kwargs)


class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """JWT serializer that authenticates with email (or phone) + password.

    ``TokenObtainSerializer.validate`` authenticates against
    ``attrs[self.username_field]``; ``username_field`` points at ``email``.
    The identifier (email or phone) is passed through unchanged and resolved
    by ``EmailOrPhoneBackend`` against both unique columns, so phone-only
    accounts (email IS NULL) authenticate too.
    """

    username_field = "email"

    def validate(self, attrs):
        # The identifier (email or phone) is passed through unchanged;
        # EmailOrPhoneBackend resolves it against both unique columns, so
        # phone-only accounts (email IS NULL) authenticate too.
        data = super().validate(attrs)
        # Hard email verification: the password was right, but the account
        # stays locked until the signup OTP proves inbox ownership. Only
        # applies to accounts that HAVE an email — phone-only accounts have
        # nothing to verify and sign in immediately. The specific error code
        # is safe here — only someone who knows this account's password ever
        # sees it, so it cannot enumerate *other* accounts.
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

    def validate_email(self, value):
        # Email is optional (a phone alone is enough); normalize empty to None.
        if not value:
            return None
        # KYC accounts must be reachable long-term, so disposable / temp-mail
        # providers are rejected at signup. EmailField already guarantees a
        # syntactically valid address; this adds the domain blocklist check.
        if is_disposable_email(value):
            raise serializers.ValidationError(
                "Disposable or temporary email addresses are not allowed. "
                "Please use a permanent email address."
            )
        return value

    def validate_first_name(self, value):
        return validate_person_name(value, "First name")

    def validate_middle_name(self, value):
        return validate_person_name(value, "Middle name", required=False)

    def validate_last_name(self, value):
        return validate_person_name(value, "Last name")

    def validate_date_of_birth(self, value):
        # Same sanity bounds as KYCApplicationSerializer.
        if value is None:
            return None
        if value > date.today():
            raise serializers.ValidationError("Date of birth cannot be in the future.")
        if value < DOB_MIN:
            raise serializers.ValidationError("Enter a valid date of birth.")
        return value

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
        # Explicitly declared fields do not receive the ModelSerializer's
        # UniqueValidator, so enforce uniqueness here — otherwise a duplicate
        # hits the DB constraint and surfaces as a 500 instead of a 400.
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


class DocumentSerializer(serializers.ModelSerializer):
    file = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = ("id", "doc_type", "file", "original_filename", "uploaded_at")
        read_only_fields = ("id", "uploaded_at")

    def get_file(self, obj):
        # List serialization (review queue, dashboard) only needs metadata —
        # skip building the per-document download URL.
        if not self.context.get("include_document_url", True):
            return None
        if not obj.file:
            return None
        request = self.context.get("request")
        if not request:
            return None
        # Time-limited signed URL served by our own download view: the token
        # is only issued to users who already passed the permission checks,
        # so the browser can open the file in a new tab without the JWT.
        from .models import document_download_token

        url = f"/api/documents/{obj.id}/download/?token={document_download_token(obj.id)}"
        return request.build_absolute_uri(url)


class AuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="actor.email", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = ("id", "action", "detail", "actor_email", "created_at")
        read_only_fields = fields


class KYCApplicationSerializer(serializers.ModelSerializer):
    documents = DocumentSerializer(many=True, read_only=True)
    # applicant_id is the stable ownership key (email can be null for
    # phone-only accounts, so it cannot be used to identify the owner).
    applicant_id = serializers.IntegerField(source="applicant.id", read_only=True)
    applicant_email = serializers.EmailField(
        source="applicant.email", read_only=True, default=None
    )
    reviewer_email = serializers.EmailField(source="reviewer.email", read_only=True, default=None)

    class Meta:
        model = KYCApplication
        fields = (
            "id",
            "applicant_id",
            "applicant_email",
            "status",
            "full_name",
            "date_of_birth",
            "nationality",
            "phone",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "id_type",
            "id_number",
            "id_expiry",
            "reviewer_email",
            "review_notes",
            "reviewed_at",
            "documents",
            "created_at",
            "updated_at",
            "submitted_at",
        )
        read_only_fields = (
            "id",
            "status",
            "applicant_email",
            "reviewer_email",
            "review_notes",
            "reviewed_at",
            "created_at",
            "updated_at",
            "submitted_at",
        )

    def validate_date_of_birth(self, value):
        if value > date.today():
            raise serializers.ValidationError("Date of birth cannot be in the future.")
        if value < DOB_MIN:
            raise serializers.ValidationError("Enter a valid date of birth.")
        return value

    def validate_phone(self, value):
        trimmed = value.strip()
        try:
            # Store the canonical E164 form, matching the registration path.
            return normalize_phone(trimmed)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate(self, attrs):
        request = self.context.get("request")
        if not request:
            return attrs
        # Applicants may only edit while the application is a draft or needs resubmission
        if self.instance:
            editable = (
                KYCApplication.Status.DRAFT,
                KYCApplication.Status.RESUBMISSION_REQUESTED,
            )
            if self.instance.status not in editable:
                raise serializers.ValidationError(
                    "This application can no longer be edited."
                )
        return attrs


class ReviewSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=KYCApplication.Decision.choices)
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs["decision"] in (
            KYCApplication.Decision.REJECT,
            KYCApplication.Decision.REQUEST_RESUBMISSION,
        ) and not attrs["notes"].strip():
            raise serializers.ValidationError(
                {"notes": "Notes are required when rejecting or requesting resubmission."}
            )
        return attrs
