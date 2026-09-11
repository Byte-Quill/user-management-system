import { Link } from "react-router";
import type { ReactNode } from "react";

/**
 * Marketing-grade shell shared by every auth page: sticky brand panel with
 * product story + trust signals on the left, the form in a floating card on
 * the right. One identity for sign-in/register/verify/reset/terms.
 */
export default function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="flex min-h-screen bg-ink-50">
      {/* Brand panel — hidden on small screens */}
      <aside className="relative hidden w-[42%] max-w-xl shrink-0 overflow-hidden bg-ink-950 lg:block">
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-[radial-gradient(120%_90%_at_0%_0%,rgba(79,70,229,0.2),transparent_58%)]"
        />
        <div className="relative flex h-full flex-col justify-between p-10 xl:p-12">
          <Link to="/" className="flex items-center gap-2.5" aria-label="Login Portal home">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-white text-sm font-bold text-ink-950">
              LP
            </span>
            <span className="text-[15px] font-bold tracking-tight text-white">Login Portal</span>
          </Link>

          <div className="motion-safe:animate-fade-up">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-400">
              KYC · Identity verification
            </p>
            <h2 className="mt-3 max-w-md text-3xl font-semibold leading-tight tracking-tight text-white">
              One console for onboarding and review.
            </h2>
            <p className="mt-3 max-w-md text-[15px] leading-7 text-ink-300">
              Applicants submit once. Reviewers decide with full context. Every action
              lands in the audit trail.
            </p>
            <ul className="mt-8 space-y-3 border-l border-white/10 pl-5">
              {[
                ["Guided applications", "Draft, upload, and submit — validated at every step."],
                ["Reviewer workspace", "Approve, reject, or request resubmission with notes."],
                ["Full audit trail", "Who did what, when — timestamped and exportable."],
              ].map(([title, body]) => (
                <li key={title}>
                  <span className="block text-sm font-semibold text-white">{title}</span>
                  <span className="block text-sm text-ink-400">{body}</span>
                </li>
              ))}
            </ul>
          </div>

          <p className="text-xs text-ink-500">
            Rate-limited sign-in · Sessions revoke on password reset
          </p>
        </div>
      </aside>

      {/* Form column */}
      <div className="flex min-w-0 flex-1 items-center justify-center px-4 py-10 sm:px-8">
        <div className="w-full max-w-md motion-safe:animate-fade-up">
          <div className="rounded-xl border border-ink-200 bg-white p-7 shadow-xs sm:p-8">
            <div className="mb-6">
              <h1 className="text-xl font-bold tracking-tight text-ink-900">{title}</h1>
              <p className="mt-1 text-sm text-ink-500">{subtitle}</p>
            </div>
            {children}
            {footer}
          </div>
          <p className="mt-4 text-center text-xs text-ink-400">
            By signing in you agree{" "}
            <Link
              to="/terms"
              className="font-medium text-ink-500 underline decoration-ink-200 underline-offset-2 transition hover:text-ink-700 hover:decoration-ink-400"
            >
              Terms &amp; Conditions
            </Link>
            .
          </p>
        </div>
      </div>
    </div>
  );
}
