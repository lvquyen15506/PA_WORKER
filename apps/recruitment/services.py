"""Học vấn, kinh nghiệm, chứng chỉ của hồ sơ (docs/thiet-ke/models.md mục 3.7).

Phase 5 chỉ có hàm TẠO MỚI (dùng khi lưu hồ sơ từ CV ở màn hình đối chiếu). Sửa/xóa dòng làm ở
Phase 6 và dùng lại các hàm này. Mọi thay đổi ghi nhật ký qua apps.audit.services.log; trường
chữ là trường cá nhân nên giá trị nằm ở AuditPersonalValue (câu 30).
"""

import datetime

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.audit.services import log
from apps.core.choices import AuditAction, EmploymentChangeType, RecruitmentStatus
from apps.core.models import EducationLevel
from apps.employment.models import Employment, EmploymentHistory
from apps.workers import rules

from .models import Application, Certificate, Education, WorkExperience

MIN_YEAR = 1950


class RecruitmentDataError(Exception):
    """Dữ liệu dòng không hợp lệ. `errors`: {tên trường: thông báo tiếng Việt}."""

    def __init__(self, errors):
        self.errors = errors
        super().__init__("; ".join(errors.values()))


def _check_editable(user, worker):
    """Tab Tuyển dụng thao tác được ở mọi trạng thái trừ Bị từ chối và Lưu trữ (câu 36)."""
    if not rules.can_edit_work_tabs(user, worker):
        raise PermissionDenied


def _text(value):
    return (value or "").strip()


def _lock(user, worker):
    """Khóa dòng hồ sơ rồi kiểm tra lại quyền trên bản ghi vừa đọc: đối tượng truyền vào có thể đã
    cũ (hồ sơ vừa chuyển Lưu trữ, hoặc vừa được tiếp nhận ở một phiên khác). Gọi trong giao dịch."""
    from apps.workers.models import Worker

    locked = Worker.objects.select_for_update().get(pk=worker.pk)
    if not rules.can_edit_work_tabs(user, locked):
        raise PermissionDenied
    return locked


def _create(user, worker, model, values, *, note, request):
    with transaction.atomic():
        locked = _lock(user, worker)
        row = model.objects.create(worker=locked, **values)
        locked.touch()
        changes = {
            name: (None, value.name if hasattr(value, "name") else value)
            for name, value in values.items()
            if value not in (None, "")
        }
        log(AuditAction.CREATE, user=user, obj=row, changes=changes, note=note, request=request)
    return row


def _education_values(
    *, education_level, school_name, major="", start_year=None, end_year=None, note=""
):
    """Kiểm tra và chuẩn hóa một dòng học vấn; dùng chung cho thêm và sửa."""
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
    return {
        "education_level": education_level,
        "school_name": school_name,
        "major": _text(major),
        "start_year": start_year,
        "end_year": end_year,
        "note": _text(note),
    }


def add_education(user, worker, *, request=None, **data):
    _check_editable(user, worker)
    values = _education_values(**data)
    return _create(user, worker, Education, values, note="Thêm học vấn", request=request)


def _experience_values(
    *, company_name, job_title="", start_date=None, end_date=None, description=""
):
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
    return {
        "company_name": company_name,
        "job_title": _text(job_title),
        "start_date": start_date,
        "end_date": end_date,
        "description": _text(description),
    }


def add_work_experience(user, worker, *, request=None, **data):
    _check_editable(user, worker)
    values = _experience_values(**data)
    return _create(user, worker, WorkExperience, values, note="Thêm kinh nghiệm", request=request)


def _certificate_values(*, name, issuer="", issue_date=None, expiry_date=None, note=""):
    errors = {}
    name = _text(name)
    if not name:
        errors["name"] = "Nhập tên chứng chỉ."
    if issue_date and expiry_date and expiry_date < issue_date:
        errors["expiry_date"] = "Ngày hết hạn phải sau hoặc bằng ngày cấp."
    if errors:
        raise RecruitmentDataError(errors)
    return {
        "name": name,
        "issuer": _text(issuer),
        "issue_date": issue_date,
        "expiry_date": expiry_date,
        "note": _text(note),
    }


