import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router";

import * as api from "@/lib/api";
import { GOOGLE_CLIENT_ID } from "@/app/config";
import { useAuth } from "@/features/auth/hooks/useAuth";
import { PasswordInput } from "@/components/ui/Field";
import {
  IconAlert,
  IconCheck,
  IconLock,
  IconSpinner,
  IconUser,
} from "@/components/ui/icons";
import AuthShell from "@/features/auth/components/AuthShell";
import GoogleSignInButton from "@/features/auth/components/GoogleSignInButton";
import { validateIdentifier, validateLoginPassword } from "@/lib/validation";

interface LoginLocationState {
  email?: string;
  verified?: boolean;
  passwordReset?: boolean;

  registered?: boolean;
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
      await login(identifier.trim(), password);
      navigate("/");
    } catch (err) {
      if (err instanceof api.ApiError && err.status === 403) {
        const body = err.body as { code?: string } | null;
        if (body?.code === "email_not_verified") {
          setError("Verify your email to sign in.");
          navigate("/verify-email", {
            state: { email: identifier.includes("@") ? identifier.trim() : "" },
          });
          return;
        }
      }

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
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to continue your verification."
      footer={
        <p className="mt-5 border-t border-ink-100 pt-4 text-center text-sm text-ink-600">
          No account?{" "}
          <Link
            to="/register"
            className="font-semibold text-brand-600 hover:text-brand-700 hover:underline"
          >
            Register
          </Link>
        </p>
      }
    >
      {notice && (
        <p className="mb-4 flex items-start gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2.5 text-sm text-emerald-700 motion-safe:animate-fade-in">
          <IconCheck />
          {notice}
        </p>
      )}

      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <div>
          <label htmlFor="login-identifier" className="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-ink-700">
            <IconUser />
            Email or phone
          </label>
          <div className="relative">
            <input
              id="login-identifier"
              required
              autoFocus
              autoComplete="username"
              placeholder="you@example.com or +91 98765 43210"
              value={identifier}
              onChange={(e) => onIdentifierChange(e.target.value)}
              aria-invalid={!!error}
              className="w-full rounded-xl border border-ink-200 bg-white py-2.5 pl-3.5 pr-3.5 text-sm text-ink-900 shadow-xs outline-none transition placeholder:text-ink-300 hover:border-ink-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30"
            />
          </div>
        </div>
        <div>
          <label htmlFor="login-password" className="mb-1.5 flex items-center gap-1.5 text-sm font-medium text-ink-700">
            <IconLock />
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
            <p className="mt-1.5 flex items-center gap-1 text-xs font-medium text-amber-600" role="status">
              <IconAlert /> Caps Lock is on.
            </p>
          )}
        </div>

        {error && (
          <p role="alert" className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-700 motion-safe:animate-fade-in">
            <IconAlert />
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-ink-900 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-ink-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-900 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {busy && <IconSpinner />}
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>

      <p className="mt-4 text-center text-sm">
        <Link
          to="/forgot-password"
          className="rounded-sm font-medium text-brand-600 hover:text-brand-700 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600"
        >
          Forgot password?
        </Link>
      </p>

      {GOOGLE_CLIENT_ID && (
        <>
          <div className="my-5 flex items-center gap-3" aria-hidden="true">
            <div className="h-px flex-1 bg-ink-200" />
            <span className="text-xs uppercase tracking-wide text-ink-400">or</span>
            <div className="h-px flex-1 bg-ink-200" />
          </div>
          <GoogleSignInButton onSuccess={() => navigate("/")} onError={setError} />
        </>
      )}
    </AuthShell>
  );
}
