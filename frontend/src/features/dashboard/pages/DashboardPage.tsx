import { Link } from "react-router";

import * as api from "@/lib/api";
import Pagination from "@/components/ui/Pagination";
import StatusBadge from "@/components/ui/StatusBadge";
import Alert from "@/components/ui/Alert";
import { buttonClasses } from "@/components/ui/Button";
import { SkeletonList } from "@/components/ui/Skeleton";
import { IconChevronRight } from "@/components/ui/icons";
import { usePaginatedList } from "@/hooks/usePaginatedList";

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
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">My Applications</h1>
          <p className="mt-1 text-sm text-slate-500">
            Track your KYC verification progress.
          </p>
        </div>
        <Link to="/applications/new" className={buttonClasses("primary", "md")}>
          + New Application
        </Link>
      </div>

      {loading && <SkeletonList />}
      {error && <Alert variant="error">{error}</Alert>}

      {!loading && !error && applications.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center">
          <p className="font-medium text-slate-700">No KYC applications yet</p>
          <p className="mt-1 text-sm text-slate-500">
            Start your first application — it takes a few minutes.
          </p>
          <Link to="/applications/new" className={buttonClasses("primary", "md", "mt-4")}>
            Start your first application
          </Link>
        </div>
      )}

      <div className="space-y-3">
        {applications.map((app) => (
          <Link
            key={app.id}
            to={`/applications/${app.id}`}
            className="group flex items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-blue-300 hover:shadow-md"
          >
            <div className="min-w-0">
              <p className="truncate font-semibold text-slate-900">{app.full_name}</p>
              <p className="mt-0.5 truncate text-sm text-slate-500">
                <span className="capitalize">{app.id_type.replace("_", " ")}</span> ·{" "}
                {app.id_number} · Created{" "}
                {new Date(app.created_at).toLocaleDateString()}
                {app.submitted_at && (
                  <>
                    {" "}
                    · Submitted {new Date(app.submitted_at).toLocaleDateString()}
                  </>
                )}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-3">
              <StatusBadge status={app.status} />
              <IconChevronRight className="h-4 w-4 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-blue-500" />
            </div>
          </Link>
        ))}
      </div>

      {applications.length > 0 && (
        <Pagination
          count={count}
          pageNum={pageNum}
          hasNext={hasNext}
          hasPrev={hasPrev}
          loading={loading}
          onPageChange={setPageNum}
          label="total"
        />
      )}
    </div>
  );
}