def add_certificate(user, worker, *, request=None, **data):
    _check_editable(user, worker)
    values = _certificate_values(**data)
    return _create(user, worker, Certificate, values, note="Thêm chứng chỉ", request=request)


# --- Sửa và xóa dòng con (Phase 6) ------------------------------------------------------------
# Dòng con không bảng nào trỏ tới nên được xóa cứng (ngoại lệ ở CLAUDE.md); giá trị cũ ghi nhật
# ký trước khi xóa. Mỗi hàm kiểm tra dòng thuộc đúng hồ sơ và quyền theo câu 36.
CHILD_SPECS = {
    "hoc-van": (Education, _education_values, "học vấn"),
    "chung-chi": (Certificate, _certificate_values, "chứng chỉ"),
    "kinh-nghiem": (WorkExperience, _experience_values, "kinh nghiệm"),
}


def _display(value):
    return value.name if hasattr(value, "name") else value


def _child_update(user, row, validator, noun, data, request):
    worker = row.worker
    _check_editable(user, worker)
    values = validator(**data)
    with transaction.atomic():
        locked = _lock(user, worker)
        row = type(row).objects.select_for_update().get(pk=row.pk)
        changes = {}
        for name, new in values.items():
            old = getattr(row, name)
            if old != new and (old or new):
                changes[name] = (_display(old), _display(new))
            setattr(row, name, new)
        if changes:
            row.save()
            locked.touch()
            log(
                AuditAction.UPDATE,
                user=user,
                obj=row,
                changes=changes,
                note=f"Sửa {noun}",
                request=request,
            )
    return bool(changes)


def update_education(user, row, request=None, **data):
    return _child_update(user, row, _education_values, "học vấn", data, request)


def update_certificate(user, row, request=None, **data):
    return _child_update(user, row, _certificate_values, "chứng chỉ", data, request)


def update_work_experience(user, row, request=None, **data):
    return _child_update(user, row, _experience_values, "kinh nghiệm", data, request)


def delete_child(user, row, request=None):
    """Xóa một dòng học vấn, chứng chỉ hoặc kinh nghiệm; ghi giá trị cũ vào nhật ký trước."""
    worker = row.worker
    _check_editable(user, worker)
    noun = next(n for model, _, n in CHILD_SPECS.values() if isinstance(row, model))
    fields = [
        f.name
        for f in row._meta.concrete_fields
        if f.name not in {"id", "worker"} and getattr(row, f.name) not in (None, "")
    ]
    with transaction.atomic():
        locked = _lock(user, worker)
        changes = {name: (_display(getattr(row, name)), None) for name in fields}
        log(
            AuditAction.UPDATE,
            user=user,
            obj=row,
            changes=changes,
            note=f"Xóa {noun}",
            request=request,
        )
        row.delete()
        locked.touch()


# --- Ứng tuyển (câu 7, mục IV.4) --------------------------------------------------------------
RESULT_STATUSES = (RecruitmentStatus.PASSED, RecruitmentStatus.FAILED, RecruitmentStatus.DECLINED)
APPLICATION_FIELDS = (
    "position",
    "source",
    "applied_date",
    "expected_salary",
    "available_date",
    "status",
    "interview_at",
    "interview_notes",
    "result_date",
    "reject_reason",
)
MAX_SALARY = 999_999_999_999  # DecimalField(12, 0)


