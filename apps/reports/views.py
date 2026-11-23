"""Dashboard `/` và báo cáo `/bao-cao/` (trang.md 5.3, 5.9).

- Dashboard: mọi vai trò xem; khối "Chờ duyệt" chỉ hiện với Admin, Quản lý nhân sự.
- Báo cáo: mọi vai trò xem; **xuất Excel và in chỉ Admin, Quản lý nhân sự, Nhân viên HR** (câu 18:
  Viewer chỉ xem thống kê, in cũng là xuất). Mỗi lần xuất/in ghi nhật ký (không ghi họ tên).
"""

from urllib.parse import urlencode

from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.accounts.permissions import ALL_ROLES, role_required
from apps.audit.services import log
from apps.core import excel
from apps.core.choices import AuditAction
from apps.workers.rules import ALL_STAFF, role_code

from . import reports, stats
from .forms import DepartmentFilterField, ReportFilterForm

STAFF = tuple(ALL_STAFF)


def _top(rows, label_index=0, value_index=1):
    """Dòng có giá trị lớn nhất (None nếu không có hoặc toàn số 0)."""
    best = max(rows, key=lambda r: r[value_index], default=None)
    return best if best and best[value_index] > 0 else None


def chart(chart_id, title, aria, config):
    return {"id": chart_id, "title": title, "aria": aria, "cfg": config}


def build_charts(today=None):
    start, end = stats.last_12_months(today)
    flow = stats.hires_and_exits(start, end)
    hires, exits = sum(r[1] for r in flow), sum(r[2] for r in flow)
    in_out = chart(
        "chart-in-out",
        f"Vào làm {hires} người, nghỉ việc {exits} người trong 12 tháng gần nhất",
        "Biểu đồ cột nhóm số công nhân vào làm và nghỉ việc theo tháng, đơn vị người",
        {
            "type": "bar",
            "labels": [r[0] for r in flow],
            "datasets": [
                {"label": "Vào làm", "values": [r[1] for r in flow]},
                {"label": "Nghỉ việc", "values": [r[2] for r in flow]},
            ],
            "unit": "người",
        },
    )

    departments = stats.by_department()
    top = _top([(r[0], r[1]) for r in departments])
    by_department = chart(
        "chart-department",
        f"{top[0]} có nhiều công nhân đang làm nhất, {top[1]} người"
        if top
        else "Chưa có công nhân đang làm theo phòng ban",
        "Biểu đồ cột ngang số công nhân đang làm theo phòng ban, đơn vị người",
        {
            "type": "bar",
            "horizontal": True,
            "labels": [r[0] for r in departments],
            "values": [r[1] for r in departments],
            "unit": "người",
        },
    )

    gender = stats.by_gender()
    age = stats.by_age_group(today=today)
    education = stats.by_education()
    structure = []
    for chart_id, rows, title_fn, aria in (
        (
            "chart-gender",
            gender,
            lambda: ", ".join(f"{label} {n}" for label, n in gender) + " (công nhân đang làm)",
            "Biểu đồ cột công nhân đang làm theo giới tính, đơn vị người",
        ),
        (
            "chart-age",
            age,
            lambda: (
                f"Nhóm tuổi {_top(age)[0]} đông nhất, {_top(age)[1]} người"
                if _top(age)
                else "Chưa có công nhân đang làm theo nhóm tuổi"
            ),
            "Biểu đồ cột công nhân đang làm theo nhóm tuổi, đơn vị người",
        ),
        (
            "chart-education",
            [(r[0], r[1]) for r in education],
            lambda: (
                f"Trình độ {_top(education)[0]} nhiều nhất, {_top(education)[1]} người"
                if _top(education)
                else "Chưa có công nhân đang làm theo trình độ"
            ),
            "Biểu đồ cột công nhân đang làm theo trình độ cao nhất, đơn vị người",
        ),
    ):
        structure.append(
            chart(
                chart_id,
                title_fn(),
                aria,
                {
                    "type": "bar",
                    "labels": [r[0] for r in rows],
                    "values": [r[1] for r in rows],
                    "unit": "người",
                },
            )
        )

    statuses = stats.by_verification_status()
    total = sum(r[1] for r in statuses)
    best = _top(statuses)
    verification = chart(
        "chart-verification",
        f"{best[0]} nhiều nhất, {best[1]} trong {total} hồ sơ" if best else "Chưa có hồ sơ nào",
        "Biểu đồ cột số hồ sơ theo trạng thái xác minh, đơn vị hồ sơ",
        {
            "type": "bar",
            "labels": [r[0] for r in statuses],
            "values": [r[1] for r in statuses],
            "unit": "hồ sơ",
        },
    )
    return {
        "in_out": in_out,
        "department": by_department,
        "structure": structure,
        "verification": verification,
    }


