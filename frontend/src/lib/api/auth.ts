import { request } from "./client";

import type { User } from "@/types";

export const login = (email: string, password: string) =>
  request<{ access: string }>("/auth/token/", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

/** Exchange a Google ID token (from the Sign-In button) for our JWT session. */
export const googleLogin = (credential: string) =>
  request<{ access: string }>("/auth/google/", {
    method: "POST",
    body: JSON.stringify({ credential }),
  });

export const register = (payload: {
  /** Optional, but at least one of email/phone is required server-side. */
  email?: string;
  password: string;
  first_name: string;
  middle_name?: string;
  last_name: string;
  phone?: string;
  gender: string;
  date_of_birth?: string | null;
  nationality?: string;
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state?: string;
  postal_code?: string;
  country?: string;
}) =>
  request<User>("/auth/register/", { method: "POST", body: JSON.stringify(payload) });

/** Confirm the signup OTP; unlocks password login for the account. */
export const verifyEmail = (email: string, code: string) =>
  request<{ detail: string }>("/auth/verify-email/", {
    method: "POST",
    body: JSON.stringify({ email, code }),
  });

/** Ask for a fresh signup OTP (server enforces the 60s cooldown). */
export const resendVerification = (email: string) =>
  request<{ detail: string }>("/auth/verify-email/resend/", {
    method: "POST",
    body: JSON.stringify({ email }),
  });

/** Ask for a password-reset OTP (always 200; no account enumeration). */
export const requestPasswordReset = (email: string) =>
  request<{ detail: string }>("/auth/password-reset/request/", {
    method: "POST",
    body: JSON.stringify({ email }),
  });

/** Consume the reset OTP and set a new password. */
export const confirmPasswordReset = (email: string, code: string, newPassword: string) =>
  request<{ detail: string }>("/auth/password-reset/confirm/", {
    method: "POST",
    body: JSON.stringify({ email, code, new_password: newPassword }),
  });

export const fetchMe = () => request<User>("/auth/me/");

export const logout = () =>
  request<void>("/auth/logout/", {
    method: "POST",
    body: JSON.stringify({}),
  });
