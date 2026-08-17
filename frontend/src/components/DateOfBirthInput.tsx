import { useState } from "react";

import { Select } from "./Field";

/**
 * Date-of-birth picker as three dropdowns: native date inputs force tedious
 * calendar paging to reach past decades; dropdowns are one click per part.
 * Emits a complete ISO date (YYYY-MM-DD) or "" while any part is unselected.
 */

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

// Backend bound (kyc/serializers.py DOB_MIN) — years before 1900 are rejected.
const MIN_YEAR = 1900;
const CURRENT_YEAR = new Date().getFullYear();
const YEARS = Array.from(
  { length: CURRENT_YEAR - MIN_YEAR + 1 },
  (_, i) => String(CURRENT_YEAR - i)
);

interface Parts {
  year: string;
  month: string; // 1-based, unpadded
  day: string;
}

function parseISO(value: string): Parts {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!m) return { year: "", month: "", day: "" };
  return { year: m[1], month: String(Number(m[2])), day: String(Number(m[3])) };
}

function daysInMonth(year: number, month: number): number {
  // Day 0 of the *next* month is the last day of this one.
  return new Date(year, month, 0).getDate();
}

const pad = (n: string) => n.padStart(2, "0");

interface DateOfBirthInputProps {
  /** ISO date (YYYY-MM-DD) or "". */
  value: string;
  /** Called with the ISO date once all three parts are chosen, else "". */
  onChange: (iso: string) => void;
  invalid?: boolean;
}

export default function DateOfBirthInput({ value, onChange, invalid = false }: DateOfBirthInputProps) {
  const [parts, setParts] = useState<Parts>(() => parseISO(value));

  const update = (patch: Partial<Parts>) => {
    const next = { ...parts, ...patch };
    let iso = "";
    if (next.year && next.month && next.day) {
      // Clamp day overflow (e.g. Jan 31 -> Feb 28) instead of erroring.
      const maxDay = daysInMonth(Number(next.year), Number(next.month));
      if (Number(next.day) > maxDay) next.day = String(maxDay);
      iso = `${next.year}-${pad(next.month)}-${pad(next.day)}`;
    }
    setParts(next);
    onChange(iso);
  };

  const maxDay =
    parts.year && parts.month
      ? daysInMonth(Number(parts.year), Number(parts.month))
      : 31;

  return (
    <div className="grid grid-cols-3 gap-2">
      <Select
        aria-label="Day"
        value={parts.day}
        onChange={(e) => update({ day: e.target.value })}
        invalid={invalid}
      >
        <option value="">Day</option>
        {Array.from({ length: maxDay }, (_, i) => (
          <option key={i + 1} value={String(i + 1)}>
            {i + 1}
          </option>
        ))}
      </Select>
      <Select
        aria-label="Month"
        value={parts.month}
        onChange={(e) => update({ month: e.target.value })}
        invalid={invalid}
      >
        <option value="">Month</option>
        {MONTHS.map((name, i) => (
          <option key={name} value={String(i + 1)}>
            {name}
          </option>
        ))}
      </Select>
      <Select
        aria-label="Year"
        value={parts.year}
        onChange={(e) => update({ year: e.target.value })}
        invalid={invalid}
      >
        <option value="">Year</option>
        {YEARS.map((year) => (
          <option key={year} value={year}>
            {year}
          </option>
        ))}
      </Select>
    </div>
  );
}
