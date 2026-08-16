from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .auth_views import (
    CookieTokenObtainPairView,
    CookieTokenRefreshView,
    LogoutView,
)
from .views import (
    DocumentDownloadView,
    KYCApplicationViewSet,
    MeView,
    RegisterView,
    ReviewQueueView,
)

router = DefaultRouter()
router.register("applications", KYCApplicationViewSet, basename="application")

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/token/", CookieTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", CookieTokenRefreshView.as_view(), name="token_refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("review-queue/", ReviewQueueView.as_view(), name="review_queue"),
    path(
        "documents/<uuid:doc_id>/download/",
        DocumentDownloadView.as_view(),
        name="document_download",
    ),
    path("", include(router.urls)),
]
