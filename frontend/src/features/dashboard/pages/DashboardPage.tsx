import { Link } from "react-router";

import * as api from "@/lib/api";
import Pagination from "@/components/ui/Pagination";
import StatusBadge from "@/components/ui/StatusBadge";
import Alert from "@/components/ui/Alert";
import { buttonClasses } from "@/components/ui/Button";
import { SkeletonList } from "@/components/ui/Skeleton";
import { IconChevronRight } from "@/components/ui/icons";
import { usePaginatedList } from "@/hooks/usePaginatedList";
import { useAuth } from "@/features/auth/hooks/useAuth";

export default function DashboardPage() {
  const { user } = useAuth();
  const isApplicant = user?.role === "applicant";
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
          <h1 className="text-2xl font-bold text-slate-900">
            {isApplicant ? "My Applications" : "Applications"}
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            {isApplicant
              ? "Track your KYC verification progress."
              : "All KYC applications across the platform."}
          </p>
        </div>
        {/* Only applicants can create/submit KYC — admins review (403 from the
            API otherwise), so the creation entry points stay applicant-only. */}
        {isApplicant && (
          <Link to="/applications/new" className={buttonClasses("primary", "md")}>
            + New Application
          </Link>
        )}
      </div>

      {loading && <SkeletonList />}
      {error && <Alert variant="error">{error}</Alert>}

      {!loading && !error && applications.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center">
          <p className="font-medium text-slate-700">
            {isApplicant ? "No KYC applications yet" : "No applications yet"}
          </p>
          <p className="mt-1 text-sm text-slate-500">
            {isApplicant
              ? "Start your first application — it takes a few minutes."
              : "Applications will appear here once customers submit them."}
          </p>
          {isApplicant && (
            <Link to="/applications/new" className={buttonClasses("primary", "md", "mt-4")}>
              Start your first application
            </Link>
          )}
        </div>
      )}

      <div className="space-y-3">
        {applications.map((app) => (
          <Link
            key={app.id}
            to={`/applications/${app.id}`}
            className="group flex items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-xs transition hover:border-slate-300"
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
              <IconChevronRight className="h-4 w-4 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-slate-500" />
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
