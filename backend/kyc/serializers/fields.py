"""Shared serializer fields and validators (mirrors the SPA validation rules)."""
import re
from datetime import date

import phonenumbers
from phonenumbers import NumberParseException
from rest_framework import serializers


DOB_MIN = date(1900, 1, 1)


NAME_CHARS_RE = re.compile(r"^(?:[^\W\d_]|[ \-'.])+$", re.UNICODE)


DEFAULT_PHONE_REGION = "IN"


def normalize_phone(value: str) -> str:
    """Canonical E164 form (e.g. "+919876543210") via libphonenumber."""
    try:
        parsed = phonenumbers.parse(value.strip(), DEFAULT_PHONE_REGION)
    except NumberParseException as exc:
        raise ValueError("Enter a valid phone number.") from exc
    if not phonenumbers.is_valid_number(parsed):
        raise ValueError("Enter a valid phone number for the selected country.")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def legacy_phone_key(value: str) -> str:
    """Pre-libphonenumber canonical form, kept for backwards-compatible lookups."""
    digits = re.sub(r"\D", "", value)
    return f"+{digits}" if value.strip().startswith("+") else digits


def validate_dob(value):
    """Shared sanity bounds for dates of birth (registration + application)."""
    if value > date.today():
        raise serializers.ValidationError("Date of birth cannot be in the future.")
    if value < DOB_MIN:
        raise serializers.ValidationError("Enter a valid date of birth.")
    return value


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

    return value[0].upper() + value[1:]


class PasswordField(serializers.CharField):
    """Write-only password field for registration."""

    def __init__(self, **kwargs):
        kwargs.setdefault("write_only", True)
        kwargs.setdefault("min_length", 8)
        super().__init__(**kwargs)
