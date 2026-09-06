import { useMemo } from "react";
import { PhoneInput, usePhoneInput } from "react-international-phone";
import "react-international-phone/style.css";

interface PhoneInputFieldProps {
  /** E.164 value, e.g. "+919876543210". Empty string when unset. */
  value: string;
  /** Called with the E.164 value ("" when cleared). */
  onChange: (value: string) => void;
  invalid?: boolean;
}

/**
 * Telegram-style phone input (react-international-phone): a country selector
 * with flag + dial code on the left, national number on the right. The
 * dropdown is searchable. Emits canonical E.164 ("+91…"), matching the
 * backend's normalize_phone().
 *
 * No default country: the selector starts as a globe and resolves once the
 * user picks a country or types a dial code the library can guess.
 */
export default function PhoneInputField({
  value,
  onChange,
  invalid = false,
}: PhoneInputFieldProps) {
  const borderColor = invalid ? "#f87171" : "#cbd5e1";

  // usePhoneInput drives the state so we can suppress the library's
  // default-country prefill ("+1") and start from a truly empty field.
  const { inputValue, handlePhoneValueChange, inputRef } = usePhoneInput({
    value,
    onChange: ({ phone }) => onChange(phone),
    disableDialCodePrefill: true,
  });

  // Hide the library's own input; render ours so the empty state is clean.
  const showValue = useMemo(() => inputValue, [inputValue]);

  return (
    <PhoneInput
      ref={inputRef}
      value={showValue}
      onChange={(phone) => onChange(phone)}
      placeholder="Phone number"
      inputProps={{ autoComplete: "tel" }}
      disableDialCodePrefill
      style={
        {
          "--react-international-phone-border-color": borderColor,
          "--react-international-phone-border-radius": "0.25rem",
          "--react-international-phone-height": "2.25rem",
          "--react-international-phone-font-size": "0.875rem",
          "--react-international-phone-country-selector-background-color-hover":
            "#f1f5f9",
          width: "100%",
        } as React.CSSProperties
      }
      inputClassName="focus:border-blue-500"
    />
  );
}
