import { createContext, useCallback, useContext, useRef, useState } from "react";
import type { ReactNode } from "react";

import { IconAlert, IconCheck, IconInfo } from "@/components/ui/icons";

type ToastKind = "success" | "error" | "info";

interface ToastItem {
  id: number;
  kind: ToastKind;
  title: string;
  detail?: string;
}

interface ToastApi {
  notify: (kind: ToastKind, title: string, detail?: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

const KIND_STYLES: Record<ToastKind, { bar: string; icon: typeof IconInfo; text: string }> = {
  success: { bar: "bg-emerald-500", icon: IconCheck, text: "text-emerald-600" },
  error: { bar: "bg-red-500", icon: IconAlert, text: "text-red-600" },
  info: { bar: "bg-brand-500", icon: IconInfo, text: "text-brand-600" },
};

const DISMISS_MS = 4200;

/**
 * Global toast stack. Pro: transient successes (saved, uploaded, decision
 * recorded) and background notices no longer fight the inline Alert slot,
 * which stays reserved for blocking form/page errors.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const idRef = useRef(1);

  const dismiss = useCallback((id: number) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const notify = useCallback(
    (kind: ToastKind, title: string, detail?: string) => {
      const id = idRef.current++;
      setItems((prev) => [...prev.slice(-3), { id, kind, title, detail }]);
      window.setTimeout(() => dismiss(id), DISMISS_MS);
    },
    [dismiss]
  );

  return (
    <ToastContext.Provider value={{ notify }}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-0 z-[70] flex flex-col items-center gap-2 px-4 pb-5 sm:items-end sm:pr-6"
      >
        {items.map((toast) => {
          const style = KIND_STYLES[toast.kind];
          const Icon = style.icon;
          return (
            <div
              key={toast.id}
              role="status"
              className="pointer-events-auto w-full max-w-sm overflow-hidden rounded-xl border border-ink-200/80 bg-white shadow-pop motion-safe:animate-pop-in"
            >
              <div className="flex items-start gap-3 p-3.5">
                <span className={`mt-0.5 ${style.text}`}>
                  <Icon className="h-5 w-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-ink-900">{toast.title}</p>
                  {toast.detail && (
                    <p className="mt-0.5 truncate text-xs text-ink-500">{toast.detail}</p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => dismiss(toast.id)}
                  aria-label="Dismiss notification"
                  className="-mr-1 rounded p-1 text-ink-300 transition hover:bg-ink-50 hover:text-ink-600"
                >
                  ✕
                </button>
              </div>
              <div className="h-0.5 w-full bg-ink-100">
                <div
                  className={`h-full w-full origin-left ${style.bar} motion-safe:animate-toast-life`}
                  style={{ animationDuration: `${DISMISS_MS}ms` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
