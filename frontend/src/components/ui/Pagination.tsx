interface Props {
  count: number;
  pageNum: number;
  hasNext: boolean;
  hasPrev: boolean;
  loading: boolean;
  onPageChange: (page: number) => void;
  label: string;
}

export default function Pagination({
  count,
  pageNum,
  hasNext,
  hasPrev,
  loading,
  onPageChange,
  label,
}: Props) {
  return (
    <div className="mt-6 flex items-center justify-between text-sm">
      <span className="text-slate-500">
        {count} {label}
      </span>
      <div className="flex gap-2">
        <button
          onClick={() => onPageChange(Math.max(1, pageNum - 1))}
          disabled={!hasPrev || loading}
          className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-50 disabled:opacity-50"
        >
          ← Prev
        </button>
        <span className="px-2 py-1 text-slate-600">Page {pageNum}</span>
        <button
          onClick={() => onPageChange(pageNum + 1)}
          disabled={!hasNext || loading}
          className="rounded border border-slate-300 px-3 py-1 hover:bg-slate-50 disabled:opacity-50"
        >
          Next →
        </button>
      </div>
    </div>
  );
}
