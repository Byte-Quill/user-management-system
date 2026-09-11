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
      <aside className="relative hidden w-[44%] max-w-xl shrink-0 overflow-hidden bg-ink-950 lg:block">
        <div
          aria-hidden="true"
          className="absolute inset-0 bg-[radial-gradient(110%_70%_at_20%_10%,rgba(99,102,241,0.5),transparent_55%),radial-gradient(90%_60%_at_85%_85%,rgba(56,189,248,0.28),transparent_60%),linear-gradient(180deg,#1b2140_0%,#12151b_100%)]"
        />
        <div aria-hidden="true" className="absolute inset-0 opacity-[0.14] [background-image:linear-gradient(rgba(255,255,255,0.5)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.5)_1px,transparent_1px)] [background-size:44px_44px] [mask-image:radial-gradient(80%_70%_at_30%_20%,black,transparent)]" />
        <div className="relative flex h-full flex-col justify-between p-10 xl:p-12">
          <Link to="/" className="flex items-center gap-2.5" aria-label="Login Portal home">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/10 text-sm font-bold text-white ring-1 ring-white/20 backdrop-blur">
              LP
            </span>
            <span className="text-[15px] font-bold tracking-tight text-white">Login Portal</span>
          </Link>

          <div className="motion-safe:animate-fade-up">
            <p className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-brand-200 ring-1 ring-white/15">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" aria-hidden="true" />
              KYC identity verification
            </p>
            <h2 className="mt-4 max-w-md text-4xl font-bold leading-[1.1] tracking-tight text-white xl:text-[2.75rem]">
              Verify identity.
              <br />
              Build trust.
            </h2>
            <p className="mt-4 max-w-md text-[15px] leading-7 text-slate-300">
              Guided applications, reviewer decisions with a full audit trail, and
              analytics your compliance team can actually read.
            </p>
            <ul className="mt-8 space-y-3.5">
              {[
                ["Guided KYC flow", "Draft, upload, and submit in minutes — nothing lost."],
                ["Human review", "Every decision recorded with notes and timestamps."],
                ["Secure by default", "HttpOnly sessions, rate limits, signed downloads."],
              ].map(([title, body]) => (
                <li key={title} className="flex items-start gap-3">
                  <span
                    aria-hidden="true"
                    className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-400/15 text-xs font-bold text-emerald-300 ring-1 ring-emerald-300/30"
                  >
                    ✓
                  </span>
                  <span>
                    <span className="block text-sm font-semibold text-white">{title}</span>
                    <span className="block text-sm text-slate-400">{body}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>

          <p className="text-xs text-slate-500">
            Protected by rate limiting · Sessions revoke on password reset
          </p>
        </div>
      </aside>

      {/* Form column */}
      <div className="flex min-w-0 flex-1 items-center justify-center px-4 py-10 sm:px-8">
        <div className="w-full max-w-md motion-safe:animate-fade-up">
          <div className="rounded-2xl border border-ink-200/70 bg-white p-7 shadow-card sm:p-8">
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
