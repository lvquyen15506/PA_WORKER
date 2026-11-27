"""Trang Cài đặt (chỉ Admin): Danh mục, Sinh mã, Ngưỡng và thời hạn (Phase 6), OCR và QR
(Phase 5). Chờ hủy và Biên bản hủy thêm ở Phase 7."""

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.permissions import role_required
from apps.core.choices import CodeType, RoleCode

from . import badges, settings_services
from .catalogs import BY_SLUG, CATALOGS, catalog_form_class
from .codes import preview_code
from .forms_settings import CodeRulesForm, OcrQrForm, ThresholdsForm, load_qr_formats
from .models import SystemSetting

admin_only = role_required(RoleCode.ADMIN)

# Danh sách tab khai báo một chỗ: (mã, nhãn, URL). Chờ hủy và Biên bản hủy: view ở
# apps/workers/views_retention.py (Phase 7).
SETTINGS_TABS = [
    ("danh-muc", "Danh mục", "/cai-dat/danh-muc/"),
    ("sinh-ma", "Sinh mã", "/cai-dat/sinh-ma/"),
    ("nguong", "Ngưỡng và thời hạn", "/cai-dat/nguong/"),
    ("ocr-qr", "OCR và QR", "/cai-dat/ocr-qr/"),
    ("cho-huy", "Chờ hủy", "/cai-dat/cho-huy/"),
    ("bien-ban-huy", "Biên bản hủy", "/cai-dat/bien-ban-huy/"),
]
CRUMBS = [("Cài đặt", None)]
PAGE_SIZE = 20


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


# --- Danh mục ---------------------------------------------------------------------------------
class CatalogPickForm(forms.Form):
    """Ô chọn loại danh mục trong thanh lọc (GET)."""

    loai = forms.ChoiceField(
        label="Loại danh mục", choices=[(c.slug, c.title) for c in CATALOGS], required=False
    )


def _catalog_or_404(slug):
    catalog = BY_SLUG.get(slug)
    if catalog is None:
        raise Http404
    return catalog


def _catalog_crumbs(catalog, *extra):
    return [("Cài đặt", "/cai-dat/"), (catalog.title, f"/cai-dat/danh-muc/{catalog.slug}/")] + list(
        extra
    )


@admin_only
def catalog_home(request):
    return redirect(f"/cai-dat/danh-muc/{CATALOGS[0].slug}/")


CLIENT_COMPANY_SLUG = "cong-ty-khach"


@role_required(RoleCode.ADMIN, RoleCode.HR_MANAGER)
def catalog_list(request, loai):
    catalog = _catalog_or_404(loai)
    # v1.1.1: Quản lý nhân sự chỉ xem danh mục công ty khách (mục "Công ty khách" ở sidebar);
    # các danh mục khác và mọi thao tác thêm/sửa/ngừng vẫn chỉ Admin.
    can_edit = request.user.role.code == RoleCode.ADMIN
    if not can_edit:
        if catalog.slug != CLIENT_COMPANY_SLUG:
            raise PermissionDenied
        return _catalog_readonly(request, catalog)
    picked = request.GET.get("loai")
    if picked and picked != catalog.slug and picked in BY_SLUG:
        return redirect(f"/cai-dat/danh-muc/{picked}/")
    base = f"/cai-dat/danh-muc/{catalog.slug}"
    queryset = catalog.model.objects.all()
    page = Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("trang"))
    columns = [{"key": key, "label": label, "kind": "text"} for key, label, _ in catalog.columns]
    columns += [
        {"key": "status", "label": "Trạng thái", "kind": "badge"},
        {"key": "actions", "label": "Thao tác", "kind": "actions"},
    ]
    rows = []
    for obj in page:
        row = {key: getter(obj) for key, _, getter in catalog.columns}
        row["status"] = badges.CATALOG_ACTIVE if obj.is_active else badges.CATALOG_STOPPED
        if obj.is_active:
            toggle = {
                "label": "Ngừng sử dụng",
                "post_url": f"{base}/{obj.pk}/ngung/",
                "title": "Ngừng sử dụng",
                "message": f"Ngừng sử dụng {catalog.noun} “{obj}”? Mục này không hiện khi tạo "
                "mới nhưng vẫn giữ ở dữ liệu cũ.",
                "danger": True,
            }
        else:
            toggle = {
                "label": "Dùng lại",
                "post_url": f"{base}/{obj.pk}/dung-lai/",
                "title": "Dùng lại",
                "message": f"Dùng lại {catalog.noun} “{obj}”?",
            }
        row["actions"] = [
            {"kind": "link", "icon": "bi-pencil", "tooltip": "Sửa", "url": f"{base}/{obj.pk}/sua/"},
            {"kind": "menu", "label": "Thêm", "items": [toggle]},
        ]
        rows.append(row)
    context = {
        "catalog": catalog,
        "tabs": settings_tabs("danh-muc"),
        "crumbs": CRUMBS,
        "pick_form": CatalogPickForm(initial={"loai": catalog.slug}),
        "columns": columns,
        "rows": rows,
        "page": page,
        "header_actions": [
            {"label": f"Thêm {catalog.noun}", "kind": "primary", "url": f"{base}/them/"}
        ],
    }
    return render(request, "core/settings_catalog.html", context)


