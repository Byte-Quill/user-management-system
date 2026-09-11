import type { ReactNode } from "react";

/**
 * Elevated content surface used across every operational page.
 * Single source of truth for card radius / border / shadow so panels,
 * tables and wizards all share one premium elevation language.
 */
export function Card({ className = "", children }: { className?: string; children: ReactNode }) {
  return (
    <section className={`rounded-xl border border-ink-200 bg-white shadow-xs ${className}`.trim()}>
      {children}
    </section>
  );
}

export function CardHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 px-5 pt-5 sm:px-6">
      <div className="min-w-0">
        <h2 className="text-base font-semibold tracking-tight text-ink-900">{title}</h2>
        {subtitle && <p className="mt-0.5 text-sm text-ink-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/**
 * Consistent page title block: eyebrow kicker + H1 + description + actions.
 * Replaces the ad-hoc h1/p divs scattered across pages.
 */
export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0 motion-safe:animate-fade-up">
        {eyebrow && (
          <p className="mb-1.5 inline-flex items-center gap-1.5 rounded-full bg-brand-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-brand-700 ring-1 ring-inset ring-brand-200">
            {eyebrow}
          </p>
        )}
        <h1 className="text-2xl font-bold tracking-tight text-ink-900 sm:text-[1.7rem]">
          {title}
        </h1>
        {description && <p className="mt-1 max-w-2xl text-sm text-ink-500">{description}</p>}
      </div>
      {actions && (
        <div className="flex shrink-0 flex-wrap items-center gap-2 motion-safe:animate-fade-up">
          {actions}
        </div>
      )}
    </div>
  );
}
