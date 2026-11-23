"""Nhật ký thao tác `/nhat-ky/` và chi tiết `/nhat-ky/<id>/` (trang.md 5.9; câu 11, 30).

Chỉ Admin và Quản lý nhân sự. Không có thao tác sửa/xóa. Trường cá nhân chỉ hiện "(xem giá trị
chi tiết)" ở danh sách; trang chi tiết giải mã giá trị trước/sau từ `AuditPersonalValue`, số
định danh và CMND cũ vẫn che, hồ sơ đã ẩn danh hiện "(đã ẩn danh)". Xem nhật ký không ghi nhật ký.
"""

import datetime

from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.accounts.permissions import role_required
from apps.workers.rules import MANAGERS

from . import presenters
from .forms import SYSTEM, AuditFilterForm
from .models import AuditLog

PAGE_SIZE = 20
LIST_COLUMNS = [
    {"key": "at", "label": "Thời điểm", "kind": "datetime"},
    {"key": "who", "label": "Người thực hiện", "kind": "text"},
    {"key": "action", "label": "Hành động", "kind": "text", "nowrap": True},
    {"key": "target", "label": "Đối tượng", "kind": "text"},
    {"key": "fields", "label": "Trường thay đổi", "kind": "text"},
    {"key": "actions", "label": "Thao tác", "kind": "actions"},
]
CHANGE_COLUMNS = [
    {"key": "field", "label": "Trường", "kind": "text"},
    {"key": "old", "label": "Giá trị trước", "kind": "text"},
    {"key": "new", "label": "Giá trị sau", "kind": "text"},
]
MAX_FIELDS_SHOWN = 120  # số ký tự tối đa của cột "Trường thay đổi"


def _day_start(day):
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time.min))


def filtered(form):
    """Queryset nhật ký theo bộ lọc đã kiểm tra (mới nhất trước)."""
    qs = AuditLog.objects.select_related("user", "worker")
    data = form.cleaned_data
    who = data.get("nguoi")
    if who == SYSTEM:
        qs = qs.filter(user__isnull=True)
    elif who:
        qs = qs.filter(user_id=who)
    code = (data.get("ho_so") or "").strip()
    if code:
        qs = qs.filter(Q(worker__worker_code__iexact=code) | Q(worker__employee_code__iexact=code))
    if data.get("hanh_dong"):
        qs = qs.filter(action=data["hanh_dong"])
    if data.get("tu_ngay"):
        qs = qs.filter(created_at__gte=_day_start(data["tu_ngay"]))
    if data.get("den_ngay"):
        qs = qs.filter(created_at__lt=_day_start(data["den_ngay"] + datetime.timedelta(days=1)))
    return qs.order_by("-created_at", "-id")


def _who(entry):
    return entry.user.full_name if entry.user else entry.actor_label


def _target(entry):
    return entry.object_repr or entry.object_type


def _fields_text(entry):
    text = ", ".join(presenters.field_labels(entry))
    if len(text) > MAX_FIELDS_SHOWN:
        text = text[: MAX_FIELDS_SHOWN - 1].rstrip() + "…"
    return text or None


@role_required(*MANAGERS)
@require_GET
def audit_list(request):
    form = AuditFilterForm(request.GET)
    form.is_valid()
    page = Paginator(filtered(form), PAGE_SIZE).get_page(request.GET.get("trang"))
    rows = [
        {
            "at": entry.created_at,
            "who": _who(entry),
            "action": entry.get_action_display(),
            "target": _target(entry),
            "fields": _fields_text(entry),
            "actions": [
                {
                    "kind": "link",
                    "icon": "bi-eye",
                    "tooltip": "Xem chi tiết",
                    "url": f"/nhat-ky/{entry.pk}/",
                }
            ],
        }
        for entry in page
    ]
    query = request.GET.copy()
    query.pop("trang", None)
    return render(
        request,
        "audit/list.html",
        {
            "form": form,
            "columns": LIST_COLUMNS,
            "rows": rows,
            "page": page,
            "query": query.urlencode(),
        },
    )


@role_required(*MANAGERS)
@require_GET
def audit_detail(request, pk):
    entry = get_object_or_404(
        AuditLog.objects.select_related("user", "worker").prefetch_related("personal_values"),
        pk=pk,
    )
    worker = entry.worker
    items = [
        ("Thời điểm", timezone.localtime(entry.created_at).strftime("%d/%m/%Y %H:%M:%S")),
        ("Người thực hiện", _who(entry)),
        ("Hành động", entry.get_action_display()),
        ("Đối tượng", _target(entry)),
        ("Mã hồ sơ", worker.worker_code if worker else None),
        ("Mã nhân viên", worker.employee_code if worker else None),
        ("Địa chỉ IP", entry.ip_address),
        ("Ghi chú", entry.note or None),
    ]
    return render(
        request,
        "audit/detail.html",
        {
            "entry": entry,
            "items": items,
            "columns": CHANGE_COLUMNS,
            "rows": presenters.change_rows(entry),
            "anonymized": bool(worker and worker.anonymized_at),
            "crumbs": [("Nhật ký thao tác", "/nhat-ky/"), (f"Dòng {entry.pk}", None)],
        },
    )
