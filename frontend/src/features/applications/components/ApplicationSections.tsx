import type { ReactNode } from "react";

import type { AuditEntry, KycDocument, KYCApplication } from "@/types";
import { todayISO } from "@/lib/validation";
import Alert from "@/components/ui/Alert";
import { IconFile } from "@/components/ui/icons";


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
            <dd className={app.id_expiry < todayISO() ? "font-medium text-red-600" : ""}>
              {app.id_expiry}
              {app.id_expiry < todayISO() && (
                <span className="ml-2 rounded-full bg-red-50 px-2 py-0.5 text-xs font-semibold text-red-700 ring-1 ring-inset ring-red-200">
                  expired
                </span>
              )}
            </dd>
          </>
        )}
        {children}
      </dl>
    </section>
  );
}


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
        <li key={doc.id} className="flex items-center justify-between gap-3 text-sm">
          <span className="flex min-w-0 items-center gap-2">
            <IconFile className="h-4 w-4 shrink-0 text-slate-400" />
            <span className="font-medium capitalize text-slate-800">
              {doc.doc_type.replace("_", " ")}
            </span>
            <span className="text-slate-300">·</span>
            {doc.file ? (
              <a
                href={doc.file}
                target="_blank"
                rel="noreferrer"
                className="truncate text-blue-600 hover:underline"
              >
                {doc.original_filename}
              </a>
            ) : (
              <span className="truncate text-slate-600">{doc.original_filename}</span>
            )}
          </span>
          <span className="flex shrink-0 items-center gap-3">
            <span className="text-slate-400">
              {new Date(doc.uploaded_at).toLocaleDateString()}
            </span>
            {onRemove && (
              <button
                onClick={() => onRemove(doc.id)}
                disabled={busy}
                className="rounded px-1.5 py-0.5 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
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


const ACTION_DOTS: Record<string, string> = {
  created: "bg-slate-400",
  updated: "bg-slate-400",
  submitted: "bg-blue-500",
  document_uploaded: "bg-blue-400",
  document_removed: "bg-slate-300",
  approved: "bg-emerald-500",
  rejected: "bg-red-500",
  resubmission_requested: "bg-orange-500",
};


export function AuditTrail({
  entries,
  error,
  children,
}: {
  entries: AuditEntry[];

  error?: string;
  children?: ReactNode;
}) {
  return (
    <section className="rounded-lg bg-white p-6 shadow">
      <h2 className="mb-4 text-lg font-semibold">Audit Trail</h2>
      {error && <Alert variant="error" className="mb-3">{error}</Alert>}
      <ol className="relative space-y-4 border-l border-slate-200 pl-6">
        {entries.map((entry) => (
          <li key={entry.id} className="text-sm">
            <span
              className={`absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full ${
                ACTION_DOTS[entry.action] ?? "bg-slate-400"
              }`}
            />
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
