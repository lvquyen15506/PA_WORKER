"""Chín loại báo cáo của /bao-cao/ (trang.md 5.9, phac-thao-trang.md 2.9).

Mỗi loại là một hàm `ReportContext -> Report` (cột, dòng, dòng Tổng, biểu đồ); trang xem, bản in và
file Excel dùng chung kết quả này nên ba nơi luôn cùng số liệu. Báo cáo cơ cấu (1–6, 9) tính công
nhân đang làm hiện tại và lọc được theo phòng ban; khoảng ngày chỉ áp cho báo cáo theo tháng (7, 8).
"""

from dataclasses import dataclass, field

from django.utils import timezone

from apps.core import excel

from . import stats

TOTAL = "Tổng"
ZERO_TEXT = "Không có số liệu trong khoảng đã chọn."


def count_cell(number, url=""):
    """Ô số liệu (cột kind link): bấm được khi có `url`."""
    return {"text": number, "url": url or None}


def plain(cell):
    """Giá trị thuần của một ô (dùng cho Excel)."""
    return cell.get("text") if isinstance(cell, dict) else cell


@dataclass
class ReportContext:
    code: str
    start: object
    end: object
    department: object = None  # Department, stats.NO_SECTION hoặc None (tất cả)

    @property
    def department_label(self):
        if self.department is None:
            return "Tất cả phòng ban"
        return stats.NO_SECTION if self.department == stats.NO_SECTION else self.department.name


@dataclass
class Report:
    code: str
    title: str
    scope: str
    columns: list
    rows: list  # dòng dữ liệu (không gồm dòng Tổng)
    total: dict
    headline: str  # tiêu đề biểu đồ: nói kết quả
    chart: dict
    unit: str = "người"
    has_data: bool = True
    monthly: bool = False
    filters: str = ""  # mô tả bộ lọc cho nhật ký (không có họ tên)

    @property
    def table_rows(self):
        return [*self.rows, self.total]


@dataclass
class Definition:
    code: str
    title: str
    build: object = field(repr=False)
    monthly: bool = False


def _col(key, label, kind="text", **extra):
    return {"key": key, "label": label, "kind": kind, **extra}


def _count_col(label="Số công nhân"):
    return _col("n", label, "link", num=True)


def _scope(ctx, monthly):
    if monthly:
        return f"Từ {ctx.start:%d/%m/%Y} đến {ctx.end:%d/%m/%Y} · Phòng ban: {ctx.department_label}"
    return (
        f"Công nhân đang làm (Thử việc và Đang làm việc) · Phòng ban: {ctx.department_label}"
        " · Không lọc theo khoảng ngày"
    )


def _monthly_filters(ctx):
    """Mô tả bộ lọc ghi vào nhật ký (không có họ tên)."""
    return f"từ {ctx.start:%d/%m/%Y} đến {ctx.end:%d/%m/%Y}; phòng ban: {ctx.department_label}"


def _top_headline(pairs, unit, noun="nhiều nhất"):
    best = max(pairs, key=lambda p: p[1], default=None)
    total = sum(n for _, n in pairs)
    if not best or best[1] == 0:
        return ZERO_TEXT
    return f"{best[0]} {noun}, {best[1]} {unit} (tổng {total})"


def _build(ctx, definition, columns, rows, labels, *, horizontal=False):
    """Báo cáo cơ cấu một chuỗi: `rows` là [{...cột..., "n": ô số}] chưa có dòng Tổng."""
    counts = [plain(r["n"]) for r in rows]
    total = sum(counts)
    first = columns[0]["key"]
    total_row = {c["key"]: "" for c in columns}
    total_row[first] = TOTAL
    total_row["n"] = count_cell(total)
    chart = {"type": "bar", "labels": labels, "values": counts, "unit": "người"}
    if horizontal:
        chart["horizontal"] = True
    return Report(
        code=definition.code,
        title=definition.title,
        scope=_scope(ctx, False),
        columns=columns,
        rows=rows,
        total=total_row,
        headline=_top_headline(list(zip(labels, counts, strict=True)), "người"),
        chart=chart,
        has_data=total > 0,
        filters=f"phòng ban: {ctx.department_label}",
    )


