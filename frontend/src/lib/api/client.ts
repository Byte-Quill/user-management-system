const BASE = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL.replace(/\/$/, "")}/api`
  : "/api";

// Access token stays in memory only; the refresh token lives in an HttpOnly
// cookie the backend sets, sent automatically with `credentials: "include"`.
let accessToken: string | null = null;

export function setTokens(access: string) {
  accessToken = access;
}

export function clearTokens() {
  accessToken = null;
}

async function doRefresh(): Promise<boolean> {
  // The refresh cookie travels with the request automatically.
  let res: Response;
  try {
    res = await fetch(`${BASE}/auth/token/refresh/`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
  } catch {
    // Network failure: treat as logged-out rather than crashing the caller.
    clearTokens();
    return false;
  }
  if (!res.ok) {
    clearTokens();
    return false;
  }
  try {
    const data = await res.json();
    if (typeof data?.access === "string") {
      accessToken = data.access;
      return true;
    }
  } catch {
    // Non-JSON body (e.g. a proxy error page): fall through to logout.
  }
  clearTokens();
  return false;
}

// Single-flight: the backend rotates and blacklists refresh tokens, so two
// concurrent refreshes with the same token would invalidate the session.
let refreshPromise: Promise<boolean> | null = null;

export async function refreshAccess(): Promise<boolean> {
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
    if (err.status === 0) {
      return "Network error. Check your connection and try again.";
    }
    if (err.status === 429) {
      return err.retryAfter
        ? `Too many requests. Please try again in ${err.retryAfter} seconds.`
        : "Too many requests. Please try again later.";
    }
    if (err.body && typeof err.body === "object" && !Array.isArray(err.body)) {
      const body = err.body as Record<string, string | string[]>;
      // DRF APIView-style errors: show the message without a "detail:" prefix.
      if (typeof body.detail === "string") return body.detail;
      const parts = Object.entries(body).map(([k, v]) => {
        const text = Array.isArray(v) ? v.join(", ") : String(v);
        return k === "non_field_errors" ? text : `${k}: ${text}`;
      });
      if (parts.length > 0) return parts.join(" ");
    }
  }
  return fallback;
}

export async function request<T>(
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

  let res: Response;
  try {
    // Offline / DNS / connection refused: surface as ApiError(0) so callers
    // get a friendly message from errorMessage() instead of a raw TypeError.
    res = await fetch(`${BASE}${path}`, {
      ...options,
      headers,
      credentials: "include",
    });
  } catch {
    throw new ApiError(0, null);
  }

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
