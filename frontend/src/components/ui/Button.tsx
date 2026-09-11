import { IconSpinner } from "./icons";

type Variant = "primary" | "secondary" | "danger" | "success" | "ghost";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-ink-900 text-white shadow-sm hover:bg-ink-950 active:scale-[0.99] focus-visible:outline-ink-900",
  secondary:
    "border border-ink-200 bg-white text-ink-700 shadow-xs hover:border-ink-300 hover:bg-ink-50 active:scale-[0.99] focus-visible:outline-brand-600",
  danger:
    "bg-red-600 text-white shadow-sm hover:bg-red-700 active:scale-[0.99] focus-visible:outline-red-600",
  success:
    "bg-emerald-600 text-white shadow-sm hover:bg-emerald-700 active:scale-[0.99] focus-visible:outline-emerald-600",
  ghost:
    "text-ink-500 hover:bg-ink-100/70 hover:text-ink-900 active:scale-[0.99] focus-visible:outline-brand-600",
};

const SIZES = {
  xs: "px-2.5 py-1 text-[11px]",
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
  lg: "px-5 py-2.5 text-sm",
} as const;

const BASE =
  "inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-60";


interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: keyof typeof SIZES;
  loading?: boolean;
}

export function buttonClasses(
  variant: Variant = "primary",
  size: keyof typeof SIZES = "md",
  extra = ""
): string {
  return `${BASE} ${VARIANTS[variant]} ${SIZES[size]}${extra ? ` ${extra}` : ""}`;
}

export default function Button({
  variant = "primary",
  size = "md",
  loading = false,
  disabled,
  className = "",
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={buttonClasses(variant, size, className)}
    >
      {loading && <IconSpinner />}
      {children}
    </button>
  );
}
