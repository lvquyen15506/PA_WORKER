"""Tệp mẫu nhỏ, hợp lệ về chữ ký, dùng cho test tài liệu. Không chứa dữ liệu cá nhân thật."""

import io
import zipfile

from django.core.files.uploadedfile import SimpleUploadedFile

JPG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"x" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 64
PDF = b"%PDF-1.4\n% tai lieu mau\n%%EOF\n"
OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
DOC = OLE + b"\x00" * 64 + "WordDocument".encode("utf-16-le") + b"\x00" * 64
XLS = OLE + b"\x00" * 64 + "Workbook".encode("utf-16-le") + b"\x00" * 64
EXE = b"MZ\x90\x00\x03\x00\x00\x00" + b"x" * 64


def _zip(names):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in names:
            archive.writestr(name, "<x/>")
    return buffer.getvalue()


DOCX = _zip(["[Content_Types].xml", "word/document.xml"])
XLSX = _zip(["[Content_Types].xml", "xl/workbook.xml"])  # zip Office nhưng không phải Word

BY_KIND = {"JPG": JPG, "PNG": PNG, "PDF": PDF, "DOC": DOC, "DOCX": DOCX}
EXT = {"JPG": ".jpg", "PNG": ".png", "PDF": ".pdf", "DOC": ".doc", "DOCX": ".docx"}


def upload(kind="PDF", name=None):
    """UploadedFile hợp lệ của định dạng `kind`."""
    return SimpleUploadedFile(name or f"mau{EXT[kind]}", BY_KIND[kind])
