import { Navigate } from "react-router";
import type { ReactNode } from "react";

import { useAuth } from "@/features/auth/hooks/useAuth";

export function PageLoader() {
  return <p className="p-8 text-center text-slate-500">Loading…</p>;
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
