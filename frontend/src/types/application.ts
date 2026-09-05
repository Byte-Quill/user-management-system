export type ApplicationStatus =
  | "draft"
  | "submitted"
  | "approved"
  | "rejected"
  | "resubmission_requested";

export interface KycDocument {
  id: string;
  doc_type: "id_proof" | "address_proof" | "selfie";
  /** Signed download URL; null in list payloads (metadata only). */
  file: string | null;
  original_filename: string;
  uploaded_at: string;
}

export interface KYCApplication {
  id: string;
  /** Stable ownership key (email can be null for phone-only accounts). */
  applicant_id: number;
  applicant_email: string | null;
  status: ApplicationStatus;
  full_name: string;
  date_of_birth: string;
  nationality: string;
  phone: string;
  address_line1: string;
  address_line2: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
  id_type: "passport" | "national_id" | "drivers_license";
  id_number: string;
  id_expiry: string | null;
  reviewer_email: string | null;
  review_notes: string;
  reviewed_at: string | null;
  documents: KycDocument[];
  created_at: string;
  updated_at: string;
  submitted_at: string | null;
}

export interface AuditEntry {
  id: string;
  action: string;
  detail: string;
  actor_email: string | null;
  created_at: string;
}

export type ApplicationPayload = Omit<
  KYCApplication,
  | "id"
  | "applicant_id"
  | "applicant_email"
  | "status"
  | "reviewer_email"
  | "review_notes"
  | "reviewed_at"
  | "documents"
  | "created_at"
  | "updated_at"
  | "submitted_at"
>;