@role_required(*ALL_ROLES)
def dashboard(request):
    return render(
        request,
        "reports/dashboard.html",
        {
            "cards": stats.cards(request.user),
            "charts": build_charts(),
            "todo": stats.todo_blocks(request.user),
        },
    )


# --- Báo cáo ------------------------------------------------------------------------------------
def _query(ctx):
    """Tham số chuẩn hóa (đủ loại, khoảng ngày, phòng ban) dùng cho liên kết In và Xuất Excel."""
    if ctx.department == stats.NO_SECTION:
        department = DepartmentFilterField.NONE
    else:
        department = ctx.department.pk if ctx.department is not None else ""
    return urlencode(
        {
            "loai": ctx.code,
            "tu_ngay": ctx.start.strftime("%d/%m/%Y"),
            "den_ngay": ctx.end.strftime("%d/%m/%Y"),
            "phong_ban": department,
        }
    )


def _report(request):
    form = ReportFilterForm(request.GET)
    form.is_valid()
    ctx = form.context()
    return form, ctx, reports.build_report(ctx)


@role_required(*ALL_ROLES)
@require_GET
def report_page(request):
    form, ctx, report = _report(request)
    can_export = role_code(request.user) in ALL_STAFF
    query = _query(ctx)
    actions = (
        [
            {"label": "In", "kind": "secondary", "url": f"/bao-cao/in/?{query}"},
            {"label": "Xuất Excel", "kind": "secondary", "url": f"/bao-cao/xuat-excel/?{query}"},
        ]
        if can_export
        else []
    )
    chart_data = chart(
        "chart-report",
        report.headline,
        f"Biểu đồ cột: {report.title}, đơn vị {report.unit}",
        report.chart,
    )
    return render(
        request,
        "reports/report.html",
        {
            "form": form,
            "report": report,
            "chart": chart_data,
            "header_actions": actions,
        },
    )


def _log_report(request, event, report):
    log(
        event,
        user=request.user,
        object_type="report",
        object_id=report.code,
        object_repr=report.title,
        note=f"{len(report.rows)} dòng; {report.filters}",
        request=request,
    )


@role_required(*STAFF)
@require_GET
def report_export(request):
    form, ctx, report = _report(request)
    if form.errors:  # không xuất khi bộ lọc sai: quay lại trang để sửa
        messages.error(request, "Bộ lọc báo cáo chưa hợp lệ. Hãy kiểm tra lại rồi xuất.")
        return redirect(f"/bao-cao/?{request.GET.urlencode()}")
    _log_report(request, AuditAction.EXPORT, report)
    book = reports.workbook(report, request.user)
    stamp = timezone.localdate().strftime("%Y%m%d")
    return excel.xlsx_response(book, f"Bao-cao-{report.code}-{stamp}.xlsx")


@role_required(*STAFF)
@require_GET
def report_print(request):
    form, ctx, report = _report(request)
    if form.errors:
        messages.error(request, "Bộ lọc báo cáo chưa hợp lệ. Hãy kiểm tra lại rồi in.")
        return redirect(f"/bao-cao/?{request.GET.urlencode()}")
    _log_report(request, AuditAction.PRINT, report)
    return render(
        request,
        "reports/report_print.html",
        {
            "report": report,
            "printed_on": timezone.localdate(),
            "printed_by": request.user.full_name or request.user.username,
        },
    )
