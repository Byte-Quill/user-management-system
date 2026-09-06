"""Application, document, audit and review serializers."""
from datetime import date

from rest_framework import serializers

from kyc.common.tokens import document_download_token
from kyc.models import AuditLog, Document, EmailLog, KYCApplication
from kyc.serializers.fields import normalize_phone, validate_dob

class DocumentSerializer(serializers.ModelSerializer):
    file = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = ("id", "doc_type", "file", "original_filename", "uploaded_at")
        read_only_fields = ("id", "uploaded_at")

    def get_file(self, obj):

        if not self.context.get("include_document_url", True):
            return None
        if not obj.file:
            return None
        request = self.context.get("request")
        if not request:
            return None

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
        return validate_dob(value)

    def validate_id_expiry(self, value):

        if value and self.instance is None and value < date.today():
            raise serializers.ValidationError(
                "The ID has already expired; provide a current expiry date."
            )
        return value

    def validate_phone(self, value):
        trimmed = value.strip()
        try:

            return normalize_phone(trimmed)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def validate(self, attrs):
        request = self.context.get("request")
        if not request:
            return attrs

        if self.instance and self.instance.status not in KYCApplication.EDITABLE_STATUSES:
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

class EmailLogSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True, default=None)

    class Meta:
        model = EmailLog
        fields = ("id", "purpose", "recipient", "subject", "status", "user_email", "created_at")
        read_only_fields = fields
