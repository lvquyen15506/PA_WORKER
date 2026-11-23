"""Số liệu cho Dashboard và báo cáo (yeu-cau.md IV.2, IV.8; trang.md 5.3; lam-ro-yeu-cau.md
câu 14, 26, 45, 48). Một chỗ khai báo, Dashboard và /bao-cao/ dùng chung để số liệu luôn khớp.

- **Thẻ số liệu:** mỗi thẻ có bộ tham số lọc; con số = số dòng của đúng danh sách đích với đúng
  các tham số đó (cùng `build_queryset` / `filter_queryset`), nên "số dòng bằng số trên thẻ".
- **Cơ cấu** (phòng ban/bộ phận, giới tính, nhóm tuổi, trình độ, chức danh, hoàn thiện, công ty
  khách) tính **công nhân đang làm hiện tại** (Thử việc + Đang làm việc); khoảng ngày chỉ áp cho
  báo cáo theo tháng (quyết định Phase 7).
"""

import datetime
from collections import Counter
from urllib.parse import urlencode

from django.db.models import Count, OuterRef, Subquery
from django.utils import timezone

from apps.core import badges
from apps.core.choices import Gender, VerificationStatus, WorkStatus
from apps.core.dates import add_months
from apps.core.models import ClientCompany, EducationLevel, SystemSetting
from apps.core.validators import age_on
from apps.employment.assignments import current_q
from apps.employment.models import Employment, WorkAssignment
from apps.recruitment.forms import RecruitmentFilterForm
from apps.recruitment.models import Application, Education
from apps.workers import indicators
from apps.workers.listing import WORKING, WorkerFilterForm, build_queryset
from apps.workers.models import Worker

DATE = "%d/%m/%Y"
NO_SECTION = "Chưa có bộ phận"
NONE_LABEL = "Chưa có"
NO_BIRTH = "Chưa có ngày sinh"
WORKING_STATUSES = (WorkStatus.PROBATION, WorkStatus.ACTIVE)
AGE_GROUPS = [  # câu 26: 5 nhóm + "Chưa có ngày sinh" để tổng các nhóm luôn bằng tổng hồ sơ
    ("Dưới 18", lambda age: age < 18),
    ("18–25", lambda age: 18 <= age <= 25),
    ("26–35", lambda age: 26 <= age <= 35),
    ("36–45", lambda age: 36 <= age <= 45),
    ("Trên 45", lambda age: age > 45),
]
WORKER_LIST = "/ho-so/"
RECRUITMENT_LIST = "/tuyen-dung/"


def list_url(path, params):
    return path + ("?" + urlencode(params) if params else "")


# --- Thẻ số liệu --------------------------------------------------------------------------------
def month_bounds(today):
    first = today.replace(day=1)
    return first, add_months(first, 1) - datetime.timedelta(days=1)


def card_definitions(today=None):
    """[(mã, nhãn, dòng phụ, đường dẫn, tham số)] theo đúng bảng ở trang.md 5.3."""
    today = today or timezone.localdate()
    first, last = month_bounds(today)
    month = {"tao_tu": first.strftime(DATE), "tao_den": last.strftime(DATE)}
    return [
        (
            "total",
            "Tổng số hồ sơ",
            "Không tính Lưu trữ",
            WORKER_LIST,
            {"trang_thai_ho_so": "chua-luu-tru"},
        ),
        (
            "working",
            "Đang làm việc",
            "Thử việc và Đang làm việc",
            WORKER_LIST,
            {"trang_thai_lam_viec": WORKING},
        ),
        (
            "new_month",
            "Hồ sơ mới trong tháng",
            f"Tháng {today.month}/{today.year}",
            WORKER_LIST,
            month,
        ),
        (
            "pending",
            "Chờ duyệt",
            "Cần Quản lý nhân sự duyệt",
            WORKER_LIST,
            {"trang_thai_ho_so": "PENDING"},
        ),
        (
            "missing",
            "Thiếu giấy tờ",
            "Không tính hồ sơ Lưu trữ",
            WORKER_LIST,
            {"thieu_giay_to": "1", "trang_thai_ho_so": "chua-luu-tru"},
        ),
        ("complete", "Hoàn thiện", "Đã xác minh và đủ giấy tờ", WORKER_LIST, {"hoan_thien": "1"}),
        (
            "recruiting",
            "Đang tuyển dụng",
            "Mới nộp, Đang sàng lọc, Hẹn phỏng vấn",
            RECRUITMENT_LIST,
            {"trang_thai": "NEW,SCREENING,INTERVIEW"},
        ),
        (
            "resigned",
            "Nghỉ việc trong tháng",
            f"Tháng {today.month}/{today.year}",
            WORKER_LIST,
            {
                "trang_thai_lam_viec": "RESIGNED",
                "nghi_tu": first.strftime(DATE),
                "nghi_den": last.strftime(DATE),
            },
        ),
        (
            "contracts",
            "Hợp đồng sắp hết hạn",
            "Trong thời hạn cảnh báo",
            WORKER_LIST,
            {"hop_dong_sap_het_han": "1"},
        ),
    ]


