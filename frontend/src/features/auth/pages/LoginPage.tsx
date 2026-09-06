import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router";

import * as api from "@/lib/api";
import { GOOGLE_CLIENT_ID } from "@/app/config";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { PasswordInput } from "@/components/ui/Field";
import GoogleSignInButton from "@/features/auth/components/GoogleSignInButton";
import { validateIdentifier, validateLoginPassword } from "@/lib/validation";

interface LoginLocationState {
  email?: string;
  verified?: boolean;
  passwordReset?: boolean;
  /** Set after a phone-only signup (nothing to verify). */
  registered?: boolean;
}

/** Small inline icon set (no icon dependency). */
function IconUser() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      className="h-4 w-4" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.5 20.25a7.5 7.5 0 0 1 15 0" />
    </svg>
  );
}

function IconLock() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      className="h-4 w-4" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M16.5 10.5V6.75a4.5 4.5 0 1 0-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 0 0 2.25-2.25v-6.75a2.25 2.25 0 0 0-2.25-2.25H6.75A2.25 2.25 0 0 0 4.5 12.75v6.75a2.25 2.25 0 0 0 2.25 2.25Z" />
    </svg>
  );
}

function IconAlert() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
      className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M12 9v3.75m0 3.5h.01M10.34 3.94 2.25 18a1.5 1.5 0 0 0 1.29 2.25h16.92A1.5 1.5 0 0 0 21.75 18L13.66 3.94a1.5 1.5 0 0 0-2.32 0Z" />
    </svg>
  );
}

function IconCheck() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round"
        d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
    </svg>
  );
}

function Spinner() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4 animate-spin" aria-hidden="true">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" className="opacity-25" />
      <path fill="currentColor" className="opacity-75"
        d="M4 12a8 8 0 0 1 8-8v4a4 4 0 0 0-4 4H4Z" />
    </svg>
  );
}

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const state = (location.state as LoginLocationState | null) ?? {};
  const [identifier, setIdentifier] = useState(state.email ?? "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(
    state.verified
      ? "Email verified. You can sign in now."
      : state.passwordReset
        ? "Password updated. You can sign in now."
        : state.registered
          ? "Account created. Sign in with your phone number and password."
          : ""
  );
  const [busy, setBusy] = useState(false);
  const [capsLock, setCapsLock] = useState(false);

  /** Any edit after a failure clears the error — stale errors are noise. */
  const onIdentifierChange = (next: string) => {
    setIdentifier(next);
    if (error) setError("");
  };
  const onPasswordChange = (next: string) => {
    setPassword(next);
    if (error) setError("");
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const identifierError = validateIdentifier(identifier);
    const passwordError = validateLoginPassword(password);
    if (identifierError || passwordError) {
      setError(identifierError ?? passwordError ?? "");
      return;
    }
    setError("");
    setNotice("");
    setBusy(true);
    try {
      // The backend accepts email or phone in the `email` field.
      await login(identifier.trim(), password);
      navigate("/");
    } catch (err) {
      if (err instanceof api.ApiError && err.status === 403) {
        const body = err.body as { code?: string } | null;
        if (body?.code === "email_not_verified") {
          // Route to the OTP page with the email prefilled. Only the
          // password holder sees this, so it is not an enumeration leak.
          setError("Verify your email to sign in.");
          navigate("/verify-email", {
            state: { email: identifier.includes("@") ? identifier.trim() : "" },
          });
          return;
        }
      }
      // Surface rate-limit feedback; keep auth failures generic otherwise.
      setError(
        err instanceof api.ApiError && err.status === 429
          ? api.errorMessage(err, "Too many attempts. Please try again later.")
          : "Invalid email/phone or password."
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-8">
      <div className="w-full max-w-sm">
        <div className="rounded-xl border border-slate-200 bg-white p-8 shadow-lg shadow-slate-200/60">
          {/* Brand */}
          <div className="mb-6 flex flex-col items-center gap-2">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-600 text-white shadow-md shadow-blue-600/30">
              <IconLock />
            </div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900">Login Portal</h1>
            <p className="text-sm text-slate-500">Sign in to your account</p>
          </div>

          <form onSubmit={onSubmit} className="space-y-4" noValidate>
            <div>
              <label htmlFor="login-identifier" className="mb-1 block text-sm font-medium text-slate-700">
                Email or phone
              </label>
              <div className="relative">
                <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-slate-400">
                  <IconUser />
                </span>
                <input
                  id="login-identifier"
                  required
                  autoFocus
                  autoComplete="username"
                  placeholder="you@example.com or +91 98765 43210"
                  value={identifier}
                  onChange={(e) => onIdentifierChange(e.target.value)}
                  aria-invalid={!!error}
                  className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm transition-colors focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>
            <div>
              <label htmlFor="login-password" className="mb-1 block text-sm font-medium text-slate-700">
                Password
              </label>
              <PasswordInput
                id="login-password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => onPasswordChange(e.target.value)}
                onKeyUp={(e) => setCapsLock(e.getModifierState?.("CapsLock") ?? false)}
              />
              {capsLock && (
                <p className="mt-1 flex items-center gap-1 text-xs text-amber-600" role="status">
                  <IconAlert /> Caps Lock is on.
                </p>
              )}
            </div>

            {error && (
              <p role="alert" className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                <IconAlert />
                {error}
              </p>
            )}
            {notice && (
              <p className="flex items-start gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                <IconCheck />
                {notice}
              </p>
            )}

            <button
              type="submit"
              disabled={busy}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {busy && <Spinner />}
              {busy ? "Signing in…" : "Sign in"}
            </button>
          </form>

          <p className="mt-3 text-center text-sm">
            <Link
              to="/forgot-password"
              className="font-medium text-blue-600 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 rounded-sm"
            >
              Forgot password?
            </Link>
          </p>

          {GOOGLE_CLIENT_ID && (
            <>
              <div className="my-5 flex items-center gap-3" aria-hidden="true">
                <div className="h-px flex-1 bg-slate-200" />
                <span className="text-xs uppercase tracking-wide text-slate-400">or</span>
                <div className="h-px flex-1 bg-slate-200" />
              </div>
              <GoogleSignInButton onSuccess={() => navigate("/")} onError={setError} />
            </>
          )}

          <p className="mt-6 border-t border-slate-100 pt-4 text-center text-sm text-slate-600">
            No account?{" "}
            <Link
              to="/register"
              className="font-medium text-blue-600 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 rounded-sm"
            >
              Register
            </Link>
          </p>
        </div>
        <p className="mt-4 text-center text-xs text-slate-400">
          By signing in you agree <a
            href="/terms"
            className="text-slate-500 underline decoration-slate-300 underline-offset-2 hover:text-slate-700 hover:decoration-slate-500"
          >
            Terms &amp; Conditions
          </a>
          .
        </p>
      </div>
    </div>
  );
}
