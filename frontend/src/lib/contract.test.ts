import { describe, expect, test } from "bun:test";

import rawContract from "./backend-contract.json";
import {
  ALLOWED_FILE_EXTENSIONS,
  DOB_MIN_ISO,
  LIMITS,
  MAX_FILE_SIZE_MB,
  OTP_LENGTH,
  PASSWORD_MIN_LENGTH,
} from "./validation";


interface BackendContract {
  dob_min: string;
  max_upload_mb: number;
  allowed_upload_extensions: string[];
  max_documents_per_application: number;
  phone_default_region: string;
  phone_max_length: number;
  password_min_length: number;
  otp_length: number;
  name_max_length: number;
  email_max_length: number;
  page_size: number;
  application_max_lengths: Record<string, number>;
  gender_values: string[];
  application_id_types: string[];
  document_doc_types: string[];
  application_statuses: string[];
}

const contract: BackendContract = rawContract;


describe("backend validation contract", () => {
  test("upload rules match the backend", () => {
    expect(MAX_FILE_SIZE_MB).toBe(contract.max_upload_mb);
    expect([...ALLOWED_FILE_EXTENSIONS]).toEqual(contract.allowed_upload_extensions);
  });

  test("field length limits match the backend models", () => {
    expect(LIMITS.fullName).toBe(contract.application_max_lengths.full_name);
    expect(LIMITS.nationality).toBe(contract.application_max_lengths.nationality);
    expect(LIMITS.phone).toBe(contract.application_max_lengths.phone);
    expect(LIMITS.phone).toBe(contract.phone_max_length);
    expect(LIMITS.addressLine1).toBe(contract.application_max_lengths.address_line1);
    expect(LIMITS.addressLine2).toBe(contract.application_max_lengths.address_line2);
    expect(LIMITS.city).toBe(contract.application_max_lengths.city);
    expect(LIMITS.state).toBe(contract.application_max_lengths.state);
    expect(LIMITS.postalCode).toBe(contract.application_max_lengths.postal_code);
    expect(LIMITS.country).toBe(contract.application_max_lengths.country);
    expect(LIMITS.idNumber).toBe(contract.application_max_lengths.id_number);
    expect(LIMITS.name).toBe(contract.name_max_length);
    expect(LIMITS.email).toBe(contract.email_max_length);
  });

  test("auth / OTP / DOB rules match the backend", () => {
    expect(PASSWORD_MIN_LENGTH).toBe(contract.password_min_length);
    expect(OTP_LENGTH).toBe(contract.otp_length);
    expect(DOB_MIN_ISO).toBe(contract.dob_min);
  });
});
