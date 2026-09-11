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
      <span className="mb-1.5 block text-sm font-medium text-ink-700">{label}</span>
      {children}
      {error ? (
        <span className="mt-1.5 block text-xs font-medium text-red-600 motion-safe:animate-fade-in" role="alert">
          {error}
        </span>
      ) : valid ? (
        <span className="mt-1.5 flex items-center gap-1 text-xs font-medium text-emerald-600">
          <IconCheckSmall /> Looks good
        </span>
      ) : hint ? (
        <span className="mt-1.5 flex items-start gap-1 text-xs text-ink-400">
          <IconInfo className="mt-0.5 h-3 w-3 shrink-0" />
          {hint}
        </span>
      ) : null}
    </label>
  );
}

const baseInputClass =
  "w-full rounded-xl border bg-white px-3.5 py-2.5 text-sm text-ink-900 shadow-xs outline-none transition placeholder:text-ink-300 hover:border-ink-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30 disabled:cursor-not-allowed disabled:bg-ink-50 disabled:text-ink-400";

function inputClass(invalid: boolean, extra?: string): string {
  const tone = invalid
    ? "border-red-400 focus:border-red-500 focus:ring-red-400/30"
    : "border-ink-200";
  return `${baseInputClass} ${tone}${extra ? ` ${extra}` : ""}`;
}

interface InvalidProp {
  invalid?: boolean;
  className?: string;
}

export function TextInput({
  invalid = false,
  className = "",
  ...props
}: InputHTMLAttributes<HTMLInputElement> & InvalidProp) {
  return <input {...props} className={inputClass(invalid, className)} />;
}

export function Select({
  invalid = false,
  className = "",
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & InvalidProp) {
  return <select {...props} className={inputClass(invalid, className)} />;
}


export function PasswordInput({
  invalid = false,
  className = "",
  ...props
}: InputHTMLAttributes<HTMLInputElement> & InvalidProp) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <input
        {...props}
        type={visible ? "text" : "password"}
        className={`${inputClass(invalid, className)} pr-16`}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        className="absolute inset-y-0 right-0 px-3.5 text-xs font-semibold text-ink-400 transition hover:text-ink-700"
        aria-label={visible ? "Hide password" : "Show password"}
      >
        {visible ? "Hide" : "Show"}
      </button>
    </div>
  );
}
