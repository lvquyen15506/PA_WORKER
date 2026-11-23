"""Cấp mã hồ sơ / mã nhân viên (models.md mục 3.3, câu 6 và 27).

Khóa dòng CodeSequence bằng select_for_update trong giao dịch nên hai người cấp mã cùng lúc
không bao giờ nhận trùng. Trước khi trả mã còn kiểm tra mã chưa tồn tại (ví dụ mã nhập từ
Excel); đã tồn tại thì tăng tiếp. Bộ đếm chỉ tăng; mã đã cấp không bao giờ cấp lại.
"""

from django.db import transaction
from django.utils import timezone

from .choices import CodeType
from .models import CodeSequence, SystemSetting

MAX_CODE_LENGTH = 20  # độ dài tối đa của worker_code / employee_code


def _config(setting, code_type):
    if code_type == CodeType.WORKER:
        return (
            setting.worker_code_prefix,
            setting.worker_code_use_year,
            setting.worker_code_digits,
        )
    return (
        setting.employee_code_prefix,
        setting.employee_code_use_year,
        setting.employee_code_digits,
    )


def format_code(prefix, year, number, digits):
    """HS-2026-00123 khi có năm, CN-00456 khi không."""
    middle = f"{year}-" if year else ""
    return f"{prefix}-{middle}{number:0{digits}d}"


def _exists(code_type, code):
    from apps.workers.models import Worker

    field = "worker_code" if code_type == CodeType.WORKER else "employee_code"
    return Worker.objects.filter(**{field: code}).exists()


def next_code(code_type):
    """Cấp mã kế tiếp. Gọi trong cùng giao dịch với việc lưu hồ sơ nếu có thể."""
    code_type = CodeType(code_type)
    with transaction.atomic():
        prefix, use_year, digits = _config(SystemSetting.load(), code_type)
        year = timezone.localtime().year if use_year else 0
        # Tạo dòng bộ đếm nếu chưa có (get_or_create xử lý được hai luồng cùng tạo).
        CodeSequence.objects.get_or_create(code_type=code_type, year=year)
        seq = CodeSequence.objects.select_for_update().get(code_type=code_type, year=year)
        while True:
            seq.last_number += 1
            code = format_code(prefix, year, seq.last_number, digits)
            if not _exists(code_type, code):
                break
        if len(code) > MAX_CODE_LENGTH:
            raise ValueError(
                f"Mã {code!r} dài quá {MAX_CODE_LENGTH} ký tự; giảm tiền tố hoặc số chữ số."
            )
        seq.save(update_fields=["last_number"])
        return code


def preview_code(code_type, setting=None):
    """Mã sẽ được cấp ở lần kế tiếp theo cấu hình hiện tại; KHÔNG tăng bộ đếm (trang Cài đặt)."""
    code_type = CodeType(code_type)
    prefix, use_year, digits = _config(setting or SystemSetting.load(), code_type)
    year = timezone.localtime().year if use_year else 0
    seq = CodeSequence.objects.filter(code_type=code_type, year=year).first()
    number = seq.last_number if seq else 0
    while True:
        number += 1
        code = format_code(prefix, year, number, digits)
        if not _exists(code_type, code):
            return code


def bump_sequence(code_type, code):
    """Đẩy bộ đếm lên số của mã cũ nhập từ Excel, chỉ khi mã khớp định dạng đang cấu hình
    (câu 27). Mã khác định dạng không đụng tới bộ đếm. Trả True nếu khớp định dạng."""
    import re

    code_type = CodeType(code_type)
    with transaction.atomic():
        prefix, use_year, digits = _config(SystemSetting.load(), code_type)
        pattern = (
            rf"{re.escape(prefix)}-(\d{{4}})-(\d{{{digits},}})"
            if use_year
            else rf"{re.escape(prefix)}-()(\d{{{digits},}})"
        )
        match = re.fullmatch(pattern, code or "")
        if not match:
            return False
        year = int(match.group(1)) if use_year else 0
        CodeSequence.objects.get_or_create(code_type=code_type, year=year)
        seq = CodeSequence.objects.select_for_update().get(code_type=code_type, year=year)
        seq.last_number = max(seq.last_number, int(match.group(2)))
        seq.save(update_fields=["last_number"])
        return True
