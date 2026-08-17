import PhoneInput, {
  getCountryCallingCode,
  getCountries,
} from "react-phone-number-input";
import type { Country, FlagProps } from "react-phone-number-input";
import flags from "react-phone-number-input/flags";
import enLabels from "react-phone-number-input/locale/en";
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
 * Country `<select/>` option labels like "India (+91)" so the calling code is
 * visible while choosing a country. Built once from the bundled English locale
 * plus libphonenumber metadata (no CDN, no runtime fetch).
 */
const LABELS_WITH_CALLING_CODES: Record<string, string> = { ...enLabels };
for (const country of getCountries()) {
  LABELS_WITH_CALLING_CODES[country] = `${enLabels[country] || country} (+${getCountryCallingCode(country)})`;
}

/**
 * Selected-country indicator: flag + calling code (e.g. 🇮🇳 +91). Passed via
 * the `flagComponent` prop; sizing comes from the `.PhoneInputCountryIcon`
 * overrides in index.css (the library stylesheet sizes that box for a bare
 * flag only).
 */
function FlagWithCallingCode({
  country,
  countryName,
  className,
}: FlagProps & { className?: string }) {
  const FlagIcon = flags[country];
  return (
    <span
      className={className}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "0.4em",
        whiteSpace: "nowrap",
      }}
    >
      {FlagIcon && <FlagIcon title={countryName} />}
      <span style={{ fontSize: "0.8em", fontWeight: 500, color: "#475569" }}>
        +{getCountryCallingCode(country)}
      </span>
    </span>
  );
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
        flagComponent={FlagWithCallingCode}
        labels={LABELS_WITH_CALLING_CODES}
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
