"""Đọc mã QR offline (docs/yeu-cau.md mục V bước 2). Bộ đọc chính là zxing-cpp (byte gốc, giải
UTF-8); pyzbar và OpenCV chỉ là dự phòng vì zbar tự đoán bảng mã và làm mất chữ có dấu."""

from collections import namedtuple

import cv2
import zxingcpp
from pyzbar import pyzbar
from pyzbar.pyzbar import ZBarSymbol

from .fields import plausible_qr_text

# rect: (trái, trên, rộng, cao) theo tọa độ ảnh gốc, để che vùng QR trước khi OCR.
QrReading = namedtuple("QrReading", ["text", "rect"])


def _candidates(data):
    """Các cách hiểu byte gốc của QR, theo thứ tự thử. zbar đôi khi đoán sai bảng mã (UTF-8 bị hiểu
    thành Shift-JIS) nên trả chữ Nhật/Trung; khi đó mã hóa ngược về Shift-JIS rồi giải UTF-8."""
    try:
        first = data.decode("utf-8")
    except UnicodeDecodeError:
        first = data.decode("latin-1")
    yield first
    for codec in ("shift_jis", "cp932"):
        try:
            yield first.encode(codec).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue


def decode_text(data, extra=()):
    """Byte gốc của QR -> chuỗi hợp lệ đầu tiên (chỉ chữ Latin, số, dấu câu). `extra`: các chuỗi
    dự phòng (ví dụ kết quả OpenCV) thử sau cùng. Không có chuỗi hợp lệ thì trả cách hiểu đầu tiên
    (các trường chữ sẽ bị loại ở bộ tách QR, HR nhập tay)."""
    options = [*_candidates(data), *extra]
    for text in options:
        if plausible_qr_text(text):
            return text.strip()
    return options[0].strip()


def _opencv_text(gray):
    """Giải mã dự phòng bằng cv2.QRCodeDetector (hiểu byte là UTF-8). Lỗi thì trả rỗng."""
    try:
        text, _, _ = cv2.QRCodeDetector().detectAndDecode(gray)
    except cv2.error:
        return ""
    return text or ""


def _attempts(gray):
    """Các biến thể ảnh thử lần lượt (ảnh, tỷ lệ so với ảnh gốc)."""
    yield gray, 1.0
    yield cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(gray), 1.0
    yield cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC), 2.0
    yield cv2.resize(gray, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA), 0.5


def _zxing_read(variant, scale):
    """Bộ đọc CHÍNH: zxing-cpp trả byte gốc của QR (không đoán bảng mã như zbar), giải UTF-8.
    Trả QrReading hoặc None."""
    try:
        results = zxingcpp.read_barcodes(variant, formats=zxingcpp.BarcodeFormat.QRCode)
    except Exception:  # lỗi thư viện không được làm hỏng cả quy trình nhận diện: dùng dự phòng
        return None
    for result in results:
        text = decode_text(bytes(result.bytes))
        if not text:
            continue
        pos = result.position
        xs = [p.x for p in (pos.top_left, pos.top_right, pos.bottom_left, pos.bottom_right)]
        ys = [p.y for p in (pos.top_left, pos.top_right, pos.bottom_left, pos.bottom_right)]
        rect = tuple(
            round(v / scale) for v in (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        )
        return QrReading(text, rect)
    return None


def read_qr(gray, budget=None):
    """Mảng xám -> QrReading hoặc None. Dừng sớm khi hết ngân sách thời gian. Mỗi biến thể ảnh thử
    zxing-cpp (chính) trước, rồi pyzbar và OpenCV (dự phòng)."""
    for variant, scale in _attempts(gray):
        if budget is not None and budget.expired:
            budget.mark_exhausted()
            return None
        reading = _zxing_read(variant, scale)
        if reading is not None:
            return reading
        for symbol in pyzbar.decode(variant, symbols=[ZBarSymbol.QRCODE]):
            text = decode_text(symbol.data)
            if text and not plausible_qr_text(text):
                # Cả zbar lẫn bản sửa Shift-JIS đều không ra chữ hợp lệ: thử bộ giải mã của OpenCV.
                fallback = _opencv_text(variant).strip()
                if fallback and plausible_qr_text(fallback):
                    text = fallback
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
