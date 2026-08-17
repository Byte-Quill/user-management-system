import { Link } from "react-router";

import * as api from "../api";
import Pagination from "../components/Pagination";
import StatusBadge from "../components/StatusBadge";
import { usePaginatedList } from "../hooks/usePaginatedList";

export default function DashboardPage() {
  const {
    items: applications,
    count,
    hasNext,
    hasPrev,
    pageNum,
    setPageNum,
    loading,
    error,
  } = usePaginatedList(api.listApplications, "Failed to load applications.");

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold">My Applications</h1>
        <Link
          to="/applications/new"
          className="rounded bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
        >
          New Application
        </Link>
      </div>

      {loading && <p className="text-slate-500">Loading…</p>}
      {error && <p className="text-red-600">{error}</p>}

      {!loading && applications.length === 0 && (
        <div className="rounded-lg bg-white p-10 text-center shadow">
          <p className="text-slate-600">You have no KYC applications yet.</p>
          <Link to="/applications/new" className="mt-2 inline-block font-medium text-blue-600 hover:underline">
            Start your first application →
          </Link>
        </div>
      )}

      <div className="space-y-3">
        {applications.map((app) => (
          <Link
            key={app.id}
            to={`/applications/${app.id}`}
            className="flex items-center justify-between rounded-lg bg-white p-4 shadow transition hover:shadow-md"
          >
            <div>
              <p className="font-semibold">{app.full_name}</p>
              <p className="text-sm text-slate-500">
                {app.id_type.replace("_", " ")} · {app.id_number} · created{" "}
                {new Date(app.created_at).toLocaleDateString()}
              </p>
            </div>
            <StatusBadge status={app.status} />
          </Link>
        ))}
      </div>

      <Pagination
        count={count}
        pageNum={pageNum}
        hasNext={hasNext}
        hasPrev={hasPrev}
        loading={loading}
        onPageChange={setPageNum}
        label="total"
      />
    </div>
  );
}
