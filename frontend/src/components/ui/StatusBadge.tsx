import type { ApplicationStatus } from "@/types";

const DOT_STYLES: Record<ApplicationStatus, string> = {
  draft: "bg-slate-500",
  submitted: "bg-blue-500",
  approved: "bg-green-500",
  rejected: "bg-red-500",
  resubmission_requested: "bg-orange-500",
};

const STYLES: Record<ApplicationStatus, string> = {
  draft: "bg-slate-100 text-slate-700 ring-1 ring-inset ring-slate-300/60",
  submitted: "bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-200",
  approved: "bg-green-50 text-green-700 ring-1 ring-inset ring-green-200",
  rejected: "bg-red-50 text-red-700 ring-1 ring-inset ring-red-200",
  resubmission_requested: "bg-orange-50 text-orange-700 ring-1 ring-inset ring-orange-200",
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
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold ${STYLES[status]}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${DOT_STYLES[status]}`} />
      {LABELS[status]}
    </span>
  );
}
