from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from kyc.common import health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", health.healthz, name="healthz"),
    path("readyz", health.readyz, name="readyz"),
    path("api/", include("kyc.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
