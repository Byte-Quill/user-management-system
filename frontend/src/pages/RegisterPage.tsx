import { useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import * as api from "../api";
import { useAuth } from "../auth";
import { Field, TextInput } from "../components/Field";
import { validateEmail, validatePassword, validateUsername } from "../validation";

export default function RegisterPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    email: "",
    username: "",
    password: "",
    first_name: "",
    last_name: "",
  });
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<keyof typeof form, string>>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const set = (key: keyof typeof form) => (e: ChangeEvent<HTMLInputElement>) => {
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
    const errors: Partial<Record<keyof typeof form, string>> = {};
    const emailError = validateEmail(form.email);
    if (emailError) errors.email = emailError;
    const usernameError = validateUsername(form.username);
    if (usernameError) errors.username = usernameError;
    const passwordError = validatePassword(form.password);
    if (passwordError) errors.password = passwordError;
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }
    setBusy(true);
    try {
      await api.register(form);
      await login(form.email, form.password);
      navigate("/");
    } catch (err) {
      setError(api.errorMessage(err, "Registration failed. Please try again."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
      <div className="w-full max-w-md rounded-lg bg-white p-8 shadow">
        <h1 className="mb-6 text-center text-2xl font-bold text-slate-900">Create account</h1>
        <form onSubmit={onSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Field label="First name">
              <TextInput value={form.first_name} onChange={set("first_name")} maxLength={150} />
            </Field>
            <Field label="Last name">
              <TextInput value={form.last_name} onChange={set("last_name")} maxLength={150} />
            </Field>
          </div>
          <Field label="Username" error={fieldErrors.username}>
            <TextInput required value={form.username} onChange={set("username")} maxLength={150}
              invalid={!!fieldErrors.username} />
          </Field>
          <Field label="Email" error={fieldErrors.email}>
            <TextInput type="email" required value={form.email} onChange={set("email")} maxLength={254}
              invalid={!!fieldErrors.email} />
          </Field>
          <Field label="Password" error={fieldErrors.password}>
            <TextInput type="password" required minLength={8} value={form.password} onChange={set("password")}
              invalid={!!fieldErrors.password} />
          </Field>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <button type="submit" disabled={busy}
            className="w-full rounded bg-blue-600 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50">
            {busy ? "Creating…" : "Create account"}
          </button>
        </form>
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
