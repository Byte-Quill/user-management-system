import type { ChangeEvent } from "react";

import { COUNTRIES, countryFlag } from "@/data/countries";
import { Select } from "@/components/ui/Field";

interface CountrySelectProps {

  value: string;
  onChange: (e: ChangeEvent<HTMLSelectElement>) => void;
  invalid?: boolean;

  placeholder?: string;
}


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
