import { PhoneInput } from "react-international-phone";
import "react-international-phone/style.css";

interface PhoneInputFieldProps {
  value: string;

  onChange: (value: string) => void;
  invalid?: boolean;
}


export default function PhoneInputField({
  value,
  onChange,
  invalid = false,
}: PhoneInputFieldProps) {
  const borderColor = invalid ? "#f87171" : "#cbd5e1";
  return (
    <PhoneInput
      value={value}
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
