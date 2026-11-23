"""Đợt làm việc tại công ty khách hàng và lịch sử lương (v1.1; câu 40–43, 48; models.md 3.9).

- Mỗi lúc một công nhân chỉ một công ty: tối đa một đợt đang mở (ràng buộc CSDL) và các đợt không
  chồng lấn ngày (kiểm tra ở đây, khóa dòng hồ sơ). Ngày kết thúc là ngày làm cuối cùng.
- Đợt giữ lịch sử, không xóa; nhập nhầm thì sửa (giá trị cũ ghi nhật ký).
- Lương gắn với đợt (đơn giá phụ thuộc công ty khách); chỉ thêm dòng mới, chỉ Admin và Quản lý
  nhân sự thêm; giá trị lương mã hóa và không vào AuditLog.changes (câu 41, 42).
"""

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.audit.services import log
from apps.core.choices import AuditAction, RoleCode, WorkStatus
from apps.workers import rules

from .models import Employment, SalaryHistory, WorkAssignment

MAX_MONEY = 999_999_999_999
MANAGER_ROLES = frozenset({RoleCode.ADMIN.value, RoleCode.HR_MANAGER.value})


class AssignmentError(Exception):
    """Vi phạm quy tắc nghiệp vụ. `errors`: {trường: thông báo tiếng Việt}; `message`: lỗi chung."""

    def __init__(self, errors=None, message=""):
        self.errors = errors or {}
        self.message = message or "; ".join(self.errors.values())
        super().__init__(self.message)


def _check_editable(user, worker):
    """Quá trình làm việc thao tác được ở mọi trạng thái trừ Bị từ chối và Lưu trữ (câu 36)."""
    if not rules.can_edit_work_tabs(user, worker):
        raise PermissionDenied


def _lock_worker(worker, user):
    """Khóa dòng hồ sơ rồi kiểm tra lại quyền trên bản ghi mới đọc: đối tượng truyền vào có thể đã
    cũ (hồ sơ vừa chuyển Lưu trữ hoặc Bị từ chối ở một phiên khác)."""
    from apps.workers.models import Worker

    locked = Worker.objects.select_for_update().get(pk=worker.pk)
    if not rules.can_edit_work_tabs(user, locked):
        raise PermissionDenied
    return locked


def _usable(obj, current_id=None):
    return obj is not None and (obj.is_active or obj.pk == current_id)


def overlaps(start, end, other_start, other_end):
    """Hai khoảng ngày (cả hai đầu tính, end rỗng = chưa kết thúc) có giao nhau không."""
    return (other_end is None or start <= other_end) and (end is None or other_start <= end)


def current_q(today):
    """Đợt đang diễn ra: bắt đầu không sau hôm nay, chưa kết thúc hoặc kết thúc từ hôm nay."""
    from django.db.models import Q

    return Q(start_date__lte=today) & (Q(end_date__isnull=True) | Q(end_date__gte=today))


def current_assignment(worker, today):
    return (
        WorkAssignment.objects.filter(worker=worker)
        .filter(current_q(today))
        .select_related("client_company", "position")
        .order_by("-start_date", "-id")
        .first()
    )


def current_salary(assignment, today):
    """Mức hiện tại của đợt: dòng có ngày áp dụng lớn nhất không quá hôm nay (cùng ngày: sau)."""
    return (
        SalaryHistory.objects.filter(assignment=assignment, effective_date__lte=today)
        .order_by("-effective_date", "-id")
        .first()
    )


def _salary_range_errors(assignment_pk, start, end):
    """Sửa ngày của đợt không được làm dòng lương nằm ngoài khoảng ngày của đợt."""
    if assignment_pk is None:
        return {}
    days = list(
        SalaryHistory.objects.filter(assignment_id=assignment_pk).values_list(
            "effective_date", flat=True
        )
    )
    if any(day < start or (end is not None and day > end) for day in days):
        return {
            "start_date": "Đợt này đã có dòng lương ngoài khoảng ngày mới. "
            "Chọn khoảng ngày bao hết ngày áp dụng của các dòng lương."
        }
    return {}


