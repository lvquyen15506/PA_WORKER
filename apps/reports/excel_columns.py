"""Cấu trúc file Excel mẫu nhập hàng loạt (docs/thiet-ke/excel-mau.md mục 2).

34 cột ở sheet "Hồ sơ", thứ tự và tên đúng như tài liệu: phần A (A1–A21, thông tin cá nhân) rồi phần
B (B1–B13, thông tin làm việc, chỉ Admin và Quản lý nhân sự). File mẫu, bộ nhập và test cùng dùng
danh sách này nên không lệch nhau.
"""

from collections import namedtuple

from openpyxl.utils import get_column_letter

Column = namedtuple("Column", ["code", "header", "key", "kind"])
# kind: text | multiline | date | choice (chọn từ danh sách, có ô thả xuống)

SHEET_DATA = "Hồ sơ"
SHEET_GUIDE = "Hướng dẫn"
SHEET_CATALOG = "Danh mục"

COLUMNS = [
    Column("A1", "Họ và tên", "full_name", "text"),
    Column("A2", "Số điện thoại", "phone", "text"),
    Column("A3", "Ngày sinh", "date_of_birth", "date"),
    Column("A4", "Giới tính", "gender", "choice"),
    Column("A5", "Quốc tịch", "nationality", "text"),
    Column("A6", "Loại giấy tờ", "id_doc_type", "choice"),
    Column("A7", "Số định danh", "id_number", "text"),
    Column("A8", "Ngày cấp", "issue_date", "date"),
    Column("A9", "Nơi cấp", "issue_place", "text"),
    Column("A10", "Ngày hết hạn", "expiry_date", "date"),
    Column("A11", "Quê quán", "hometown", "text"),
    Column("A12", "Nơi đăng ký khai sinh", "birth_registration_place", "text"),
    Column("A13", "Nơi thường trú/cư trú", "permanent_address", "text"),
    Column("A14", "Số CMND cũ", "old_id_number", "text"),
    Column("A15", "Email", "email", "text"),
    Column("A16", "Nơi ở hiện tại", "current_address", "text"),
    Column("A17", "Người liên hệ khẩn cấp – Họ tên", "contact_name", "text"),
    Column("A18", "Người liên hệ khẩn cấp – Quan hệ", "contact_relationship", "text"),
    Column("A19", "Người liên hệ khẩn cấp – SĐT", "contact_phone", "text"),
    Column("A20", "Kỹ năng", "skills", "multiline"),
    Column("A21", "Ghi chú", "note", "multiline"),
    Column("B1", "Mã nhân viên", "employee_code", "text"),
    Column("B2", "Phòng ban", "department", "choice"),
    Column("B3", "Bộ phận", "section", "choice"),
    Column("B4", "Tổ", "team", "choice"),
    Column("B5", "Chức danh", "position", "choice"),
    Column("B6", "Ca làm việc", "shift", "choice"),
    Column("B7", "Ngày tiếp nhận", "received_date", "date"),
    Column("B8", "Ngày vào làm", "start_date", "date"),
    Column("B9", "Trạng thái làm việc", "work_status", "choice"),
    Column("B10", "Ngày nghỉ việc", "resign_date", "date"),
    Column("B11", "Lý do nghỉ", "resign_reason", "choice"),
    Column("B12", "Công ty khách", "client_company", "choice"),
    Column("B13", "Ngày bắt đầu đợt", "assignment_start", "date"),
]
BY_CODE = {c.code: c for c in COLUMNS}
BY_KEY = {c.key: c for c in COLUMNS}
HEADERS = [c.header for c in COLUMNS]
WORK_COLUMNS = [c for c in COLUMNS if c.code.startswith("B")]
WORK_KEYS = [c.key for c in WORK_COLUMNS]


def letter(code):
    """Chữ cột Excel của một mã cột (A1 -> A, B1 -> V)."""
    return get_column_letter(COLUMNS.index(BY_CODE[code]) + 1)


# Hai dòng ví dụ ở sheet "Hướng dẫn" (excel-mau.md mục 5): dữ liệu hư cấu, số giấy tờ bắt đầu 999.
EXAMPLES = {
    "full_name": ("Trần Thị Mẫu", "Lê Văn Thử"),
    "phone": ("0900000001", "0900000003"),
    "date_of_birth": ("15/03/2000", "02/09/1990"),
    "gender": ("Nữ", "Nam"),
    "nationality": ("Việt Nam", "Việt Nam"),
    "id_doc_type": ("CCCD gắn chip (mẫu 2021)", "Thẻ Căn cước (từ 01/7/2024)"),
    "id_number": ("999000000001", "999000000002"),
    "issue_date": ("20/06/2023", "10/08/2024"),
    "issue_place": ("Cục Cảnh sát QLHC về TTXH", "Bộ Công an"),
    "expiry_date": ("15/03/2040", "02/09/2030"),
    "hometown": ("Xã Mẫu Một, Tỉnh Mẫu", ""),
    "birth_registration_place": ("", "Xã Mẫu Hai, Tỉnh Mẫu"),
    "permanent_address": ("Số 1 Đường Mẫu, Phường Mẫu", "Số 2 Đường Mẫu, Phường Mẫu"),
    "old_id_number": ("999000001", ""),
    "email": ("mau.tran@example.com", ""),
    "current_address": ("Khu trọ Mẫu, Phường Mẫu", "Khu trọ Mẫu, Phường Mẫu"),
    "contact_name": ("Trần Văn Mẫu", "Lê Thị Thử"),
    "contact_relationship": ("Bố", "Vợ"),
    "contact_phone": ("0900000002", "0900000004"),
    "skills": ("Vận hành máy may công nghiệp", ""),
    "note": ("", ""),
    "employee_code": ("", "CN-00012"),
    "department": ("", "Xưởng May"),
    "section": ("", "Chuyền May 1"),
    "team": ("", "Tổ 1"),
    "position": ("", "Công nhân may"),
    "shift": ("", "Ca 1"),
    "received_date": ("", "01/02/2023"),
    "start_date": ("", "01/02/2023"),
    "work_status": ("", "Đang làm việc"),
    "resign_date": ("", ""),
    "resign_reason": ("", ""),
    "client_company": ("", "Công ty Mẫu A – Tỉnh Mẫu"),
    "assignment_start": ("", "01/03/2023"),
}
