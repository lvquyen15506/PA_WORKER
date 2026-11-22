"""Trường nhận diện từ CCCD/thẻ Căn cước và cách chuẩn hóa từng trường (docs/yeu-cau.md mục V).

Danh sách trường cố định trong code; thứ tự và dấu phân cách trong QR là cấu hình (`QrFormat`,
câu 20). Giá trị sai định dạng thì bỏ trống (không đoán, không sửa ký tự).

Giá trị chuẩn hóa là chuỗi: ngày dạng ISO `yyyy-mm-dd`, giới tính là `MALE`/`FEMALE`.
"""

import datetime
import re

from apps.core.choices import Gender

SKIP = "skip"

# (tên logic, nhãn tiếng Việt). Tên khớp WORKER_FIELDS / IDENTITY_FIELDS (apps.workers.validation).
FIELD_LABELS = {
    "id_number": "Số CCCD",
    "old_id_number": "Số CMND cũ",
    "full_name": "Họ và tên",
    "date_of_birth": "Ngày sinh",
    "gender": "Giới tính",
    "nationality": "Quốc tịch",
    "permanent_address": "Nơi thường trú",
    "hometown": "Quê quán",
    "birth_registration_place": "Nơi đăng ký khai sinh",
    "issue_date": "Ngày cấp",
    "issue_place": "Nơi cấp",
    "expiry_date": "Có giá trị đến",
}
FIELD_NAMES = tuple(FIELD_LABELS)
DATE_FIELDS = ("date_of_birth", "issue_date", "expiry_date")

# Định dạng ngày cho phép chọn ở Cài đặt: tên -> mẫu strptime.
DATE_FORMATS = {
    "ddmmyyyy": "%d%m%Y",
    "dd/mm/yyyy": "%d/%m/%Y",
    "dd-mm-yyyy": "%d-%m-%Y",
    "yyyymmdd": "%Y%m%d",
    "yyyy-mm-dd": "%Y-%m-%d",
}

_MAX_TEXT = 255


def _digits(raw):
    return re.sub(r"\s", "", raw or "")


def _id_number(raw, date_format):
    value = _digits(raw)
    return value if re.fullmatch(r"\d{12}", value) else None


def _old_id_number(raw, date_format):
    value = _digits(raw)
    return value if re.fullmatch(r"\d{9}|\d{12}", value) else None


def parse_date(raw, date_format):
    """Chuỗi ngày theo `date_format` -> `datetime.date`, sai thì None."""
    pattern = DATE_FORMATS.get(date_format)
    text = (raw or "").strip()
    if not pattern or not text:
        return None
    try:
        return datetime.datetime.strptime(text, pattern).date()
    except ValueError:
        return None


def _date(raw, date_format):
    parsed = parse_date(raw, date_format)
    return parsed.isoformat() if parsed else None


def parse_gender(raw):
    text = (raw or "").strip().lower()
    if text == "nam":
        return Gender.MALE.value
    if text in ("nữ", "nu", "nư"):
        return Gender.FEMALE.value
    return None


def _gender(raw, date_format):
    return parse_gender(raw)


def _text(raw, date_format):
    value = re.sub(r"\s+", " ", raw or "").strip()
    return value[:_MAX_TEXT] if value else None


_NORMALIZERS = {
    "id_number": _id_number,
    "old_id_number": _old_id_number,
    "date_of_birth": _date,
    "issue_date": _date,
    "expiry_date": _date,
    "gender": _gender,
}


def normalize(name, raw, date_format="ddmmyyyy"):
    """Chuẩn hóa một giá trị thô; trả None nếu rỗng hoặc sai định dạng (để trống, không đoán)."""
    if name not in FIELD_LABELS:
        raise ValueError(f"Trường nhận diện không hợp lệ: {name!r}")
    return _NORMALIZERS.get(name, _text)(raw, date_format)
