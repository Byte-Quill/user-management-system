export type Role = "applicant" | "admin" | "super_admin" | "ceo";

export type Gender = "male" | "female" | "other" | "prefer_not_to_say" | "";

export interface User {
  id: number;

  email: string | null;

  username: string;
  first_name: string;
  middle_name: string;
  last_name: string;

  phone: string | null;
  gender: Gender;

  date_of_birth: string | null;
  nationality: string;
  address_line1: string;
  address_line2: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
  role: Role;

  email_verified: boolean;
}

export interface ManagedUser {
  id: number;
  email: string | null;
  username: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  role: Role;
  email_verified: boolean;
  is_active: boolean;
  date_joined: string;
}
