"""Nhãn tiếng Việt cho tab "Lịch sử thay đổi": tên trường và giá trị trong nhật ký (người dùng
không đọc mã kỹ thuật như `full_name`, `VERIFIED`, `emergency_contacts[7].phone`)."""

import re

from apps.core.choices import (
    ConsentMethod,
    DocumentVerificationStatus,
    Gender,
    IdDocType,
    VerificationStatus,
)

DOCUMENT_TYPE = "documents.WorkerDocument"

_BASE_LABELS = {
    "full_name": "Họ và tên",
    "date_of_birth": "Ngày sinh",
    "gender": "Giới tính",
    "nationality": "Quốc tịch",
    "phone": "Số điện thoại",
    "email": "Email",
    "current_address": "Nơi ở hiện tại",
    "skills": "Kỹ năng",
    "note": "Ghi chú",
    "verification_status": "Trạng thái hồ sơ",
    "id_doc_type": "Loại giấy tờ",
    "id_number": "Số CCCD",
    "old_id_number": "Số CMND cũ",
    "issue_date": "Ngày cấp",
    "issue_place": "Nơi cấp",
    "expiry_date": "Có giá trị đến",
    "hometown": "Quê quán",
    "birth_registration_place": "Nơi đăng ký khai sinh",
    "permanent_address": "Nơi thường trú",
    "relationship": "Quan hệ",
    "school_name": "Trường",
    "major": "Ngành",
    "name": "Tên",
    "issuer": "Nơi cấp",
    "company_name": "Công ty",
    "job_title": "Chức danh",
    "description": "Mô tả",
    "expected_salary": "Mức lương mong muốn",
    "interview_notes": "Ghi chú phỏng vấn",
    "reject_reason": "Lý do không đạt",
    "resign_note": "Ghi chú nghỉ việc",
}
_PREFIXES = {
    "identity": "Giấy tờ",
    "employment": "Làm việc",
    "emergency_contacts": "Người liên hệ khẩn cấp",
    "applications": "Ứng tuyển",
    "education": "Học vấn",
    "certificates": "Chứng chỉ",
    "work_experiences": "Kinh nghiệm",
    "contracts": "Hợp đồng",
}
_COLLECTION = re.compile(r"(\w+)\[\d+\]\.(\w+)")


def field_label(field_name, object_type=""):
    """Tên trường tiếng Việt; không biết thì giữ nguyên chuỗi gốc để không mất thông tin."""
    if field_name == "verification_status" and object_type == DOCUMENT_TYPE:
        return "Trạng thái xác minh tài liệu"
    prefix, _, base = field_name.rpartition(".")
    match = _COLLECTION.fullmatch(field_name)
    if match:
        prefix, base = match.group(1), match.group(2)
    label = _BASE_LABELS.get(base)
    if label is None:
        return field_name
    if prefix in _PREFIXES and prefix != "identity":
        return f"{_PREFIXES[prefix]} – {label.lower()}"
    return label


def value_label(field_name, object_type, value):
    """Giá trị tiếng Việt: nhãn trạng thái/giới tính/loại giấy tờ, ngày dd/mm/yyyy."""
    if value is None or value == "":
        return None
    base = _COLLECTION.sub(r"\2", field_name).rpartition(".")[2]
    choices = {
        "verification_status": (
            DocumentVerificationStatus if object_type == DOCUMENT_TYPE else VerificationStatus
        ),
        "gender": Gender,
        "id_doc_type": IdDocType,
        "method": ConsentMethod,
    }.get(base)
    if choices is not None:
        try:
            return choices(value).label
        except ValueError:
            return value
    text = str(value)
    date = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
    if date:
        return f"{date.group(3)}/{date.group(2)}/{date.group(1)}"
    return text
