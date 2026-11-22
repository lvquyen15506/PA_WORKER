"""Học vấn, kinh nghiệm, chứng chỉ của hồ sơ (docs/thiet-ke/models.md mục 3.7).

Phase 5 chỉ có hàm TẠO MỚI (dùng khi lưu hồ sơ từ CV ở màn hình đối chiếu). Sửa/xóa dòng làm ở
Phase 6 và dùng lại các hàm này. Mọi thay đổi ghi nhật ký qua apps.audit.services.log; trường
chữ là trường cá nhân nên giá trị nằm ở AuditPersonalValue (câu 30).
"""

import datetime

from django.core.exceptions import PermissionDenied
from django.utils import timezone

from apps.audit.services import log
from apps.core.choices import AuditAction, VerificationStatus
from apps.core.models import EducationLevel
from apps.workers import rules

from .models import Certificate, Education, WorkExperience

MIN_YEAR = 1950


class RecruitmentDataError(Exception):
    """Dữ liệu dòng không hợp lệ. `errors`: {tên trường: thông báo tiếng Việt}."""

    def __init__(self, errors):
        self.errors = errors
        super().__init__("; ".join(errors.values()))


def _check_editable(user, worker):
    """Tab Tuyển dụng thao tác được ở mọi trạng thái trừ Bị từ chối và Lưu trữ (câu 36)."""
    if user is None or not getattr(user, "is_authenticated", False):
        raise PermissionDenied
    if user.role.code not in rules.ALL_STAFF:
        raise PermissionDenied
    if worker.anonymized_at or worker.verification_status in (
        VerificationStatus.REJECTED,
        VerificationStatus.ARCHIVED,
    ):
        raise PermissionDenied


def _text(value):
    return (value or "").strip()


def _create(user, worker, model, values, *, note, request):
    row = model.objects.create(worker=worker, **values)
    worker.touch()
    changes = {
        name: (None, value.name if hasattr(value, "name") else value)
        for name, value in values.items()
        if value not in (None, "")
    }
    log(AuditAction.CREATE, user=user, obj=row, changes=changes, note=note, request=request)
    return row


def add_education(
    user,
    worker,
    *,
    education_level,
    school_name,
    major="",
    start_year=None,
    end_year=None,
    note="",
    request=None,
):
    _check_editable(user, worker)
    errors = {}
    school_name = _text(school_name)
    if not school_name:
        errors["school_name"] = "Nhập tên trường."
    if not isinstance(education_level, EducationLevel) or not education_level.is_active:
        errors["education_level"] = "Chọn trình độ học vấn."
    this_year = timezone.localdate().year
    for name, year in (("start_year", start_year), ("end_year", end_year)):
        if year is not None and not MIN_YEAR <= year <= this_year + 1:
            errors[name] = f"Năm phải từ {MIN_YEAR} đến {this_year + 1}."
    if not errors and start_year and end_year and start_year > end_year:
        errors["end_year"] = "Năm kết thúc phải sau hoặc bằng năm bắt đầu."
    if errors:
        raise RecruitmentDataError(errors)
    values = {
        "education_level": education_level,
        "school_name": school_name,
        "major": _text(major),
        "start_year": start_year,
        "end_year": end_year,
        "note": _text(note),
    }
    return _create(user, worker, Education, values, note="Thêm học vấn", request=request)


def add_work_experience(
    user,
    worker,
    *,
    company_name,
    job_title="",
    start_date=None,
    end_date=None,
    description="",
    request=None,
):
    _check_editable(user, worker)
    errors = {}
    company_name = _text(company_name)
    if not company_name:
        errors["company_name"] = "Nhập tên công ty."
    if start_date and end_date and start_date > end_date:
        errors["end_date"] = "Ngày kết thúc phải sau hoặc bằng ngày bắt đầu."
    for name, day in (("start_date", start_date), ("end_date", end_date)):
        if isinstance(day, datetime.date) and day > timezone.localdate():
            errors[name] = "Ngày không được ở tương lai."
    if errors:
        raise RecruitmentDataError(errors)
    values = {
        "company_name": company_name,
        "job_title": _text(job_title),
        "start_date": start_date,
        "end_date": end_date,
        "description": _text(description),
    }
    return _create(user, worker, WorkExperience, values, note="Thêm kinh nghiệm", request=request)


def add_certificate(
    user, worker, *, name, issuer="", issue_date=None, expiry_date=None, note="", request=None
):
    _check_editable(user, worker)
    errors = {}
    name = _text(name)
    if not name:
        errors["name"] = "Nhập tên chứng chỉ."
    if issue_date and expiry_date and expiry_date < issue_date:
        errors["expiry_date"] = "Ngày hết hạn phải sau hoặc bằng ngày cấp."
    if errors:
        raise RecruitmentDataError(errors)
    values = {
        "name": name,
        "issuer": _text(issuer),
        "issue_date": issue_date,
        "expiry_date": expiry_date,
        "note": _text(note),
    }
    return _create(user, worker, Certificate, values, note="Thêm chứng chỉ", request=request)
