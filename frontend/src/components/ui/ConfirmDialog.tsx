import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";

import Button from "@/components/ui/Button";
import { Field, TextInput } from "@/components/ui/Field";
import Modal from "@/components/ui/Modal";

export interface ConfirmDialogConfig {
  title: string;
  message: string;
  confirmLabel?: string;
  tone?: "danger" | "brand" | "success";
  requireTypedText?: string;
  requireTypedHint?: string;
}

interface ConfirmDialogApi {
  confirm: (config: ConfirmDialogConfig) => Promise<boolean>;
}

const ConfirmDialogContext = createContext<ConfirmDialogApi | null>(null);

const TONE_BUTTON: Record<NonNullable<ConfirmDialogConfig["tone"]>, "danger" | "primary" | "success"> = {
  danger: "danger",
  brand: "primary",
  success: "success",
};

const TONE_ICON: Record<NonNullable<ConfirmDialogConfig["tone"]>, { wrap: string; glyph: string }> = {
  danger: { wrap: "bg-red-50 text-red-600 ring-red-100", glyph: "!" },
  brand: { wrap: "bg-brand-50 text-brand-600 ring-brand-100", glyph: "?" },
  success: { wrap: "bg-emerald-50 text-emerald-600 ring-emerald-100", glyph: "✓" },
};

interface PendingState extends Required<Pick<ConfirmDialogConfig, "title" | "message">> {
  confirmLabel: string;
  tone: NonNullable<ConfirmDialogConfig["tone"]>;
  requireTypedText?: string;
  requireTypedHint?: string;
  resolve: (value: boolean) => void;
}

/**
 * Promise-based confirm dialog. Destructive actions get one consistent
 * title/icon/copy/footer contract (optional typed confirmation for
 * irreversible actions) instead of ad-hoc markup per page.
 */
export function ConfirmDialogProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<PendingState | null>(null);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setTyped("");
    setBusy(false);
  }, [pending]);

  const confirm = useCallback((config: ConfirmDialogConfig) => {
    return new Promise<boolean>((resolve) => {
      setPending({
        title: config.title,
        message: config.message,
        confirmLabel: config.confirmLabel ?? "Confirm",
        tone: config.tone ?? "danger",
        requireTypedText: config.requireTypedText,
        requireTypedHint: config.requireTypedHint,
        resolve,
      });
    });
  }, []);
  const close = useCallback((value: boolean) => {
    setPending((current) => {
      current?.resolve(value);
      return null;
    });
  }, []);

  const needsTyped = !!pending?.requireTypedText;
  const typedOk = !needsTyped || typed.trim() === (pending?.requireTypedText ?? "");

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!pending || !typedOk) return;
    setBusy(true);
    try {
      close(true);
    } finally {
      setBusy(false);
    }
  };

  return (
    <ConfirmDialogContext.Provider value={{ confirm }}>
      {children}
      <Modal open={!!pending} title={pending?.title ?? "Confirm"} onClose={() => close(false)}>
        {pending && (
          <form onSubmit={(e) => void onSubmit(e)} className="space-y-4">
            <div className="flex items-start gap-3">
              <span
                aria-hidden="true"
                className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-lg font-bold ring-1 ${TONE_ICON[pending.tone].wrap}`}
              >
                {TONE_ICON[pending.tone].glyph}
              </span>
              <p className="pt-1.5 text-sm leading-6 text-ink-600">{pending.message}</p>
            </div>
            {needsTyped && (
              <Field
                label={`Type “${pending.requireTypedText}” to confirm`}
                hint={pending.requireTypedHint ?? "This action cannot be undone."}
                error={
                  typed && !typedOk ? "The typed text does not match." : undefined
                }
              >
                <TextInput
                  autoFocus
                  autoComplete="off"
                  value={typed}
                  onChange={(e) => setTyped(e.target.value)}
                  placeholder={pending.requireTypedText}
                />
              </Field>
            )}
            <div className="flex justify-end gap-2.5 pt-1">
              <Button type="button" variant="secondary" onClick={() => close(false)}>
                Cancel
              </Button>
              <Button
                type="submit"
                variant={TONE_BUTTON[pending.tone]}
                loading={busy}
                disabled={needsTyped && !typedOk}
              >
                {pending.confirmLabel}
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </ConfirmDialogContext.Provider>
  );
}

export function useConfirmDialog(): ConfirmDialogApi {
  const ctx = useContext(ConfirmDialogContext);
  if (!ctx) throw new Error("useConfirmDialog must be used within ConfirmDialogProvider");
  return ctx;
}