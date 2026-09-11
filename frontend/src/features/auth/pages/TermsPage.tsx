import { Link } from "react-router";

/**
 * Placeholder Terms & Conditions page.
 *
 * The login page links here; before this route existed the link bounced
 * users back to "/" via the catch-all redirect. Replace this copy with the
 * real terms once legal content is available.
 */
export default function TermsPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-2xl rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-semibold text-slate-900">
          Terms &amp; Conditions
        </h1>
        <p className="mt-2 text-sm text-slate-500">Last updated: September 2026</p>
        <div className="mt-6 space-y-4 text-sm leading-6 text-slate-700">
          <p>
            This placeholder page exists so the Terms &amp; Conditions link on
            the sign-in page resolves to real content. The final terms of
            service for this platform will be published here.
          </p>
          <p>
            By using this service, you agree to use it only for lawful
            purposes, to provide accurate information during identity
            verification, and to keep your account credentials confidential.
          </p>
        </div>
        <p className="mt-8 text-sm">
          <Link
            to="/login"
            className="font-medium text-indigo-600 underline-offset-2 hover:underline"
          >
            Back to sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
