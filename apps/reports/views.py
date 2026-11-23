"""Dashboard `/` (trang.md 5.3): 9 thẻ số liệu bấm được, 4 khung biểu đồ, việc cần làm.

Mọi vai trò đã đăng nhập xem được; khối "Chờ duyệt" chỉ hiện với Admin, Quản lý nhân sự.
"""

from django.shortcuts import render

from apps.accounts.permissions import ALL_ROLES, role_required

from . import stats


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
