import { Link } from "react-router-dom";

import * as api from "../api";
import Pagination from "../components/Pagination";
import StatusBadge from "../components/StatusBadge";
import { usePaginatedList } from "../hooks/usePaginatedList";

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
      <h1 className="mb-6 text-2xl font-bold">Review Queue</h1>
      {loading && <p className="text-slate-500">Loading…</p>}
      {error && <p className="text-red-600">{error}</p>}

      {!loading && queue.length === 0 && (
        <div className="rounded-lg bg-white p-10 text-center shadow">
          <p className="text-slate-600">No applications awaiting review. 🎉</p>
        </div>
      )}

      <div className="overflow-hidden rounded-lg bg-white shadow">
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
              <tr key={app.id} className="hover:bg-slate-50">
                <td className="px-4 py-3">
                  <p className="font-medium">{app.full_name}</p>
                  <p className="text-slate-500">{app.applicant_email ?? app.phone}</p>
                </td>
                <td className="px-4 py-3 capitalize">
                  {app.id_type.replace("_", " ")} · {app.id_number}
                </td>
                <td className="px-4 py-3">{app.documents.length}</td>
                <td className="px-4 py-3">
                  {app.submitted_at ? new Date(app.submitted_at).toLocaleDateString() : "—"}
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={app.status} />
                </td>
                <td className="px-4 py-3 text-right">
                  <Link
                    to={`/review/${app.id}`}
                    className="rounded bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700"
                  >
                    Review
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Pagination
        count={count}
        pageNum={pageNum}
        hasNext={hasNext}
        hasPrev={hasPrev}
        loading={loading}
        onPageChange={setPageNum}
        label="awaiting review"
      />
    </div>
  );
}
