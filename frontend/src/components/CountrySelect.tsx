import type { ChangeEvent } from "react";

import { COUNTRIES, countryFlag } from "../countries";
import { Select } from "./Field";

interface CountrySelectProps {
  /** The stored value is the country's English name (e.g. "India"). */
  value: string;
  onChange: (e: ChangeEvent<HTMLSelectElement>) => void;
  invalid?: boolean;
  /** Placeholder shown for the empty selection; selectable so optional fields can be cleared. */
  placeholder?: string;
}

/** Country picker with flag emoji, used for nationality and address country. */
export default function CountrySelect({
  value,
  onChange,
  invalid = false,
  placeholder = "Select a country…",
}: CountrySelectProps) {
  return (
    <Select value={value} onChange={onChange} invalid={invalid} autoComplete="country-name">
      <option value="">{placeholder}</option>
      {COUNTRIES.map((country) => (
        <option key={country.code} value={country.name}>
          {countryFlag(country.code)} {country.name}
        </option>
      ))}
    </Select>
  );
}
