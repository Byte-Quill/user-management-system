import { Navigate } from "react-router";
import type { ReactNode } from "react";

import { useAuth } from "@/features/auth/hooks/useAuth";

export function PageLoader() {
  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4 p-16" role="status">
      <span className="relative flex h-12 w-12 items-center justify-center">
        <span className="absolute inset-0 rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 opacity-90" aria-hidden="true" />
        <span className="absolute inset-0 animate-ping rounded-2xl bg-brand-400/40" aria-hidden="true" />
        <span className="relative text-sm font-bold text-white">LP</span>
      </span>
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
