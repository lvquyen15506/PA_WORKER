"""Kiểm tra tệp tải lên (yeu-cau.md mục IV.6, VIII; models.md 4.5): định dạng THẬT theo chữ ký
nội dung (magic bytes), không tin đuôi tên hay Content-Type do trình duyệt gửi; tối đa 10 MB.

Định dạng cho phép: JPG, PNG, PDF, DOC, DOCX. Đuôi tên tệp phải khớp với nội dung.
"""

import io
import os
import zipfile
from collections import namedtuple

from django.core.exceptions import ValidationError

MAX_SIZE = 10 * 1024 * 1024  # 10 MB

DetectedFile = namedtuple("DetectedFile", ["kind", "mime", "ext"])

FORMATS = {
    "JPG": ("image/jpeg", ".jpg", {".jpg", ".jpeg"}),
    "PNG": ("image/png", ".png", {".png"}),
    "PDF": ("application/pdf", ".pdf", {".pdf"}),
    "DOC": ("application/msword", ".doc", {".doc"}),
    "DOCX": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".docx",
        {".docx"},
    ),
}
INLINE_KINDS = {"JPG", "PNG", "PDF"}  # xem trước được trên trình duyệt; DOC/DOCX chỉ tải xuống

MSG_FORMAT = "Chỉ nhận tệp JPG, PNG, PDF, DOC hoặc DOCX."
MSG_TOO_BIG = "Tệp vượt quá 10 MB."
MSG_EMPTY = "Tệp rỗng."
MSG_EXT = "Đuôi tên tệp không khớp với nội dung tệp. Hãy chọn đúng tệp."

_OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_WORD_STREAM = "WordDocument".encode("utf-16-le")  # tên luồng chính của tệp .doc (Word 97–2003)


def _is_docx(data):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
    except (zipfile.BadZipFile, ValueError, OSError):
        return False
    return "[Content_Types].xml" in names and "word/document.xml" in names


def detect_kind(data):
    """Nhận dạng định dạng thật từ nội dung; None nếu không thuộc 5 định dạng được phép."""
    if data.startswith(b"\xff\xd8\xff"):
        return "JPG"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG"
    if data.startswith(b"%PDF-"):
        return "PDF"
    if data.startswith(b"PK\x03\x04") and _is_docx(data):
        return "DOCX"
    # .xls, .ppt cũng là OLE: phải có luồng WordDocument mới là .doc.
    if data.startswith(_OLE) and _WORD_STREAM in data:
        return "DOC"
    return None


def validate_upload(uploaded):
    """Kiểm tra một tệp tải lên (UploadedFile).

    Trả DetectedFile hoặc ném ValidationError tiếng Việt. Đọc toàn bộ nội dung (đã giới hạn
    10 MB) rồi trả con trỏ về đầu tệp.
    """
    size = getattr(uploaded, "size", None)
    if size is not None and size > MAX_SIZE:
        raise ValidationError(MSG_TOO_BIG)
    uploaded.seek(0)
    data = uploaded.read(MAX_SIZE + 1)
    uploaded.seek(0)
    if len(data) > MAX_SIZE:
        raise ValidationError(MSG_TOO_BIG)
    if not data:
        raise ValidationError(MSG_EMPTY)
    kind = detect_kind(data)
    if kind is None:
        raise ValidationError(MSG_FORMAT)
    mime, ext, allowed_ext = FORMATS[kind]
    given_ext = os.path.splitext(getattr(uploaded, "name", "") or "")[1].lower()
    if given_ext not in allowed_ext:
        raise ValidationError(MSG_EXT)
    return DetectedFile(kind, mime, ext)