def _catalog_readonly(request, catalog):
    """Danh sách chỉ xem (Q): không tab Cài đặt, không nút thêm/sửa/ngừng."""
    page = Paginator(catalog.model.objects.all(), PAGE_SIZE).get_page(request.GET.get("trang"))
    columns = [{"key": key, "label": label, "kind": "text"} for key, label, _ in catalog.columns]
    columns.append({"key": "status", "label": "Trạng thái", "kind": "badge"})
    rows = []
    for obj in page:
        row = {key: getter(obj) for key, _, getter in catalog.columns}
        row["status"] = badges.CATALOG_ACTIVE if obj.is_active else badges.CATALOG_STOPPED
        rows.append(row)
    context = {
        "catalog": catalog,
        "crumbs": [(catalog.title, None)],
        "columns": columns,
        "rows": rows,
        "page": page,
        "readonly": True,
    }
    return render(request, "core/settings_catalog.html", context)


def _catalog_form_view(request, catalog, instance=None):
    form_class = catalog_form_class(catalog)
    form = form_class(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        obj, similar = settings_services.save_catalog(request.user, form, request=request)
        verb = "Đã thêm" if instance is None else "Đã lưu"
        messages.success(request, f"{verb} {catalog.noun} “{obj}”.")
        for other in similar:  # câu 48: chỉ cảnh báo, không chặn lưu
            messages.warning(request, f"Có thể trùng với: {other}")
        return redirect(f"/cai-dat/danh-muc/{catalog.slug}/")
    title = f"Thêm {catalog.noun}" if instance is None else f"Sửa {catalog.noun}"
    context = {
        "form": form,
        "catalog": catalog,
        "page_title": title,
        "crumbs": _catalog_crumbs(catalog, (title, None)),
        "tabs": settings_tabs("danh-muc"),
        "cancel_url": f"/cai-dat/danh-muc/{catalog.slug}/",
        "system_code": getattr(instance, "system_code", None),
    }
    return render(request, "core/settings_catalog_form.html", context)


@admin_only
def catalog_add(request, loai):
    return _catalog_form_view(request, _catalog_or_404(loai))


@admin_only
def catalog_edit(request, loai, pk):
    catalog = _catalog_or_404(loai)
    return _catalog_form_view(request, catalog, get_object_or_404(catalog.model, pk=pk))


def _set_active(request, loai, pk, active):
    catalog = _catalog_or_404(loai)
    obj = get_object_or_404(catalog.model, pk=pk)
    try:
        settings_services.set_catalog_active(request.user, obj, active, request=request)
    except settings_services.CatalogError as exc:
        messages.error(request, str(exc))
    else:
        verb = "Đã dùng lại" if active else "Đã ngừng sử dụng"
        messages.success(request, f"{verb} {catalog.noun} “{obj}”.")
    return redirect(f"/cai-dat/danh-muc/{catalog.slug}/")


@admin_only
@require_POST
def catalog_stop(request, loai, pk):
    return _set_active(request, loai, pk, False)


@admin_only
@require_POST
def catalog_resume(request, loai, pk):
    return _set_active(request, loai, pk, True)


# --- Sinh mã ----------------------------------------------------------------------------------
def _code_examples(system):
    """Mã kế tiếp theo cấu hình đang lưu (không tăng bộ đếm)."""
    return [
        ("Mã hồ sơ kế tiếp", preview_code(CodeType.WORKER, system)),
        ("Mã nhân viên kế tiếp", preview_code(CodeType.EMPLOYEE, system)),
    ]


@admin_only
def settings_codes(request):
    system = SystemSetting.load()
    initial = {name: getattr(system, name) for name in settings_services.CODE_FIELDS}
    form = CodeRulesForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        if settings_services.save_code_rules(request.user, form.cleaned_data, request=request):
            messages.success(request, "Đã lưu quy tắc sinh mã. Mã đã cấp giữ nguyên.")
        else:
            messages.info(request, "Không có thay đổi nào để lưu.")
        return redirect("settings_codes")
    context = {
        "form": form,
        "tabs": settings_tabs("sinh-ma"),
        "crumbs": CRUMBS,
        "examples": _code_examples(system),
    }
    return render(request, "core/settings_codes.html", context)


# --- Ngưỡng và thời hạn ------------------------------------------------------------------------
@admin_only
def settings_thresholds(request):
    system = SystemSetting.load()
    initial = {name: getattr(system, name) for name in settings_services.THRESHOLD_FIELDS}
    form = ThresholdsForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        if settings_services.save_thresholds(request.user, form.cleaned_data, request=request):
            messages.success(request, "Đã lưu ngưỡng và thời hạn.")
        else:
            messages.info(request, "Không có thay đổi nào để lưu.")
        return redirect("settings_thresholds")
    context = {"form": form, "tabs": settings_tabs("nguong"), "crumbs": CRUMBS}
    return render(request, "core/settings_thresholds.html", context)
