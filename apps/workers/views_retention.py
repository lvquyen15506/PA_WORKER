"""Cài đặt (chỉ Admin): tab Chờ hủy và Biên bản hủy (trang.md 5.2; lam-ro-yeu-cau.md câu 2, 38).

- Chờ hủy: danh sách tính tự động (không phải trạng thái) của hồ sơ Lưu trữ đã quá hạn lưu trữ;
  Admin chọn nhiều hồ sơ rồi ẩn danh hóa qua hộp xác nhận. Máy chủ kiểm tra lại mọi hồ sơ được gửi
  lên nằm trong danh sách chờ hủy; chỉ cần một hồ sơ không hợp lệ thì không ẩn danh hồ sơ nào.
- Biên bản hủy: danh sách, xem và in (ghi PRINT). Không xuất Excel biên bản.
"""

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.audit.services import log
from apps.core import settings_views
from apps.core.choices import AnonymizationKind, AuditAction, RetentionBasis
from apps.core.settings_views import admin_only

from . import retention
from .models import AnonymizationRecord

PAGE_SIZE = 20
CRUMBS = settings_views.CRUMBS
WAITING_COLUMNS = [
    {"key": "pick", "label": "Chọn", "kind": "check", "name": "workers", "form": "form-huy"},
    {"key": "code", "label": "Mã hồ sơ", "kind": "link", "nowrap": True},
    {"key": "employee_code", "label": "Mã NV", "kind": "text", "nowrap": True},
    {"key": "archived", "label": "Lưu trữ từ", "kind": "date"},
    {"key": "basis", "label": "Căn cứ lưu trữ", "kind": "text"},
    {"key": "expires", "label": "Hết hạn lưu trữ", "kind": "date"},
    {"key": "status", "label": "Trạng thái", "kind": "badge"},
]
RECORD_COLUMNS = [
    {"key": "record_no", "label": "Số biên bản", "kind": "link", "nowrap": True},
    {"key": "at", "label": "Thời điểm", "kind": "datetime"},
    {"key": "kind", "label": "Loại", "kind": "text"},
    {"key": "request_ref", "label": "Số đơn", "kind": "text"},
    {"key": "count", "label": "Số hồ sơ", "kind": "num"},
    {"key": "by", "label": "Người duyệt", "kind": "text"},
]
ITEM_COLUMNS = [
    {"key": "worker_code", "label": "Mã hồ sơ", "kind": "text", "nowrap": True},
    {"key": "employee_code", "label": "Mã NV", "kind": "text", "nowrap": True},
    {"key": "basis", "label": "Căn cứ lưu trữ", "kind": "text"},
    {"key": "expired_on", "label": "Hết hạn lưu trữ", "kind": "date"},
]
MSG_NOT_WAITING = (
    "Có hồ sơ không còn trong danh sách chờ hủy (chưa hết hạn lưu trữ hoặc đã ẩn danh hóa). "
    "Không ẩn danh hóa hồ sơ nào."
)


# --- Chờ hủy -----------------------------------------------------------------------------------
@admin_only
@require_GET
def waiting_list(request):
    entries = retention.expired_entries()
    page = Paginator(entries, PAGE_SIZE).get_page(request.GET.get("trang"))
    rows = [
        {
            "pick": worker.pk,
            "code": {"text": worker.worker_code, "url": f"/ho-so/{worker.pk}/"},
            "employee_code": worker.employee_code,
            "archived": retention.archived_on(worker),
            "basis": RetentionBasis(info.basis).label,
            "expires": info.expires_on,
            "status": worker.verification_status,
        }
        for worker, info in page
    ]
    return render(
        request,
        "workers/settings_waiting.html",
        {
            "tabs": settings_views.settings_tabs("cho-huy"),
            "crumbs": CRUMBS,
            "columns": WAITING_COLUMNS,
            "rows": rows,
            "page": page,
            "total": len(entries),
        },
    )


