"""Tách trường từ chuỗi QR của CCCD theo cấu hình `QrFormat` (câu 20).

Dấu phân cách, thứ tự trường, định dạng ngày đọc từ cấu hình, KHÔNG viết cứng. Muốn thử thẻ thật
chỉ cần sửa cấu hình ở /cai-dat/ocr-qr/. Chuỗi không khớp cấu hình thì không điền gì.
"""

from dataclasses import dataclass, field

from apps.core.models import QrFormat

from .fields import FIELD_NAMES, SKIP, normalize


@dataclass
class QrResult:
    ok: bool = False
    values: dict = field(default_factory=dict)  # {tên trường: giá trị chuẩn hóa}
    error: str = ""


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
    values = {}
    for name, part in zip(order, parts, strict=True):
        if name == SKIP or name not in FIELD_NAMES or name in values:
            continue  # tên lạ hoặc lặp thì bỏ qua phần tử đó
        value = normalize(name, part, qr_format.date_format)
        if value:
            values[name] = value
    if "id_number" not in values:
        return QrResult(values={}, error="Số định danh trong QR không hợp lệ.")
    return QrResult(ok=True, values=values)


def choose_format(raw, doc_type=None):
    """Chọn cấu hình QR cho chuỗi `raw`. Trả (QrFormat, QrResult) hoặc (None, None).

    - `doc_type` có giá trị (HR chọn tay, hoặc nhận ra từ tiêu đề thẻ): chỉ dùng mẫu đó.
    - Không có: thử từng cấu hình đang bật theo thứ tự mã mẫu thẻ, lấy cấu hình tách được đầu tiên.
      Khi hai cấu hình giống nhau (câu 20) mẫu đứng trước được chọn.
    """
    formats = QrFormat.objects.order_by("id_doc_type")
    if doc_type:
        formats = formats.filter(id_doc_type=doc_type)
    else:
        formats = formats.filter(is_active=True)
    for qr_format in formats:
        result = parse_qr(raw, qr_format)
        if result.ok:
            return qr_format, result
    return None, None
