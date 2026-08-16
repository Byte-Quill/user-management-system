import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

interface FieldProps {
  label: string;
  /** Validation error message rendered below the input. */
  error?: string;
  children: ReactNode;
}

export function Field({ label, error, children }: FieldProps) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700">{label}</span>
      {children}
      {error && <span className="mt-1 block text-xs text-red-600">{error}</span>}
    </label>
  );
}

const baseInputClass =
  "w-full rounded border px-3 py-2 text-sm focus:outline-none focus:ring-1";

function inputClass(invalid: boolean): string {
  return invalid
    ? `${baseInputClass} border-red-400 focus:border-red-500 focus:ring-red-500`
    : `${baseInputClass} border-slate-300 focus:border-blue-500 focus:ring-blue-500`;
}

interface InvalidProp {
  /** Renders a red border to flag a validation failure. */
  invalid?: boolean;
}

export function TextInput({
  invalid = false,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & InvalidProp) {
  return <input {...props} className={inputClass(invalid)} />;
}

export function Select({
  invalid = false,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & InvalidProp) {
  return <select {...props} className={inputClass(invalid)} />;
}
