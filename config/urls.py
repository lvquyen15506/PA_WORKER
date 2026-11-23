"""Bộ định tuyến gốc. Không có /admin/ (trang admin Django không bật)."""

from django.urls import include, path

urlpatterns = [
    path("", include("apps.accounts.urls")),
    path("", include("apps.core.urls")),
    path("", include("apps.workers.urls")),
    path("", include("apps.documents.urls")),
    path("", include("apps.intake.urls")),
    path("", include("apps.recruitment.urls")),
    path("", include("apps.employment.urls")),
]