def count_for(user, path, params):
    """Số dòng của danh sách đích với đúng các tham số (cùng bộ lọc với trang đích)."""
    if path == RECRUITMENT_LIST:
        form = RecruitmentFilterForm(params)
        form.is_valid()
        return form.filter_queryset(Application.objects.all()).count()
    form = WorkerFilterForm(params)
    form.is_valid()
    return build_queryset(user, dict(form.cleaned_data)).count()


def cards(user, today=None):
    return [
        {
            "code": code,
            "label": label,
            "sub": sub,
            "url": list_url(path, params),
            "value": count_for(user, path, params),
        }
        for code, label, sub, path, params in card_definitions(today)
    ]


# --- Tập công nhân đang làm ---------------------------------------------------------------------
def working_workers(department=None):
    """Công nhân đang làm (Thử việc + Đang làm việc). `department`: một Phòng ban, hoặc NO_SECTION
    để lấy người chưa có bộ phận."""
    qs = Worker.objects.filter(employment__work_status__in=WORKING_STATUSES)
    if department == NO_SECTION:
        qs = qs.filter(employment__section__isnull=True)
    elif department is not None:
        qs = qs.filter(employment__section__department=department)
    return qs


def _working_link(extra, department=None):
    params = {"trang_thai_lam_viec": WORKING, **extra}
    if department == NO_SECTION:
        params["bo_phan"] = "chua-co"
    elif department is not None:
        params["phong_ban"] = department.pk
    return list_url(WORKER_LIST, params)


def by_section(department=None):
    """[(phòng ban, bộ phận, số công nhân, liên kết)] có nhóm "Chưa có bộ phận" (câu 48)."""
    groups = (
        working_workers(department)
        .values(
            "employment__section",
            "employment__section__name",
            "employment__section__department",
            "employment__section__department__name",
            "employment__section__department__sort_order",
            "employment__section__sort_order",
        )
        .annotate(n=Count("pk"))
    )
    rows = []
    for g in groups:
        section_id = g["employment__section"]
        if section_id is None:
            rows.append(
                ("—", NO_SECTION, g["n"], _working_link({"bo_phan": "chua-co"}), (9999, 9999))
            )
        else:
            rows.append(
                (
                    g["employment__section__department__name"],
                    g["employment__section__name"],
                    g["n"],
                    _working_link({"bo_phan": section_id}),
                    (
                        g["employment__section__department__sort_order"],
                        g["employment__section__sort_order"],
                    ),
                )
            )
    rows.sort(key=lambda r: (r[4], r[0], r[1]))
    return [r[:4] for r in rows]


def by_department(department=None):
    """[(phòng ban, số công nhân, liên kết)]; chưa có bộ phận thì vào nhóm "Chưa có bộ phận"."""
    groups = (
        working_workers(department)
        .values(
            "employment__section__department",
            "employment__section__department__name",
            "employment__section__department__sort_order",
        )
        .annotate(n=Count("pk"))
    )
    rows = []
    for g in groups:
        dep_id = g["employment__section__department"]
        if dep_id is None:
            rows.append((NO_SECTION, g["n"], _working_link({"bo_phan": "chua-co"}), 9999))
        else:
            rows.append(
                (
                    g["employment__section__department__name"],
                    g["n"],
                    _working_link({"phong_ban": dep_id}),
                    g["employment__section__department__sort_order"],
                )
            )
    rows.sort(key=lambda r: (r[3], r[0]))
    return [r[:3] for r in rows]


def by_gender(department=None):
    counts = Counter(working_workers(department).values_list("gender", flat=True))
    rows = [(g.label, counts.get(g.value, 0)) for g in Gender]
    other = sum(n for key, n in counts.items() if key not in Gender.values)
    if other:
        rows.append((NONE_LABEL, other))
    return rows


def by_age_group(department=None, today=None):
    today = today or timezone.localdate()
    counts = Counter()
    for birth in working_workers(department).values_list("date_of_birth", flat=True):
        if birth is None:
            counts[NO_BIRTH] += 1
            continue
        age = age_on(birth, today)
        counts[next(label for label, test in AGE_GROUPS if test(age))] += 1
    return [(label, counts.get(label, 0)) for label, _ in AGE_GROUPS] + [
        (NO_BIRTH, counts.get(NO_BIRTH, 0))
    ]


