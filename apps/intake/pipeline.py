"""Nhận diện ảnh CCCD: kiểm tra ảnh -> đọc QR -> OCR trường còn thiếu (docs/yeu-cau.md mục V).

Kết quả chỉ là dữ liệu tạm cho màn hình đối chiếu; không ghi gì vào hồ sơ (HR phải xác nhận).
Quy tắc tô vàng (`low = True`): trường OCR có độ tin cậy dưới ngưỡng, hoặc trường mà mẫu thẻ phải
có nhưng không đọc được / sai định dạng (để trống, không đoán). Trường QR hợp lệ không tô vàng.
"""

import time

from . import imaging, qr_reader
from .budget import Budget
from .fields import CARD_FIELDS, FIELD_NAMES, UNKNOWN_CARD_FIELDS
from .ocr import detect_title, extract_fields, ocr_lines
from .qr import choose_format

WARN_TIMEOUT = "Hết thời gian xử lý, vui lòng kiểm tra tay."
SIDE_LABEL = {"front": "Mặt trước", "back": "Mặt sau"}


def _expected(doc_type, sides):
    layout = CARD_FIELDS.get(doc_type, UNKNOWN_CARD_FIELDS)
    return {name for side in sides for name in layout[side]}


def _pick_type(chosen, title, raw_qr):
    """Trả (mã mẫu thẻ | None, nguồn, QrFormat | None, QrResult | None)."""
    if raw_qr:
        hint = chosen or {"CAN_CUOC_2024": "CAN_CUOC_2024", "legacy": "CCCD_2021"}.get(title)
        qr_format, qr_result = choose_format(raw_qr, doc_type=hint)
        if qr_format is None and not chosen:
            qr_format, qr_result = choose_format(raw_qr)  # tiêu đề đoán sai: thử mọi cấu hình
        if qr_format is not None:
            return (
                (chosen or qr_format.id_doc_type),
                "chosen" if chosen else "qr",
                qr_format,
                qr_result,
            )
    if chosen:
        return chosen, "chosen", None, None
    if title == "CAN_CUOC_2024":
        return "CAN_CUOC_2024", "title", None, None
    if title == "legacy":
        return "CCCD_2016", "title", None, None
    return None, "none", None, None


def recognize(front, back, doc_type="", threshold=80, budget=None, engine=None):
    """Nhận diện một hoặc hai mặt thẻ. `front`/`back`: PIL.Image hoặc None; `doc_type`: mã mẫu
    thẻ HR đã chọn ("" = tự nhận biết); `threshold`: ngưỡng tin cậy OCR (%); `engine`: hàm OCR
    thay thế (test). Trả dict JSON-được (xem docs/thiet-ke/models.md, IntakeSession.result_enc)."""
    budget = budget or Budget()
    images = {side: img for side, img in (("front", front), ("back", back)) if img is not None}
    timings = {}
    warnings, quality = [], {}

    started = time.monotonic()
    for side, image in images.items():
        report = imaging.check_quality(image)
        quality[side] = report.as_dict()
        warnings += [f"{SIDE_LABEL[side]}: {text}" for text in report.warnings]
    timings["quality"] = round(time.monotonic() - started, 3)

    started = time.monotonic()
    reading, qr_side = None, None
    for side, image in images.items():
        reading = qr_reader.read_qr(imaging.to_gray(image), budget)
        if reading:
            qr_side = side
            break
    timings["qr"] = round(time.monotonic() - started, 3)

    started = time.monotonic()
    lines, failed = [], False
    for side, image in images.items():
        target = qr_reader.mask_rect(image, reading.rect) if side == qr_side else image
        side_lines = ocr_lines(target, budget, engine)
        if side_lines is None:
            failed = True
        else:
            lines += side_lines
    timings["ocr"] = round(time.monotonic() - started, 3)

    raw_qr = reading.text if reading else None
    title = detect_title(lines)
    card_type, type_source, qr_format, qr_result = _pick_type(doc_type, title, raw_qr)
    qr_values = qr_result.values if qr_result else {}
    ocr_values = extract_fields(lines)
    wanted = _expected(card_type, images)

    fields = {}
    for name in FIELD_NAMES:
        found = ocr_values.get(name)
        if name in qr_values:
            fields[name] = {
                "value": qr_values[name],
                "source": "QR",
                "confidence": None,
                "low": False,
            }
        elif found is not None and found.value:
            fields[name] = {
                "value": found.value,
                "source": "OCR",
                "confidence": round(found.confidence, 1),
                "low": found.confidence < threshold,
            }
        elif name in wanted:
            fields[name] = {"value": None, "source": None, "confidence": None, "low": True}

    # Ngân sách đã cạn (kể cả khi giai đoạn cuối chạy quá phần được cấp) thì phải báo kiểm tra tay.
    out_of_time = bool(failed or budget.exhausted or budget.expired)
    if out_of_time:
        warnings.append(WARN_TIMEOUT)
    timings["total"] = round(budget.elapsed(), 3)
    return {
        "doc_type": card_type,
        "doc_type_source": type_source,
        "quality": quality,
        "warnings": warnings,
        "qr": {
            "raw": raw_qr,
            "side": qr_side,
            "format": qr_format.id_doc_type if qr_format else None,
        },
        "fields": fields,
        "timings": timings,
        "budget_exhausted": out_of_time,
    }
