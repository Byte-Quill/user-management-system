interface Props {
  count: number;
  pageNum: number;
  hasNext: boolean;
  hasPrev: boolean;
  loading: boolean;
  onPageChange: (page: number) => void;
  label: string;

  pageSize?: number;
}

export default function Pagination({
  count,
  pageNum,
  hasNext,
  hasPrev,
  loading,
  onPageChange,
  label,
  pageSize = 20,
}: Props) {
  const totalPages = Math.max(1, Math.ceil(count / pageSize));
  return (
    <div className="mt-6 flex items-center justify-between text-sm">
      <span className="text-slate-500">
        <strong className="font-semibold text-slate-700">{count}</strong> {label}
      </span>
      <div className="flex items-center gap-2">
        <button
          onClick={() => onPageChange(Math.max(1, pageNum - 1))}
          disabled={!hasPrev || loading}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 font-medium hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          ← Prev
        </button>
        <span className="px-1 text-slate-600">
          Page {pageNum} of {totalPages}
        </span>
        <button
          onClick={() => onPageChange(pageNum + 1)}
          disabled={!hasNext || loading}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 font-medium hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Next →
        </button>
      </div>
    </div>
  );
}
