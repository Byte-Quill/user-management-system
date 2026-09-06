import { describe, expect, test } from "bun:test";

import type { ApplicationPayload } from "@/types";
import {
  ALLOWED_FILE_EXTENSIONS,
  MAX_FILE_SIZE_MB,
  capitalizeFirst,
  capitalizeWords,
  validateApplication,
  validateConfirmPassword,
  validateDateOfBirth,
  validateE164Phone,
  validateEmail,
  validateGender,
  validateIdExpiry,
  validateIdentifier,
  validateLoginPassword,
  validateName,
  validateOtp,
  validateOptional,
  validateOptionalDateOfBirth,
  validatePassword,
  validatePhone,
  validateRegistrationEmail,
  validateRequired,
  validateReviewNotes,
  validateUploadFile,
} from "@/lib/validation";


const validApplication = (): ApplicationPayload => ({
  full_name: "Ada Lovelace",
  date_of_birth: "1990-01-31",
  nationality: "British",
  phone: "+919876543210",
  address_line1: "12 St James's Square",
  address_line2: "",
  city: "London",
  state: "Greater London",
  postal_code: "SW1Y 4LE",
  country: "United Kingdom",
  id_number: "P1234567",
  id_expiry: "2030-06-30",
  id_type: "passport",
});

describe("validateEmail", () => {
  test("accepts a normal address", () => {
    expect(validateEmail("user@example.com")).toBeNull();
  });

  test("rejects blank and malformed input", () => {
    expect(validateEmail("")).toBe("Email is required.");
    expect(validateEmail("   ")).toBe("Email is required.");
    expect(validateEmail("not-an-email")).toBe("Enter a valid email address.");
    expect(validateEmail("a@b")).toBe("Enter a valid email address.");
  });
});

describe("validateRegistrationEmail", () => {
  test("accepts a permanent domain", () => {
    expect(validateRegistrationEmail("user@example.com")).toBeNull();
  });

  test("rejects disposable/temp-mail domains", () => {

    const msg = validateRegistrationEmail("user@mailinator.com");
    expect(msg).toContain("Disposable or temporary email addresses are not allowed");
  });

  test("still validates format first", () => {
    expect(validateRegistrationEmail("garbage")).toBe("Enter a valid email address.");
  });
});

describe("validateName", () => {
  test("accepts letters with spaces, hyphens, apostrophes, periods", () => {
    expect(validateName("Jean-Luc O'Neill Jr.", "Full name")).toBeNull();
    expect(validateName("李明", "Full name")).toBeNull();
  });

  test("enforces required, length and charset rules", () => {
    expect(validateName("", "Full name")).toBe("Full name is required.");
    expect(validateName("   ", "Full name")).toBe("Full name is required.");
    expect(validateName("A".repeat(151), "Full name")).toContain("at most 150 characters.");
    expect(validateName("John123", "Full name")).toContain(
      "may only contain letters, spaces, hyphens, apostrophes and periods."
    );
  });

  test("optional names may be blank", () => {
    expect(validateName("", "Middle name", false)).toBeNull();
  });

  test("names must start with a capital letter", () => {
    expect(validateName("john", "First name")).toBe(
      "First name must start with a capital letter."
    );
    expect(validateName("john doe", "Full name")).toContain("capital letter");
    expect(validateName("John", "First name")).toBeNull();
    expect(validateName("McDonald", "Last name")).toBeNull();

    expect(validateName("李明", "Full name")).toBeNull();
  });
});

describe("capitalizeFirst / capitalizeWords", () => {
  test("capitalizeFirst uppercases only the first letter", () => {
    expect(capitalizeFirst("jane")).toBe("Jane");
    expect(capitalizeFirst("Jane")).toBe("Jane");
    expect(capitalizeFirst("李明")).toBe("李明");
    expect(capitalizeFirst("")).toBe("");
  });

  test("capitalizeWords uppercases the first letter of every word", () => {
    expect(capitalizeWords("john doe")).toBe("John Doe");
    expect(capitalizeWords("jean-luc o'neill")).toBe("Jean-Luc O'Neill");
    expect(capitalizeWords("John")).toBe("John");
    expect(capitalizeWords("")).toBe("");
  });
});

describe("validateGender", () => {
  test("accepts only known options", () => {
    expect(validateGender("male")).toBeNull();
    expect(validateGender("prefer_not_to_say")).toBeNull();
    expect(validateGender("robot")).toBe("Please select a gender.");
  });
});

describe("validateIdentifier", () => {
  test("routes emails to the email validator", () => {
    expect(validateIdentifier("user@example.com")).toBeNull();
    expect(validateIdentifier("bad@")).toBe("Enter a valid email address.");
  });

  test("accepts lenient phone formats for login", () => {
    expect(validateIdentifier("+91 98765 43210")).toBeNull();
    expect(validateIdentifier("9876543210")).toBeNull();
  });

  test("rejects junk", () => {
    expect(validateIdentifier("")).toBe("Email or phone is required.");
    expect(validateIdentifier("abc")).toBe("Enter a valid email address or phone number.");
  });
});

describe("validateOtp", () => {
  test("requires exactly six digits", () => {
    expect(validateOtp("123456")).toBeNull();
    expect(validateOtp("")).toBe("Enter the 6-digit code.");
    expect(validateOtp("12345")).toBe("The code must be exactly 6 digits.");
    expect(validateOtp("12345a")).toBe("The code must be exactly 6 digits.");
  });
});

