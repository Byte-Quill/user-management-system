import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router";

import { PageLoader, Protected, RoleOnly } from "@/app/guards";
import Layout from "@/components/layout/Layout";
import { AuthProvider, useAuth } from "@/features/auth/hooks/useAuth";


const ApplicationDetailPage = lazy(() => import("@/features/applications/pages/ApplicationDetailPage"));
const ApplicationFormPage = lazy(() => import("@/features/applications/pages/ApplicationFormPage"));
const DashboardPage = lazy(() => import("@/features/dashboard/pages/DashboardPage"));
const ForgotPasswordPage = lazy(() => import("@/features/auth/pages/ForgotPasswordPage"));
const LoginPage = lazy(() => import("@/features/auth/pages/LoginPage"));
const RegisterPage = lazy(() => import("@/features/auth/pages/RegisterPage"));
const ReviewDetailPage = lazy(() => import("@/features/review/pages/ReviewDetailPage"));
const ReviewQueuePage = lazy(() => import("@/features/review/pages/ReviewQueuePage"));
const VerifyEmailPage = lazy(() => import("@/features/auth/pages/VerifyEmailPage"));
const UsersPage = lazy(() => import("@/features/users/pages/UsersPage"));
const AnalyticsPage = lazy(() => import("@/features/analytics/pages/AnalyticsPage"));

function HomeRoute() {
  const { user } = useAuth();
  return user?.role === "ceo" ? <Navigate to="/analytics" replace /> : <DashboardPage />;
}

export default function AppRoutes() {
  return (
    <AuthProvider>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/verify-email" element={<VerifyEmailPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route
            element={
              <Protected>
                <Layout />
              </Protected>
            }
          >
            <Route path="/" element={<HomeRoute />} />
            <Route path="/applications/new" element={<ApplicationFormPage />} />
            <Route path="/applications/:id/edit" element={<ApplicationFormPage />} />
            <Route path="/applications/:id" element={<ApplicationDetailPage />} />
            <Route
              path="/review"
              element={
                <RoleOnly roles={["admin", "super_admin"]}>
                  <ReviewQueuePage />
                </RoleOnly>
              }
            />
            <Route
              path="/review/:id"
              element={
                <RoleOnly roles={["admin", "super_admin"]}>
                  <ReviewDetailPage />
                </RoleOnly>
              }
            />
            <Route path="/users" element={<RoleOnly roles={["super_admin"]}><UsersPage /></RoleOnly>} />
            <Route path="/analytics" element={<RoleOnly roles={["ceo"]}><AnalyticsPage /></RoleOnly>} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </AuthProvider>
  );
}
