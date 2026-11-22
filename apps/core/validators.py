"""Kiểm tra dữ liệu dùng chung (docs/thiet-ke/models.md mục 4.5)."""

import re
from datetime import date

from django.core.exceptions import ValidationError


def validate_id_number(value):
    """Số định danh đúng 12 chữ số."""
    if not re.fullmatch(r"\d{12}", value or ""):
        raise ValidationError("Số CCCD phải gồm 12 chữ số.")


def validate_phone(value):
    """Số điện thoại đúng 10 chữ số, bắt đầu bằng 0."""
    if not re.fullmatch(r"0\d{9}", value or ""):
        raise ValidationError("Số điện thoại phải gồm 10 chữ số và bắt đầu bằng 0.")


def age_on(birth_date, today):
    years = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


def check_age(birth_date, today=None):
    """Câu 16: dưới 15 tuổi chặn lưu; 15 đến dưới 18 cảnh báo.

    Trả "block", "warn" hoặc None (chưa nhập ngày sinh thì None).
    """
    if birth_date is None:
        return None
    age = age_on(birth_date, today or date.today())
    if age < 15:
        return "block"
    if age < 18:
        return "warn"
    return None


def validate_birth_date(value):
    if check_age(value) == "block":
        raise ValidationError("Không nhập hồ sơ người dưới 15 tuổi.")
