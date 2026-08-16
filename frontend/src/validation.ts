import type { ApplicationPayload } from "./types";

/**
 * Client-side validators mirroring the backend rules (kyc/models.py field
 * limits, config/settings.py upload limits, DRF serializer checks) so users
 * get immediate feedback. The server remains the source of truth.
 */

export type FieldErrors<T extends string = string> = Partial<Record<T, string>>;

// Mirror MAX_UPLOAD_SIZE_MB / ALLOWED_UPLOAD_EXTENSIONS in config/settings.py.
export const MAX_FILE_SIZE_MB = 5;
export const ALLOWED_FILE_EXTENSIONS = [".jpg", ".jpeg", ".png", ".pdf"];

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
// Django's UnicodeUsernameValidator: letters, digits and @/./+/-/_ only.
const USERNAME_RE = /^[\p{L}\p{N}._@+-]+$/u;
const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

// Small subset of Django's CommonPasswordValidator list — catches the most
// frequent choices without bundling the full ~1000-entry dataset.
const COMMON_PASSWORDS = new Set([
  "password", "password1", "123456", "1234567", "12345678", "123456789",
  "1234567890", "12345", "qwerty", "qwerty123", "abc123", "iloveyou",
  "admin", "welcome", "letmein", "monkey", "dragon", "sunshine",
  "princess", "football", "superman", "trustno1", "shadow", "111111",
]);

export const isBlank = (value: string): boolean => value.trim() === "";

function isValidISODate(value: string): boolean {
  return ISO_DATE_RE.test(value) && !Number.isNaN(Date.parse(value));
}

/** Local date as YYYY-MM-DD (toISOString uses UTC and can be off by a day). */
function todayISO(): string {
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

export function validateUsername(value: string): string | null {
  if (isBlank(value)) return "Username is required.";
  if (value.length > 150) return "Username must be at most 150 characters.";
  if (!USERNAME_RE.test(value)) {
    return "Username may only contain letters, digits and @ . + - _ characters.";
  }
  return null;
}

/** Mirrors Django's AUTH_PASSWORD_VALIDATORS (server enforces min length 8). */
export function validatePassword(value: string): string | null {
  if (!value) return "Password is required.";
  if (value.length < 8) return "Password must be at least 8 characters.";
  if (/^\d+$/.test(value)) return "Password cannot be entirely numeric.";
  if (COMMON_PASSWORDS.has(value.toLowerCase())) {
    return "This password is too common. Please choose something else.";
  }
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
  if (trimmed.length > 30) return "Phone must be at most 30 characters.";
  if (!/^\+?[\d\s\-().]+$/.test(trimmed)) {
    return "Enter a valid phone number (digits, spaces, + - ( ) .).";
  }
  const digits = trimmed.replace(/\D/g, "");
  if (digits.length < 7 || digits.length > 15) {
    return "Phone must contain 7-15 digits.";
  }
  return null;
}

export function validateDateOfBirth(value: string): string | null {
  if (isBlank(value)) return "Date of birth is required.";
  if (!isValidISODate(value)) return "Enter a valid date.";
  if (value > todayISO()) return "Date of birth cannot be in the future.";
  if (value < "1900-01-01") return "Enter a valid date of birth.";
  return null;
}

export function validateIdExpiry(value: string): string | null {
  if (!value) return null; // optional field
  if (!isValidISODate(value)) return "Enter a valid date.";
  return null;
}

/** Mirrors Document.clean(): extension allow-list + 5 MB size cap. */
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

/** Mirrors ReviewSerializer: notes required for reject / request_resubmission. */
export function validateReviewNotes(decision: string, notes: string): string | null {
  if (decision !== "approve" && isBlank(notes)) {
    return "Notes are required when rejecting or requesting resubmission.";
  }
  return null;
}

/** Validate the KYC application form; limits mirror the KYCApplication model. */
export function validateApplication(
  form: ApplicationPayload
): FieldErrors<keyof ApplicationPayload> {
  const errors: FieldErrors<keyof ApplicationPayload> = {};
  const check = (key: keyof ApplicationPayload, message: string | null) => {
    if (message) errors[key] = message;
  };

  check("full_name", validateRequired(form.full_name, "Full name", 255));
  check("date_of_birth", validateDateOfBirth(form.date_of_birth));
  check("nationality", validateRequired(form.nationality, "Nationality", 100));
  check("phone", validatePhone(form.phone));
  check("address_line1", validateRequired(form.address_line1, "Address line 1", 255));
  check("address_line2", validateOptional(form.address_line2, "Address line 2", 255));
  check("city", validateRequired(form.city, "City", 100));
  check("state", validateRequired(form.state, "State", 100));
  check("postal_code", validateRequired(form.postal_code, "Postal code", 20));
  check("country", validateRequired(form.country, "Country", 100));
  check("id_number", validateRequired(form.id_number, "ID number", 100));
  check("id_expiry", validateIdExpiry(form.id_expiry ?? ""));
  if (!["passport", "national_id", "drivers_license"].includes(form.id_type)) {
    errors.id_type = "Select a valid ID type.";
  }
  return errors;
}