def by_education(department=None):
    """Trình độ cao nhất của mỗi người (câu 14): [(trình độ, số công nhân, liên kết)]."""
    top = (
        Education.objects.filter(worker=OuterRef("pk"))
        .order_by("-education_level__rank")
        .values("education_level__rank")[:1]
    )
    counts = {
        row["top_rank"]: row["n"]
        for row in working_workers(department)
        .annotate(top_rank=Subquery(top))
        .values("top_rank")
        .annotate(n=Count("pk"))
    }
    rows = [
        (level.name, counts.get(level.rank, 0), _working_link({"trinh_do": level.pk}, department))
        for level in EducationLevel.objects.order_by("rank")
    ]
    if counts.get(None):
        rows.append((NONE_LABEL, counts[None], ""))
    return rows


def by_position(department=None):
    groups = (
        working_workers(department)
        .values("employment__position", "employment__position__name")
        .annotate(n=Count("pk"))
        .order_by("-n", "employment__position__name")
    )
    return [
        (
            g["employment__position__name"],
            g["n"],
            _working_link({"chuc_danh": g["employment__position"]}, department),
        )
        for g in groups
    ]


def completeness(department=None):
    """[(Hoàn thiện, n, liên kết), (Chưa hoàn thiện, n, "")] trong số công nhân đang làm."""
    workers = working_workers(department)
    total = workers.count()
    done = indicators.complete(workers).count()
    return [
        ("Hoàn thiện", done, _working_link({"hoan_thien": "1"}, department)),
        ("Chưa hoàn thiện", total - done, ""),
    ]


def by_client(department=None, today=None):
    """Công nhân đang làm theo công ty khách (câu 45): đếm công nhân có đợt đang diễn ra, mỗi dòng
    một công ty (tên + địa điểm); liên kết tới `/ho-so/?cong_ty_khach=<id>`."""
    today = today or timezone.localdate()
    assignments = WorkAssignment.objects.filter(current_q(today))
    if department == NO_SECTION:
        assignments = assignments.filter(worker__employment__section__isnull=True)
    elif department is not None:
        assignments = assignments.filter(worker__employment__section__department=department)
    counts = {
        row["client_company"]: row["n"]
        for row in assignments.values("client_company").annotate(n=Count("worker", distinct=True))
    }
    rows = []
    for company in ClientCompany.objects.order_by("name", "location"):
        if company.pk not in counts:
            continue
        params = {"cong_ty_khach": company.pk}
        if department == NO_SECTION:
            params["bo_phan"] = "chua-co"
        elif department is not None:
            params["phong_ban"] = department.pk
        rows.append(
            (company.name, company.location, counts[company.pk], list_url(WORKER_LIST, params))
        )
    return rows


def by_verification_status():
    """Hồ sơ theo trạng thái xác minh (mọi hồ sơ, kể cả Lưu trữ)."""
    counts = dict(
        Worker.objects.values_list("verification_status").annotate(n=Count("pk")).order_by()
    )
    return [(s.label, counts.get(s.value, 0)) for s in VerificationStatus]


