"""Phần HTTP của việc xem/tải tài liệu: tên tệp an toàn trong Content-Disposition và header bảo vệ.

Tên tệp gốc do người dùng cung cấp nên không tin: bỏ ký tự điều khiển, dấu ngoặc kép, gạch chéo...
trước khi đưa vào header (chống chèn header, chèn tham số, đường dẫn). Tên tiếng Việt giữ nguyên
qua `filename*` (RFC 5987/6266), kèm `filename` chỉ ASCII cho trình duyệt cũ.
"""

import re
import unicodedata
from urllib.parse import quote

from django.http import FileResponse

from .validators import FORMATS, INLINE_KINDS

MAX_NAME_LENGTH = 100  # độ dài tên (tính cả đuôi) đưa vào header
DEFAULT_NAME = "tai-lieu"
_BAD_CHARS = re.compile(r'["\\/;]')
_BAD_CATEGORIES = {"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"}  # điều khiển, định dạng (bidi), lạ


def safe_filename(original_name, fallback_ext=""):
    """Tên tệp an toàn (còn dấu tiếng Việt) để hiển thị cho người tải về."""
    name = unicodedata.normalize("NFC", original_name or "")
    name = re.split(r"[\\/]", name)[-1]  # bỏ đường dẫn: "..\\a.pdf" -> "a.pdf"
    name = "".join(ch for ch in name if unicodedata.category(ch) not in _BAD_CATEGORIES)
    name = _BAD_CHARS.sub("", name).strip()
    stem, ext = _split_ext(name)
    stem = stem.lstrip(".").strip()  # không để tên bắt đầu bằng dấu chấm (tệp ẩn, "..")
    if not stem:
        stem = DEFAULT_NAME
    if not ext:
        ext = fallback_ext
    stem = stem[: max(1, MAX_NAME_LENGTH - len(ext))].rstrip()
    return f"{stem}{ext}"


def _split_ext(name):
    match = re.search(r"(\.[A-Za-z0-9]{1,5})$", name)
    return (name[: match.start()], match.group(1)) if match else (name, "")


def ascii_filename(name):
    """Bản chỉ ASCII của tên (bỏ dấu, đ -> d, ký tự lạ -> "_")."""
    text = unicodedata.normalize("NFD", name)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D")
    return re.sub(r"[^A-Za-z0-9._ -]", "_", text)


def safe_content_disposition(disposition, original_name, fallback_ext=""):
    """Giá trị header Content-Disposition (disposition = "inline" | "attachment"), một dòng,
    không chứa ký tự điều khiển; có cả filename (ASCII) và filename* (UTF-8, mã hóa phần trăm)."""
    if disposition not in ("inline", "attachment"):
        raise ValueError(disposition)
    name = safe_filename(original_name, fallback_ext)
    plain = ascii_filename(name)
    encoded = quote(name, safe="")
    return f"{disposition}; filename=\"{plain}\"; filename*=UTF-8''{encoded}"


def file_response(document, *, inline):
    """Phản hồi trả tệp của một tài liệu: Content-Type theo định dạng thật đã lưu; nosniff; xem
    trước (inline) thêm Content-Security-Policy: sandbox để tệp không chạy script trong trang."""
    kind = next((k for k, (mime, _, _) in FORMATS.items() if mime == document.mime_type), None)
    ext = FORMATS[kind][1] if kind else ""
    if inline and kind not in INLINE_KINDS:
        raise ValueError("Định dạng này chỉ cho tải xuống.")
    response = FileResponse(
        document.stored_file.open("rb"),
        content_type=document.mime_type or "application/octet-stream",
    )
    response["Content-Disposition"] = safe_content_disposition(
        "inline" if inline else "attachment", document.original_name, ext
    )
    response["X-Content-Type-Options"] = "nosniff"
    if inline:
        response["Content-Security-Policy"] = "sandbox"
    return response
