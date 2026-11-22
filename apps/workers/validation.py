"""Kiểm tra dữ liệu hồ sơ ở máy chủ (models.md mục 4.5, lam-ro-yeu-cau.md câu 5, 16).

Một nơi duy nhất cho form và service: form gọi để hiện lỗi dưới từng ô, service gọi lại để không
tin dữ liệu từ nguồn nào (form, Excel, nhận diện CCCD).

Mức kiểm tra (`level`):
- DRAFT: Nháp / Cần bổ sung, chỉ bắt buộc họ tên + SĐT.
- SUBMISSION: thêm các trường bắt buộc khi gửi duyệt; dùng khi sửa hồ sơ Đã xác minh (quyết định
  22/11/2026: sửa hồ sơ đã xác minh phải giữ hồ sơ đủ điều kiện gửi duyệt).
"""

import re
from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils import timezone

from apps.core.choices import Gender, IdDocType
from apps.core.validators import check_age, validate_id_number, validate_phone

from .duplicates import find_by_id_number, find_similar

DRAFT = "draft"
SUBMISSION = "submission"

# Trường của hồ sơ và của giấy tờ định danh (tên logic như PERSONAL_FIELDS).
WORKER_FIELDS = (
    "full_name",
    "date_of_birth",
    "gender",
    "nationality",
    "phone",
    "email",
    "current_address",
    "skills",
    "note",
)
IDENTITY_FIELDS = (
    "id_doc_type",
    "id_number",
    "old_id_number",
    "issue_date",
    "issue_place",
    "expiry_date",
    "hometown",
    "birth_registration_place",
    "permanent_address",
)

SUBMISSION_REQUIRED = {
    "date_of_birth": "Nhập ngày sinh.",
    "gender": "Chọn giới tính.",
    "nationality": "Nhập quốc tịch.",
    "current_address": "Nhập nơi ở hiện tại.",
    "id_doc_type": "Chọn loại giấy tờ.",
    "id_number": "Nhập số CCCD.",
}

MSG_UNDER_15 = "Không nhập hồ sơ người dưới 15 tuổi."
MSG_WARN_UNDER_18 = "Người này dưới 18 tuổi. Kiểm tra giấy tờ và quy định về sử dụng lao động."


@dataclass
class ValidationResult:
    errors: dict = field(default_factory=dict)  # tên trường -> thông báo lỗi
    warnings: list = field(default_factory=list)  # chuỗi cảnh báo, không chặn lưu
    duplicate: object = None  # hồ sơ đang giữ số định danh trùng (để "Mở hồ sơ cũ")
    similar: list = field(default_factory=list)  # SimilarMatch (trùng SĐT / họ tên + ngày sinh)


def clean_id_number(value):
    """Bỏ khoảng trắng đầu/cuối và giữa các chữ số ("0791 2345 6789"); không bỏ ký tự khác."""
    return re.sub(r"\s+", "", value or "")


def validate_contacts(rows):
    """Người liên hệ khẩn cấp: dòng có dữ liệu phải đủ 3 trường.

    Trả {chỉ số dòng: {trường: lỗi}}."""
    errors = {}
    for index, row in enumerate(rows or ()):
        if row.get("delete"):
            continue
        values = {k: (row.get(k) or "").strip() for k in ("full_name", "relationship", "phone")}
        if not any(values.values()):
            continue
        row_errors = {}
        if not values["full_name"]:
            row_errors["full_name"] = "Nhập họ tên người liên hệ."
        if not values["relationship"]:
            row_errors["relationship"] = "Nhập mối quan hệ."
        if not values["phone"]:
            row_errors["phone"] = "Nhập số điện thoại."
        else:
            try:
                validate_phone(values["phone"])
            except ValidationError as exc:
                row_errors["phone"] = exc.messages[0]
        if row_errors:
            errors[index] = row_errors
    return errors


