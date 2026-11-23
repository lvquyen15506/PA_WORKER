"""Tiện ích Excel dùng chung cho xuất danh sách, báo cáo, file mẫu, biên bản và nhập hàng loạt
(models.md 4.5; excel-mau.md mục 3).

Lớp bảo vệ chính chống chèn công thức: MỌI giá trị ghi ra file đi qua `safe_cell()`. Chiều nhập:
`check_zip_safe()` chạy TRƯỚC khi openpyxl mở tệp để chặn zip bomb.
"""

import io
import re
import zipfile
from datetime import date, datetime
from decimal import Decimal

from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font

from apps.documents.http import safe_content_disposition

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MSG_INVALID = "Tệp Excel không hợp lệ."

# Giới hạn chống zip bomb (nhập Excel). Tệp tải lên tối đa 10 MB nên tỉ lệ nén 100 lần cũng vẫn
# chặn ở mức 100 MB; ngưỡng 1 MiB để mục nhỏ (nhiều ô trống nén rất tốt) không bị chặn oan.
MAX_UNZIPPED_BYTES = 100 * 1024 * 1024
MAX_COMPRESSION_RATIO = 100
RATIO_CHECK_MIN_BYTES = 1024 * 1024
_CHUNK = 1024 * 1024

# Ký tự đầu khiến Excel hiểu giá trị chữ là công thức (hoặc lệnh DDE).
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")


class ExcelFileError(Exception):
    """Tệp Excel không dùng được (cả tệp); `message` là câu tiếng Việt hiển thị cho người dùng."""

    def __init__(self, message=MSG_INVALID):
        super().__init__(message)
        self.message = message


def safe_cell(value):
    """Giá trị an toàn để ghi vào một ô.

    - Chữ bắt đầu bằng `=` `+` `-` `@`, tab hoặc xuống dòng: thêm dấu `'` phía trước.
    - Ngày ghi dạng dd/mm/yyyy (giờ: dd/mm/yyyy hh:mm); số, đúng/sai giữ nguyên; None thành ô trống.
    - Bỏ ký tự điều khiển mà định dạng XLSX không chấp nhận (dữ liệu OCR/CV có thể lẫn vào).
    """
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, (int, float, Decimal)):
        return value
    text = ILLEGAL_CHARACTERS_RE.sub("", str(value))
    if text.startswith(FORMULA_PREFIXES):
        return "'" + text
    return text


def write_rows(sheet, headers, rows, *, widths=True):
    """Ghi dòng tiêu đề (in đậm) rồi các dòng dữ liệu; mọi ô qua `safe_cell`."""
    sheet.append([safe_cell(h) for h in headers])
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append([safe_cell(v) for v in row])
    if widths:
        autosize(sheet)
    return sheet


def autosize(sheet, *, minimum=10, maximum=50):
    """Chỉnh độ rộng cột theo nội dung dài nhất (có giới hạn)."""
    longest = {}
    for row in sheet.iter_rows():
        for cell in row:
            if cell.value is not None:
                longest[cell.column_letter] = max(
                    longest.get(cell.column_letter, 0), len(str(cell.value))
                )
    for letter, length in longest.items():
        sheet.column_dimensions[letter].width = max(minimum, min(maximum, length + 2))


def new_workbook(title):
    """Sổ tính có một sheet đã đặt tên (tên sheet tối đa 31 ký tự, bỏ ký tự cấm của Excel)."""
    book = Workbook()
    book.active.title = re.sub(r"[\\/*?:\[\]]", " ", title)[:31]
    return book


def xlsx_response(book, filename):
    """Phản hồi tải về một sổ tính. Có dữ liệu cá nhân nên không cho trình duyệt/proxy lưu đệm."""
    buffer = io.BytesIO()
    book.save(buffer)
    response = HttpResponse(buffer.getvalue(), content_type=XLSX_MIME)
    response["Content-Disposition"] = safe_content_disposition("attachment", filename, ".xlsx")
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "no-store"
    return response


def is_xlsx(data):
    """Có phải tệp .xlsx thật không: zip có `[Content_Types].xml` và `xl/workbook.xml` (cùng cách
    `_is_docx` ở apps/documents/validators.py). Không tin đuôi tên."""
    if not data.startswith(b"PK\x03\x04"):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
    except (zipfile.BadZipFile, ValueError, OSError):
        return False
    return "[Content_Types].xml" in names and "xl/workbook.xml" in names


def check_zip_safe(data):
    """Chặn zip bomb TRƯỚC khi openpyxl mở tệp; vi phạm thì ném `ExcelFileError`.

    1. Duyệt danh sách mục (chưa giải nén): tổng `file_size` > 100 MB, hoặc tỉ lệ nén (tổng, hoặc
       từng mục từ 1 MiB trở lên) > 100 lần → từ chối.
    2. Header zip có thể khai man kích thước, nên đếm lại dung lượng THỰC khi giải nén theo từng
       khối (không giữ trong bộ nhớ) và dừng ngay khi vượt 100 MB.
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, ValueError, OSError) as exc:
        raise ExcelFileError() from exc
    with archive:
        infos = archive.infolist()
        total_size = sum(info.file_size for info in infos)
        total_compressed = sum(info.compress_size for info in infos)
        if total_size > MAX_UNZIPPED_BYTES:
            raise ExcelFileError()
        if total_size >= RATIO_CHECK_MIN_BYTES and total_size > MAX_COMPRESSION_RATIO * max(
            total_compressed, 1
        ):
            raise ExcelFileError()
        for info in infos:
            if (
                info.file_size >= RATIO_CHECK_MIN_BYTES
                and info.file_size > MAX_COMPRESSION_RATIO * max(info.compress_size, 1)
            ):
                raise ExcelFileError()
        actual = 0
        try:
            for info in infos:
                if info.is_dir():
                    continue
                with archive.open(info) as member:
                    while chunk := member.read(_CHUNK):
                        actual += len(chunk)
                        if actual > MAX_UNZIPPED_BYTES:
                            raise ExcelFileError()
        except (zipfile.BadZipFile, ValueError, OSError, EOFError, RuntimeError) as exc:
            raise ExcelFileError() from exc