def _assignment_values(*, client_company, position, start_date, end_date, note, current=None):
    errors = {}
    if client_company is None or not _usable(
        client_company, getattr(current, "client_company_id", None)
    ):
        errors["client_company"] = "Chọn công ty khách hàng đang sử dụng."
    if position is None or not _usable(position, getattr(current, "position_id", None)):
        errors["position"] = "Chọn vị trí đang sử dụng."
    if not start_date:
        errors["start_date"] = "Nhập ngày bắt đầu."
    elif end_date and end_date < start_date:
        errors["end_date"] = "Ngày kết thúc không được trước ngày bắt đầu."
    if errors:
        raise AssignmentError(errors)
    return {
        "client_company": client_company,
        "position": position,
        "start_date": start_date,
        "end_date": end_date,
        "note": (note or "").strip(),
    }


def _display(value):
    return str(value) if hasattr(value, "location") else getattr(value, "name", value)


def add_assignment(
    user,
    worker,
    *,
    client_company,
    position,
    start_date,
    end_date=None,
    note="",
    previous_end_date=None,
    request=None,
):
    """Thêm một đợt làm việc. Đang có đợt mở thì phải nhập `previous_end_date` để kết thúc đợt đó
    trong cùng thao tác (đóng đợt cũ rồi mở đợt mới)."""
    _check_editable(user, worker)
    with transaction.atomic():
        locked = _lock_worker(worker, user)
        employment = Employment.objects.filter(worker=locked).first()
        if employment is None:
            raise AssignmentError(
                message="Hồ sơ chưa có thông tin làm việc. Hãy tiếp nhận vào làm trước."
            )
        if employment.work_status == WorkStatus.RESIGNED:
            raise AssignmentError(message="Công nhân đã nghỉ việc nên không thêm đợt làm việc mới.")
        values = _assignment_values(
            client_company=client_company,
            position=position,
            start_date=start_date,
            end_date=end_date,
            note=note,
        )
        errors = {}
        open_one = (
            WorkAssignment.objects.select_for_update()
            .filter(worker=locked, end_date__isnull=True)
            .first()
        )
        if open_one is not None:
            if previous_end_date is None:
                errors["previous_end_date"] = (
                    "Công nhân đang có đợt làm việc chưa kết thúc. Nhập ngày kết thúc của đợt đó."
                )
            elif previous_end_date < open_one.start_date:
                errors["previous_end_date"] = (
                    "Ngày kết thúc không được trước ngày bắt đầu của đợt đó."
                )
        if errors:
            raise AssignmentError(errors)
        others = WorkAssignment.objects.filter(worker=locked)
        for other in others:
            other_end = other.end_date
            if open_one is not None and other.pk == open_one.pk:
                other_end = previous_end_date
            if overlaps(values["start_date"], values["end_date"], other.start_date, other_end):
                raise AssignmentError(
                    {
                        "start_date": "Đợt làm việc bị chồng lấn ngày với một đợt khác của "
                        "công nhân này. Mỗi lúc chỉ làm cho một công ty khách hàng."
                    }
                )
        if open_one is not None:
            open_one.end_date = previous_end_date
            open_one.save(update_fields=["end_date", "updated_at"])
            log(
                AuditAction.UPDATE,
                user=user,
                obj=open_one,
                changes={"end_date": (None, previous_end_date)},
                note="Kết thúc đợt làm việc khi chuyển sang đợt mới",
                request=request,
            )
        assignment = WorkAssignment.objects.create(worker=locked, created_by=user, **values)
        locked.touch()
        log(
            AuditAction.CREATE,
            user=user,
            obj=assignment,
            changes={n: (None, _display(v)) for n, v in values.items() if v not in (None, "")},
            note="Thêm đợt làm việc",
            request=request,
        )
    return assignment


def update_assignment(
    user, assignment, *, client_company, position, start_date, end_date=None, note="", request=None
):
    """Sửa đợt làm việc (kể cả đặt ngày kết thúc). Trả True nếu có thay đổi."""
    worker = assignment.worker
    _check_editable(user, worker)
    with transaction.atomic():
        locked = _lock_worker(worker, user)
        assignment = WorkAssignment.objects.select_for_update().get(pk=assignment.pk)
        values = _assignment_values(
            client_company=client_company,
            position=position,
            start_date=start_date,
            end_date=end_date,
            note=note,
            current=assignment,
        )
        errors = _salary_range_errors(assignment.pk, values["start_date"], values["end_date"])
        for other in WorkAssignment.objects.filter(worker=locked).exclude(pk=assignment.pk):
            if overlaps(values["start_date"], values["end_date"], other.start_date, other.end_date):
                errors["start_date"] = (
                    "Đợt làm việc bị chồng lấn ngày với một đợt khác của công nhân này."
                )
        if errors:
            raise AssignmentError(errors)
        changes = {}
        for name, new in values.items():
            old = getattr(assignment, name)
            if old != new and (old or new):
                changes[name] = (_display(old), _display(new))
            setattr(assignment, name, new)
        if changes:
            assignment.save()
            locked.touch()
            log(
                AuditAction.UPDATE,
                user=user,
                obj=assignment,
                changes=changes,
                note="Sửa đợt làm việc",
                request=request,
            )
    return bool(changes)