def validate_worker_data(data, *, instance=None, level=DRAFT, today=None):
    """Kiểm tra dữ liệu hồ sơ + giấy tờ. `data` có thể thiếu khóa (cập nhật một phần): khi sửa
    hồ sơ có sẵn (`instance`), trường vắng mặt giữ nguyên giá trị cũ khi tính các quy tắc chéo."""
    today = today or timezone.localdate()
    result = ValidationResult()
    errors = result.errors

    def value(name):
        if name in data:
            return data[name]
        if instance is None:
            return None
        if name in IDENTITY_FIELDS:
            identity = getattr(instance, "identity", None)
            if identity is None:
                return None
            attr = {
                "id_number": "id_number_enc",
                "old_id_number": "old_id_number_enc",
                "permanent_address": "permanent_address_enc",
            }.get(name, name)
            return getattr(identity, attr, None)
        return getattr(instance, name, None)

    def text(name):
        current = value(name)
        return current.strip() if isinstance(current, str) else current

    if not text("full_name"):
        errors["full_name"] = "Nhập họ và tên."
    phone = text("phone")
    if not phone:
        errors["phone"] = "Nhập số điện thoại."
    else:
        try:
            validate_phone(phone)
        except ValidationError as exc:
            errors["phone"] = exc.messages[0]
    email = text("email")
    if email:
        try:
            validate_email(email)
        except ValidationError:
            errors["email"] = "Email không đúng định dạng."

    gender = text("gender")
    if gender and gender not in Gender.values:
        errors["gender"] = "Chọn giới tính Nam hoặc Nữ."
    id_doc_type = text("id_doc_type")
    if id_doc_type and id_doc_type not in IdDocType.values:
        errors["id_doc_type"] = "Chọn loại giấy tờ trong danh sách."

    # Tuổi (câu 16): dưới 15 chặn, 15 đến dưới 18 cảnh báo; chỉ kiểm tra khi đã nhập ngày sinh.
    birth = value("date_of_birth")
    if birth:
        if birth > today:
            errors["date_of_birth"] = "Ngày sinh không được ở tương lai."
        elif check_age(birth, today) == "block":
            errors["date_of_birth"] = MSG_UNDER_15
        elif check_age(birth, today) == "warn":
            result.warnings.append(MSG_WARN_UNDER_18)

    # Số định danh: 12 chữ số và không trùng (so giá trị băm).
    id_number = clean_id_number(value("id_number"))
    if id_number:
        try:
            validate_id_number(id_number)
        except ValidationError as exc:
            errors["id_number"] = exc.messages[0]
        else:
            duplicate = find_by_id_number(id_number, exclude_worker=instance)
            if duplicate is not None:
                errors["id_number"] = f"Số CCCD này đã có hồ sơ {duplicate.worker_code}."
                result.duplicate = duplicate
    old_id = clean_id_number(value("old_id_number"))
    if old_id and not re.fullmatch(r"\d{9}|\d{12}", old_id):
        errors["old_id_number"] = "Số CMND cũ phải gồm 9 hoặc 12 chữ số."

    issue_date = value("issue_date")
    if issue_date and birth and issue_date <= birth:
        errors["issue_date"] = "Ngày cấp phải sau ngày sinh."

    if level == SUBMISSION:
        for name, message in SUBMISSION_REQUIRED.items():
            if not text(name) and name not in errors:
                errors[name] = message

    # Chưa có số định danh: cảnh báo trùng SĐT hoặc họ tên + ngày sinh (câu 5), không chặn.
    if not id_number:
        result.similar = find_similar(
            phone=phone if "phone" not in errors else "",
            full_name=text("full_name"),
            date_of_birth=birth,
            exclude_worker=instance,
        )
        for match in result.similar:
            reasons = []
            if match.by_phone:
                reasons.append("số điện thoại")
            if match.by_name_dob:
                reasons.append("họ tên và ngày sinh")
            result.warnings.append(
                f"Có thể trùng hồ sơ {match.worker.worker_code} (cùng {' và '.join(reasons)})."
            )
    return result
