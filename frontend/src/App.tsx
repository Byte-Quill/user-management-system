import { GoogleOAuthProvider } from "@react-oauth/google";
import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router";

import { AuthProvider, useAuth } from "./auth";
import Layout from "./components/Layout";

// Google OAuth client ID (from Google Cloud Console). Empty when Google
// Sign-In is not configured; the provider and button are then skipped.
export const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? "";

// Route-level code splitting: pages load on demand instead of one big bundle.
const ApplicationDetailPage = lazy(() => import("./pages/ApplicationDetailPage"));
const ApplicationFormPage = lazy(() => import("./pages/ApplicationFormPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const ForgotPasswordPage = lazy(() => import("./pages/ForgotPasswordPage"));
const LoginPage = lazy(() => import("./pages/LoginPage"));
const RegisterPage = lazy(() => import("./pages/RegisterPage"));
const ReviewDetailPage = lazy(() => import("./pages/ReviewDetailPage"));
const ReviewQueuePage = lazy(() => import("./pages/ReviewQueuePage"));
const VerifyEmailPage = lazy(() => import("./pages/VerifyEmailPage"));

function PageLoader() {
  return <p className="p-8 text-center text-slate-500">Loading…</p>;
}

function Protected({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <PageLoader />;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function ReviewerOnly({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  if (!user || (user.role !== "reviewer" && user.role !== "admin")) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  const app = (
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
          <Route path="/" element={<DashboardPage />} />
          <Route path="/applications/new" element={<ApplicationFormPage />} />
          <Route path="/applications/:id" element={<ApplicationDetailPage />} />
          <Route
            path="/review"
            element={
              <ReviewerOnly>
                <ReviewQueuePage />
              </ReviewerOnly>
            }
          />
          <Route
            path="/review/:id"
            element={
              <ReviewerOnly>
                <ReviewDetailPage />
              </ReviewerOnly>
            }
          />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </AuthProvider>
  );

  // Only mount the Google provider when a client ID is configured; otherwise
  // GoogleOAuthProvider would throw on an empty clientId.
  if (!GOOGLE_CLIENT_ID) {
    return app;
  }
  return <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>{app}</GoogleOAuthProvider>;
}
