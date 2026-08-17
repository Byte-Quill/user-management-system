import type { ApplicationPayload, AuditEntry, KYCApplication, KycDocument, Page, User } from "./types";

const BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL.replace(/\/$/, "")}/api`
  : "/api";

// Access token lives in memory ONLY (survives nothing, XSS cannot read it long-term).
// The refresh token lives in an HttpOnly cookie set by the backend, sent
// automatically with `credentials: "include"`.
let accessToken: string | null = null;

export function setTokens(access: string) {
  accessToken = access;
}

export function clearTokens() {
  accessToken = null;
}

async function doRefresh(): Promise<boolean> {
  // The refresh cookie travels with the request automatically.
  const res = await fetch(`${BASE}/auth/token/refresh/`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!res.ok) {
    clearTokens();
    return false;
  }
  const data = await res.json();
  accessToken = data.access;
  return true;
}

// Single-flight guard: the backend rotates and blacklists refresh tokens, so
// two concurrent refresh calls with the same token would invalidate the
// session. All callers share one in-flight refresh promise.
let refreshPromise: Promise<boolean> | null = null;

async function refreshAccess(): Promise<boolean> {
  refreshPromise ??= doRefresh().finally(() => {
    refreshPromise = null;
  });
  return refreshPromise;
}

export class ApiError extends Error {
  status: number;
  body: unknown;
  /** Seconds to wait before retrying, from the Retry-After header on 429s. */
  retryAfter: number | null;
  constructor(status: number, body: unknown, retryAfter: number | null = null) {
    super(`API error ${status}`);
    this.status = status;
    this.body = body;
    this.retryAfter = retryAfter;
  }
}

/** Flatten a DRF error body ({field: [messages]}) into a single display string. */
export function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    if (err.status === 429) {
      return err.retryAfter
        ? `Too many requests. Please try again in ${err.retryAfter} seconds.`
        : "Too many requests. Please try again later.";
    }
    if (err.body && typeof err.body === "object") {
      return Object.entries(err.body as Record<string, string | string[]>)
        .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : v}`)
        .join(" ");
    }
  }
  return fallback;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  retry = true
): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });

  if (res.status === 401 && retry && (await refreshAccess())) {
    return request<T>(path, options, false);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const retryHeader = res.headers.get("Retry-After");
    const parsed = retryHeader ? Number(retryHeader) : NaN;
    const retryAfter = Number.isFinite(parsed) ? Math.max(1, Math.ceil(parsed)) : null;
    throw new ApiError(res.status, body, retryAfter);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

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
  email: string;
  password: string;
  first_name: string;
  middle_name?: string;
  last_name: string;
  phone: string;
  gender: string;
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
export { refreshAccess };

export const logout = () =>
  request<void>("/auth/logout/", {
    method: "POST",
    body: JSON.stringify({}),
  });

export const listApplications = (page = 1) =>
  request<Page<KYCApplication>>(`/applications/?page=${page}`);
export const getApplication = (id: string) => request<KYCApplication>(`/applications/${id}/`);
export const createApplication = (payload: ApplicationPayload) =>
  request<KYCApplication>("/applications/", { method: "POST", body: JSON.stringify(payload) });
export const submitApplication = (id: string) =>
  request<KYCApplication>(`/applications/${id}/submit/`, { method: "POST" });

export const uploadDocument = (id: string, docType: string, file: File) => {
  const form = new FormData();
  form.append("doc_type", docType);
  form.append("file", file);
  return request<KycDocument>(`/applications/${id}/documents/`, {
    method: "POST",
    body: form,
  });
};

export const deleteDocument = (id: string, docId: string) =>
  request<void>(`/applications/${id}/documents/${docId}/`, { method: "DELETE" });

export const reviewApplication = (id: string, decision: string, notes: string) =>
  request<KYCApplication>(`/applications/${id}/review/`, {
    method: "POST",
    body: JSON.stringify({ decision, notes }),
  });

export const fetchAudit = (id: string, page = 1) =>
  request<Page<AuditEntry>>(`/applications/${id}/audit/?page=${page}`);
export const fetchReviewQueue = (page = 1) =>
  request<Page<KYCApplication>>(`/review-queue/?page=${page}`);
