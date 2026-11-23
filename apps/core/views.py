"""Trang chung: giới thiệu, bộ giao diện mẫu /ui-kit/ (trang chủ là Dashboard ở apps.reports)."""

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.accounts.permissions import role_required

from . import ui_kit
from .choices import RoleCode


@login_required
def about(request):
    items = [
        ("Tên phần mềm", "PA Worker – quản lý hồ sơ công nhân"),
        ("Đơn vị phát triển", "QQIT"),
        ("Phiên bản", settings.APP_VERSION),
        ("Năm phát hành", "2026"),
    ]
    return render(request, "about.html", {"about_items": items})


@role_required(RoleCode.ADMIN)
def ui_kit_view(request):
    """Bản chuẩn của mọi component; chỉ Admin xem (Phase 3)."""
    return render(request, "core/ui_kit.html", ui_kit.build_context())
