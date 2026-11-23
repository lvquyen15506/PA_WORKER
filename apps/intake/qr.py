"""Tách trường từ chuỗi QR của CCCD theo cấu hình `QrFormat` (câu 20).

Dấu phân cách, thứ tự trường, định dạng ngày đọc từ cấu hình, KHÔNG viết cứng. Muốn thử thẻ thật
chỉ cần sửa cấu hình ở /cai-dat/ocr-qr/. Chuỗi không khớp cấu hình thì không điền gì.
"""

import datetime
from dataclasses import dataclass, field

from apps.core.models import QrFormat

from .fields import (
    FIELD_NAMES,
    SKIP,
    TEXT_FIELDS_FROM_QR,
    is_vietnamese_text,
    normalize,
    valid_full_name,
)
from .hints import CAN_CUOC_2024_START

WARN_BAD_QR = "Không đọc được QR đúng, vui lòng nhập tay."


@dataclass
class QrResult:
    ok: bool = False
    values: dict = field(default_factory=dict)  # {tên trường: giá trị chuẩn hóa}
    error: str = ""
    rejected: list = field(default_factory=list)  # trường chữ bị loại vì ký tự lạ (CJK...)


def parse_qr(raw, qr_format):
    """Tách chuỗi QR theo `qr_format` (QrFormat hoặc đối tượng có separator, field_order,
    date_format). `ok` chỉ đúng khi số phần tử khớp cấu hình và số định danh hợp lệ (12 số)."""
    text = (raw or "").strip()
    if not text:
        return QrResult(error="Không có dữ liệu QR.")
    parts = text.split(qr_format.separator)
    order = list(qr_format.field_order)
    if len(parts) != len(order):
        return QrResult(error="Chuỗi QR không khớp cấu hình (số phần tử khác nhau).")
    values, rejected = {}, []
    for name, part in zip(order, parts, strict=True):
        if name == SKIP or name not in FIELD_NAMES or name in values:
            continue  # tên lạ hoặc lặp thì bỏ qua phần tử đó
        value = normalize(name, part, qr_format.date_format)
        if value and name in TEXT_FIELDS_FROM_QR:
            good = valid_full_name(value) if name == "full_name" else is_vietnamese_text(value)
            if not good:  # ký tự CJK hoặc lạ: dấu hiệu đọc sai bảng mã; để trống, không đoán
                rejected.append(name)
                continue
        if value:
            values[name] = value
    if "id_number" not in values:
        return QrResult(values={}, error="Số định danh trong QR không hợp lệ.")
    return QrResult(ok=True, values=values, rejected=rejected)


def _issue_date(result):
    value = result.values.get("issue_date")
    return datetime.date.fromisoformat(value) if value else None


def choose_format(raw, doc_type=None):
    """Chọn cấu hình QR cho chuỗi `raw`. Trả (QrFormat, QrResult) hoặc (None, None).

    - `doc_type` có giá trị (HR chọn tay, hoặc nhận ra từ tiêu đề thẻ): chỉ dùng mẫu đó.
    - Không có: thử từng cấu hình đang bật. Khi nhiều cấu hình cùng tách được (hai mẫu có cấu hình
      giống nhau, câu 20) thì chọn theo NGÀY CẤP: trước 01/7/2024 không thể là Căn cước 2024;
      từ ngày đó thì ưu tiên Căn cước 2024. Không có ngày cấp thì mẫu đứng trước được chọn.
    """
    formats = QrFormat.objects.order_by("id_doc_type")
    if doc_type:
        formats = formats.filter(id_doc_type=doc_type)
    else:
        formats = formats.filter(is_active=True)
    matches = []
    for qr_format in formats:
        result = parse_qr(raw, qr_format)
        if result.ok:
            matches.append((qr_format, result))
    if not matches:
        return None, None
    if doc_type:
        return matches[0]  # mẫu do HR chọn (hoặc đoán từ tiêu đề) được giữ nguyên
    for qr_format, result in matches:
        issued = _issue_date(result)
        is_2024 = qr_format.id_doc_type == "CAN_CUOC_2024"
        if issued is not None and (issued >= CAN_CUOC_2024_START) == is_2024:
            return qr_format, result
    # Không mẫu nào khớp theo ngày cấp: bỏ mẫu Căn cước 2024 nếu ngày cấp trước 01/7/2024.
    possible = [
        m
        for m in matches
        if not (
            m[0].id_doc_type == "CAN_CUOC_2024"
            and _issue_date(m[1]) is not None
            and _issue_date(m[1]) < CAN_CUOC_2024_START
        )
    ]
    return (possible or matches)[0]
