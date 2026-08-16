import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import * as api from "../api";
import StatusBadge from "../components/StatusBadge";
import type { AuditEntry, KYCApplication } from "../types";

export default function ReviewDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [app, setApp] = useState<KYCApplication | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [decision, setDecision] = useState("approve");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const [application, trail] = await Promise.all([
        api.getApplication(id),
        api.fetchAudit(id),
      ]);
      setApp(application);
      setAudit(trail.results);
    } catch {
      setError("Failed to load application.");
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  if (error && !app) return <p className="text-red-600">{error}</p>;
  if (!app) return <p className="text-slate-500">Loading…</p>;

  const reviewable = app.status === "submitted";

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!id) return;
    setBusy(true);
    setError("");
    try {
      await api.reviewApplication(id, decision, notes);
      navigate("/review");
    } catch (err) {
      setError(
        err instanceof api.ApiError
          ? `Review failed: ${JSON.stringify(err.body)}`
          : "Review failed."
      );
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Link to="/review" className="text-sm text-blue-600 hover:underline">
            ← Back to queue
          </Link>
          <h1 className="mt-1 text-2xl font-bold">{app.full_name}</h1>
          <p className="text-sm text-slate-500">{app.applicant_email}</p>
        </div>
        <StatusBadge status={app.status} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-lg bg-white p-6 shadow">
          <h2 className="mb-4 text-lg font-semibold">Applicant Details</h2>
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
            <dt className="text-slate-500">Submitted</dt>
            <dd>{app.submitted_at ? new Date(app.submitted_at).toLocaleString() : "—"}</dd>
          </dl>
        </section>

        <section className="rounded-lg bg-white p-6 shadow">
          <h2 className="mb-4 text-lg font-semibold">Documents</h2>
          {app.documents.length === 0 && (
            <p className="text-sm text-slate-500">No documents uploaded.</p>
          )}
          <ul className="space-y-2">
            {app.documents.map((doc) => (
              <li key={doc.id} className="flex items-center justify-between text-sm">
                <span>
                  <span className="font-medium capitalize">
                    {doc.doc_type.replace("_", " ")}
                  </span>{" "}
                  —{" "}
                  <a
                    href={doc.file}
                    target="_blank"
                    rel="noreferrer"
                    className="text-blue-600 hover:underline"
                  >
                    {doc.original_filename}
                  </a>
                </span>
                <span className="text-slate-400">
                  {new Date(doc.uploaded_at).toLocaleDateString()}
                </span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      {reviewable ? (
        <section className="rounded-lg bg-white p-6 shadow">
          <h2 className="mb-4 text-lg font-semibold">Decision</h2>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="flex flex-wrap gap-4">
              {[
                { value: "approve", label: "Approve", color: "green" },
                { value: "reject", label: "Reject", color: "red" },
                { value: "request_resubmission", label: "Request Resubmission", color: "orange" },
              ].map((opt) => (
                <label
                  key={opt.value}
                  className={`flex cursor-pointer items-center gap-2 rounded border px-4 py-2 text-sm font-medium ${
                    decision === opt.value
                      ? "border-blue-500 bg-blue-50 text-blue-800"
                      : "border-slate-300 text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  <input
                    type="radio"
                    name="decision"
                    value={opt.value}
                    checked={decision === opt.value}
                    onChange={() => setDecision(opt.value)}
                    className="accent-blue-600"
                  />
                  {opt.label}
                </label>
              ))}
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">
                Notes {decision !== "approve" && <span className="text-red-600">*</span>}
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                placeholder={
                  decision === "approve"
                    ? "Optional notes"
                    : "Explain what is wrong or missing"
                }
                className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <button
              type="submit"
              disabled={busy}
              className="rounded bg-blue-600 px-5 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {busy ? "Submitting…" : "Submit decision"}
            </button>
          </form>
        </section>
      ) : (
        <section className="rounded-lg bg-white p-6 shadow">
          <h2 className="mb-2 text-lg font-semibold">Decision</h2>
          <p className="text-sm text-slate-600">
            This application is <StatusBadge status={app.status} />
            {app.reviewer_email && <> — reviewed by {app.reviewer_email}</>}
          </p>
          {app.review_notes && (
            <p className="mt-2 rounded bg-slate-50 p-3 text-sm text-slate-700">
              {app.review_notes}
            </p>
          )}
        </section>
      )}

      <section className="rounded-lg bg-white p-6 shadow">
        <h2 className="mb-4 text-lg font-semibold">Audit Trail</h2>
        <ol className="relative space-y-4 border-l border-slate-200 pl-6">
          {audit.map((entry) => (
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
      </section>
    </div>
  );
}
