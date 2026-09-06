import { isValidPhoneNumber } from "libphonenumber-js/max";

import type { ApplicationPayload } from "@/types";
import { isDisposableEmail } from "@/data/disposableEmails";


export type FieldErrors<T extends string = string> = Partial<Record<T, string>>;


export const MAX_FILE_SIZE_MB = 5;
export const ALLOWED_FILE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".pdf"];


export const LIMITS = {
  fullName: 255,
  name: 150,
  nationality: 100,
  phone: 30,
  email: 254,
  addressLine1: 255,
  addressLine2: 255,
  city: 100,
  state: 100,
  postalCode: 20,
  country: 100,
  idNumber: 100,
};

export const DOB_MIN_ISO = "1900-01-01";
export const OTP_LENGTH = 6;
export const PASSWORD_MIN_LENGTH = 8;

export const APPLICATION_ID_TYPES = [
  "passport",
  "national_id",
  "drivers_license",
] as const;

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;


const NAME_RE = /^(?:\p{L}\p{M}*|[ \-'.])+$/u;
const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

// Small subset of Django's CommonPasswordValidator list.
const COMMON_PASSWORDS = new Set([
  "password", "password1", "123456", "1234567", "12345678", "123456789",
  "1234567890", "12345", "qwerty", "qwerty123", "abc123", "iloveyou",
  "admin", "welcome", "letmein", "monkey", "dragon", "sunshine",
  "princess", "football", "superman", "trustno1", "shadow", "111111",
]);

export const isBlank = (value: string): boolean => value.trim() === "";


export function capitalizeFirst(value: string): string {
  const trimmed = value.trimStart();
  if (!trimmed || !/^\p{Ll}/u.test(trimmed)) return value;
  return value.slice(0, value.length - trimmed.length) + trimmed[0].toUpperCase() + trimmed.slice(1);
}


export function capitalizeWords(value: string): string {
  return value.replace(/(^|[\s'-])(\p{Ll})/gu, (_, sep: string, ch: string) => sep + ch.toUpperCase());
}

function isValidISODate(value: string): boolean {
  return ISO_DATE_RE.test(value) && !Number.isNaN(Date.parse(value));
}

/** Local date as YYYY-MM-DD (toISOString uses UTC and can be off by a day). */
export function todayISO(): string {
  const d = new Date();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${month}-${day}`;
}

export function validateEmail(value: string): string | null {
  if (isBlank(value)) return "Email is required.";
  if (!EMAIL_RE.test(value.trim())) return "Enter a valid email address.";
  return null;
}

/**
 * Registration-only email check: format + disposable/temp-mail blocklist.
 * Mirrors RegisterSerializer.validate_email on the backend. Login, password
 * reset and OTP verification intentionally use plain validateEmail so
 * existing accounts are never locked out by a later blocklist change.
 */
export function validateRegistrationEmail(value: string): string | null {
  const formatError = validateEmail(value);
  if (formatError) return formatError;
  if (isDisposableEmail(value.trim())) {
    return "Disposable or temporary email addresses are not allowed. Please use a permanent email address.";
  }
  return null;
}

/** Mirrors kyc/serializers.py validate_person_name. */
export function validateName(
  value: string,
  label: string,
  required = true
): string | null {
  const trimmed = value.trim();
  if (!trimmed) return required ? `${label} is required.` : null;
  if (trimmed.length > LIMITS.name) {
    return `${label} must be at most ${LIMITS.name} characters.`;
  }
  if (!NAME_RE.test(trimmed)) {
    return `${label} may only contain letters, spaces, hyphens, apostrophes and periods.`;
  }
  if (/^\p{Ll}/u.test(trimmed)) {
    return `${label} must start with a capital letter.`;
  }
  return null;
}

export const GENDER_OPTIONS = [
  { value: "male", label: "Male" },
  { value: "female", label: "Female" },
  { value: "other", label: "Other" },
  { value: "prefer_not_to_say", label: "Prefer not to say" },
] as const;

export function validateGender(value: string): string | null {
  if (!GENDER_OPTIONS.some((option) => option.value === value)) {
    return "Please select a gender.";
  }
  return null;
}

/** Login identifier: a valid email OR a valid phone number. */
export function validateIdentifier(value: string): string | null {
  if (isBlank(value)) return "Email or phone is required.";
  const trimmed = value.trim();
  if (trimmed.includes("@")) return validateEmail(trimmed);
  const phoneError = validatePhone(trimmed);
  if (phoneError) return "Enter a valid email address or phone number.";
  return null;
}

/** 6-digit email OTP (mirrors kyc/services/otp.py OTP_LENGTH). */
export function validateOtp(value: string): string | null {
  if (isBlank(value)) return `Enter the ${OTP_LENGTH}-digit code.`;
  if (!new RegExp(`^\\d{${OTP_LENGTH}}$`).test(value.trim())) {
    return `The code must be exactly ${OTP_LENGTH} digits.`;
  }
  return null;
}

/** Mirrors Django's AUTH_PASSWORD_VALIDATORS (server enforces min length 8). */
export function validatePassword(value: string): string | null {
  if (!value) return "Password is required.";
  if (value.length < PASSWORD_MIN_LENGTH) {
    return `Password must be at least ${PASSWORD_MIN_LENGTH} characters.`;
  }
  if (/^\d+$/.test(value)) return "Password cannot be entirely numeric.";
  if (COMMON_PASSWORDS.has(value.toLowerCase())) {
    return "This password is too common. Please choose something else.";
  }
  return null;
}


export function validateConfirmPassword(password: string, confirm: string): string | null {
  if (!confirm) return "Please confirm your password.";
  if (password !== confirm) return "Passwords do not match.";
  return null;
}


export function validateLoginPassword(value: string): string | null {
  if (!value) return "Password is required.";
  return null;
}

export function validateRequired(
  value: string,
  label: string,
  maxLength?: number
): string | null {
  if (isBlank(value)) return `${label} is required.`;
  if (maxLength !== undefined && value.length > maxLength) {
    return `${label} must be at most ${maxLength} characters.`;
  }
  return null;
}

export function validateOptional(
  value: string,
  label: string,
  maxLength: number
): string | null {
  if (value && value.length > maxLength) {
    return `${label} must be at most ${maxLength} characters.`;
  }
  return null;
}

export function validatePhone(value: string): string | null {
  if (isBlank(value)) return "Phone is required.";
  const trimmed = value.trim();
  if (trimmed.length > LIMITS.phone) {
    return `Phone must be at most ${LIMITS.phone} characters.`;
  }
  if (!/^\+?[\d\s\-().]+$/.test(trimmed)) {
    return "Enter a valid phone number (digits, spaces, + - ( ) .).";
  }
  const digits = trimmed.replace(/\D/g, "");
  if (digits.length < 7 || digits.length > 15) {
    return "Phone must contain 7-15 digits.";
  }
  return null;
}


export function validateE164Phone(value: string): string | null {
  if (isBlank(value)) return "Phone is required.";
  if (!isValidPhoneNumber(value)) {
    return "Enter a valid phone number for the selected country.";
  }
  return null;
}

export function validateDateOfBirth(value: string): string | null {
  if (isBlank(value)) return "Date of birth is required.";
  if (!isValidISODate(value)) return "Enter a valid date.";
  if (value > todayISO()) return "Date of birth cannot be in the future.";
  if (value < DOB_MIN_ISO) return "Enter a valid date of birth.";
  return null;
}


export function validateOptionalDateOfBirth(value: string): string | null {
  if (!value) return null;
  if (!isValidISODate(value)) return "Enter a valid date.";
  if (value > todayISO()) return "Date of birth cannot be in the future.";
  if (value < DOB_MIN_ISO) return "Enter a valid date of birth.";
  return null;
}

export function validateIdExpiry(value: string): string | null {
  if (!value) return null;
  if (!isValidISODate(value)) return "Enter a valid date.";
  return null;
}


export function validateUploadFile(file: File): string | null {
  const dot = file.name.lastIndexOf(".");
  const ext = dot >= 0 ? file.name.slice(dot).toLowerCase() : "";
  if (!ALLOWED_FILE_EXTENSIONS.includes(ext)) {
    return `File type '${ext || "unknown"}' is not allowed. Use JPG, PNG or PDF.`;
  }
  if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
    return `File exceeds the ${MAX_FILE_SIZE_MB} MB size limit.`;
  }
  return null;
}


export function validateReviewNotes(decision: string, notes: string): string | null {
  if (decision !== "approve" && isBlank(notes)) {
    return "Notes are required when rejecting or requesting resubmission.";
  }
  return null;
}


export function validateApplication(
  form: ApplicationPayload
): FieldErrors<keyof ApplicationPayload> {
  const errors: FieldErrors<keyof ApplicationPayload> = {};
  const check = (key: keyof ApplicationPayload, message: string | null) => {
    if (message) errors[key] = message;
  };

  check("full_name", validateRequired(form.full_name, "Full name", LIMITS.fullName));
  check("date_of_birth", validateDateOfBirth(form.date_of_birth));
  check("nationality", validateRequired(form.nationality, "Nationality", LIMITS.nationality));
  check("phone", validateE164Phone(form.phone));
  check("address_line1", validateRequired(form.address_line1, "Address line 1", LIMITS.addressLine1));
  check("address_line2", validateOptional(form.address_line2, "Address line 2", LIMITS.addressLine2));
  check("city", validateRequired(form.city, "City", LIMITS.city));
  check("state", validateRequired(form.state, "State", LIMITS.state));
  check("postal_code", validateRequired(form.postal_code, "Postal code", LIMITS.postalCode));
  check("country", validateRequired(form.country, "Country", LIMITS.country));
  check("id_number", validateRequired(form.id_number, "ID number", LIMITS.idNumber));
  check("id_expiry", validateIdExpiry(form.id_expiry ?? ""));
  if (!(APPLICATION_ID_TYPES as readonly string[]).includes(form.id_type)) {
    errors.id_type = "Select a valid ID type.";
  }
  return errors;
}
