"""File Excel mẫu nhập hàng loạt (excel-mau.md mục 1, 5): ba sheet "Hồ sơ" (chỉ có dòng tiêu đề,
mọi cột định dạng Text, ô chọn thả xuống lấy từ sheet "Danh mục"), "Hướng dẫn" (quy tắc + hai dòng
ví dụ hư cấu) và "Danh mục" (giá trị hợp lệ lấy từ hệ thống lúc tải). Mọi ô ghi qua `safe_cell`."""

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.worksheet.datavalidation import DataValidation

from apps.core import excel
from apps.core.choices import Gender, IdDocType, ResignReason, WorkStatus
from apps.core.models import ClientCompany, Department, Position, Section, Shift, Team

from . import importer
from .excel_columns import (
    COLUMNS,
    EXAMPLES,
    HEADERS,
    SHEET_CATALOG,
    SHEET_DATA,
    SHEET_GUIDE,
    letter,
)

# Cột của sheet "Danh mục" theo khóa cột nhập (để tạo ô thả xuống).
CATALOG_COLUMNS = {
    "department": "A",
    "section": "B",
    "team": "D",
    "position": "F",
    "shift": "G",
    "client_company": "H",
    "id_doc_type": "I",
    "gender": "J",
    "work_status": "K",
    "resign_reason": "L",
}


def _catalog_lists():
    """{chữ cột Danh mục: (tiêu đề, danh sách giá trị)}; cột C và E ghi phòng ban/bộ phận cha."""
    sections = list(Section.objects.filter(is_active=True).select_related("department"))
    teams = list(Team.objects.filter(is_active=True).select_related("section"))
    return {
        "A": ("Phòng ban", [d.name for d in Department.objects.filter(is_active=True)]),
        "B": ("Bộ phận", [s.name for s in sections]),
        "C": ("Phòng ban của bộ phận", [s.department.name for s in sections]),
        "D": ("Tổ", [t.name for t in teams]),
        "E": ("Bộ phận của tổ", [t.section.name for t in teams]),
        "F": ("Chức danh", [p.name for p in Position.objects.filter(is_active=True)]),
        "G": ("Ca làm việc", [s.name for s in Shift.objects.filter(is_active=True)]),
        "H": (
            "Công ty khách (tên – địa điểm)",
            [str(c) for c in ClientCompany.objects.filter(is_active=True)],
        ),
        "I": ("Loại giấy tờ", [label for _, label in IdDocType.choices]),
        "J": ("Giới tính", [label for _, label in Gender.choices]),
        "K": ("Trạng thái làm việc", [label for _, label in WorkStatus.choices]),
        "L": ("Lý do nghỉ", [label for _, label in ResignReason.choices]),
    }


GUIDE_LINES = [
    "HƯỚNG DẪN NHẬP HỒ SƠ TỪ FILE EXCEL",
    "Chỉ nhập vào sheet “Hồ sơ”. Giữ nguyên dòng 1 (tên cột), không đổi tên, không đổi thứ tự cột.",
    f"Mỗi lần nhập tối đa {importer.MAX_ROWS} dòng và {importer.MAX_BYTES // (1024 * 1024)} MB.",
    "Mọi cột đã định dạng Text để giữ số 0 đầu của số điện thoại, số CCCD, mã nhân viên.",
    "Ngày nhập dạng dd/mm/yyyy (ví dụ 15/03/2000). Không dùng công thức Excel ở bất kỳ ô nào.",
    "Phần A (A1–A21): thông tin cá nhân. Bắt buộc họ tên và số điện thoại; còn lại bổ sung sau.",
    "Phần B (B1–B13): thông tin làm việc của công nhân hiện hữu, chỉ Admin và Quản lý nhân sự "
    "nhập. Có điền phần B thì bắt buộc: Mã nhân viên, Chức danh, Ngày vào làm, Trạng thái.",
    "Bộ phận không bắt buộc; để trống thì hồ sơ thuộc nhóm “Chưa có bộ phận”.",
    "Công ty khách: chọn đúng dạng “tên – địa điểm” ở sheet “Danh mục”; có công ty khách thì "
    "bắt buộc Ngày bắt đầu đợt. Lương không nhập ở file này.",
    "Hồ sơ nhập vào ở trạng thái Nháp và phải do một tài khoản khác duyệt "
    "(người nhập không tự duyệt).",
    "Dòng đúng được nhập, dòng sai bị bỏ qua và được báo rõ số dòng, cột, lý do.",
]


def _style_header(sheet):
    for cell in sheet[1]:
        cell.font = Font(bold=True)


def _build_catalog(book):
    sheet = book.create_sheet(SHEET_CATALOG)
    lists = _catalog_lists()
    for col_letter, (title, values) in lists.items():
        index = ord(col_letter) - ord("A") + 1
        sheet.cell(row=1, column=index, value=excel.safe_cell(title)).font = Font(bold=True)
        for offset, value in enumerate(values, start=2):
            sheet.cell(row=offset, column=index, value=excel.safe_cell(value))
        sheet.column_dimensions[col_letter].width = 32
    return lists


def _add_dropdowns(data, lists):
    """Ô thả xuống cho các cột chọn từ danh mục (hàng 2..MAX_ROWS+1)."""
    last = importer.MAX_ROWS + 1
    for column in COLUMNS:
        catalog_letter = CATALOG_COLUMNS.get(column.key)
        if not catalog_letter:
            continue
        count = max(1, len(lists[catalog_letter][1]))
        validation = DataValidation(
            type="list",
            formula1=f"'{SHEET_CATALOG}'!${catalog_letter}$2:${catalog_letter}${count + 1}",
            allow_blank=True,
        )
        col = letter(column.code)
        validation.add(f"{col}2:{col}{last}")
        data.add_data_validation(validation)


def _build_guide(book):
    sheet = book.create_sheet(SHEET_GUIDE)
    for line in GUIDE_LINES:
        sheet.append([excel.safe_cell(line)])
    sheet["A1"].font = Font(bold=True, size=14)
    sheet.append([])
    sheet.append(
        [
            excel.safe_cell(v)
            for v in (
                "Cột",
                "Tên cột",
                "Ví dụ 1: ứng viên (chỉ phần A)",
                "Ví dụ 2: công nhân hiện hữu (A + B)",
            )
        ]
    )
    for cell in sheet[sheet.max_row]:
        cell.font = Font(bold=True)
    for column in COLUMNS:
        one, two = EXAMPLES[column.key]
        sheet.append([excel.safe_cell(v) for v in (column.code, column.header, one, two)])
    sheet.column_dimensions["A"].width = 60
    for col_letter in "BCD":
        sheet.column_dimensions[col_letter].width = 38
    return sheet


def build_template():
    """Sổ tính file mẫu (không có dòng dữ liệu ở sheet "Hồ sơ")."""
    book = Workbook()
    data = book.active
    data.title = SHEET_DATA
    data.append([excel.safe_cell(h) for h in HEADERS])
    _style_header(data)
    data.freeze_panes = "A2"
    for column in COLUMNS:
        dimension = data.column_dimensions[letter(column.code)]
        dimension.number_format = "@"  # Text: giữ số 0 đầu và chuỗi ngày
        dimension.width = 22
    _build_guide(book)  # thứ tự sheet: Hồ sơ, Hướng dẫn, Danh mục
    lists = _build_catalog(book)
    _add_dropdowns(data, lists)
    return book
