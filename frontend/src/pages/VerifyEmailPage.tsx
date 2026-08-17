import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router";

import * as api from "../api";
import { validateEmail, validateOtp } from "../validation";

const RESEND_COOLDOWN_SECONDS = 60;

/**
 * Signup email verification: enter the 6-digit OTP that was emailed after
 * registration. Reached from RegisterPage (email prefilled via router state)
 * or from the login page when a login is blocked with code email_not_verified.
 */
export default function VerifyEmailPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const prefilled = (location.state as { email?: string } | null)?.email ?? "";

  const [email, setEmail] = useState(prefilled);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setNotice("");
    const emailError = validateEmail(email);
    const codeError = validateOtp(code);
    if (emailError || codeError) {
      setError(emailError ?? codeError ?? "");
      return;
    }
    setBusy(true);
    try {
      await api.verifyEmail(email.trim(), code.trim());
      // Verified: straight to login with the email prefilled.
      navigate("/login", { state: { email: email.trim(), verified: true } });
    } catch (err) {
      setError(api.errorMessage(err, "Invalid or expired code."));
    } finally {
      setBusy(false);
    }
  };

  const onResend = async () => {
    setError("");
    setNotice("");
    const emailError = validateEmail(email);
    if (emailError) {
      setError(emailError);
      return;
    }
    setBusy(true);
    try {
      await api.resendVerification(email.trim());
      setNotice("If the account needs verification, a new code was sent.");
      setCooldown(RESEND_COOLDOWN_SECONDS);
    } catch (err) {
      setError(api.errorMessage(err, "Could not resend the code. Try again later."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
      <div className="w-full max-w-sm rounded-lg bg-white p-8 shadow">
        <h1 className="mb-2 text-center text-2xl font-bold text-slate-900">Verify your email</h1>
        <p className="mb-6 text-center text-sm text-slate-600">
          Enter the 6-digit code we emailed you. It expires in 10 minutes.
        </p>
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Email</label>
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Code</label>
            <input
              required
              autoFocus
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              placeholder="123456"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              className="w-full rounded border border-slate-300 px-3 py-2 text-center text-lg tracking-[0.5em] focus:border-blue-500 focus:outline-none"
            />
          </div>
          {error && <p className="text-sm text-red-600">{error}</p>}
          {notice && <p className="text-sm text-green-700">{notice}</p>}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded bg-blue-600 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {busy ? "Verifying…" : "Verify email"}
          </button>
        </form>
        <div className="mt-4 text-center text-sm text-slate-600">
          <button
            type="button"
            onClick={onResend}
            disabled={busy || cooldown > 0}
            className="font-medium text-blue-600 hover:underline disabled:text-slate-400 disabled:no-underline"
          >
            {cooldown > 0 ? `Resend code in ${cooldown}s` : "Resend code"}
          </button>
        </div>
        <p className="mt-4 text-center text-sm text-slate-600">
          <Link to="/login" className="font-medium text-blue-600 hover:underline">
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
