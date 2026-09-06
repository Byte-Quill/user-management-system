import { request } from "./client";

import type { User } from "@/types";


export const login = (email: string, password: string) =>
  request<{ access: string }>(
    "/auth/token/",
    {
      method: "POST",
      body: JSON.stringify({ email, password }),
    },
    false
  );


export const googleLogin = (credential: string) =>
  request<{ access: string }>(
    "/auth/google/",
    {
      method: "POST",
      body: JSON.stringify({ credential }),
    },
    false
  );

export const register = (payload: {

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
  request<User>(
    "/auth/register/",
    { method: "POST", body: JSON.stringify(payload) },
    false
  );


export const verifyEmail = (email: string, code: string) =>
  request<{ detail: string }>(
    "/auth/verify-email/",
    {
      method: "POST",
      body: JSON.stringify({ email, code }),
    },
    false
  );


export const resendVerification = (email: string) =>
  request<{ detail: string }>(
    "/auth/verify-email/resend/",
    {
      method: "POST",
      body: JSON.stringify({ email }),
    },
    false
  );


export const requestPasswordReset = (email: string) =>
  request<{ detail: string }>(
    "/auth/password-reset/request/",
    {
      method: "POST",
      body: JSON.stringify({ email }),
    },
    false
  );


export const confirmPasswordReset = (email: string, code: string, newPassword: string) =>
  request<{ detail: string }>(
    "/auth/password-reset/confirm/",
    {
      method: "POST",
      body: JSON.stringify({ email, code, new_password: newPassword }),
    },
    false
  );

export const fetchMe = () => request<User>("/auth/me/");

export const logout = () =>
  request<void>(
    "/auth/logout/",
    {
      method: "POST",
      body: JSON.stringify({}),
    },
    false
  );
