import { useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";

import Button from "@/components/ui/Button";

interface DrawerShellProps {
  open: boolean;
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  widthClass?: string;
}

/**
 * Slide-over drawer shell: focus trap via the Modal shell contract is
 * replaced with a right-rail panel + scrim, Escape/backdrop dismissal, and a
 * sticky footer — the premium pattern for create/detail flows that deserve
 * more room than a centered dialog.
 */
export function DrawerShell({
  open,
  title,
  subtitle,
  onClose,
  children,
  footer,
  widthClass = "max-w-xl",
}: DrawerShellProps) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label={title}>
      <div
        className="absolute inset-0 bg-ink-950/45 backdrop-blur-[2px] motion-safe:animate-fade-in"
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        className={`nice-scroll absolute inset-y-0 right-0 flex w-full ${widthClass} flex-col overflow-y-auto border-l border-ink-200/70 bg-white shadow-pop motion-safe:animate-[drawer-in_0.28s_cubic-bezier(0.22,1,0.36,1)_both]`}
      >
        <style>{`@keyframes drawer-in { from { transform: translateX(32px); opacity: 0; } to { transform: translateX(0); opacity: 1; } }`}</style>
        <div className="flex items-start justify-between gap-3 border-b border-ink-100 px-6 py-5">
          <div className="min-w-0">
            <h2 className="text-lg font-semibold tracking-tight text-ink-900">{title}</h2>
            {subtitle && <p className="mt-0.5 text-sm text-ink-500">{subtitle}</p>}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close panel"
            className="rounded-lg p-1.5 text-ink-400 transition hover:bg-ink-50 hover:text-ink-700"
          >
            ✕
          </button>
        </div>
        <div className="flex-1 px-6 py-5">{children}</div>
        {footer && (
          <div className="sticky bottom-0 border-t border-ink-100 bg-white/95 px-6 py-4 backdrop-blur">
            {footer}
          </div>
        )}
      </aside>
    </div>
  );
}

interface DrawerFormProps<T extends Record<string, string>> {
  title: string;
  subtitle?: string;
  open: boolean;
  onClose: () => void;
  initial: T;
  validate: (values: T) => Partial<Record<keyof T, string>>;
  onSubmit: (values: T) => Promise<void> | void;
  submitLabel: string;
  successMessage: string;
  render: (ctx: {
    values: T;
    set: (key: keyof T) => (value: string) => void;
    errors: Partial<Record<keyof T, string>>;
    busy: boolean;
  }) => ReactNode;
}

export function useDrawerForm() {
  const [open, setOpen] = useState(false);
  const openDrawer = () => setOpen(true);
  const closeDrawer = () => setOpen(false);
  return { open, openDrawer, closeDrawer };
}

export function DrawerForm<T extends Record<string, string>>({
  title,
  subtitle,
  open,
  onClose,
  initial,
  validate,
  onSubmit,
  submitLabel,
  successMessage,
  render,
}: DrawerFormProps<T>) {
  const [values, setValues] = useState<T>(initial);
  const [errors, setErrors] = useState<Partial<Record<keyof T, string>>>({});
  const [busy, setBusy] = useState(false);
  const [serverError, setServerError] = useState("");

  useEffect(() => {
    if (open) {
      setValues(initial);
      setErrors({});
      setServerError("");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open ]);

  const set =
    (key: keyof T) =>
    (value: string) => {
      setValues((prev) => ({ ...prev, [key]: value }));
      setErrors((prev) => {
        if (!(key in prev)) return prev;
        const next = { ...prev };
        delete next[key];
        return next;
      });
    };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const problems = validate(values);
    setErrors(problems);
    if (Object.keys(problems).length > 0) return;
    setServerError("");
    setBusy(true);
    try {
      await onSubmit(values);
      onClose();
    } catch (err) {
      setServerError(err instanceof Error ? err.message : successMessage);
    } finally {
      setBusy(false);
    }
  };

  return (
    <DrawerShell
      open={open}
      title={title}
      subtitle={subtitle}
      onClose={onClose}
      footer={
        <div className="flex justify-end gap-2.5">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="drawer-form" loading={busy}>
            {submitLabel}
          </Button>
        </div>
      }
    >
      <form id="drawer-form" onSubmit={(e) => void submit(e)} className="space-y-4" noValidate>
        {serverError && (
          <p role="alert" className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {serverError}
          </p>
        )}
        {render({ values, set, errors, busy })}
      </form>
    </DrawerShell>
  );
}
