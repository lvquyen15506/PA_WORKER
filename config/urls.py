"""Bộ định tuyến gốc. Không có /admin/ (trang admin Django không bật)."""

from django.urls import include, path

urlpatterns = [
    path("", include("apps.accounts.urls")),
    path("", include("apps.core.urls")),
]
