import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router";

import * as api from "@/lib/api";
import { PasswordInput } from "@/components/ui/Field";
import AuthShell from "@/features/auth/components/AuthShell";
import Alert from "@/components/ui/Alert";
import { OTP_LENGTH, validateConfirmPassword, validateEmail, validateOtp, validatePassword } from "@/lib/validation";

type Step = "email" | "code";


export default function ForgotPasswordPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const requestStep = async (e: FormEvent) => {
    e.preventDefault();
    const emailError = validateEmail(email);
    if (emailError) {
      setError(emailError);
      return;
    }
    setError("");
    setBusy(true);
    try {
      await api.requestPasswordReset(email.trim());
      setStep("code");
    } catch (err) {
      setError(api.errorMessage(err, "Could not send the reset code. Try again later."));
    } finally {
      setBusy(false);
    }
  };

  const confirmStep = async (e: FormEvent) => {
    e.preventDefault();
    const codeError = validateOtp(code);
    const passwordError = validatePassword(password);
    const confirmError = validateConfirmPassword(password, confirmPassword);
    if (codeError || passwordError || confirmError) {
      setError(codeError ?? passwordError ?? confirmError ?? "");
      return;
    }
    setError("");
    setBusy(true);
    try {
      await api.confirmPasswordReset(email.trim(), code.trim(), password);
      navigate("/login", { state: { email: email.trim(), passwordReset: true } });
    } catch (err) {
      setError(api.errorMessage(err, "Reset failed. The code may be expired."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthShell
      title="Reset password"
      subtitle={
        step === "email"
          ? "Enter your account email and we'll send a 6-digit reset code."
          : `Enter the code sent to ${email.trim()}, then choose a new password.`
      }
    >
      {step === "email" ? (
        <form onSubmit={requestStep} className="space-y-4" noValidate>
          <div>
            <label htmlFor="reset-email" className="mb-1.5 block text-sm font-medium text-ink-700">Email</label>
            <input
              id="reset-email"
              type="email"
              required
              autoFocus
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-xl border border-ink-200 bg-white px-3.5 py-2.5 text-sm text-ink-900 shadow-xs outline-none transition placeholder:text-ink-300 hover:border-ink-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30"
            />
          </div>
          {error && <Alert variant="error">{error}</Alert>}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-xl bg-ink-900 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-ink-950 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busy ? "Sending…" : "Send reset code"}
          </button>
        </form>
      ) : (
        <form onSubmit={confirmStep} className="space-y-4" noValidate>
          <div>
            <label htmlFor="reset-code" className="mb-1.5 block text-sm font-medium text-ink-700">Code</label>
            <input
              id="reset-code"
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
          <div>
            <label htmlFor="reset-password" className="mb-1.5 block text-sm font-medium text-ink-700">New password</label>
            <PasswordInput
              id="reset-password"
              required
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="reset-confirm" className="mb-1.5 block text-sm font-medium text-ink-700">
              Confirm new password
            </label>
            <PasswordInput
              id="reset-confirm"
              required
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />
          </div>
          {error && <Alert variant="error">{error}</Alert>}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-xl bg-ink-900 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-ink-950 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busy ? "Resetting…" : "Reset password"}
          </button>
        </form>
      )}

      <p className="mt-4 border-t border-ink-100 pt-4 text-center text-sm text-ink-600">
        <Link to="/login" className="font-semibold text-brand-600 hover:text-brand-700 hover:underline">
          Back to sign in
        </Link>
      </p>
    </AuthShell>
  );
}
