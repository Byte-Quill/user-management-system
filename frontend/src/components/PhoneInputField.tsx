import PhoneInput from "react-phone-number-input";
import type { Country } from "react-phone-number-input";
import flags from "react-phone-number-input/flags";
import "react-phone-number-input/style.css";

interface PhoneInputFieldProps {
  /** E.164 value, e.g. "+919876543210". Empty string when unset. */
  value: string;
  /** Called with the E.164 value ("" when cleared). */
  onChange: (value: string) => void;
  invalid?: boolean;
  /** Initial country for the calling-code picker. */
  defaultCountry?: string;
}

/**
 * Phone input with a country picker (flag + calling code) powered by
 * react-phone-number-input / libphonenumber. It formats as the user types and
 * emits a canonical E.164 number ("+91…"), which matches the backend's
 * normalize_phone() canonical form. Flags are bundled inline SVGs — no CDN.
 */
export default function PhoneInputField({
  value,
  onChange,
  invalid = false,
  defaultCountry = "IN",
}: PhoneInputFieldProps) {
  const border = invalid
    ? "border-red-400 focus-within:border-red-500 focus-within:ring-red-500"
    : "border-slate-300 focus-within:border-blue-500 focus-within:ring-blue-500";
  return (
    <div
      className={`rounded border bg-white px-3 focus-within:ring-1 ${border}`}
    >
      <PhoneInput
        flags={flags}
        defaultCountry={defaultCountry as Country}
        value={value || undefined}
        onChange={(next) => onChange(next ?? "")}
        placeholder="98765 43210"
        autoComplete="tel"
        className="w-full border-0 py-2 text-sm focus:outline-none focus:ring-0"
      />
    </div>
  );
}
