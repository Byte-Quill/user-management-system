import { Navigate } from "react-router";
import type { ReactNode } from "react";

import { useAuth } from "@/features/auth/hooks/useAuth";
import { IconSpinner } from "@/components/ui/icons";

export function PageLoader() {
  return (
    <div className="flex items-center justify-center gap-2 p-16 text-slate-500" role="status">
      <IconSpinner className="h-5 w-5" />
      <span className="text-sm">Loading…</span>
    </div>
  );
}

export function Protected({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <PageLoader />;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export function RoleOnly({ roles, children }: { roles: string[]; children: ReactNode }) {
  const { user } = useAuth();
  if (!user || !roles.includes(user.role)) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}
