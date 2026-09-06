import { useState } from "react";
import type { InputHTMLAttributes, SelectHTMLAttributes } from "react";
import { IconCheckSmall, IconInfo } from "./icons";

interface FieldProps {
  label: string;

  error?: string;

  hint?: string;

  valid?: boolean;
  children: React.ReactNode;
}

export function Field({ label, error, hint, valid, children }: FieldProps) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700">{label}</span>
      {children}
      {error ? (
        <span className="mt-1 block text-xs text-red-600" role="alert">
          {error}
        </span>
      ) : valid ? (
        <span className="mt-1 flex items-center gap-1 text-xs text-emerald-600">
          <IconCheckSmall /> Looks good
        </span>
      ) : hint ? (
        <span className="mt-1 flex items-start gap-1 text-xs text-slate-400">
          <IconInfo className="mt-0.5 h-3 w-3 shrink-0" />
          {hint}
        </span>
      ) : null}
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


export function PasswordInput({
  invalid = false,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & InvalidProp) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <input {...props} type={visible ? "text" : "password"} className={inputClass(invalid)} />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        className="absolute inset-y-0 right-0 px-3 text-xs font-medium text-slate-500 hover:text-slate-700"
        aria-label={visible ? "Hide password" : "Show password"}
      >
        {visible ? "Hide" : "Show"}
      </button>
    </div>
  );
}
