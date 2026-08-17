import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router";

import * as api from "../api";
import { GOOGLE_CLIENT_ID } from "../App";
import { useAuth } from "../auth";
import GoogleSignInButton from "../components/GoogleSignInButton";
import { validateIdentifier, validateLoginPassword } from "../validation";

interface LoginLocationState {
  email?: string;
  verified?: boolean;
  passwordReset?: boolean;
  /** Set after a phone-only signup (nothing to verify). */
  registered?: boolean;
}

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const state = (location.state as LoginLocationState | null) ?? {};
  const [identifier, setIdentifier] = useState(state.email ?? "");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
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
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
      <div className="w-full max-w-sm rounded-lg bg-white p-8 shadow">
        <h1 className="mb-6 text-center text-2xl font-bold text-slate-900">Login Portal</h1>
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Email or phone</label>
            <input
              required
              autoFocus
              autoComplete="username"
              placeholder="you@example.com or +91 98765 43210"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Password</label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute inset-y-0 right-0 px-3 text-xs font-medium text-slate-500 hover:text-slate-700"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          {notice && <p className="text-sm text-green-700">{notice}</p>}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded bg-blue-600 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="mt-3 text-center text-sm">
          <Link to="/forgot-password" className="font-medium text-blue-600 hover:underline">
            Forgot password?
          </Link>
        </p>

        {GOOGLE_CLIENT_ID && (
          <>
            <div className="my-4 flex items-center gap-3">
              <div className="h-px flex-1 bg-slate-200" />
              <span className="text-xs uppercase tracking-wide text-slate-400">or</span>
              <div className="h-px flex-1 bg-slate-200" />
            </div>
            <GoogleSignInButton onSuccess={() => navigate("/")} onError={setError} />
          </>
        )}

        <p className="mt-4 text-center text-sm text-slate-600">
          No account?{" "}
          <Link to="/register" className="font-medium text-blue-600 hover:underline">
            Register
          </Link>
        </p>
      </div>
    </div>
  );
}
