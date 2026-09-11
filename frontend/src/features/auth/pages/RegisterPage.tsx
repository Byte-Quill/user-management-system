import { useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { Link, useNavigate } from "react-router";

import * as api from "@/lib/api";
import { GOOGLE_CLIENT_ID } from "@/app/config";
import CountrySelect from "@/components/form/CountrySelect";
import DateOfBirthInput from "@/components/form/DateOfBirthInput";
import { Field, PasswordInput, Select, TextInput } from "@/components/ui/Field";
import GoogleSignInButton from "@/features/auth/components/GoogleSignInButton";
import PhoneInputField from "@/components/form/PhoneInputField";
import AuthShell from "@/features/auth/components/AuthShell";
import PasswordStrength from "@/components/ui/PasswordStrength";
import {
  GENDER_OPTIONS,
  LIMITS,
  PASSWORD_MIN_LENGTH,
  capitalizeFirst,
  validateConfirmPassword,
  validateGender,
  validateName,
  validateOptional,
  validateOptionalDateOfBirth,
  validateE164Phone,
  validatePassword,
  validateRegistrationEmail,
} from "@/lib/validation";

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


const FIELD_VALIDATORS: Record<FieldKey, (form: RegisterForm) => string | null> = {
  first_name: (f) => validateName(f.first_name, "First name"),
  middle_name: (f) => validateName(f.middle_name, "Middle name", false),
  last_name: (f) => validateName(f.last_name, "Last name"),

  email: (f) => (f.email.trim() ? validateRegistrationEmail(f.email) : null),
  phone: (f) => (f.phone.trim() ? validateE164Phone(f.phone) : null),
  gender: (f) => validateGender(f.gender),
  password: (f) => validatePassword(f.password),
  confirm_password: (f) => validateConfirmPassword(f.password, f.confirm_password),

  date_of_birth: (f) => validateOptionalDateOfBirth(f.date_of_birth),
  nationality: (f) => validateOptional(f.nationality, "Nationality", LIMITS.nationality),
  address_line1: (f) => validateOptional(f.address_line1, "Address line 1", LIMITS.addressLine1),
  address_line2: (f) => validateOptional(f.address_line2, "Address line 2", LIMITS.addressLine2),
  city: (f) => validateOptional(f.city, "City", LIMITS.city),
  state: (f) => validateOptional(f.state, "State", LIMITS.state),
  postal_code: (f) => validateOptional(f.postal_code, "Postal code", LIMITS.postalCode),
  country: (f) => validateOptional(f.country, "Country", LIMITS.country),
};

interface Step {
  title: string;

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

  const [touched, setTouched] = useState<Partial<Record<FieldKey, true>>>({});
  const blur = (key: FieldKey) => () => {
    setTouched((prev) => ({ ...prev, [key]: true }));

    let current = form;
    if (key === "first_name" || key === "middle_name" || key === "last_name") {
      current = { ...form, [key]: capitalizeFirst(form[key]) };
      setForm(current);
    }
    const message = FIELD_VALIDATORS[key](current);
    setFieldErrors((prev) => {
      const next = { ...prev };
      if (message) next[key] = message;
      else delete next[key];
      return next;
    });
    if (key === "password" && touched.confirm_password) {
      const matchError = validateConfirmPassword(form.password, form.confirm_password);
      setFieldErrors((prev) => {
        const next = { ...prev };
        if (matchError) next.confirm_password = matchError;
        else delete next.confirm_password;
        return next;
      });
    }
  };

  const computeStepErrors = (index: number): Partial<Record<FieldKey, string>> => {
    const errors: Partial<Record<FieldKey, string>> = {};
    for (const key of STEPS[index].fields) {
      const message = FIELD_VALIDATORS[key](form);
      if (message) errors[key] = message;
    }

    if (index === 0 && !form.email.trim() && !form.phone.trim()) {
      errors.email = "Provide an email address or a phone number.";
    }
    return errors;
  };

  const stepErrors = STEPS.map((_s, i) => computeStepErrors(i));
  const firstInvalidStep = stepErrors.findIndex(
    (errors) => Object.keys(errors).length > 0,
  );
  const canRegister = firstInvalidStep === -1;

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

    if (step < STEPS.length - 1) {
      setStep(step + 1);
      return;
    }

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
        first_name: capitalizeFirst(form.first_name.trim()),
        middle_name: form.middle_name.trim()
          ? capitalizeFirst(form.middle_name.trim())
          : undefined,
        last_name: capitalizeFirst(form.last_name.trim()),
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
        navigate("/verify-email", { state: { email } });
      } else {
        navigate("/login", { state: { registered: true } });
      }
    } catch (err) {
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
    <AuthShell
      title="Create account"
      subtitle={`Step ${step + 1} of ${STEPS.length} · ${STEPS[step].title}`}
      footer={
        <p className="mt-5 border-t border-ink-100 pt-4 text-center text-sm text-ink-600">
          Already registered?{" "}
          <Link to="/login" className="font-semibold text-brand-600 hover:text-brand-700 hover:underline">
            Sign in
          </Link>
        </p>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
          <div className="mb-2 flex items-start justify-between">
              {STEPS.map((s, i) => {
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
                          ? "bg-brand-600 text-white hover:bg-brand-700"
                          : i === step
                            ? "border-2 border-brand-600 bg-white text-brand-600"
                            : "border border-ink-300 bg-white text-ink-400 hover:border-brand-400 hover:text-brand-500")
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
                className="h-full rounded-full bg-brand-600 transition-all duration-300"
                style={{ width: `${((step + 1) / STEPS.length) * 100}%` }}
              />
            </div>

          <p className="rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-xs leading-relaxed text-brand-800 motion-safe:animate-fade-in">
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
                  onBlur={blur("email")}
                  maxLength={LIMITS.email}
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
                <PasswordInput
                  required
                  minLength={PASSWORD_MIN_LENGTH}
                  autoComplete="new-password"
                  value={form.password}
                  onChange={set("password")}
                  onBlur={blur("password")}
                  invalid={!!fieldErrors.password}
                />
                <PasswordStrength password={form.password} />
              </Field>
              <Field label="Confirm password" error={fieldErrors.confirm_password}>
                <PasswordInput
                  required
                  minLength={PASSWORD_MIN_LENGTH}
                  autoComplete="new-password"
                  value={form.confirm_password}
                  onChange={set("confirm_password")}
                  onBlur={blur("confirm_password")}
                  invalid={!!fieldErrors.confirm_password}
                />
                {form.confirm_password && !fieldErrors.confirm_password && (
                  <span className="mt-1 flex items-center gap-1 text-xs text-emerald-600">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="h-3.5 w-3.5" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
                    </svg>
                    Passwords match
                  </span>
                )}
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
                    onBlur={blur("first_name")}
                    maxLength={LIMITS.name}
                    invalid={!!fieldErrors.first_name}
                  />
                </Field>
                <Field label="Last name" error={fieldErrors.last_name}>
                  <TextInput
                    required
                    autoComplete="family-name"
                    value={form.last_name}
                    onChange={set("last_name")}
                    onBlur={blur("last_name")}
                    maxLength={LIMITS.name}
                    invalid={!!fieldErrors.last_name}
                  />
                </Field>
              </div>
              <Field label="Middle name (optional)" error={fieldErrors.middle_name}>
                <TextInput
                  autoComplete="additional-name"
                  value={form.middle_name}
                  onChange={set("middle_name")}
                  maxLength={LIMITS.name}
                  invalid={!!fieldErrors.middle_name}
                />
              </Field>
              <Field label="Gender" error={fieldErrors.gender}>
                <Select
                  required
                  autoComplete="sex"
                  value={form.gender}
                  onChange={set("gender")}
                  onBlur={blur("gender")}
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
                  maxLength={LIMITS.addressLine1}
                  invalid={!!fieldErrors.address_line1}
                />
              </Field>
              <Field label="Address line 2" error={fieldErrors.address_line2}>
                <TextInput
                  autoComplete="address-line2"
                  value={form.address_line2}
                  onChange={set("address_line2")}
                  maxLength={LIMITS.addressLine2}
                  invalid={!!fieldErrors.address_line2}
                />
              </Field>
              <div className="grid grid-cols-2 gap-4">
                <Field label="City" error={fieldErrors.city}>
                  <TextInput
                    autoComplete="address-level2"
                    value={form.city}
                    onChange={set("city")}
                    maxLength={LIMITS.city}
                    invalid={!!fieldErrors.city}
                  />
                </Field>
                <Field label="State" error={fieldErrors.state}>
                  <TextInput
                    autoComplete="address-level1"
                    value={form.state}
                    onChange={set("state")}
                    maxLength={LIMITS.state}
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
                    maxLength={LIMITS.postalCode}
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
                className="flex-1 rounded-xl border border-ink-200 py-2 text-sm font-semibold text-ink-700 hover:border-ink-300 hover:bg-ink-50 disabled:opacity-50"
              >
                Back
              </button>
            )}
            {step < STEPS.length - 1 && (
              <button
                type="submit"
                disabled={busy}
                className="flex-1 rounded-xl bg-ink-900 py-2 text-sm font-semibold text-white hover:bg-ink-950 active:scale-[0.99] disabled:opacity-50"
              >
                Next
              </button>
            )}
            {step === STEPS.length - 1 && canRegister && (
              <button
                type="submit"
                disabled={busy}
                className="flex-1 rounded-xl bg-ink-900 py-2 text-sm font-semibold text-white hover:bg-ink-950 active:scale-[0.99] disabled:opacity-50"
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
    </AuthShell>
  );
}
