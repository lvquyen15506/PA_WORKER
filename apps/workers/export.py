"""Xuất Excel danh sách hồ sơ đang lọc (kịch bản 13; yeu-cau.md IV.8; trang.md 5.4).

- Dùng đúng `WorkerFilterForm` + `build_queryset` của `/ho-so/` (cùng tham số, cùng thứ tự sắp xếp),
  nên số dòng và nội dung khớp màn hình.
- Số CCCD luôn che (`0791••••2345`). Admin và Quản lý nhân sự có thêm lựa chọn "Xuất kèm số CCCD đầy
  đủ" (POST có CSRF, hộp xác nhận); Nhân viên HR luôn nhận bản che, gửi yêu cầu số đầy đủ thì 403.
  Viewer không xuất được (câu 18). Không có cột lương.
- Mọi ô ghi qua `safe_cell`. Nhật ký `EXPORT` ghi số dòng và bộ lọc, không ghi chữ tìm kiếm (có
  thể là họ tên hoặc số CCCD) và không ghi họ tên.
"""

from django.core.exceptions import PermissionDenied
from django.http import QueryDict
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.accounts.permissions import role_required
from apps.audit.services import log
from apps.core import excel
from apps.core.choices import AuditAction, Gender, VerificationStatus, WorkStatus
from apps.core.text import mask_id_number
from apps.employment.assignments import current_q
from apps.employment.models import WorkAssignment

from .listing import WorkerFilterForm, build_queryset
from .rules import ALL_STAFF, MANAGERS, role_code

STAFF = tuple(ALL_STAFF)
HEADERS = [
    "STT",
    "Mã NV",
    "Họ và tên",
    "Ngày sinh",
    "Giới tính",
    "SĐT",
    "Công ty khách",
    "Chức danh",
    "Ngày vào làm",
    "Trạng thái hồ sơ",
    "Trạng thái làm việc",
    "Mã hồ sơ",
    "Số CCCD",
]
# Tham số không đưa vào nhật ký: chữ tìm kiếm (có thể là họ tên/số CCCD), sắp xếp, trang.
NOT_LOGGED = {"q", "sap_xep", "trang"}


def _label(choices, value):
    return choices(value).label if value else None


def _clients(queryset):
    """{worker_id: "tên – địa điểm"} của đợt đang diễn ra, một truy vấn cho cả danh sách."""
    assignments = (
        WorkAssignment.objects.filter(
            current_q(timezone.localdate()), worker_id__in=queryset.order_by().values("pk")
        )
        .select_related("client_company")
        .order_by("start_date", "id")
    )
    return {a.worker_id: str(a.client_company) for a in assignments}


def build_rows(queryset, *, full_id=False):
    """Các dòng của file (cùng thứ tự với màn hình), STT từ 1."""
    clients = _clients(queryset)
    rows = []
    for number, worker in enumerate(
        queryset.select_related("employment__position", "identity").iterator(chunk_size=500),
        start=1,
    ):
        employment = getattr(worker, "employment", None)
        identity = getattr(worker, "identity", None)
        id_number = identity.id_number_enc if identity else ""
        rows.append(
            [
                number,
                worker.employee_code,
                worker.full_name,
                worker.date_of_birth,
                _label(Gender, worker.gender),
                worker.phone,
                clients.get(worker.pk),
                employment.position.name if employment else None,
                employment.start_date if employment else None,
                _label(VerificationStatus, worker.verification_status),
                _label(WorkStatus, employment.work_status) if employment else None,
                worker.worker_code,
                (id_number if full_id else mask_id_number(id_number)) or None,
            ]
        )
    return rows


def _filter_note(form, params):
    """Mô tả bộ lọc cho nhật ký: tên tham số=giá trị; chữ tìm kiếm chỉ ghi "có tìm kiếm"."""
    parts = [
        f"{name}={str(params.get(name))[:40]}"
        for name in form.fields
        if name not in NOT_LOGGED and params.get(name)
    ]
    if params.get("q"):
        parts.append("có tìm kiếm")
    return ", ".join(parts) or "không lọc"


@role_required(*STAFF)
@require_http_methods(["GET", "POST"])
def export_workers(request):
    full_id = request.method == "POST" and request.POST.get("cccd_day_du") == "1"
    if full_id and role_code(request.user) not in MANAGERS:
        raise PermissionDenied  # HR không được nhận số CCCD đầy đủ trong file xuất
    params = QueryDict(request.GET.urlencode())  # bộ lọc luôn nằm trên URL, kể cả khi POST
    form = WorkerFilterForm(params)
    form.is_valid()
    queryset = build_queryset(request.user, dict(form.cleaned_data))
    rows = build_rows(queryset, full_id=full_id)

    book = excel.new_workbook("Danh sách hồ sơ")
    excel.write_rows(book.active, HEADERS, rows)
    note = f"{len(rows)} dòng; {_filter_note(form, params)}"
    if full_id:
        note += "; có số CCCD đầy đủ"
    log(
        AuditAction.EXPORT,
        user=request.user,
        object_type="worker_list",
        object_id="danh-sach",
        object_repr="Danh sách hồ sơ",
        note=note,
        request=request,
    )
    stamp = timezone.localdate().strftime("%Y%m%d")
    return excel.xlsx_response(book, f"Danh-sach-ho-so-{stamp}.xlsx")
