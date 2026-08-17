import type { ReactNode } from "react";

import type { AuditEntry, KycDocument, KYCApplication } from "../types";

/** Shared applicant-detail definition list used by the applicant and reviewer views. */
export function ApplicationDetails({
  app,
  title,
  children,
}: {
  app: KYCApplication;
  title: string;
  children?: ReactNode;
}) {
  return (
    <section className="rounded-lg bg-white p-6 shadow">
      <h2 className="mb-4 text-lg font-semibold">{title}</h2>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
        <dt className="text-slate-500">Date of birth</dt>
        <dd>{app.date_of_birth}</dd>
        <dt className="text-slate-500">Nationality</dt>
        <dd>{app.nationality}</dd>
        <dt className="text-slate-500">Phone</dt>
        <dd>{app.phone}</dd>
        <dt className="text-slate-500">Address</dt>
        <dd>
          {app.address_line1}
          {app.address_line2 && `, ${app.address_line2}`}, {app.city}, {app.state}{" "}
          {app.postal_code}, {app.country}
        </dd>
        <dt className="text-slate-500">ID type</dt>
        <dd className="capitalize">{app.id_type.replace("_", " ")}</dd>
        <dt className="text-slate-500">ID number</dt>
        <dd>{app.id_number}</dd>
        {app.id_expiry && (
          <>
            <dt className="text-slate-500">ID expiry</dt>
            <dd>{app.id_expiry}</dd>
          </>
        )}
        {children}
      </dl>
    </section>
  );
}

/** Document list with an optional per-row remove action (owner-only). */
export function DocumentList({
  documents,
  onRemove,
  busy,
  className = "",
}: {
  documents: KycDocument[];
  onRemove?: (docId: string) => void;
  busy?: boolean;
  className?: string;
}) {
  return (
    <ul className={`space-y-2 ${className}`.trim()}>
      {documents.map((doc) => (
        <li key={doc.id} className="flex items-center justify-between text-sm">
          <span>
            <span className="font-medium capitalize">{doc.doc_type.replace("_", " ")}</span>{" "}
            —{" "}
            {doc.file ? (
              <a
                href={doc.file}
                target="_blank"
                rel="noreferrer"
                className="text-blue-600 hover:underline"
              >
                {doc.original_filename}
              </a>
            ) : (
              <span>{doc.original_filename}</span>
            )}
          </span>
          <span className="flex items-center gap-3">
            <span className="text-slate-400">
              {new Date(doc.uploaded_at).toLocaleDateString()}
            </span>
            {onRemove && (
              <button
                onClick={() => onRemove(doc.id)}
                disabled={busy}
                className="text-xs font-medium text-red-600 hover:underline disabled:opacity-50"
              >
                Remove
              </button>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Immutable audit-trail timeline; pass pagination as children when needed. */
export function AuditTrail({
  entries,
  error,
  children,
}: {
  entries: AuditEntry[];
  /** Load failure message; shown inside the section, not page-replacing. */
  error?: string;
  children?: ReactNode;
}) {
  return (
    <section className="rounded-lg bg-white p-6 shadow">
      <h2 className="mb-4 text-lg font-semibold">Audit Trail</h2>
      {error && <p className="mb-3 text-sm text-red-600">{error}</p>}
      <ol className="relative space-y-4 border-l border-slate-200 pl-6">
        {entries.map((entry) => (
          <li key={entry.id} className="text-sm">
            <span className="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full bg-blue-500" />
            <p className="font-medium capitalize">{entry.action.replace(/_/g, " ")}</p>
            <p className="text-slate-500">
              {entry.actor_email ?? "system"} · {new Date(entry.created_at).toLocaleString()}
            </p>
            {entry.detail && <p className="text-slate-600">{entry.detail}</p>}
          </li>
        ))}
      </ol>
      {children}
    </section>
  );
}
