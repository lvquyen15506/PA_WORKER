"""Mở ảnh an toàn, kiểm tra chất lượng, xóa EXIF (docs/yeu-cau.md mục V bước 1; Phase 5 quyết
định 6, 7).

- Ảnh khai báo quá `MAX_IMAGE_PIXELS` điểm ảnh bị từ chối ngay từ header, TRƯỚC khi giải nén và
  trước khi đưa vào OpenCV.
- `strip_metadata` ghi lại ảnh đã xoay theo EXIF, không còn EXIF/GPS/ICC/chú thích.
"""

import io
import warnings
from dataclasses import dataclass, field

import cv2
import numpy as np
from django.conf import settings
from PIL import Image, ImageOps, UnidentifiedImageError

MIN_WIDTH = 1000  # px (yêu cầu mục V)
MIN_SHARPNESS = 60.0  # phương sai Laplacian, đo trên ảnh chuẩn hóa về rộng 1000 px
MIN_BRIGHTNESS = 70.0  # độ sáng trung bình thang 0-255
MAX_BRIGHTNESS = 253.0  # ảnh giả nền trắng đạt khoảng 250; ảnh cháy sáng gần 255
_NORMAL_WIDTH = 1000

MSG_TOO_LARGE = "Ảnh quá lớn (tối đa 40 triệu điểm ảnh). Hãy chụp lại hoặc giảm kích thước ảnh."
MSG_CANNOT_OPEN = "Không mở được ảnh. Hãy chọn tệp JPG hoặc PNG còn nguyên vẹn."
WARN_LOW_RES = "Ảnh có chiều ngang dưới 1000 px. Nên chụp lại ở độ phân giải cao hơn."
WARN_BLUR = "Ảnh bị mờ. Nên chụp lại cho nét."
WARN_DARK = "Ảnh quá tối. Nên chụp lại nơi đủ sáng."
WARN_BRIGHT = "Ảnh quá sáng hoặc bị lóa. Nên chụp lại."


class ImageRejected(Exception):
    """Ảnh không dùng được; `args[0]` là thông báo tiếng Việt cho người dùng."""


def _limit():
    return int(settings.MAX_IMAGE_PIXELS)


def load_image(data):
    """Bytes -> PIL.Image RGB đã xoay theo EXIF. Ném ImageRejected (tiếng Việt)."""
    Image.MAX_IMAGE_PIXELS = _limit()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(io.BytesIO(data))
            width, height = image.size  # chỉ đọc header
            if width * height > _limit():
                raise ImageRejected(MSG_TOO_LARGE)
            image.load()
    except ImageRejected:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ImageRejected(MSG_TOO_LARGE) from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ImageRejected(MSG_CANNOT_OPEN) from exc
    image = ImageOps.exif_transpose(image)
    return image.convert("RGB")


def to_gray(image):
    """PIL.Image -> mảng xám cho OpenCV."""
    return cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2GRAY)


def strip_metadata(image, kind="JPG"):
    """Ghi lại ảnh (đã xoay theo EXIF) không còn metadata. Trả bytes; kind: "JPG" hoặc "PNG"."""
    clean = Image.frombytes("RGB", image.size, image.convert("RGB").tobytes())
    buffer = io.BytesIO()
    if kind == "PNG":
        clean.save(buffer, format="PNG")
    else:
        clean.save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()


def rotate(image, degrees=90):
    """Xoay ngược chiều kim đồng hồ `degrees` độ (bội của 90)."""
    return image.rotate(degrees, expand=True)


@dataclass
class QualityReport:
    width: int
    height: int
    sharpness: float
    brightness: float
    warnings: list = field(default_factory=list)

    def as_dict(self):
        return {
            "width": self.width,
            "height": self.height,
            "sharpness": round(self.sharpness, 1),
            "brightness": round(self.brightness, 1),
            "warnings": list(self.warnings),
        }


def check_quality(image):
    """Độ phân giải, độ nét, độ sáng. Ảnh kém chỉ có cảnh báo; vẫn cho đi tiếp."""
    gray = to_gray(image)
    height, width = gray.shape
    scale = _NORMAL_WIDTH / width
    small = cv2.resize(gray, (_NORMAL_WIDTH, max(1, round(height * scale))))
    sharpness = float(cv2.Laplacian(small, cv2.CV_64F).var())
    brightness = float(gray.mean())
    report = QualityReport(width, height, sharpness, brightness)
    if width < MIN_WIDTH:
        report.warnings.append(WARN_LOW_RES)
    if sharpness < MIN_SHARPNESS:
        report.warnings.append(WARN_BLUR)
    if brightness < MIN_BRIGHTNESS:
        report.warnings.append(WARN_DARK)
    elif brightness > MAX_BRIGHTNESS:
        report.warnings.append(WARN_BRIGHT)
    return report
