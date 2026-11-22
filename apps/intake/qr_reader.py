"""Đọc mã QR offline bằng pyzbar (docs/yeu-cau.md mục V bước 2)."""

from collections import namedtuple

import cv2
from pyzbar import pyzbar
from pyzbar.pyzbar import ZBarSymbol

# rect: (trái, trên, rộng, cao) theo tọa độ ảnh gốc, để che vùng QR trước khi OCR.
QrReading = namedtuple("QrReading", ["text", "rect"])


def _decode_text(data):
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")


def _attempts(gray):
    """Các biến thể ảnh thử lần lượt (ảnh, tỷ lệ so với ảnh gốc)."""
    yield gray, 1.0
    yield cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(gray), 1.0
    yield cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC), 2.0
    yield cv2.resize(gray, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA), 0.5


def read_qr(gray, budget=None):
    """Mảng xám -> QrReading hoặc None. Dừng sớm khi hết ngân sách thời gian."""
    for variant, scale in _attempts(gray):
        if budget is not None and budget.expired:
            budget.mark_exhausted()
            return None
        for symbol in pyzbar.decode(variant, symbols=[ZBarSymbol.QRCODE]):
            text = _decode_text(symbol.data).strip()
            if text:
                r = symbol.rect
                rect = tuple(round(v / scale) for v in (r.left, r.top, r.width, r.height))
                return QrReading(text, rect)
    return None


def mask_rect(image, rect, margin=12):
    """Bản sao ảnh PIL với vùng QR tô trắng (để OCR không đọc nhiễu từ khối QR)."""
    from PIL import ImageDraw

    left, top, width, height = rect
    masked = image.copy()
    ImageDraw.Draw(masked).rectangle(
        [left - margin, top - margin, left + width + margin, top + height + margin], fill="white"
    )
    return masked