@admin_only
@require_POST
def waiting_destroy(request):
    try:
        ids = {int(value) for value in request.POST.getlist("workers")}
    except ValueError:
        ids = set()
    if not ids:
        messages.error(request, "Chưa chọn hồ sơ nào để hủy.")
        return redirect("settings_waiting")
    waiting = {w.pk: w for w, _ in retention.expired_entries()}
    if not ids <= set(waiting):  # kiểm tra lại ở máy chủ: không tin danh sách gửi lên
        messages.error(request, MSG_NOT_WAITING)
        return redirect("settings_waiting")
    try:
        record = retention.anonymize(
            [waiting[pk] for pk in sorted(ids)],
            AnonymizationKind.EXPIRED,
            request.user,
            request=request,
        )
    except retention.RetentionError as exc:
        messages.error(request, exc.message)
        return redirect("settings_waiting")
    messages.success(
        request, f"Đã ẩn danh hóa {record.worker_count} hồ sơ. Biên bản {record.record_no}."
    )
    return redirect("settings_record", pk=record.pk)


# --- Biên bản hủy ------------------------------------------------------------------------------
def _record_url(record):
    return f"/cai-dat/bien-ban-huy/{record.pk}/"


@admin_only
@require_GET
def record_list(request):
    records = AnonymizationRecord.objects.select_related("performed_by").order_by("-id")
    page = Paginator(records, PAGE_SIZE).get_page(request.GET.get("trang"))
    rows = [
        {
            "record_no": {"text": record.record_no, "url": _record_url(record)},
            "at": record.performed_at,
            "kind": AnonymizationKind(record.kind).label,
            "request_ref": record.request_ref or None,
            "count": record.worker_count,
            "by": record.performed_by.full_name or record.performed_by.username,
        }
        for record in page
    ]
    return render(
        request,
        "workers/settings_records.html",
        {
            "tabs": settings_views.settings_tabs("bien-ban-huy"),
            "crumbs": CRUMBS,
            "columns": RECORD_COLUMNS,
            "rows": rows,
            "page": page,
        },
    )


def _record_context(record):
    items = list(record.items.order_by("worker_code"))
    subject = record.kind == AnonymizationKind.SUBJECT_REQUEST
    info = [
        ("Số biên bản", record.record_no),
        ("Loại", AnonymizationKind(record.kind).label),
        ("Người duyệt", record.performed_by.full_name or record.performed_by.username),
        ("Thời điểm", timezone.localtime(record.performed_at).strftime("%d/%m/%Y %H:%M")),
        ("Số hồ sơ", record.worker_count),
    ]
    if subject:
        info.append(("Số đơn yêu cầu", record.request_ref))
        info.append(("Lý do", record.note))
    rows = [
        {
            "worker_code": item.worker_code,
            "employee_code": item.employee_code or None,
            "basis": RetentionBasis(item.retention_basis).label,
            "expired_on": item.retention_expired_on,
        }
        for item in items
    ]
    notes = (
        [
            f"Xóa sớm theo yêu cầu – lẽ ra lưu đến {item.retention_expired_on:%d/%m/%Y} "
            f"(hồ sơ {item.worker_code})."
            for item in items
        ]
        if subject
        else []
    )
    return {"record": record, "info": info, "columns": ITEM_COLUMNS, "rows": rows, "notes": notes}


@admin_only
@require_GET
def record_detail(request, pk):
    record = get_object_or_404(AnonymizationRecord.objects.select_related("performed_by"), pk=pk)
    context = _record_context(record)
    context.update(
        {
            "tabs": settings_views.settings_tabs("bien-ban-huy"),
            "crumbs": CRUMBS,
            "print_url": f"{_record_url(record)}in/",
        }
    )
    return render(request, "workers/settings_record.html", context)


@admin_only
@require_GET
def record_print(request, pk):
    record = get_object_or_404(AnonymizationRecord.objects.select_related("performed_by"), pk=pk)
    log(AuditAction.PRINT, user=request.user, obj=record, note="In biên bản hủy", request=request)
    return render(request, "workers/settings_record_print.html", _record_context(record))
