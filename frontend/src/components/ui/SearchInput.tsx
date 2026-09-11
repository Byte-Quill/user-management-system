import { useEffect, useRef, useState } from "react";

/**
 * Debounced input with a built-in clear affordance. Professional search fields
 * clear themselves without a page-level "reset" button and never fire a fetch
 * per keystroke.
 */
interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  delayMs?: number;
  className?: string;
}

export default function SearchInput({
  value,
  onChange,
  placeholder = "Search…",
  delayMs = 300,
  className = "",
}: SearchInputProps) {
  const [draft, setDraft] = useState(value);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => setDraft(value), [value]);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  const schedule = (next: string) => {
    setDraft(next);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => onChange(next), delayMs);
  };

  return (
    <div className={`relative ${className}`.trim()}>
      <span
        aria-hidden="true"
        className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-ink-400"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-4 w-4">
          <circle cx="11" cy="11" r="7" />
          <path strokeLinecap="round" d="m20 20-3.5-3.5" />
        </svg>
      </span>
      <input
        type="search"
        value={draft}
        onChange={(e) => schedule(e.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        className="w-full rounded-xl border border-ink-200 bg-white py-2 pl-9 pr-9 text-sm text-ink-900 shadow-xs outline-none transition placeholder:text-ink-400 hover:border-ink-300 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30 [&::-webkit-search-cancel-button]:hidden"
      />
      {draft && (
        <button
          type="button"
          onClick={() => {
            if (timer.current) clearTimeout(timer.current);
            setDraft("");
            onChange("");
          }}
          aria-label="Clear search"
          className="absolute inset-y-0 right-1 flex items-center rounded-md px-2 text-ink-400 transition hover:text-ink-700"
        >
          ✕
        </button>
      )}
    </div>
  );
}