# --- 1–6, 9: báo cáo cơ cấu ---------------------------------------------------------------------
def r_section(ctx, definition):
    data = stats.by_section(ctx.department)
    columns = [_col("dep", "Phòng ban"), _col("sec", "Bộ phận"), _count_col()]
    rows = [{"dep": d, "sec": s, "n": count_cell(n, url)} for d, s, n, url in data]
    labels = [s if d == "—" else f"{d} – {s}" for d, s, _, _ in data]
    return _build(ctx, definition, columns, rows, labels, horizontal=True)


def r_gender(ctx, definition):
    data = stats.by_gender(ctx.department)
    columns = [_col("label", "Giới tính"), _count_col()]
    rows = [{"label": label, "n": count_cell(n)} for label, n in data]
    return _build(ctx, definition, columns, rows, [label for label, _ in data])


def r_age(ctx, definition):
    data = stats.by_age_group(ctx.department)
    columns = [_col("label", "Nhóm tuổi"), _count_col()]
    rows = [{"label": label, "n": count_cell(n)} for label, n in data]
    return _build(ctx, definition, columns, rows, [label for label, _ in data])


def r_education(ctx, definition):
    data = stats.by_education(ctx.department)
    columns = [_col("label", "Trình độ cao nhất"), _count_col()]
    rows = [{"label": label, "n": count_cell(n, url)} for label, n, url in data]
    return _build(ctx, definition, columns, rows, [label for label, _, _ in data])


def r_position(ctx, definition):
    data = stats.by_position(ctx.department)
    columns = [_col("label", "Chức danh"), _count_col()]
    rows = [{"label": label, "n": count_cell(n, url)} for label, n, url in data]
    return _build(ctx, definition, columns, rows, [label for label, _, _ in data], horizontal=True)


def r_complete(ctx, definition):
    data = stats.completeness(ctx.department)
    columns = [_col("label", "Tình trạng hồ sơ"), _count_col()]
    rows = [{"label": label, "n": count_cell(n, url)} for label, n, url in data]
    return _build(ctx, definition, columns, rows, [label for label, _, _ in data])


def r_client(ctx, definition):
    data = stats.by_client(ctx.department)
    columns = [
        _col("company", "Công ty"),
        _col("location", "Địa điểm"),
        _count_col("Số công nhân đang làm"),
    ]
    rows = [{"company": c, "location": loc, "n": count_cell(n, url)} for c, loc, n, url in data]
    labels = [f"{c} – {loc}" for c, loc, _, _ in data]
    report = _build(ctx, definition, columns, rows, labels, horizontal=True)
    report.scope = (
        f"Công nhân có đợt làm việc đang diễn ra · Phòng ban: {ctx.department_label}"
        " · Không lọc theo khoảng ngày"
    )
    return report


# --- 7, 8: báo cáo theo tháng -------------------------------------------------------------------
def r_new_workers(ctx, definition):
    data = stats.new_workers_by_month(ctx.start, ctx.end, ctx.department)
    columns = [_col("label", "Tháng"), _col("n", "Hồ sơ mới", "link", num=True)]
    rows = [{"label": month, "n": count_cell(n)} for month, n in data]
    total = sum(n for _, n in data)
    return Report(
        code=definition.code,
        title=definition.title,
        scope=_scope(ctx, True),
        columns=columns,
        rows=rows,
        total={"label": TOTAL, "n": count_cell(total)},
        headline=f"{total} hồ sơ mới trong khoảng đã chọn" if total else ZERO_TEXT,
        chart={
            "type": "bar",
            "labels": [m for m, _ in data],
            "values": [n for _, n in data],
            "unit": "hồ sơ",
        },
        unit="hồ sơ",
        has_data=total > 0,
        monthly=True,
        filters=_monthly_filters(ctx),
    )


