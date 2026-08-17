import { useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { Link, useNavigate } from "react-router";

import * as api from "../api";
import { GOOGLE_CLIENT_ID } from "../App";
import CountrySelect from "../components/CountrySelect";
import DateOfBirthInput from "../components/DateOfBirthInput";
import { Field, Select, TextInput } from "../components/Field";
import GoogleSignInButton from "../components/GoogleSignInButton";
import PhoneInputField from "../components/PhoneInputField";
import {
  GENDER_OPTIONS,
  validateConfirmPassword,
  validateGender,
  validateName,
  validateOptional,
  validateOptionalDateOfBirth,
  validateE164Phone,
  validatePassword,
  validateRegistrationEmail,
} from "../validation";

interface RegisterForm {
  first_name: string;
  middle_name: string;
  last_name: string;
  email: string;
  phone: string;
  gender: string;
  password: string;
  confirm_password: string;
  date_of_birth: string;
  nationality: string;
  address_line1: string;
  address_line2: string;
  city: string;
  state: string;
  postal_code: string;
  country: string;
}

const INITIAL: RegisterForm = {
  first_name: "",
  middle_name: "",
  last_name: "",
  email: "",
  phone: "",
  gender: "",
  password: "",
  confirm_password: "",
  date_of_birth: "",
  nationality: "",
  address_line1: "",
  address_line2: "",
  city: "",
  state: "",
  postal_code: "",
  country: "",
};

type FieldKey = keyof RegisterForm;

/** Per-field validators; each step validates only its own fields. */
const FIELD_VALIDATORS: Record<FieldKey, (form: RegisterForm) => string | null> = {
  first_name: (f) => validateName(f.first_name, "First name"),
  middle_name: (f) => validateName(f.middle_name, "Middle name", false),
  last_name: (f) => validateName(f.last_name, "Last name"),
  // Email and phone are each optional; the at-least-one rule is checked in
  // computeStepErrors. Empty values skip their own validator.
  email: (f) => (f.email.trim() ? validateRegistrationEmail(f.email) : null),
  phone: (f) => (f.phone.trim() ? validateE164Phone(f.phone) : null),
  gender: (f) => validateGender(f.gender),
  password: (f) => validatePassword(f.password),
  confirm_password: (f) => validateConfirmPassword(f.password, f.confirm_password),
  // Optional profile details — only bounds-checked when provided.
  date_of_birth: (f) => validateOptionalDateOfBirth(f.date_of_birth),
  nationality: (f) => validateOptional(f.nationality, "Nationality", 100),
  address_line1: (f) => validateOptional(f.address_line1, "Address line 1", 255),
  address_line2: (f) => validateOptional(f.address_line2, "Address line 2", 255),
  city: (f) => validateOptional(f.city, "City", 100),
  state: (f) => validateOptional(f.state, "State", 100),
  postal_code: (f) => validateOptional(f.postal_code, "Postal code", 20),
  country: (f) => validateOptional(f.country, "Country", 100),
};

interface Step {
  title: string;
  /** Short guidance shown above the step's fields. */
  hint: string;
  fields: FieldKey[];
}

const STEPS: Step[] = [
  {
    title: "Account",
    hint: "Provide an email or a phone number (at least one). If you add an email, we'll send you a verification code before you can sign in.",
    fields: ["email", "phone", "password", "confirm_password"],
  },
  {
    title: "Personal details",
    hint: "Enter your name exactly as it appears on your ID document — reviewers compare it during KYC. Date of birth and nationality are optional.",
    fields: ["first_name", "middle_name", "last_name", "gender", "date_of_birth", "nationality"],
  },
  {
    title: "Address",
    hint: "Optional — you can skip this step. Anything entered here is prefilled into your KYC application later.",
    fields: ["address_line1", "address_line2", "city", "state", "postal_code", "country"],
  },
];

export default function RegisterPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState<RegisterForm>(INITIAL);
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<FieldKey, string>>>({});
  const [step, setStep] = useState(0);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const set =
    (key: FieldKey) =>
    (e: ChangeEvent<HTMLInputElement | HTMLSelectElement> | string) => {
      const value = typeof e === "string" ? e : e.target.value;
      setForm({ ...form, [key]: value });
      setFieldErrors((prev) => {
        if (!(key in prev)) return prev;
        const next = { ...prev };
        delete next[key];
        return next;
      });
    };

  /** Compute a step's errors without showing them. */
  const computeStepErrors = (index: number): Partial<Record<FieldKey, string>> => {
    const errors: Partial<Record<FieldKey, string>> = {};
    for (const key of STEPS[index].fields) {
      const message = FIELD_VALIDATORS[key](form);
      if (message) errors[key] = message;
    }
    // Cross-field rule (Account step): at least one contact method required.
    if (index === 0 && !form.email.trim() && !form.phone.trim()) {
      errors.email = "Provide an email address or a phone number.";
    }
    return errors;
  };

  // Per-step validity for the current form — drives the ✓ indicators and
  // gates the register action: "Create account" only appears once every
  // required field across all steps is filled.
  const stepErrors = STEPS.map((_s, i) => computeStepErrors(i));
  const firstInvalidStep = stepErrors.findIndex(
    (errors) => Object.keys(errors).length > 0,
  );
  const canRegister = firstInvalidStep === -1;

  /** Jump to any step from the indicator — navigation is free in both
   *  directions, even with empty fields; requirements are only enforced
   *  when creating the account. */
  const goToStep = (target: number) => {
    if (busy || target === step) return;
    setError("");
    setFieldErrors({});
    setStep(target);
  };

  const back = () => {
    setError("");
    setFieldErrors({});
    setStep((s) => Math.max(s - 1, 0));
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    // Multi-step: Enter/submit advances freely until the final step —
    // navigation never requires input; only creating the account does.
    if (step < STEPS.length - 1) {
      setStep(step + 1);
      return;
    }
    // Final step: every step must pass before the account is created.
    for (let i = 0; i < STEPS.length; i += 1) {
      if (Object.keys(stepErrors[i]).length > 0) {
        setFieldErrors(stepErrors[i]);
        setStep(i);
        return;
      }
    }
    setBusy(true);
    try {
      const email = form.email.trim();
      const phone = form.phone.trim();
      await api.register({
        email: email || undefined,
        password: form.password,
        first_name: form.first_name.trim(),
        middle_name: form.middle_name.trim() || undefined,
        last_name: form.last_name.trim(),
        phone: phone || undefined,
        gender: form.gender,
        date_of_birth: form.date_of_birth || null,
        nationality: form.nationality.trim() || undefined,
        address_line1: form.address_line1.trim() || undefined,
        address_line2: form.address_line2.trim() || undefined,
        city: form.city.trim() || undefined,
        state: form.state.trim() || undefined,
        postal_code: form.postal_code.trim() || undefined,
        country: form.country.trim() || undefined,
      });
      if (email) {
        // Hard email verification: no auto-login — the user must confirm the
        // OTP that was just emailed before password login works.
        navigate("/verify-email", { state: { email } });
      } else {
        // Phone-only account: nothing to verify — go straight to sign-in.
        navigate("/login", { state: { registered: true } });
      }
    } catch (err) {
      // Map server-side field errors (duplicate email/phone, disposable
      // email, …) onto the wizard: inline error on the field + jump back to
      // the step that contains it, instead of one opaque message.
      if (err instanceof api.ApiError && err.body && typeof err.body === "object") {
        const body = err.body as Record<string, string | string[]>;
        const errors: Partial<Record<FieldKey, string>> = {};
        let firstStep = -1;
        for (const [key, value] of Object.entries(body)) {
          if (!(key in FIELD_VALIDATORS)) continue;
          const fieldKey = key as FieldKey;
          errors[fieldKey] = Array.isArray(value) ? value.join(" ") : String(value);
          const stepIndex = STEPS.findIndex((s) => s.fields.includes(fieldKey));
          if (stepIndex >= 0 && (firstStep === -1 || stepIndex < firstStep)) {
            firstStep = stepIndex;
          }
        }
        if (Object.keys(errors).length > 0) {
          setFieldErrors(errors);
          if (firstStep >= 0) setStep(firstStep);
          return;
        }
      }
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
          {/* Step indicator + progress bar */}
          <div>
            <div className="mb-2 flex items-start justify-between">
              {STEPS.map((s, i) => {
                // ✓ means the step's requirements are met (not just visited).
                const done =
                  i !== step && Object.keys(stepErrors[i]).length === 0;
                return (
                  <button
                    key={s.title}
                    type="button"
                    onClick={() => goToStep(i)}
                    disabled={busy}
                    aria-current={i === step ? "step" : undefined}
                    aria-label={`Go to step ${i + 1}: ${s.title}`}
                    className="flex w-1/3 cursor-pointer flex-col items-center gap-1 disabled:cursor-not-allowed"
                  >
                    <span
                      className={
                        "flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold transition-colors " +
                        (done
                          ? "bg-blue-600 text-white hover:bg-blue-700"
                          : i === step
                            ? "border-2 border-blue-600 bg-white text-blue-600"
                            : "border border-slate-300 bg-white text-slate-400 hover:border-blue-400 hover:text-blue-500")
                      }
                    >
                      {done ? "✓" : i + 1}
                    </span>
                    <span
                      className={
                        "text-center text-[11px] leading-tight " +
                        (i === step
                          ? "font-medium text-blue-700"
                          : done
                            ? "font-medium text-slate-700"
                            : "text-slate-400")
                      }
                    >
                      {s.title}
                    </span>
                  </button>
                );
              })}
            </div>
            <div
              className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200"
              role="progressbar"
              aria-valuenow={step + 1}
              aria-valuemin={1}
              aria-valuemax={STEPS.length}
              aria-label={`Step ${step + 1} of ${STEPS.length}: ${STEPS[step].title}`}
            >
              <div
                className="h-full rounded-full bg-blue-600 transition-all duration-300"
                style={{ width: `${((step + 1) / STEPS.length) * 100}%` }}
              />
            </div>
          </div>

          {/* Per-step hint */}
          <p className="rounded bg-blue-50 px-3 py-2 text-xs leading-relaxed text-blue-800">
            {STEPS[step].hint}
          </p>

          {step === 0 && (
            <>
              <Field label="Email (optional if phone is provided)" error={fieldErrors.email}>
                <TextInput
                  type="email"
                  autoFocus
                  autoComplete="email"
                  value={form.email}
                  onChange={set("email")}
                  maxLength={254}
                  invalid={!!fieldErrors.email}
                />
              </Field>
              <Field label="Phone (optional if email is provided)" error={fieldErrors.phone}>
                <PhoneInputField
                  value={form.phone}
                  onChange={set("phone")}
                  invalid={!!fieldErrors.phone}
                />
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
              <Field label="Confirm password" error={fieldErrors.confirm_password}>
                <div className="relative">
                  <TextInput
                    type={showConfirmPassword ? "text" : "password"}
                    required
                    minLength={8}
                    autoComplete="new-password"
                    value={form.confirm_password}
                    onChange={set("confirm_password")}
                    invalid={!!fieldErrors.confirm_password}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword((v) => !v)}
                    className="absolute inset-y-0 right-0 px-3 text-xs font-medium text-slate-500 hover:text-slate-700"
                    aria-label={showConfirmPassword ? "Hide password" : "Show password"}
                  >
                    {showConfirmPassword ? "Hide" : "Show"}
                  </button>
                </div>
              </Field>
            </>
          )}

          {step === 1 && (
            <>
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
              <div className="grid grid-cols-2 gap-4">
                <Field label="Date of birth (optional)" error={fieldErrors.date_of_birth}>
                  <DateOfBirthInput
                    value={form.date_of_birth}
                    onChange={set("date_of_birth")}
                    invalid={!!fieldErrors.date_of_birth}
                  />
                </Field>
                <Field label="Nationality (optional)" error={fieldErrors.nationality}>
                  <CountrySelect
                    value={form.nationality}
                    onChange={set("nationality")}
                    invalid={!!fieldErrors.nationality}
                  />
                </Field>
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <Field label="Address line 1" error={fieldErrors.address_line1}>
                <TextInput
                  autoFocus
                  autoComplete="address-line1"
                  value={form.address_line1}
                  onChange={set("address_line1")}
                  maxLength={255}
                  invalid={!!fieldErrors.address_line1}
                />
              </Field>
              <Field label="Address line 2" error={fieldErrors.address_line2}>
                <TextInput
                  autoComplete="address-line2"
                  value={form.address_line2}
                  onChange={set("address_line2")}
                  maxLength={255}
                  invalid={!!fieldErrors.address_line2}
                />
              </Field>
              <div className="grid grid-cols-2 gap-4">
                <Field label="City" error={fieldErrors.city}>
                  <TextInput
                    autoComplete="address-level2"
                    value={form.city}
                    onChange={set("city")}
                    maxLength={100}
                    invalid={!!fieldErrors.city}
                  />
                </Field>
                <Field label="State" error={fieldErrors.state}>
                  <TextInput
                    autoComplete="address-level1"
                    value={form.state}
                    onChange={set("state")}
                    maxLength={100}
                    invalid={!!fieldErrors.state}
                  />
                </Field>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <Field label="Postal code" error={fieldErrors.postal_code}>
                  <TextInput
                    autoComplete="postal-code"
                    value={form.postal_code}
                    onChange={set("postal_code")}
                    maxLength={20}
                    invalid={!!fieldErrors.postal_code}
                  />
                </Field>
                <Field label="Country" error={fieldErrors.country}>
                  <CountrySelect
                    value={form.country}
                    onChange={set("country")}
                    invalid={!!fieldErrors.country}
                  />
                </Field>
              </div>
            </>
          )}

          {error && <p className="text-sm text-red-600">{error}</p>}

          {step === STEPS.length - 1 && !canRegister && (
            <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-800">
              Some required fields are still missing.{" "}
              <button
                type="button"
                onClick={() => goToStep(firstInvalidStep)}
                className="font-semibold underline hover:text-amber-950"
              >
                Go to {STEPS[firstInvalidStep].title}
              </button>
            </div>
          )}

          <div className="flex gap-3">
            {step > 0 && (
              <button
                type="button"
                onClick={back}
                disabled={busy}
                className="flex-1 rounded border border-slate-300 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                Back
              </button>
            )}
            {step < STEPS.length - 1 && (
              <button
                type="submit"
                disabled={busy}
                className="flex-1 rounded bg-blue-600 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
              >
                Next
              </button>
            )}
            {step === STEPS.length - 1 && canRegister && (
              <button
                type="submit"
                disabled={busy}
                className="flex-1 rounded bg-blue-600 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {busy ? "Creating…" : "Create account"}
              </button>
            )}
          </div>
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
