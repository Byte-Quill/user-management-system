import { useEffect, useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { useNavigate, useParams } from "react-router";

import * as api from "@/lib/api";
import { useAuth } from "@/features/auth/hooks/useAuth";
import CountrySelect from "@/components/form/CountrySelect";
import DateOfBirthInput from "@/components/form/DateOfBirthInput";
import { Field, Select, TextInput } from "@/components/ui/Field";
import Alert from "@/components/ui/Alert";
import Button from "@/components/ui/Button";
import PhoneInputField from "@/components/form/PhoneInputField";
import type { ApplicationPayload } from "@/types";
import { LIMITS, capitalizeWords, todayISO, validateApplication } from "@/lib/validation";
import type { FieldErrors } from "@/lib/validation";

const EMPTY: ApplicationPayload = {
  full_name: "",
  date_of_birth: "",
  nationality: "",
  phone: "",
  address_line1: "",
  address_line2: "",
  city: "",
  state: "",
  postal_code: "",
  country: "",
  id_type: "passport",
  id_number: "",
  id_expiry: "",
};

export default function ApplicationFormPage() {
  const { user } = useAuth();
  const navigate = useNavigate();

  const { id } = useParams<{ id: string }>();
  const [loadingExisting, setLoadingExisting] = useState(!!id);

  const [form, setForm] = useState<ApplicationPayload>(() => ({
    ...EMPTY,
    full_name: user
      ? [user.first_name, user.middle_name, user.last_name].filter(Boolean).join(" ")
      : "",
    phone: user?.phone ?? "",
    date_of_birth: user?.date_of_birth ?? "",
    nationality: user?.nationality ?? "",
    address_line1: user?.address_line1 ?? "",
    address_line2: user?.address_line2 ?? "",
    city: user?.city ?? "",
    state: user?.state ?? "",
    postal_code: user?.postal_code ?? "",
    country: user?.country ?? "",
  }));
  const [fieldErrors, setFieldErrors] = useState<FieldErrors<keyof ApplicationPayload>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    (async () => {
      try {
        const app = await api.getApplication(id);
        if (cancelled) return;
        if (app.status !== "draft" && app.status !== "resubmission_requested") {
          setError("This application can no longer be edited.");
          setLoadingExisting(false);
          return;
        }
        setForm({
          full_name: app.full_name,
          date_of_birth: app.date_of_birth,
          nationality: app.nationality,
          phone: app.phone,
          address_line1: app.address_line1,
          address_line2: app.address_line2,
          city: app.city,
          state: app.state,
          postal_code: app.postal_code,
          country: app.country,
          id_type: app.id_type,
          id_number: app.id_number,
          id_expiry: app.id_expiry ?? "",
        });
      } catch (err) {
        if (!cancelled) {
          setError(api.errorMessage(err, "Failed to load application."));
        }
      } finally {
        if (!cancelled) setLoadingExisting(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  const set =
    (key: keyof ApplicationPayload) =>
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

  const blur =
    (key: keyof ApplicationPayload) => () => {
      let current = form;
      if (key === "full_name") {
        current = { ...form, full_name: capitalizeWords(form.full_name) };
        setForm(current);
      }
      const message = validateApplication(current)[key];
      setFieldErrors((prev) => {
        const next = { ...prev };
        if (message) next[key] = message;
        else delete next[key];
        return next;
      });
    };

  const expiryIsPast = !!form.id_expiry && form.id_expiry < todayISO();

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    const errors = validateApplication(form);
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }
    setBusy(true);
    try {
      const payload: ApplicationPayload = {
        ...form,
        full_name: capitalizeWords(form.full_name.trim()),
        id_expiry: form.id_expiry || null,
      };
      const app = id
        ? await api.updateApplication(id, payload)
        : await api.createApplication(payload);
      navigate(`/applications/${app.id}`);
    } catch (err) {
      setError(
        api.errorMessage(err, id ? "Failed to update application." : "Failed to create application.")
      );
    } finally {
      setBusy(false);
    }
  };

  if (loadingExisting) return <p className="p-8 text-center text-slate-500">Loading…</p>;

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-1 text-2xl font-bold text-slate-900">
        {id ? "Edit KYC Application" : "New KYC Application"}
      </h1>
      <p className="mb-6 text-sm text-slate-500">
        Fields are checked as you go; you can save a draft and finish later.
      </p>
      <form onSubmit={onSubmit} className="space-y-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <section>
          <h2 className="mb-3 text-lg font-semibold text-slate-800">Personal Information</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Full name" error={fieldErrors.full_name}>
              <TextInput required value={form.full_name} onChange={set("full_name")} onBlur={blur("full_name")} maxLength={LIMITS.fullName}
                invalid={!!fieldErrors.full_name} />
            </Field>
            <Field label="Date of birth" error={fieldErrors.date_of_birth}>
              <DateOfBirthInput value={form.date_of_birth} onChange={set("date_of_birth")}
                invalid={!!fieldErrors.date_of_birth} />
            </Field>
            <Field label="Nationality" error={fieldErrors.nationality}>
              <CountrySelect value={form.nationality} onChange={set("nationality")}
                invalid={!!fieldErrors.nationality} />
            </Field>
            <Field label="Phone" error={fieldErrors.phone}>
              <PhoneInputField value={form.phone} onChange={set("phone")}
                invalid={!!fieldErrors.phone} />
            </Field>
          </div>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-semibold text-slate-800">Address</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <Field label="Address line 1" error={fieldErrors.address_line1}>
                <TextInput required value={form.address_line1} onChange={set("address_line1")} onBlur={blur("address_line1")}
                  maxLength={LIMITS.addressLine1} invalid={!!fieldErrors.address_line1} />
              </Field>
            </div>
            <div className="sm:col-span-2">
              <Field label="Address line 2 (optional)" error={fieldErrors.address_line2}>
                <TextInput value={form.address_line2} onChange={set("address_line2")} onBlur={blur("address_line2")}
                  maxLength={LIMITS.addressLine2} invalid={!!fieldErrors.address_line2} />
              </Field>
            </div>
            <Field label="City" error={fieldErrors.city}>
              <TextInput required value={form.city} onChange={set("city")} onBlur={blur("city")} maxLength={LIMITS.city}
                invalid={!!fieldErrors.city} />
            </Field>
            <Field label="State" error={fieldErrors.state}>
              <TextInput required value={form.state} onChange={set("state")} onBlur={blur("state")} maxLength={LIMITS.state}
                invalid={!!fieldErrors.state} />
            </Field>
            <Field label="Postal code" error={fieldErrors.postal_code}>
              <TextInput required value={form.postal_code} onChange={set("postal_code")} onBlur={blur("postal_code")}
                maxLength={LIMITS.postalCode} invalid={!!fieldErrors.postal_code} />
            </Field>
            <Field label="Country" error={fieldErrors.country}>
              <CountrySelect value={form.country} onChange={set("country")}
                invalid={!!fieldErrors.country} />
            </Field>
          </div>
        </section>

        <section>
          <h2 className="mb-3 text-lg font-semibold text-slate-800">Identity Document</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="ID type" error={fieldErrors.id_type}>
              <Select value={form.id_type} onChange={set("id_type")}>
                <option value="passport">Passport</option>
                <option value="national_id">National ID</option>
                <option value="drivers_license">Driver's License</option>
              </Select>
            </Field>
            <Field label="ID number" error={fieldErrors.id_number}>
              <TextInput required value={form.id_number} onChange={set("id_number")} onBlur={blur("id_number")} maxLength={LIMITS.idNumber}
                invalid={!!fieldErrors.id_number} />
            </Field>
            <Field
              label="ID expiry (optional)"
              error={fieldErrors.id_expiry}
              hint="Leave blank if the ID has no expiry date."
            >
              <TextInput type="date" value={form.id_expiry ?? ""} onChange={set("id_expiry")}
                invalid={!!fieldErrors.id_expiry} />
              {expiryIsPast && (
                <span className="mt-1 flex items-start gap-1 text-xs text-amber-600" role="status">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m0 3.5h.01M10.34 3.94 2.25 18a1.5 1.5 0 0 0 1.29 2.25h16.92A1.5 1.5 0 0 0 21.75 18L13.66 3.94a1.5 1.5 0 0 0-2.32 0Z" />
                  </svg>
                  This ID has expired — update the expiry before submitting for review.
                </span>
              )}
            </Field>
          </div>
        </section>

        {error && <Alert variant="error">{error}</Alert>}

        <div className="flex justify-end gap-3">
          <Button type="button" variant="secondary" onClick={() => navigate("/")}>
            Cancel
          </Button>
          <Button type="submit" loading={busy}>
            {busy ? "Saving…" : id ? "Save changes" : "Save draft"}
          </Button>
        </div>
      </form>
    </div>
  );
}
