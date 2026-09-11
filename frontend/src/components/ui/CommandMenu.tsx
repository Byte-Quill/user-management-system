import { useId, useState } from "react";
import type { ReactNode } from "react";

/**
 * Accessible command-palette / dropdown primitive.
 *
 * - Full keyboard flow: ArrowUp/Down/Home/End, Enter to pick, Escape to close,
 *   live type-ahead filtering.
 * - Click-outside and focus-out dismissal, aria-activedescendant wiring.
 * - `disabledOptions` (with reasons) keeps choices visible but unpickable — the
 *   professional pattern for "why can't I choose this?" states.
 */
export interface CommandOption {
  value: string;
  label: string;
  hint?: string;
  keywords?: string;
  disabled?: boolean;
  disabledReason?: string;
}

interface CommandMenuProps {
  id?: string;
  label: string;
  placeholder?: string;
  options: CommandOption[];
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  invalid?: boolean;
  footer?: ReactNode;
}

export default function CommandMenu({
  id,
  label,
  placeholder = "Search…",
  options,
  value,
  onChange,
  disabled = false,
  invalid = false,
  footer,
}: CommandMenuProps) {
  const fallbackId = useId();
  const inputId = id ?? `cmd-${fallbackId}`;
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlight, setHighlight] = useState(0);

  const selected = options.find((o) => o.value === value);

  const q = query.trim().toLowerCase();
  const matches = q
    ? options.filter((o) =>
        `${o.label} ${o.hint ?? ""} ${o.keywords ?? ""}`.toLowerCase().includes(q)
      )
    : options;
  const openMenu = () => {
    if (disabled) return;
    setQuery("");
    const idx = Math.max(0, matches.findIndex((o) => o.value === value));
    setHighlight(idx);
    setOpen(true);
  };

  const commit = (option: CommandOption) => {
    if (option.disabled) return;
    onChange(option.value);
    setOpen(false);
  };

  const move = (delta: number) => {
    if (matches.length === 0) return;
    setHighlight((h) => (h + delta + matches.length) % matches.length);
  };

  const onSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      move(1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      move(-1);
    } else if (e.key === "Home") {
      e.preventDefault();
      setHighlight(0);
    } else if (e.key === "End") {
      e.preventDefault();
      setHighlight(Math.max(0, matches.length - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const opt = matches[highlight];
      if (opt) commit(opt);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };
  return (
    <div
      className="relative"
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOpen(false);
      }}
    >
      <label htmlFor={inputId} className="mb-1 block text-sm font-medium text-ink-700">
        {label}
      </label>
      <button
        id={`${inputId}-button`}
        type="button"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => (open ? setOpen(false) : openMenu())}
        className={`flex w-full items-center justify-between gap-2 rounded-xl border bg-white px-3 py-2 text-left text-sm shadow-xs transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-60 ${
          invalid
            ? "border-red-400 focus-visible:ring-red-400"
            : "border-ink-200 hover:border-ink-300"
        }`}
      >
        <span className={selected ? "truncate text-ink-900" : "truncate text-ink-400"}>
          {selected ? selected.label : placeholder}
        </span>
        <span aria-hidden="true" className="shrink-0 text-ink-400">
          ▾
        </span>
      </button>
      {open && (
        <div className="absolute inset-x-0 top-full z-40 mt-1.5 overflow-hidden rounded-xl border border-ink-200/80 bg-white shadow-pop motion-safe:animate-pop-in">
          <div className="border-b border-ink-100 p-2">
            <input
              id={inputId}
              autoFocus
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setHighlight(0);
              }}
              onKeyDown={onSearchKeyDown}
              placeholder={placeholder}
              role="combobox"
              aria-expanded="true"
              aria-controls={`${inputId}-listbox`}
              aria-activedescendant={
                matches[highlight] ? `${inputId}-opt-${highlight}` : undefined
              }
              className="w-full rounded-lg bg-ink-50 px-3 py-2 text-sm text-ink-900 outline-none placeholder:text-ink-400 focus:ring-2 focus:ring-brand-500/40"
            />
          </div>
          <ul
            id={`${inputId}-listbox`}
            role="listbox"
            aria-label={label}
            className="nice-scroll max-h-60 overflow-auto p-1.5"
          >
            {matches.length === 0 && (
              <li className="px-3 py-6 text-center text-sm text-ink-400">
                No matches for “{query.trim()}”.
              </li>
            )}
            {matches.map((option, i) => {
              const active = i === highlight;
              return (
                <li key={option.value}>
                  <button
                    id={`${inputId}-opt-${i}`}
                    type="button"
                    role="option"
                    aria-selected={option.value === value}
                    disabled={option.disabled}
                    title={option.disabled ? option.disabledReason : undefined}
                    onMouseEnter={() => setHighlight(i)}
                    onClick={() => commit(option)}
                    className={`flex w-full items-start gap-2.5 rounded-lg px-3 py-2 text-left text-sm transition disabled:cursor-not-allowed disabled:opacity-55 ${
                      active && !option.disabled ? "bg-brand-50" : "bg-transparent"
                    }`}
                  >
                    <span
                      aria-hidden="true"
                      className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${
                        option.disabled ? "bg-ink-200" : "bg-brand-500"
                      }`}
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium text-ink-900">
                        {option.label}
                      </span>
                      {(option.hint || (option.disabled && option.disabledReason)) && (
                        <span className="block truncate text-xs text-ink-500">
                          {option.disabled && option.disabledReason
                            ? option.disabledReason
                            : option.hint}
                        </span>
                      )}
                    </span>
                    {option.value === value && (
                      <span aria-hidden="true" className="mt-0.5 shrink-0 font-bold text-brand-600">
                        ✓
                      </span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
          {footer && <div className="border-t border-ink-100 px-3 py-2">{footer}</div>}
        </div>
      )}
    </div>
  );
}