def r_flow(ctx, definition):
    data = stats.hires_and_exits(ctx.start, ctx.end, ctx.department)
    columns = [
        _col("label", "Tháng"),
        _col("hires", "Vào làm", "link", num=True),
        _col("exits", "Nghỉ việc", "link", num=True),
    ]
    rows = [{"label": m, "hires": count_cell(a), "exits": count_cell(b)} for m, a, b in data]
    hires, exits = sum(r[1] for r in data), sum(r[2] for r in data)
    return Report(
        code=definition.code,
        title=definition.title,
        scope=_scope(ctx, True),
        columns=columns,
        rows=rows,
        total={"label": TOTAL, "hires": count_cell(hires), "exits": count_cell(exits)},
        headline=f"Vào làm {hires} người, nghỉ việc {exits} người trong khoảng đã chọn"
        if hires or exits
        else ZERO_TEXT,
        chart={
            "type": "bar",
            "labels": [r[0] for r in data],
            "datasets": [
                {"label": "Vào làm", "values": [r[1] for r in data]},
                {"label": "Nghỉ việc", "values": [r[2] for r in data]},
            ],
            "unit": "người",
        },
        has_data=bool(hires or exits),
        monthly=True,
        filters=_monthly_filters(ctx),
    )


REPORTS = [
    Definition("phong-ban", "Công nhân theo phòng ban và bộ phận", r_section),
    Definition("gioi-tinh", "Công nhân theo giới tính", r_gender),
    Definition("nhom-tuoi", "Công nhân theo nhóm tuổi", r_age),
    Definition("trinh-do", "Công nhân theo trình độ", r_education),
    Definition("chuc-danh", "Công nhân theo chức danh", r_position),
    Definition("hoan-thien", "Hồ sơ hoàn thiện và chưa hoàn thiện", r_complete),
    Definition("ho-so-moi", "Hồ sơ mới theo tháng", r_new_workers, monthly=True),
    Definition("vao-lam-nghi-viec", "Vào làm và nghỉ việc theo tháng", r_flow, monthly=True),
    Definition("cong-ty-khach", "Công nhân đang làm theo công ty khách hàng", r_client),
]
BY_CODE = {d.code: d for d in REPORTS}


def build_report(ctx):
    definition = BY_CODE[ctx.code]
    report = definition.build(ctx, definition)
    report.monthly = definition.monthly
    return report


# --- Excel --------------------------------------------------------------------------------------
def workbook(report, user, today=None):
    """Sổ tính của báo cáo: tiêu đề, phạm vi, ngày lập, người lập rồi bảng (mọi ô qua safe_cell)."""
    today = today or timezone.localdate()
    book = excel.new_workbook(report.title)
    sheet = book.active
    for line in (
        [report.title],
        [report.scope],
        [f"Ngày lập: {today:%d/%m/%Y}", f"Người lập: {user.full_name or user.username}"],
        [],
    ):
        sheet.append([excel.safe_cell(v) for v in line])
    sheet["A1"].font = excel.Font(bold=True, size=14)
    start = sheet.max_row + 1
    headers = [c["label"] for c in report.columns]
    keys = [c["key"] for c in report.columns]
    excel.write_rows(
        sheet,
        headers,
        [[plain(row.get(k)) for k in keys] for row in report.table_rows],
        widths=False,
    )
    # write_rows ghi tiêu đề ở dòng kế tiếp; in đậm dòng tiêu đề và dòng Tổng.
    for cell in sheet[start]:
        cell.font = excel.Font(bold=True)
    for cell in sheet[sheet.max_row]:
        cell.font = excel.Font(bold=True)
    excel.autosize(sheet)
    return book
