import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router";

import * as api from "@/lib/api";
import AuthShell from "@/features/auth/components/AuthShell";
import Alert from "@/components/ui/Alert";
import { OTP_LENGTH, validateEmail, validateOtp } from "@/lib/validation";

const RESEND_COOLDOWN_SECONDS = 60;


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
    <AuthShell
      title="Verify your email"
      subtitle="Enter the 6-digit code we emailed you. It expires in 10 minutes."
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        <div>
          <label htmlFor="verify-email" className="mb-1.5 block text-sm font-medium text-ink-700">Email</label>
          <input
            id="verify-email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-xl border border-ink-200 bg-white px-3.5 py-2.5 text-sm text-ink-900 shadow-xs outline-none transition placeholder:text-ink-300 hover:border-ink-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30"
          />
        </div>
        <div>
          <label htmlFor="verify-code" className="mb-1.5 block text-sm font-medium text-ink-700">Code</label>
          <input
            id="verify-code"
            required
            autoFocus
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={OTP_LENGTH}
            placeholder="123456"
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            className="w-full rounded-xl border border-ink-200 bg-white px-3.5 py-2.5 text-center text-lg tracking-[0.5em] text-ink-900 shadow-xs outline-none transition placeholder:text-ink-200 hover:border-ink-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30"
          />
        </div>
        {error && <Alert variant="error">{error}</Alert>}
        {notice && <Alert variant="success">{notice}</Alert>}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-xl bg-ink-900 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-ink-950 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
        >
          {busy ? "Verifying…" : "Verify email"}
        </button>
      </form>
      <div className="mt-4 text-center text-sm text-ink-600">
        <button
          type="button"
          onClick={onResend}
          disabled={busy || cooldown > 0}
          className="rounded-sm font-semibold text-brand-600 hover:text-brand-700 hover:underline disabled:text-ink-300 disabled:no-underline"
        >
          {cooldown > 0 ? `Resend code in ${cooldown}s` : "Resend code"}
        </button>
      </div>
      <p className="mt-4 border-t border-ink-100 pt-4 text-center text-sm text-ink-600">
        <Link to="/login" className="font-semibold text-brand-600 hover:text-brand-700 hover:underline">
          Back to sign in
        </Link>
      </p>
    </AuthShell>
  );
}
