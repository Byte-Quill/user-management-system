import { Navigate } from "react-router";
import type { ReactNode } from "react";

import { useAuth } from "@/features/auth/hooks/useAuth";

export function PageLoader() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 p-16" role="status">
      <span
        aria-hidden="true"
        className="h-6 w-6 animate-spin rounded-full border-2 border-ink-200 border-t-brand-600"
      />
      <span className="text-sm font-medium text-ink-500">Loading…</span>
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
