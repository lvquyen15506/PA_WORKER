"""Trang Cài đặt (chỉ Admin). Phase 5 làm khung và tab OCR và QR; các tab khác thêm ở phase sau."""

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render

from apps.accounts.permissions import role_required
from apps.core.choices import RoleCode

from . import settings_services
from .forms_settings import OcrQrForm, load_qr_formats
from .models import SystemSetting

admin_only = role_required(RoleCode.ADMIN)

# Danh sách tab khai báo một chỗ: (mã, nhãn, URL). Phase 6, 7 thêm tab vào đây.
SETTINGS_TABS = [("ocr-qr", "OCR và QR", "/cai-dat/ocr-qr/")]
CRUMBS = [("Cài đặt", None)]


def settings_tabs(active):
    return [
        {"label": label, "url": url, "active": code == active} for code, label, url in SETTINGS_TABS
    ]


@admin_only
def settings_home(request):
    return redirect(SETTINGS_TABS[0][2])


@admin_only
def settings_ocr_qr(request):
    system = SystemSetting.load()
    qr_formats = load_qr_formats()
    form = OcrQrForm(request.POST or None, system_setting=system, qr_formats=qr_formats)
    if request.method == "POST" and form.is_valid():
        changed = settings_services.save_ocr_qr(request.user, form, request=request)
        if changed:
            messages.success(request, "Đã lưu cài đặt OCR và QR.")
        else:
            messages.info(request, "Không có thay đổi nào để lưu.")
        return redirect("settings_ocr_qr")
    enabled = form["external_ocr_enabled"].value() if form.is_bound else system.external_ocr_enabled
    context = {
        "form": form,
        "tabs": settings_tabs("ocr-qr"),
        "system": system,
        "external_enabled": bool(enabled),
        "api_key_set": bool(settings.EXTERNAL_OCR_API_KEY),
        "crumbs": CRUMBS,
    }
    return render(request, "core/settings_ocr_qr.html", context)