describe("password validators", () => {
  test("setting a password enforces strength rules", () => {
    expect(validatePassword("Str0ngPass!x")).toBeNull();
    expect(validatePassword("")).toBe("Password is required.");
    expect(validatePassword("short1!")).toBe("Password must be at least 8 characters.");
    expect(validatePassword("12345678")).toBe("Password cannot be entirely numeric.");
    expect(validatePassword("Password")).toContain("too common");
  });

  test("login only requires presence", () => {
    expect(validateLoginPassword("whatever")).toBeNull();
    expect(validateLoginPassword("")).toBe("Password is required.");
  });

  test("confirmation must match", () => {
    expect(validateConfirmPassword("abc12345", "abc12345")).toBeNull();
    expect(validateConfirmPassword("abc12345", "")).toBe("Please confirm your password.");
    expect(validateConfirmPassword("abc12345", "other123")).toBe("Passwords do not match.");
  });
});

describe("validateRequired / validateOptional", () => {
  test("required rejects blanks and overlong values", () => {
    expect(validateRequired("London", "City", 100)).toBeNull();
    expect(validateRequired(" ", "City", 100)).toBe("City is required.");
    expect(validateRequired("x".repeat(101), "City", 100)).toContain("at most 100 characters.");
  });

  test("optional allows blanks but caps length", () => {
    expect(validateOptional("", "Address line 2", 255)).toBeNull();
    expect(validateOptional("x".repeat(256), "Address line 2", 255)).toContain(
      "at most 255 characters."
    );
  });
});

describe("phone validators", () => {
  test("lenient validator accepts free-form digits", () => {
    expect(validatePhone("+91 98765 43210")).toBeNull();
    expect(validatePhone("(555) 123-4567")).toBeNull();
  });

  test("lenient validator enforces length bounds", () => {
    expect(validatePhone("")).toBe("Phone is required.");
    expect(validatePhone("123456")).toBe("Phone must contain 7-15 digits.");
    expect(validatePhone("1".repeat(16))).toBe("Phone must contain 7-15 digits.");
    expect(validatePhone("abc")).toBe("Enter a valid phone number (digits, spaces, + - ( ) .).");
  });

  test("strict E.164 validator uses libphonenumber per-country rules", () => {
    expect(validateE164Phone("+919876543210")).toBeNull();
    expect(validateE164Phone("+91123")).toContain("valid phone number");
  });
});

describe("date validators", () => {
  test("date of birth accepts a past ISO date", () => {
    expect(validateDateOfBirth("1990-01-31")).toBeNull();
  });

  test("date of birth rejects malformed/future/too-old dates", () => {
    expect(validateDateOfBirth("")).toBe("Date of birth is required.");
    expect(validateDateOfBirth("31/01/1990")).toBe("Enter a valid date.");
    expect(validateDateOfBirth("2999-01-01")).toBe("Date of birth cannot be in the future.");
    expect(validateDateOfBirth("1899-12-31")).toBe("Enter a valid date of birth.");
  });

  test("optional DOB tolerates empty values", () => {
    expect(validateOptionalDateOfBirth("")).toBeNull();
    expect(validateOptionalDateOfBirth("2999-01-01")).toBe("Date of birth cannot be in the future.");
  });

  test("ID expiry only needs to be a valid ISO date", () => {
    expect(validateIdExpiry("")).toBeNull();
    expect(validateIdExpiry("2030-06-30")).toBeNull();
    expect(validateIdExpiry("junk")).toBe("Enter a valid date.");
  });
});

describe("validateUploadFile", () => {
  const makeFile = (name: string, size: number) =>
    new File([new Uint8Array(size)], name, { type: "application/octet-stream" });

  test("accepts an allowed extension within the size cap", () => {
    expect(validateUploadFile(makeFile("scan.pdf", 1024))).toBeNull();
    expect(validateUploadFile(makeFile("photo.JPG", 1024))).toBeNull();
  });

  test("rejects disallowed extensions", () => {
    expect(validateUploadFile(makeFile("virus.exe", 1))).toContain("not allowed");
    expect(validateUploadFile(makeFile("noext", 1))).toContain("not allowed");
  });

  test("rejects files above the size cap", () => {
    const big = makeFile("scan.pdf", MAX_FILE_SIZE_MB * 1024 * 1024 + 1);
    expect(validateUploadFile(big)).toContain("size limit");
  });

  test("extension list matches the backend contract", () => {
    expect(ALLOWED_FILE_EXTENSIONS).toEqual([".jpg", ".jpeg", ".png", ".pdf"]);
  });
});

describe("validateReviewNotes", () => {
  test("approve needs no notes; other decisions do", () => {
    expect(validateReviewNotes("approve", "")).toBeNull();
    expect(validateReviewNotes("reject", "")).toBe(
      "Notes are required when rejecting or requesting resubmission."
    );
    expect(validateReviewNotes("request_resubmission", "please fix")).toBeNull();
  });
});

describe("validateApplication", () => {
  test("accepts a fully valid payload", () => {
    expect(validateApplication(validApplication())).toEqual({});
  });

  test("collects one error per invalid field", () => {
    const form = validApplication();
    form.full_name = "";
    form.city = "";

    (form as { id_type: string }).id_type = "library_card";
    const errors = validateApplication(form);
    expect(errors.full_name).toBe("Full name is required.");
    expect(errors.city).toBe("City is required.");
    expect(errors.id_type).toBe("Select a valid ID type.");

    expect(errors.nationality).toBeUndefined();
    expect(errors.phone).toBeUndefined();
  });
});
