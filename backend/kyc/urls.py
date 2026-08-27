from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .auth_views import (
    CookieTokenObtainPairView,
    CookieTokenRefreshView,
    GoogleAuthView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    ResendVerificationView,
    VerifyEmailView,
)
from .views import (
    AnalyticsView,
    DocumentDownloadView,
    KYCApplicationViewSet,
    MeView,
    RegisterView,
    ReviewQueueView,
    UserManagementViewSet,
)

router = DefaultRouter()
router.register("applications", KYCApplicationViewSet, basename="application")
router.register("users", UserManagementViewSet, basename="user-management")

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/google/", GoogleAuthView.as_view(), name="google_auth"),
    path("auth/token/", CookieTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", CookieTokenRefreshView.as_view(), name="token_refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("auth/verify-email/", VerifyEmailView.as_view(), name="verify_email"),
    path(
        "auth/verify-email/resend/",
        ResendVerificationView.as_view(),
        name="verify_email_resend",
    ),
    path(
        "auth/password-reset/request/",
        PasswordResetRequestView.as_view(),
        name="password_reset_request",
    ),
    path(
        "auth/password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path("review-queue/", ReviewQueueView.as_view(), name="review_queue"),
    path("analytics/", AnalyticsView.as_view(), name="analytics"),
    path(
        "documents/<uuid:doc_id>/download/",
        DocumentDownloadView.as_view(),
        name="document_download",
    ),
    path("", include(router.urls)),
]
