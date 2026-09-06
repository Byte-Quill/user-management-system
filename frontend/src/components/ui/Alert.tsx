import { IconAlert, IconCheck, IconInfo } from "./icons";

type Variant = "error" | "success" | "info" | "warning";

const STYLES: Record<Variant, string> = {
  error: "border-red-200 bg-red-50 text-red-700",
  success: "border-emerald-200 bg-emerald-50 text-emerald-700",
  info: "border-blue-200 bg-blue-50 text-blue-700",
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
      className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-sm ${STYLES[variant]} ${className}`.trim()}
    >
      <Icon className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="min-w-0">{children}</div>
    </div>
  );
}