def _application_values(*, current=None, **data):
    """Kiểm tra một lần ứng tuyển. `current`: bản ghi đang sửa (cho phép giữ danh mục đã ngừng)."""
    errors = {}
    today = timezone.localdate()
    position, source = data.get("position"), data.get("source")
    for name, obj, label in (
        ("position", position, "Chọn vị trí ứng tuyển."),
        ("source", source, "Chọn nguồn ứng tuyển."),
    ):
        keep = current is not None and getattr(current, name + "_id", None) == getattr(obj, "pk", 0)
        if obj is None or not (obj.is_active or keep):
            errors[name] = label
    if not data.get("applied_date"):
        errors["applied_date"] = "Nhập ngày ứng tuyển."
    status = data.get("status") or RecruitmentStatus.NEW
    if status not in RecruitmentStatus.values:
        errors["status"] = "Chọn trạng thái tuyển dụng."
    salary = data.get("expected_salary")
    if salary is not None and not 0 <= salary <= MAX_SALARY:
        errors["expected_salary"] = "Mức lương mong muốn phải là số không âm."
    reject_reason = _text(data.get("reject_reason"))
    result_date = data.get("result_date")
    interview_at = data.get("interview_at")
    if status == RecruitmentStatus.INTERVIEW and not interview_at:
        errors["interview_at"] = "Nhập thời gian phỏng vấn."
    if status in RESULT_STATUSES and not result_date:
        result_date = today  # mặc định hôm nay (models.md 3.7)
    if status == RecruitmentStatus.FAILED and not reject_reason:
        errors["reject_reason"] = "Nhập lý do không đạt."
    if errors:
        raise RecruitmentDataError(errors)
    return {
        "position": position,
        "source": source,
        "applied_date": data["applied_date"],
        "expected_salary": salary,
        "available_date": data.get("available_date"),
        "status": status,
        "interview_at": interview_at,
        "interview_notes": _text(data.get("interview_notes")),
        "result_date": result_date,
        "reject_reason": reject_reason,
    }


def was_onboarded(app):
    """Lần ứng tuyển đã được tiếp nhận vào làm: đang gắn với Employment, hoặc đã từng (người quay
    lại làm dùng lại dòng Employment nên lần ứng tuyển cũ không còn gắn). Lần Đạt tạo trước một
    lượt tiếp nhận của cùng hồ sơ coi là đã tiếp nhận (chặt hơn một chút để không sót)."""
    if Employment.objects.filter(application=app).exists():
        return True
    return (
        app.status == RecruitmentStatus.PASSED
        and EmploymentHistory.objects.filter(
            worker_id=app.worker_id,
            change_type=EmploymentChangeType.ONBOARD,
            created_at__gte=app.created_at,
        ).exists()
    )


def add_application(user, worker, *, request=None, **data):
    _check_editable(user, worker)
    values = _application_values(**data)
    with transaction.atomic():
        locked = _lock(user, worker)
        app = Application.objects.create(worker=locked, created_by=user, **values)
        locked.touch()
        changes = {
            name: (None, _display(value))
            for name, value in values.items()
            if value not in (None, "")
        }
        log(
            AuditAction.CREATE,
            user=user,
            obj=app,
            changes=changes,
            note="Thêm lần ứng tuyển",
            request=request,
        )
    return app


def update_application(user, app, *, request=None, **data):
    """Sửa lần ứng tuyển. Trả True nếu có thay đổi."""
    worker = app.worker
    _check_editable(user, worker)
    values = _application_values(current=app, **data)
    with transaction.atomic():
        # Khóa hồ sơ trước khi kiểm tra: "Tiếp nhận vào làm" cũng khóa dòng này nên hai thao tác
        # cùng lúc được xếp tuần tự, không để Employment gắn với lần ứng tuyển đã bị đổi trạng thái.
        locked = _lock(user, worker)
        app = Application.objects.select_for_update().get(pk=app.pk)
        if values["status"] != RecruitmentStatus.PASSED and was_onboarded(app):
            raise RecruitmentDataError(
                {"status": "Lần ứng tuyển này đã được tiếp nhận vào làm nên giữ trạng thái Đạt."}
            )
        changes = {}
        for name, new in values.items():
            old = getattr(app, name)
            if old != new and (old or new):
                changes[name] = (_display(old), _display(new))
            setattr(app, name, new)
        if changes:
            app.save()
            locked.touch()
            log(
                AuditAction.UPDATE,
                user=user,
                obj=app,
                changes=changes,
                note="Sửa lần ứng tuyển",
                request=request,
            )
    return bool(changes)
