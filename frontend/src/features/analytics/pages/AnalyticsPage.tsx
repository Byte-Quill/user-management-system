import { useEffect, useState } from "react";

import { errorMessage, fetchAnalytics } from "@/lib/api";
import Alert from "@/components/ui/Alert";
import { Skeleton } from "@/components/ui/Skeleton";
import type { Analytics } from "@/types";

const LABELS: Record<string, string> = {
  draft: "Draft",
  submitted: "Submitted",
  approved: "Approved",
  rejected: "Rejected",
  resubmission_requested: "Resubmission requested",
};

export default function AnalyticsPage() {
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchAnalytics()
      .then(setData)
      .catch((err) => setError(errorMessage(err, "Failed to load analytics.")));
  }, []);

  if (error) return <Alert variant="error">{error}</Alert>;

  if (!data) {
    return (
      <div className="space-y-6" aria-hidden="true">
        <Skeleton className="h-8 w-64" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-28 rounded-xl" />
          ))}
        </div>
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-72 rounded-xl" />
          <Skeleton className="h-72 rounded-xl" />
        </div>
      </div>
    );
  }

  const totalPipeline = Object.values(data.pipeline).reduce((a, b) => a + b, 0);

  const kpis = [
    { label: "Total applications", value: data.kpis.total_applications },
    { label: "Submitted in 30 days", value: data.kpis.submitted_last_30_days },
    { label: "Users", value: data.kpis.users },
    { label: "Pending review", value: data.kpis.pending_review },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Company Analytics</h1>
        <p className="mt-1 text-sm text-slate-500">
          A current view of KYC throughput and email activity.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {kpis.map(({ label, value }) => (
          <section key={label} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-sm text-slate-500">{label}</p>
            <p className="mt-2 text-3xl font-bold text-slate-900">{value}</p>
          </section>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="font-semibold text-slate-900">Approval rate</h2>
          <p className="mt-4 text-4xl font-bold text-blue-700">
            {data.approval_rate === null ? "—" : `${data.approval_rate}%`}
          </p>
          {data.approval_rate !== null && (
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-blue-600 transition-all"
                style={{ width: `${Math.min(100, data.approval_rate)}%` }}
              />
            </div>
          )}

          <h2 className="mt-8 font-semibold text-slate-900">Pipeline</h2>
          <div className="mt-3 space-y-2">
            {Object.entries(data.pipeline).map(([status, count]) => (
              <div key={status} className="text-sm">
                <div className="flex justify-between py-1">
                  <span className="text-slate-600">{LABELS[status] ?? status}</span>
                  <strong className="text-slate-900">{count}</strong>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-slate-400"
                    style={{ width: totalPipeline ? `${(count / totalPipeline) * 100}%` : "0%" }}
                  />
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="font-semibold text-slate-900">Email activity, last 30 days</h2>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3">
              <p className="text-sm text-emerald-700">Sent</p>
              <p className="text-2xl font-bold text-emerald-800">
                {data.email_activity.sent_last_30_days}
              </p>
            </div>
            <div className="rounded-lg border border-red-200 bg-red-50 p-3">
              <p className="text-sm text-red-700">Failed</p>
              <p className="text-2xl font-bold text-red-800">
                {data.email_activity.failed_last_30_days}
              </p>
            </div>
          </div>

          <h2 className="mt-8 font-semibold text-slate-900">Recent messages</h2>
          <div className="mt-3 space-y-2">
            {data.email_activity.recent.map((email) => (
              <div key={email.id} className="flex items-center justify-between gap-3 border-b py-2 text-sm last:border-0">
                <div className="min-w-0">
                  <p className="font-medium capitalize text-slate-800">
                    {email.purpose.replace("_", " ")}
                  </p>
                  <p className="truncate text-slate-500">
                    {email.recipient} · {new Date(email.created_at).toLocaleString()}
                  </p>
                </div>
                <span
                  className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${
                    email.status === "sent"
                      ? "bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200"
                      : "bg-red-50 text-red-700 ring-1 ring-inset ring-red-200"
                  }`}
                >
                  {email.status}
                </span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
