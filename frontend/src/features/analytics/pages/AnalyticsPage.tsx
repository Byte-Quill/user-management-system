import { useEffect, useState } from "react";

import { errorMessage, fetchAnalytics } from "@/lib/api";
import type { Analytics } from "@/types";

const labels: Record<string, string> = {
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
    fetchAnalytics().then(setData).catch((err) => setError(errorMessage(err, "Failed to load analytics.")));
  }, []);

  if (error) return <p className="text-red-600">{error}</p>;
  if (!data) return <p className="text-slate-500">Loading analytics…</p>;

  return <div className="space-y-8">
    <div><h1 className="text-2xl font-bold">Company Analytics</h1><p className="mt-1 text-sm text-slate-500">A current view of KYC throughput and email activity.</p></div>
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{[
      ["Total applications", data.kpis.total_applications],
      ["Submitted in 30 days", data.kpis.submitted_last_30_days],
      ["Users", data.kpis.users],
      ["Pending review", data.kpis.pending_review],
    ].map(([label, value]) => <section key={label} className="rounded-lg bg-white p-5 shadow"><p className="text-sm text-slate-500">{label}</p><p className="mt-2 text-3xl font-bold">{value}</p></section>)}</div>
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="rounded-lg bg-white p-5 shadow"><h2 className="font-semibold">Approval rate</h2><p className="mt-4 text-4xl font-bold text-blue-700">{data.approval_rate === null ? "—" : `${data.approval_rate}%`}</p><h2 className="mt-8 font-semibold">Pipeline</h2><div className="mt-3 space-y-2">{Object.entries(data.pipeline).map(([status, count]) => <div key={status} className="flex justify-between border-b py-2 text-sm"><span>{labels[status] ?? status}</span><strong>{count}</strong></div>)}</div></section>
      <section className="rounded-lg bg-white p-5 shadow"><h2 className="font-semibold">Email activity, last 30 days</h2><div className="mt-4 grid grid-cols-2 gap-3"><div className="rounded border p-3"><p className="text-sm text-slate-500">Sent</p><strong className="text-2xl text-green-700">{data.email_activity.sent_last_30_days}</strong></div><div className="rounded border p-3"><p className="text-sm text-slate-500">Failed</p><strong className="text-2xl text-red-700">{data.email_activity.failed_last_30_days}</strong></div></div><h2 className="mt-8 font-semibold">Recent messages</h2><div className="mt-3 space-y-2">{data.email_activity.recent.map((email) => <div key={email.id} className="border-b py-2 text-sm"><div className="flex justify-between"><strong>{email.purpose.replace("_", " ")}</strong><span className={email.status === "sent" ? "text-green-700" : "text-red-700"}>{email.status}</span></div><p className="text-slate-500">{email.recipient} · {new Date(email.created_at).toLocaleString()}</p></div>)}</div></section>
    </div>
  </div>;
}
