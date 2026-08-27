import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router";

import * as api from "../api";
import { PasswordInput } from "../components/Field";
import { validateConfirmPassword, validateEmail, validateOtp, validatePassword } from "../validation";

type Step = "email" | "code";

/**
 * Forgot password: 3-step wizard (email -> OTP -> new password). The backend
 * never reveals whether the email exists, so step 2 always proceeds after a
 * request; a wrong/expired code is caught at confirm time.
 */
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
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
      <div className="w-full max-w-sm rounded-lg bg-white p-8 shadow">
        <h1 className="mb-2 text-center text-2xl font-bold text-slate-900">Reset password</h1>

        {step === "email" && (
          <>
            <p className="mb-6 text-center text-sm text-slate-600">
              Enter your account email and we&apos;ll send a 6-digit reset code.
            </p>
            <form onSubmit={requestStep} className="space-y-4" noValidate>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Email</label>
                <input
                  type="email"
                  required
                  autoFocus
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                />
              </div>
              {error && <p className="text-sm text-red-600">{error}</p>}
              <button
                type="submit"
                disabled={busy}
                className="w-full rounded bg-blue-600 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {busy ? "Sending…" : "Send reset code"}
              </button>
            </form>
          </>
        )}

        {step !== "email" && (
          <>
            <p className="mb-6 text-center text-sm text-slate-600">
              {step === "code"
                ? `Enter the code sent to ${email.trim()}, then choose a new password.`
                : ""}
            </p>
            <form onSubmit={confirmStep} className="space-y-4" noValidate>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Code</label>
                <input
                  required
                  autoFocus={step === "code"}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  maxLength={6}
                  placeholder="123456"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                  className="w-full rounded border border-slate-300 px-3 py-2 text-center text-lg tracking-[0.5em] focus:border-blue-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">New password</label>
                <PasswordInput
                  required
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">
                  Confirm new password
                </label>
                <PasswordInput
                  required
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
              </div>
              {error && <p className="text-sm text-red-600">{error}</p>}
              <button
                type="submit"
                disabled={busy}
                className="w-full rounded bg-blue-600 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {busy ? "Resetting…" : "Reset password"}
              </button>
            </form>
          </>
        )}

        <p className="mt-4 text-center text-sm text-slate-600">
          <Link to="/login" className="font-medium text-blue-600 hover:underline">
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
