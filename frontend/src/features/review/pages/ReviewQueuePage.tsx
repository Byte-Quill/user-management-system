import { Link } from "react-router";

import * as api from "@/lib/api";
import Pagination from "@/components/ui/Pagination";
import StatusBadge from "@/components/ui/StatusBadge";
import Alert from "@/components/ui/Alert";
import { buttonClasses } from "@/components/ui/Button";
import { SkeletonList } from "@/components/ui/Skeleton";
import { usePaginatedList } from "@/hooks/usePaginatedList";

export default function ReviewQueuePage() {
  const {
    items: queue,
    count,
    hasNext,
    hasPrev,
    pageNum,
    setPageNum,
    loading,
    error,
  } = usePaginatedList(api.fetchReviewQueue, "Failed to load review queue.");

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Review Queue</h1>
        <p className="mt-1 text-sm text-slate-500">
          Applications awaiting a decision.
        </p>
      </div>

      {loading && <SkeletonList />}
      {error && <Alert variant="error">{error}</Alert>}

      {!loading && !error && queue.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center">
          <p className="font-medium text-slate-700">Review queue is clear 🎉</p>
          <p className="mt-1 text-sm text-slate-500">
            No applications are awaiting a decision right now.
          </p>
        </div>
      )}

      {queue.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-4 py-3 text-left font-semibold text-slate-600">Applicant</th>
                <th className="px-4 py-3 text-left font-semibold text-slate-600">ID</th>
                <th className="px-4 py-3 text-left font-semibold text-slate-600">Docs</th>
                <th className="px-4 py-3 text-left font-semibold text-slate-600">Submitted</th>
                <th className="px-4 py-3 text-left font-semibold text-slate-600">Status</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {queue.map((app) => (
                <tr key={app.id} className="transition hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <p className="font-medium text-slate-900">{app.full_name}</p>
                    <p className="text-slate-500">{app.applicant_email ?? app.phone}</p>
                  </td>
                  <td className="px-4 py-3 capitalize text-slate-700">
                    {app.id_type.replace("_", " ")}
                    <span className="block text-slate-400">{app.id_number}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-full bg-slate-100 px-2 text-xs font-semibold text-slate-700">
                      {app.documents.length}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {app.submitted_at ? new Date(app.submitted_at).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={app.status} />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Link
                      to={`/review/${app.id}`}
                      className={buttonClasses("primary", "sm")}
                    >
                      Review
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {queue.length > 0 && (
        <Pagination
          count={count}
          pageNum={pageNum}
          hasNext={hasNext}
          hasPrev={hasPrev}
          loading={loading}
          onPageChange={setPageNum}
          label="awaiting review"
        />
      )}
    </div>
  );
}
