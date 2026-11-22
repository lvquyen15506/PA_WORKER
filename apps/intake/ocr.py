"""OCR offline bằng Tesseract (gói `vie`) cho ảnh CCCD (docs/yeu-cau.md mục V bước 3).

Tách trường theo NHÃN trên dòng chữ ("Họ và tên:", "Ngày sinh:"...), không theo tọa độ cố định.
Độ tin cậy của một trường là độ tin cậy THẤP NHẤT trong các từ của trường đó (0-100). Giá trị sai
định dạng thì để trống, không sửa ký tự, không đoán.
"""

from collections import namedtuple
from dataclasses import dataclass

import cv2
import numpy as np
import pytesseract
from django.conf import settings
from pytesseract import Output

from apps.core.text import compute_name_search

from .fields import FIELD_NAMES, OCR_LABELS, normalize
from .imaging import to_gray

Word = namedtuple("Word", ["text", "conf", "line_key"])

OCR_DATE_FORMAT = "dd/mm/yyyy"
MIN_VALUE_CONFIDENCE = 30.0  # dưới mức này không hiện giá trị (không đoán chữ mờ)
_TARGET_WIDTH = 1800  # Tesseract đọc tốt nhất khi chữ đủ lớn; ảnh hẹp hơn thì phóng to


class OcrTimeout(Exception):
    """Một lần gọi Tesseract quá thời gian cho phép."""


def _prepare(image):
    gray = to_gray(image)
    height, width = gray.shape
    if width < _TARGET_WIDTH:
        scale = _TARGET_WIDTH / width
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return np.ascontiguousarray(gray)


def tesseract_engine(image, timeout):
    """Chạy Tesseract `vie` trên một ảnh PIL; trả danh sách `Word`. Ném OcrTimeout khi quá giờ."""
    try:
        data = pytesseract.image_to_data(
            _prepare(image),
            lang="vie",
            config="--psm 6",
            output_type=Output.DICT,
            timeout=timeout,
        )
    except RuntimeError as exc:
        if "timeout" in str(exc).lower():
            raise OcrTimeout from exc
        raise
    words = []
    for i, text in enumerate(data["text"]):
        text = (text or "").strip()
        conf = float(data["conf"][i])
        if not text or conf < 0:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        words.append(Word(text, conf, key))
    return words


def group_lines(words):
    """Gom từ thành dòng, giữ thứ tự xuất hiện. Trả danh sách danh sách `Word`."""
    lines, index = [], {}
    for word in words:
        if word.line_key not in index:
            index[word.line_key] = len(lines)
            lines.append([])
        lines[index[word.line_key]].append(word)
    return lines


def ocr_lines(image, budget, engine=None):
    """OCR một ảnh trong phần ngân sách còn lại. Trả danh sách dòng, hoặc None nếu không đọc được
    (hết ngân sách hoặc quá giờ); khi đó `budget.exhausted` được đặt."""
    engine = engine or tesseract_engine
    timeout = budget.timeout_for(settings.OCR_TIMEOUT_SECONDS)
    if timeout <= 0:
        budget.mark_exhausted()
        return None
    try:
        return group_lines(engine(image, timeout))
    except OcrTimeout:
        budget.mark_exhausted()
        return None


def _norm_token(text):
    return compute_name_search(text).strip(":;.,-")


def detect_title(lines):
    """Nhận mẫu thẻ từ tiêu đề: "legacy" (CĂN CƯỚC CÔNG DÂN, mẫu 2016/2021),
    "CAN_CUOC_2024" (CĂN CƯỚC) hoặc None."""
    for line in lines:
        text = compute_name_search(" ".join(w.text for w in line))
        if "can cuoc cong dan" in text:
            return "legacy"
    for line in lines:
        text = compute_name_search(" ".join(w.text for w in line))
        if "can cuoc" in text:
            return "CAN_CUOC_2024"
    return None


@dataclass
class OcrField:
    value: str | None  # giá trị chuẩn hóa; None nếu sai định dạng hoặc rỗng
    confidence: float  # 0-100, thấp nhất trong các từ của trường
    raw: str


def _match_label(tokens, labels):
    """Trả (số token của nhãn) nếu dòng bắt đầu bằng một trong các nhãn, ngược lại 0."""
    norm = [_norm_token(t.text) for t in tokens]
    for label in labels:
        k = len(label)
        if tuple(norm[:k]) != label:
            continue
        if k == 1:  # nhãn "Số" quá ngắn: bắt buộc có dấu hai chấm để khỏi nhầm "Số 5 Đường..."
            tail = tokens[0].text.rstrip()
            following = tokens[1].text if len(tokens) > 1 else ""
            if not (tail.endswith((":", ";")) or following.startswith((":", ";"))):
                continue
        return k
    return 0


def extract_fields(lines):
    """Tách trường theo nhãn. Trả {tên trường: OcrField}; mỗi trường lấy dòng khớp đầu tiên."""
    found = {}
    for line in lines:
        for name in FIELD_NAMES:
            if name in found:
                continue
            k = _match_label(line, OCR_LABELS.get(name, []))
            if not k:
                continue
            value_words = line[k:]
            while value_words and not value_words[0].text.strip(":;"):
                value_words = value_words[1:]  # dấu ":" đứng riêng
            raw = " ".join(w.text for w in value_words).lstrip(":; ").strip()
            conf = min((w.conf for w in value_words), default=0.0)
            # Độ tin cậy dưới sàn: chữ gần như không đọc được, để trống thay vì hiện chữ rác.
            value = normalize(name, raw, OCR_DATE_FORMAT) if conf >= MIN_VALUE_CONFIDENCE else None
            found[name] = OcrField(value, conf, raw)
            break  # một dòng chỉ thuộc một trường
    return found
