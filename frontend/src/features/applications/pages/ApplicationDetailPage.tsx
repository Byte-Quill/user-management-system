import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";

import * as api from "@/lib/api";
import { useAuth } from "@/features/auth/hooks/useAuth";
import {
  ApplicationDetails,
  AuditTrail,
  DocumentList,
} from "@/features/applications/components/ApplicationSections";
import Pagination from "@/components/ui/Pagination";
import StatusBadge from "@/components/ui/StatusBadge";
import Alert from "@/components/ui/Alert";
import Button from "@/components/ui/Button";
import Modal from "@/components/ui/Modal";
import type { AuditEntry, KYCApplication } from "@/types";
import { validateUploadFile } from "@/lib/validation";

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
  const [auditError, setAuditError] = useState("");
  const [auditCount, setAuditCount] = useState(0);
  const [auditHasNext, setAuditHasNext] = useState(false);
  const [auditHasPrev, setAuditHasPrev] = useState(false);
  const [auditPage, setAuditPage] = useState(1);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [notice, setNotice] = useState("");
  const [docType, setDocType] = useState("id_proof");
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmingSubmit, setConfirmingSubmit] = useState(false);
  const loadRequestRef = useRef(0);
  const auditRequestRef = useRef(0);

  const load = useCallback(async () => {
    if (!id) return;
    const requestId = ++loadRequestRef.current;
    try {
      const application = await api.getApplication(id);
      if (requestId !== loadRequestRef.current) return;
      setApp(application);
    } catch (err) {
      if (requestId !== loadRequestRef.current) return;
      setError(
        err instanceof api.ApiError && err.status === 404
          ? "Application not found. It may have been removed, or you don't have access."
          : "Failed to load application."
      );
    }
  }, [id]);

  const loadAudit = useCallback(
    async (pageNum: number) => {
      if (!id) return;
      const requestId = ++auditRequestRef.current;
      setAuditError("");
      try {
        const trail = await api.fetchAudit(id, pageNum);
        if (requestId !== auditRequestRef.current) return;
        setAudit(trail.results);
        setAuditCount(trail.count);
        setAuditHasNext(!!trail.next);
        setAuditHasPrev(!!trail.previous);
      } catch {
        if (requestId !== auditRequestRef.current) return;

        setAuditError("Failed to load the audit trail.");
      }
    },
    [id]
  );

  useEffect(() => {
    setApp(null);
    setError("");
    load();
  }, [load]);

  useEffect(() => {
    setAuditPage(1);
    loadAudit(1);
  }, [loadAudit]);

  useEffect(() => {
    if (auditPage === 1) return;
    loadAudit(auditPage);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auditPage]);

  if (error) return <Alert variant="error">{error}</Alert>;
  if (!app) return <p className="p-8 text-center text-slate-500">Loading…</p>;

  const editable = app.status === "draft" || app.status === "resubmission_requested";

  const isOwner = user?.id === app.applicant_id;

  const runAction = async (
    action: () => Promise<unknown>,
    successNotice: string,
    failureMessage: string
  ) => {
    if (!id) return;
    setBusy(true);
    setNotice("");
    setActionError("");
    try {
      await action();
      setNotice(successNotice);
      await Promise.all([load(), loadAudit(auditPage)]);
    } catch (err) {
      setActionError(api.errorMessage(err, failureMessage));
    } finally {
      setBusy(false);
    }
  };

  const upload = async () => {
    if (!file || !id) return;
    const invalid = validateUploadFile(file);
    if (invalid) {
      setFileError(invalid);
      return;
    }
    await runAction(
      async () => {
        await api.uploadDocument(id, docType, file);
        setFile(null);
        setFileError("");
      },
      "Document uploaded.",
      "Upload failed. Please try again."
    );
  };

  const submit = () =>
    runAction(
      () => api.submitApplication(id!),
      "Application submitted for review.",
      "Submit failed. Please try again."
    );

  const confirmSubmit = async () => {
    await submit();
    setConfirmingSubmit(false);
  };

  const removeDoc = (docId: string) =>
    runAction(
      () => api.deleteDocument(id!, docId),
      "Document removed.",
      "Remove failed. Please try again."
    );

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

      {notice && <Alert variant="success">{notice}</Alert>}
      {actionError && <Alert variant="error">{actionError}</Alert>}

      {app.status === "resubmission_requested" && isOwner && (
        <Alert variant="warning">
          <strong>Resubmission requested.</strong> {app.review_notes}
        </Alert>
      )}
      {app.status === "rejected" && (
        <Alert variant="error">
          <strong>Rejected.</strong> {app.review_notes}
        </Alert>
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
            <div className="space-y-3 border-t border-slate-100 pt-4">
              <div className="flex flex-wrap gap-2">
                <select
                  value={docType}
                  onChange={(e) => setDocType(e.target.value)}
                  className="rounded-lg border border-slate-300 bg-white px-2.5 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
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
                  className="min-w-0 flex-1 text-sm file:mr-3 file:cursor-pointer file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-2 file:text-xs file:font-semibold file:text-slate-700 hover:file:bg-slate-200"
                />
                <Button size="sm" onClick={upload} disabled={!file || !!fileError} loading={busy}>
                  Upload
                </Button>
              </div>
              {fileError ? (
                <Alert variant="error">{fileError}</Alert>
              ) : (
                <p className="text-xs text-slate-400">
                  JPG, PNG or PDF up to 5 MB — verified against the file's actual content.
                </p>
              )}
            </div>
          )}
        </section>
      </div>

      {editable && isOwner && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <Button variant="success" size="lg" onClick={() => setConfirmingSubmit(true)} disabled={busy || app.documents.length === 0}>
            Submit for review
          </Button>
          <Link
            to={`/applications/${app.id}/edit`}
            className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition-colors hover:bg-slate-50"
          >
            Edit details
          </Link>
          {app.documents.length === 0 && (
            <p className="text-sm text-slate-500">
              Upload at least one document before submitting.
            </p>
          )}
        </div>
      )}

      <AuditTrail entries={audit} error={auditError}>
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

      <Modal
        open={confirmingSubmit}
        title="Submit for review?"
        onClose={() => setConfirmingSubmit(false)}
      >
        <p className="text-sm text-slate-600">
          Once submitted, your application is locked and can no longer be edited.
          A reviewer will decide whether to approve it or request changes.
        </p>
        <div className="mt-5 flex justify-end gap-3">
          <Button variant="secondary" onClick={() => setConfirmingSubmit(false)}>
            Cancel
          </Button>
          <Button variant="success" onClick={() => void confirmSubmit()} loading={busy}>
            Submit application
          </Button>
        </div>
      </Modal>
    </div>
  );
}
