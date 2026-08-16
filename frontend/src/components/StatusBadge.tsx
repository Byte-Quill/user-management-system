import type { ApplicationStatus } from "../types";

const STYLES: Record<ApplicationStatus, string> = {
  draft: "bg-slate-200 text-slate-700",
  submitted: "bg-blue-100 text-blue-800",
  approved: "bg-green-100 text-green-800",
  rejected: "bg-red-100 text-red-800",
  resubmission_requested: "bg-orange-100 text-orange-800",
};

const LABELS: Record<ApplicationStatus, string> = {
  draft: "Draft",
  submitted: "Submitted",
  approved: "Approved",
  rejected: "Rejected",
  resubmission_requested: "Resubmission Requested",
};

export default function StatusBadge({ status }: { status: ApplicationStatus }) {
  return (
    <span
      className={`inline-block rounded-full px-3 py-1 text-xs font-semibold ${STYLES[status]}`}
    >
      {LABELS[status]}
    </span>
  );
}