# --- Theo tháng ---------------------------------------------------------------------------------
def months_between(start, end):
    """Danh sách (năm, tháng) từ tháng của `start` đến tháng của `end`."""
    year, month = start.year, start.month
    out = []
    while (year, month) <= (end.year, end.month):
        out.append((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return out


def last_12_months(today=None):
    today = today or timezone.localdate()
    return add_months(today.replace(day=1), -11), today


def _label(year_month):
    return f"{year_month[1]:02d}/{year_month[0]}"


def hires_and_exits(start, end):
    """[(tháng, vào làm, nghỉ việc)] theo ngày bắt đầu và ngày nghỉ việc (Đã nghỉ việc)."""
    first = start.replace(day=1)
    last = month_bounds(end)[1]
    hires = Counter(
        (d.year, d.month)
        for d in Employment.objects.filter(start_date__range=(first, last)).values_list(
            "start_date", flat=True
        )
    )
    exits = Counter(
        (d.year, d.month)
        for d in Employment.objects.filter(
            work_status=WorkStatus.RESIGNED, resign_date__range=(first, last)
        ).values_list("resign_date", flat=True)
    )
    return [(_label(m), hires.get(m, 0), exits.get(m, 0)) for m in months_between(start, end)]


def new_workers_by_month(start, end):
    """[(tháng, số hồ sơ mới)] theo ngày tạo hồ sơ (giờ Việt Nam)."""
    first = start.replace(day=1)
    last = month_bounds(end)[1]
    low = timezone.make_aware(datetime.datetime.combine(first, datetime.time.min))
    high = timezone.make_aware(
        datetime.datetime.combine(last + datetime.timedelta(days=1), datetime.time.min)
    )
    counts = Counter()
    for stamp in Worker.objects.filter(created_at__gte=low, created_at__lt=high).values_list(
        "created_at", flat=True
    ):
        local = timezone.localtime(stamp)
        counts[(local.year, local.month)] += 1
    return [(_label(m), counts.get(m, 0)) for m in months_between(start, end)]


# --- Việc cần làm -------------------------------------------------------------------------------
TODO_LIMIT = 10


def _last_change(to_status):
    from apps.workers.models import StatusChange

    return Subquery(
        StatusChange.objects.filter(worker=OuterRef("pk"), to_status=to_status)
        .order_by("-changed_at", "-id")
        .values("changed_at")[:1]
    )


def _worker_link(worker):
    return {"text": worker.worker_code, "url": f"/ho-so/{worker.pk}/"}


def todo_blocks(user, today=None):
    """Bốn khối việc cần làm: mỗi khối {title, count, rows, columns, url}; Chờ duyệt chỉ cho
    Admin, Quản lý nhân sự."""
    from apps.workers.rules import MANAGERS, role_code

    today = today or timezone.localdate()
    blocks = []

    def worker_block(code, title, status, date_label, url):
        qs = Worker.objects.filter(verification_status=status).annotate(since=_last_change(status))
        total = qs.count()
        rows = [
            {"code": _worker_link(w), "name": w.full_name, "since": w.since}
            for w in qs.order_by("since", "id")[:TODO_LIMIT]
        ]
        columns = [
            {"key": "code", "label": "Mã hồ sơ", "kind": "link", "nowrap": True},
            {"key": "name", "label": "Họ và tên", "kind": "text"},
            {"key": "since", "label": date_label, "kind": "date"},
        ]
        blocks.append(
            {
                "code": code,
                "title": title,
                "count": total,
                "rows": rows,
                "columns": columns,
                "url": url,
            }
        )

    if role_code(user) in MANAGERS:
        worker_block(
            "pending", "Chờ duyệt", VerificationStatus.PENDING, "Ngày gửi duyệt", "/duyet-ho-so/"
        )
    worker_block(
        "needs_info",
        "Cần bổ sung",
        VerificationStatus.NEEDS_INFO,
        "Ngày trả lại",
        list_url(WORKER_LIST, {"trang_thai_ho_so": "NEEDS_INFO"}),
    )

    expiring = indicators.id_expiring(Worker.objects.all(), today).select_related("identity")
    rows = [
        {"code": _worker_link(w), "name": w.full_name, "expiry": w.identity.expiry_date}
        for w in expiring.order_by("identity__expiry_date", "id")[:TODO_LIMIT]
    ]
    blocks.append(
        {
            "code": "id_expiring",
            "title": "CCCD sắp hết hạn",
            "count": expiring.count(),
            "rows": rows,
            "columns": [
                {"key": "code", "label": "Mã hồ sơ", "kind": "link", "nowrap": True},
                {"key": "name", "label": "Họ và tên", "kind": "text"},
                {"key": "expiry", "label": "Ngày hết hạn", "kind": "date"},
            ],
            "url": list_url(WORKER_LIST, {"cccd_sap_het_han": "1"}),
        }
    )

    due = indicators.assignment_due_info(today)
    workers = {w.pk: w for w in Worker.objects.filter(pk__in=due)}
    ordered = sorted(due.items(), key=lambda item: (item[1][0], item[0]))
    rows = []
    for worker_id, (due_date, chain_start, assignment) in ordered[:TODO_LIMIT]:
        worker = workers[worker_id]
        rows.append(
            {
                "code": {
                    "text": worker.employee_code or worker.worker_code,
                    "url": f"/ho-so/{worker.pk}/?tab=lam-viec",
                },
                "client": str(assignment.client_company),
                "start": chain_start,
                "due": due_date,
                "badge": badges.EXPIRING,
            }
        )
    months = SystemSetting.load().assignment_limit_months
    blocks.append(
        {
            "code": "assignment_due",
            "title": f"Đợt làm việc sắp đủ {months} tháng",
            "count": len(due),
            "rows": rows,
            "columns": [
                {"key": "code", "label": "Mã NV", "kind": "link", "nowrap": True},
                {"key": "client", "label": "Công ty khách", "kind": "text"},
                {"key": "start", "label": "Ngày bắt đầu", "kind": "date"},
                {"key": "due", "label": f"Đủ {months} tháng ngày", "kind": "date"},
                {"key": "badge", "label": "Cảnh báo", "kind": "badge"},
            ],
            "url": list_url(WORKER_LIST, {"dot_sap_du_han": "1"}),
        }
    )
    return blocks