def close_open_on_resign(user, worker, resign_date, *, request=None):
    """Công nhân chuyển sang Đã nghỉ việc thì đợt đang mở tự kết thúc vào ngày nghỉ việc (câu 40).
    Gọi trong giao dịch của change_employment. Trả danh sách đợt đã đóng."""
    closed = []
    for assignment in WorkAssignment.objects.select_for_update().filter(
        worker=worker, end_date__isnull=True
    ):
        end = max(resign_date, assignment.start_date)  # ràng buộc: kết thúc không trước bắt đầu
        assignment.end_date = end
        assignment.save(update_fields=["end_date", "updated_at"])
        log(
            AuditAction.UPDATE,
            user=user,
            obj=assignment,
            changes={"end_date": (None, end)},
            note="Tự kết thúc đợt làm việc khi nghỉ việc",
            request=request,
        )
        closed.append(assignment)
    return closed


# --- Lương (câu 41, 42) -------------------------------------------------------------------------
def can_add_salary(user, worker):
    """Chỉ Admin và Quản lý nhân sự thêm lương; hồ sơ Bị từ chối, Lưu trữ, đã ẩn danh thì không."""
    return rules.role_code(user) in MANAGER_ROLES and rules.can_edit_work_tabs(user, worker)


def add_salary(
    user,
    assignment,
    *,
    monthly_salary,
    client_unit_price=None,
    effective_date,
    reason,
    request=None,
):
    """Thêm một dòng lịch sử lương cho đợt (không sửa, không xóa dòng cũ). Trả SalaryHistory."""
    worker = assignment.worker
    if not can_add_salary(user, worker):
        raise PermissionDenied
    errors = {}
    if monthly_salary is None or not 0 < monthly_salary <= MAX_MONEY:
        errors["monthly_salary"] = "Lương tháng phải là số nguyên lớn hơn 0."
    if client_unit_price is not None and not 0 < client_unit_price <= MAX_MONEY:
        errors["client_unit_price"] = "Đơn giá tháng phải là số nguyên lớn hơn 0."
    reason = (reason or "").strip()
    if not reason:
        errors["reason"] = "Nhập lý do thay đổi."
    if not effective_date:
        errors["effective_date"] = "Nhập ngày áp dụng."
    elif effective_date < assignment.start_date or (
        assignment.end_date and effective_date > assignment.end_date
    ):
        end = f" đến {assignment.end_date:%d/%m/%Y}" if assignment.end_date else ""
        errors["effective_date"] = (
            f"Ngày áp dụng phải nằm trong đợt làm việc (từ {assignment.start_date:%d/%m/%Y}{end})."
        )
    if errors:
        raise AssignmentError(errors)
    with transaction.atomic():
        locked = _lock_worker(worker, user)
        if not can_add_salary(user, locked):
            raise PermissionDenied
        fresh = WorkAssignment.objects.select_for_update().get(pk=assignment.pk)
        if fresh.worker_id != locked.pk:
            raise AssignmentError(message="Đợt làm việc không thuộc hồ sơ này.")
        row = SalaryHistory.objects.create(
            assignment=fresh,
            worker=locked,
            monthly_salary_enc=str(int(monthly_salary)),
            client_unit_price_enc=(
                str(int(client_unit_price)) if client_unit_price is not None else None
            ),
            effective_date=effective_date,
            reason=reason,
            created_by=user,
        )
        locked.touch()
        changes = {
            "monthly_salary": (None, int(monthly_salary)),
            "reason": (None, reason),
        }
        if client_unit_price is not None:
            changes["client_unit_price"] = (None, int(client_unit_price))
        log(
            AuditAction.CREATE,
            user=user,
            obj=row,
            changes=changes,
            note=f"Thêm dòng lương, áp dụng từ {effective_date:%d/%m/%Y}",
            request=request,
        )
    return row
