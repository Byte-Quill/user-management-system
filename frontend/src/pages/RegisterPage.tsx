import { useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import * as api from "../api";
import { GOOGLE_CLIENT_ID } from "../App";
import { useAuth } from "../auth";
import { Field, Select, TextInput } from "../components/Field";
import GoogleSignInButton from "../components/GoogleSignInButton";
import {
  GENDER_OPTIONS,
  validateEmail,
  validateGender,
  validateName,
  validatePassword,
  validatePhone,
} from "../validation";

interface RegisterForm {
  first_name: string;
  middle_name: string;
  last_name: string;
  email: string;
  phone: string;
  gender: string;
  password: string;
}

const INITIAL: RegisterForm = {
  first_name: "",
  middle_name: "",
  last_name: "",
  email: "",
  phone: "",
  gender: "",
  password: "",
};

export default function RegisterPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState<RegisterForm>(INITIAL);
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<keyof RegisterForm, string>>>({});
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const set =
    (key: keyof RegisterForm) =>
    (e: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      setForm({ ...form, [key]: e.target.value });
      setFieldErrors((prev) => {
        if (!(key in prev)) return prev;
        const next = { ...prev };
        delete next[key];
        return next;
      });
    };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    const errors: Partial<Record<keyof RegisterForm, string>> = {};
    const checks: Array<[keyof RegisterForm, string | null]> = [
      ["first_name", validateName(form.first_name, "First name")],
      ["middle_name", validateName(form.middle_name, "Middle name", false)],
      ["last_name", validateName(form.last_name, "Last name")],
      ["email", validateEmail(form.email)],
      ["phone", validatePhone(form.phone)],
      ["gender", validateGender(form.gender)],
      ["password", validatePassword(form.password)],
    ];
    for (const [key, message] of checks) {
      if (message) errors[key] = message;
    }
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }
    setBusy(true);
    try {
      await api.register({
        email: form.email.trim(),
        password: form.password,
        first_name: form.first_name.trim(),
        middle_name: form.middle_name.trim() || undefined,
        last_name: form.last_name.trim(),
        phone: form.phone.trim(),
        gender: form.gender,
      });
      await login(form.email, form.password);
      navigate("/");
    } catch (err) {
      setError(api.errorMessage(err, "Registration failed. Please try again."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4 py-8">
      <div className="w-full max-w-md rounded-lg bg-white p-8 shadow">
        <h1 className="mb-6 text-center text-2xl font-bold text-slate-900">Create account</h1>
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <div className="grid grid-cols-2 gap-4">
            <Field label="First name" error={fieldErrors.first_name}>
              <TextInput
                required
                autoFocus
                autoComplete="given-name"
                value={form.first_name}
                onChange={set("first_name")}
                maxLength={150}
                invalid={!!fieldErrors.first_name}
              />
            </Field>
            <Field label="Last name" error={fieldErrors.last_name}>
              <TextInput
                required
                autoComplete="family-name"
                value={form.last_name}
                onChange={set("last_name")}
                maxLength={150}
                invalid={!!fieldErrors.last_name}
              />
            </Field>
          </div>
          <Field label="Middle name (optional)" error={fieldErrors.middle_name}>
            <TextInput
              autoComplete="additional-name"
              value={form.middle_name}
              onChange={set("middle_name")}
              maxLength={150}
              invalid={!!fieldErrors.middle_name}
            />
          </Field>
          <Field label="Email" error={fieldErrors.email}>
            <TextInput
              type="email"
              required
              autoComplete="email"
              value={form.email}
              onChange={set("email")}
              maxLength={254}
              invalid={!!fieldErrors.email}
            />
          </Field>
          <Field label="Phone" error={fieldErrors.phone}>
            <TextInput
              type="tel"
              required
              autoComplete="tel"
              placeholder="+91 98765 43210"
              value={form.phone}
              onChange={set("phone")}
              maxLength={30}
              invalid={!!fieldErrors.phone}
            />
          </Field>
          <Field label="Gender" error={fieldErrors.gender}>
            <Select
              required
              autoComplete="sex"
              value={form.gender}
              onChange={set("gender")}
              invalid={!!fieldErrors.gender}
            >
              <option value="" disabled>
                Select…
              </option>
              {GENDER_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Password" error={fieldErrors.password}>
            <div className="relative">
              <TextInput
                type={showPassword ? "text" : "password"}
                required
                minLength={8}
                autoComplete="new-password"
                value={form.password}
                onChange={set("password")}
                invalid={!!fieldErrors.password}
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
          </Field>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded bg-blue-600 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {busy ? "Creating…" : "Create account"}
          </button>
        </form>

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
          Already registered?{" "}
          <Link to="/login" className="font-medium text-blue-600 hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
