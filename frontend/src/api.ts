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

export function isAuthenticated() {
  return !!accessToken;
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
  constructor(status: number, body: unknown) {
    super(`API error ${status}`);
    this.status = status;
    this.body = body;
  }
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
    throw new ApiError(res.status, body);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const login = (email: string, password: string) =>
  request<{ access: string }>("/auth/token/", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

export const register = (payload: {
  email: string;
  username: string;
  password: string;
  first_name?: string;
  last_name?: string;
}) =>
  request<User>("/auth/register/", { method: "POST", body: JSON.stringify(payload) });

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
export const updateApplication = (id: string, payload: Partial<ApplicationPayload>) =>
  request<KYCApplication>(`/applications/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
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
