"""API views, re-exported so urls.py has a single import surface."""
from kyc.views.analytics import AnalyticsView  # noqa: F401
from kyc.views.applications import (  # noqa: F401
    DocumentDownloadView,
    KYCApplicationViewSet,
)
from kyc.views.auth import (  # noqa: F401
    CookieTokenObtainPairView,
    CookieTokenRefreshView,
    GoogleAuthView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterView,
    ResendVerificationView,
    VerifyEmailView,
)
from kyc.views.review import ReviewQueueView  # noqa: F401
from kyc.views.users import MeView, UserManagementViewSet  # noqa: F401
