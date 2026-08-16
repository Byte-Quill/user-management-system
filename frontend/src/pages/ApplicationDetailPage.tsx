import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import * as api from "../api";
import { useAuth } from "../auth";
import {
  ApplicationDetails,
  AuditTrail,
  DocumentList,
} from "../components/ApplicationSections";
import Pagination from "../components/Pagination";
import StatusBadge from "../components/StatusBadge";
import type { AuditEntry, KYCApplication } from "../types";
import { validateUploadFile } from "../validation";

const DOC_TYPES = [
  { value: "id_proof", label: "ID Proof" },
  { value: "address_proof", label: "Address Proof" },
  { value: "selfie", label: "Selfie" },
];

export default function ApplicationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const [app, setApp] = useState<KYCApplication | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [auditCount, setAuditCount] = useState(0);
  const [auditHasNext, setAuditHasNext] = useState(false);
  const [auditHasPrev, setAuditHasPrev] = useState(false);
  const [auditPage, setAuditPage] = useState(1);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [docType, setDocType] = useState("id_proof");
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const application = await api.getApplication(id);
      setApp(application);
    } catch {
      setError("Failed to load application.");
    }
  }, [id]);

  const loadAudit = useCallback(
    async (pageNum: number) => {
      if (!id) return;
      try {
        const trail = await api.fetchAudit(id, pageNum);
        setAudit(trail.results);
        setAuditCount(trail.count);
        setAuditHasNext(!!trail.next);
        setAuditHasPrev(!!trail.previous);
      } catch {
        setError("Failed to load audit trail.");
      }
    },
    [id]
  );

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    setAuditPage(1);
    loadAudit(1);
  }, [loadAudit]);

  useEffect(() => {
    if (auditPage === 1) return; // already loaded above
    loadAudit(auditPage);
  }, [auditPage, loadAudit]);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!app) return <p className="text-slate-500">Loading…</p>;

  const editable = app.status === "draft" || app.status === "resubmission_requested";
  const isOwner = user?.email === app.applicant_email;

  const upload = async () => {
    if (!file || !id) return;
    const invalid = validateUploadFile(file);
    if (invalid) {
      setFileError(invalid);
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      await api.uploadDocument(id, docType, file);
      setFile(null);
      setFileError("");
      setNotice("Document uploaded.");
      await load();
    } catch (err) {
      setNotice(
        err instanceof api.ApiError
          ? `Upload failed: ${JSON.stringify(err.body)}`
          : "Upload failed."
      );
    } finally {
      setBusy(false);
    }
  };

  const submit = async () => {
    if (!id) return;
    setBusy(true);
    setNotice("");
    try {
      await api.submitApplication(id);
      setNotice("Application submitted for review.");
      await load();
    } catch (err) {
      setNotice(
        err instanceof api.ApiError ? `Submit failed: ${JSON.stringify(err.body)}` : "Submit failed."
      );
    } finally {
      setBusy(false);
    }
  };

  const removeDoc = async (docId: string) => {
    if (!id) return;
    setBusy(true);
    setNotice("");
    try {
      await api.deleteDocument(id, docId);
      setNotice("Document removed.");
      await Promise.all([load(), loadAudit(auditPage)]);
    } catch (err) {
      setNotice(
        err instanceof api.ApiError
          ? `Remove failed: ${JSON.stringify(err.body)}`
          : "Remove failed."
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Link to="/" className="text-sm text-blue-600 hover:underline">
            ← Back to dashboard
          </Link>
          <h1 className="mt-1 text-2xl font-bold">{app.full_name}</h1>
        </div>
        <StatusBadge status={app.status} />
      </div>

      {notice && (
        <div className="rounded bg-blue-50 px-4 py-2 text-sm text-blue-800">{notice}</div>
      )}

      {app.status === "resubmission_requested" && isOwner && (
        <div className="rounded border border-orange-300 bg-orange-50 px-4 py-3 text-sm text-orange-900">
          <strong>Resubmission requested.</strong> {app.review_notes}
        </div>
      )}
      {app.status === "rejected" && (
        <div className="rounded border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-900">
          <strong>Rejected.</strong> {app.review_notes}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <ApplicationDetails app={app} title="Details">
          {app.reviewer_email && (
            <>
              <dt className="text-slate-500">Reviewed by</dt>
              <dd>{app.reviewer_email}</dd>
            </>
          )}
        </ApplicationDetails>

        <section className="rounded-lg bg-white p-6 shadow">
          <h2 className="mb-4 text-lg font-semibold">Documents</h2>
          {app.documents.length === 0 && (
            <p className="text-sm text-slate-500">No documents uploaded yet.</p>
          )}
          <DocumentList
            documents={app.documents}
            onRemove={editable && isOwner ? (docId) => void removeDoc(docId) : undefined}
            busy={busy}
            className="mb-4"
          />

          {editable && isOwner && (
            <div className="space-y-3 border-t pt-4">
              <div className="flex gap-2">
                <select
                  value={docType}
                  onChange={(e) => setDocType(e.target.value)}
                  className="rounded border border-slate-300 px-2 py-1 text-sm"
                >
                  {DOC_TYPES.map((d) => (
                    <option key={d.value} value={d.value}>
                      {d.label}
                    </option>
                  ))}
                </select>
                <input
                  type="file"
                  accept=".jpg,.jpeg,.png,.pdf"
                  onChange={(e) => {
                    const selected = e.target.files?.[0] ?? null;
                    setFile(selected);
                    setFileError(selected ? (validateUploadFile(selected) ?? "") : "");
                  }}
                  className="flex-1 text-sm"
                />
              </div>
              {fileError && <p className="text-sm text-red-600">{fileError}</p>}
              <button
                onClick={upload}
                disabled={!file || busy || !!fileError}
                className="rounded bg-slate-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-600 disabled:opacity-50"
              >
                Upload
              </button>
            </div>
          )}
        </section>
      </div>

      {editable && isOwner && (
        <div className="rounded-lg bg-white p-6 shadow">
          <button
            onClick={submit}
            disabled={busy || app.documents.length === 0}
            className="rounded bg-green-600 px-5 py-2 text-sm font-semibold text-white hover:bg-green-700 disabled:opacity-50"
          >
            Submit for review
          </button>
          {app.documents.length === 0 && (
            <p className="mt-2 text-sm text-slate-500">
              Upload at least one document before submitting.
            </p>
          )}
        </div>
      )}

      <AuditTrail entries={audit}>
        <Pagination
          count={auditCount}
          pageNum={auditPage}
          hasNext={auditHasNext}
          hasPrev={auditHasPrev}
          loading={false}
          onPageChange={setAuditPage}
          label="events"
        />
      </AuditTrail>
    </div>
  );
}
