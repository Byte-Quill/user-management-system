/**
 * Segmented status control: the premium flow for "filter by X" on list pages.
 * One row, equal segments, active pill, live counts, full keyboard + ARIA.
 */
export interface SegmentOption {
  value: string;
  label: string;
  count?: number;
}

export default function SegmentedControl({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: SegmentOption[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className="inline-flex max-w-full items-center gap-0.5 overflow-x-auto nice-scroll rounded-xl border border-ink-200/80 bg-white p-1 shadow-xs"
    >
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(option.value)}
            className={`flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
              active
                ? "bg-ink-900 text-white shadow-sm"
                : "text-ink-500 hover:bg-ink-50 hover:text-ink-800"
            }`}
          >
            {option.label}
            {typeof option.count === "number" && (
              <span
                className={`tnum rounded-full px-1.5 py-px text-[11px] font-bold ${
                  active ? "bg-white/20 text-white" : "bg-ink-100 text-ink-500"
                }`}
              >
                {option.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
