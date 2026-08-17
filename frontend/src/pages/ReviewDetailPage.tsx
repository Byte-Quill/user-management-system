import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import * as api from "../api";
import {
  ApplicationDetails,
  AuditTrail,
  DocumentList,
} from "../components/ApplicationSections";
import StatusBadge from "../components/StatusBadge";
import type { AuditEntry, KYCApplication } from "../types";
import { validateReviewNotes } from "../validation";

export default function ReviewDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [app, setApp] = useState<KYCApplication | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [auditError, setAuditError] = useState("");
  const [decision, setDecision] = useState("approve");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      setApp(await api.getApplication(id));
    } catch {
      setError("Failed to load application.");
      return;
    }
    // Audit trail is supplementary: its failure is scoped to the section,
    // never replaces the application view.
    try {
      setAuditError("");
      const trail = await api.fetchAudit(id);
      setAudit(trail.results);
    } catch {
      setAuditError("Failed to load the audit trail.");
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
    const notesError = validateReviewNotes(decision, notes);
    if (notesError) {
      setError(notesError);
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api.reviewApplication(id, decision, notes);
      navigate("/review");
    } catch (err) {
      setError(api.errorMessage(err, "Review failed."));
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
          <p className="text-sm text-slate-500">{app.applicant_email ?? app.phone}</p>
        </div>
        <StatusBadge status={app.status} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <ApplicationDetails app={app} title="Applicant Details">
          <dt className="text-slate-500">Submitted</dt>
          <dd>{app.submitted_at ? new Date(app.submitted_at).toLocaleString() : "—"}</dd>
        </ApplicationDetails>

        <section className="rounded-lg bg-white p-6 shadow">
          <h2 className="mb-4 text-lg font-semibold">Documents</h2>
          {app.documents.length === 0 && (
            <p className="text-sm text-slate-500">No documents uploaded.</p>
          )}
          <DocumentList documents={app.documents} />
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

      <AuditTrail entries={audit} error={auditError} />
    </div>
  );
}
