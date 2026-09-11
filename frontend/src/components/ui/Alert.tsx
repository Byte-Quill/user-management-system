import { IconAlert, IconCheck, IconInfo } from "./icons";

type Variant = "error" | "success" | "info" | "warning";

const STYLES: Record<Variant, string> = {
  error: "border-red-200 bg-red-50 text-red-700",
  success: "border-emerald-200 bg-emerald-50 text-emerald-700",
  info: "border-brand-200 bg-brand-50 text-brand-800",
  warning: "border-amber-200 bg-amber-50 text-amber-800",
};

const ICONS: Record<Variant, typeof IconInfo> = {
  error: IconAlert,
  success: IconCheck,
  info: IconInfo,
  warning: IconAlert,
};

interface AlertProps {
  variant?: Variant;
  children: React.ReactNode;
  className?: string;
}


export default function Alert({ variant = "info", children, className = "" }: AlertProps) {
  const Icon = ICONS[variant];
  return (
    <div
      role={variant === "error" ? "alert" : "status"}
      className={`flex items-start gap-2.5 rounded-xl border px-3.5 py-2.5 text-sm shadow-xs motion-safe:animate-fade-in ${STYLES[variant]}${className ? ` ${className}` : ""}`}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="min-w-0 flex-1 leading-6">{children}</div>
    </div>
  );
}
