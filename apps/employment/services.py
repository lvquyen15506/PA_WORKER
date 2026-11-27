"""Nghiệp vụ quá trình làm việc (models.md mục 3.8, 4.6; câu 6, 7, 36): tiếp nhận vào làm, đổi
thông tin làm việc, hợp đồng. Mọi quy tắc kiểm tra ở đây (máy chủ); view và form chỉ chuyển lỗi.

- `onboard`: chỉ khi lần ứng tuyển Đạt và hồ sơ Đã xác minh (câu 7); sinh mã NV theo cấu hình,
  người đã có mã NV giữ mã cũ (câu 6).
- `change_employment`: đường DUY NHẤT đổi bộ phận, tổ, chức danh, ca, người quản lý, trạng thái
  làm việc; luôn thêm một dòng EmploymentHistory (không ghi đè).
Lý do, ghi chú tự điền chỉ dùng mã hồ sơ, không họ tên (câu 30).
"""

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction

from apps.audit.services import log
from apps.core.choices import (
    AuditAction,
    CodeType,
    ContractType,
    EmploymentChangeType,
    RecruitmentStatus,
    ResignReason,
    VerificationStatus,
    WorkStatus,
)
from apps.core.codes import bump_sequence, next_code
from apps.core.models import DocumentType
from apps.core.storage import private_storage
from apps.workers import rules
from apps.workers.models import Worker

from .models import Contract, Employment, EmploymentHistory


class EmploymentError(Exception):
    """Vi phạm quy tắc nghiệp vụ. `errors`: {trường: thông báo tiếng Việt}; `message`: lỗi chung."""

    def __init__(self, errors=None, message=""):
        self.errors = errors or {}
        self.message = message or "; ".join(self.errors.values())
        super().__init__(self.message)


def _check_editable(user, worker):
    """Tab Quá trình làm việc thao tác được ở mọi trạng thái trừ Bị từ chối và Lưu trữ (câu 36)."""
    if not rules.can_edit_work_tabs(user, worker):
        raise PermissionDenied


def _lock_worker(worker, user):
    """Khóa dòng hồ sơ rồi kiểm tra lại quyền trên bản ghi mới đọc (đối tượng truyền vào có thể
    đã cũ: hồ sơ vừa chuyển Lưu trữ hoặc Bị từ chối ở một phiên khác)."""
    locked = Worker.objects.select_for_update().get(pk=worker.pk)
    if not rules.can_edit_work_tabs(user, locked):
        raise PermissionDenied
    return locked


def _text(value):
    return (value or "").strip()


def _name(value):
    """Giá trị ghi nhật ký: tên danh mục; người quản lý chỉ ghi mã nhân viên (câu 30)."""
    if isinstance(value, Worker):
        return value.employee_code or value.worker_code
    return value.name if hasattr(value, "name") else value


def _usable(obj, current_id=None):
    """Danh mục còn dùng; mục đã ngừng chỉ được giữ nguyên nếu là giá trị hiện tại."""
    return obj is None or obj.is_active or obj.pk == current_id


def _check_structure(section, team, position, shift, manager, worker, current, errors):
    if position is None or not _usable(position, getattr(current, "position_id", None)):
        errors["position"] = "Chọn chức danh đang sử dụng."
    if not _usable(section, getattr(current, "section_id", None)):
        errors["section"] = "Bộ phận này đã ngừng sử dụng."
    if team is not None:
        if section is None:
            errors["team"] = "Chọn bộ phận trước khi chọn tổ."
        elif team.section_id != section.pk:
            errors["team"] = "Tổ phải thuộc bộ phận đã chọn."
        elif not _usable(team, getattr(current, "team_id", None)):
            errors["team"] = "Tổ này đã ngừng sử dụng."
    if not _usable(shift, getattr(current, "shift_id", None)):
        errors["shift"] = "Ca làm việc này đã ngừng sử dụng."
    if manager is not None:
        if manager.pk == worker.pk:
            errors["manager"] = "Người quản lý trực tiếp không được là chính mình."
        elif not manager.employee_code or manager.anonymized_at:
            errors["manager"] = "Người quản lý phải là công nhân đã có mã nhân viên."
        elif not (current is not None and current.manager_id == manager.pk):
            # Giữ nguyên người quản lý hiện tại thì không kiểm lại (người đó có thể đã nghỉ sau).
            boss = Employment.objects.filter(worker=manager).first()
            if boss is None or boss.work_status == WorkStatus.RESIGNED:
                errors["manager"] = "Người quản lý đã nghỉ việc hoặc chưa có thông tin làm việc."
            elif _manager_loop(manager, worker):
                errors["manager"] = (
                    "Không tạo được vòng quản lý: người này đang là cấp dưới của bạn."
                )


def _manager_loop(manager, worker, limit=50):
    """Đi ngược chuỗi người quản lý của `manager`; gặp `worker` nghĩa là sẽ thành vòng."""
    seen, current = set(), manager
    for _ in range(limit):
        employment = Employment.objects.filter(worker=current).only("manager_id").first()
        next_id = employment.manager_id if employment else None
        if next_id is None or next_id in seen:
            return False
        if next_id == worker.pk:
            return True
        seen.add(next_id)
        current = Worker(pk=next_id)
    return False


# --- Tiếp nhận vào làm (câu 6, 7) --------------------------------------------------------------
def can_onboard(application, worker):
    """Nút "Tiếp nhận vào làm" chỉ hiện khi lần ứng tuyển Đạt, hồ sơ Đã xác minh và chưa có quan
    hệ làm việc đang hiệu lực (chưa có hoặc đã nghỉ việc, trường hợp quay lại)."""
    if application.status != RecruitmentStatus.PASSED:
        return False
    if worker.verification_status != VerificationStatus.VERIFIED or worker.anonymized_at:
        return False
    employment = Employment.objects.filter(worker=worker).first()
    if employment is None:
        return True
    return employment.work_status == WorkStatus.RESIGNED and employment.application_id != (
        application.pk
    )


def onboard(
    user,
    application,
    *,
    received_date,
    start_date,
    position,
    section=None,
    team=None,
    shift=None,
    manager=None,
    assignment=None,
    request=None,
):
    """Tiếp nhận một lần ứng tuyển Đạt vào làm. Trả Employment (trạng thái Chờ nhận việc).

    `assignment` (v1.1.1, không bắt buộc): {client_company, position, start_date} để gán công ty
    khách ngay; đợt tạo qua `add_assignment` trong CÙNG giao dịch, lỗi đợt thì hủy cả tiếp nhận.
    """
    worker = application.worker
    _check_editable(user, worker)
    errors = {}
    with transaction.atomic():
        locked = _lock_worker(worker, user)
        application = type(application).objects.select_for_update().get(pk=application.pk)
        # Kiểm tra lại sau khi khóa: hai người bấm cùng lúc chỉ một lần thành công.
        if application.worker_id != locked.pk:
            raise EmploymentError(message="Lần ứng tuyển không thuộc hồ sơ này.")
        if application.status != RecruitmentStatus.PASSED:
            raise EmploymentError(message="Chỉ tiếp nhận lần ứng tuyển ở trạng thái Đạt.")
        if locked.verification_status != VerificationStatus.VERIFIED:
            raise EmploymentError(
                message="Hồ sơ phải ở trạng thái Đã xác minh mới tiếp nhận vào làm."
            )
        employment = Employment.objects.select_for_update().filter(worker=locked).first()
        if employment is not None and employment.work_status != WorkStatus.RESIGNED:
            raise EmploymentError(message="Công nhân này đang có thông tin làm việc.")
        if Employment.objects.filter(application=application).exclude(worker=locked).exists():
            raise EmploymentError(message="Lần ứng tuyển này đã được tiếp nhận.")
        if employment is not None and employment.application_id == application.pk:
            raise EmploymentError(message="Lần ứng tuyển này đã được tiếp nhận.")

        if not received_date:
            errors["received_date"] = "Nhập ngày tiếp nhận."
        if not start_date:
            errors["start_date"] = "Nhập ngày bắt đầu."
        if received_date and start_date and received_date > start_date:
            errors["start_date"] = "Ngày bắt đầu không được trước ngày tiếp nhận."
        if start_date and locked.date_of_birth and start_date <= locked.date_of_birth:
            errors["start_date"] = "Ngày bắt đầu phải sau ngày sinh."
        _check_structure(section, team, position, shift, manager, locked, None, errors)
        if errors:
            raise EmploymentError(errors)

        had_code = bool(locked.employee_code)
        if not had_code:
            code = next_code(CodeType.EMPLOYEE)
            Worker.objects.filter(pk=locked.pk).update(employee_code=code)
            locked.employee_code = code
        values = {
            "application": application,
            "received_date": received_date,
            "start_date": start_date,
            "section": section,
            "team": team,
            "position": position,
            "shift": shift,
            "manager": manager,
            "work_status": WorkStatus.AWAITING,
            "resign_date": None,
            "resign_reason": "",
            "resign_note": "",
        }
        # Chụp lại trước khi gán giá trị mới: `previous` và `employment` là cùng một đối tượng.
        previous = employment is not None
        previous_status = employment.work_status if employment is not None else ""
        if employment is None:
            employment = Employment.objects.create(worker=locked, **values)
        else:  # quay lại làm: dùng lại dòng 1-1, giữ mã NV cũ (câu 6)
            for name, value in values.items():
                setattr(employment, name, value)
            employment.save()
        EmploymentHistory.objects.create(
            worker=locked,
            change_type=EmploymentChangeType.ONBOARD,
            effective_date=start_date,
            reason=f"Tiếp nhận từ lần ứng tuyển của hồ sơ {locked.worker_code}",
            to_section=section,
            to_team=team,
            to_position=position,
            to_shift=shift,
            to_manager=manager,
            from_work_status=previous_status,
            to_work_status=WorkStatus.AWAITING,
            created_by=user,
        )
        locked.touch()
        if not had_code:
            log(
                AuditAction.UPDATE,
                user=user,
                obj=locked,
                changes={"employee_code": (None, locked.employee_code)},
                note="Cấp mã nhân viên khi tiếp nhận vào làm",
                request=request,
            )
        changes = {
            name: (None, _name(value))
            for name, value in values.items()
            if name not in {"resign_date", "resign_reason", "resign_note", "application"}
            and value not in (None, "")
        }
        log(
            AuditAction.UPDATE if previous else AuditAction.CREATE,
            user=user,
            obj=employment,
            changes=changes,
            note=(
                f"Tiếp nhận vào làm lại, giữ mã nhân viên {locked.employee_code}"
                if previous
                else f"Tiếp nhận vào làm, mã nhân viên {locked.employee_code}"
            ),
            request=request,
        )
        if assignment:
            from .assignments import AssignmentError, add_assignment

            try:
                add_assignment(user, locked, request=request, **assignment)
            except AssignmentError as exc:
                # Đổi tên trường sang ô của form tiếp nhận; ngoại lệ làm hủy cả giao dịch.
                raise EmploymentError(
                    {f"assign_{k}": v for k, v in exc.errors.items()}, message=exc.message
                ) from exc
    return employment


# --- Nhập từ Excel (câu 27, 48; excel-mau.md mục 3.1) -------------------------------------------
def import_employment(
    user,
    worker,
    *,
    employee_code,
    received_date,
    start_date,
    position,
    work_status,
    section=None,
    team=None,
    shift=None,
    resign_date=None,
    resign_reason="",
    client_company=None,
    assignment_start=None,
    request=None,
):
    """Thông tin làm việc của công nhân hiện hữu nhập từ file Excel (phần B), chạy trong giao dịch
    của dòng đang nhập. Chỉ Admin, Quản lý nhân sự. Hồ sơ vẫn ở Nháp và phải qua duyệt.

    - Nhận mã NV cũ (không trùng); chỉ đẩy bộ đếm khi mã khớp định dạng đang cấu hình (câu 27).
    - Tạo Employment + một dòng EmploymentHistory loại IMPORT (không sinh mã mới).
    - Có công ty khách thì tạo đợt qua `add_assignment` (một đường duy nhất, mọi kiểm tra như
      thường); Đã nghỉ việc thì đợt đóng sẵn vào ngày nghỉ. Không tạo lương.
    """
    if user.role.code not in rules.MANAGERS:
        raise PermissionDenied
    errors = {}
    if Employment.objects.filter(worker=worker).exists():
        raise EmploymentError(message="Hồ sơ này đã có thông tin làm việc.")
    if Worker.objects.filter(employee_code=employee_code).exclude(pk=worker.pk).exists():
        errors["employee_code"] = f"Mã nhân viên {employee_code} đã được dùng."
    if received_date and start_date and received_date > start_date:
        errors["received_date"] = "Ngày tiếp nhận không được sau ngày vào làm."
    _check_structure(section, team, position, shift, None, worker, None, errors)
    if errors:
        raise EmploymentError(errors)

    resigned = work_status == WorkStatus.RESIGNED
    Worker.objects.filter(pk=worker.pk).update(employee_code=employee_code)
    worker.employee_code = employee_code
    bump_sequence(CodeType.EMPLOYEE, employee_code)
    # Đã nghỉ việc: tạo ở trạng thái đang làm để thêm đợt, rồi đặt Đã nghỉ việc ngay bên dưới.
    employment = Employment.objects.create(
        worker=worker,
        received_date=received_date,
        start_date=start_date,
        section=section,
        team=team,
        position=position,
        shift=shift,
        work_status=WorkStatus.ACTIVE if resigned else work_status,
    )
    EmploymentHistory.objects.create(
        worker=worker,
        change_type=EmploymentChangeType.IMPORT,
        effective_date=start_date,
        reason=f"Nhập từ Excel, hồ sơ {worker.worker_code}",
        to_section=section,
        to_team=team,
        to_position=position,
        to_shift=shift,
        to_work_status=work_status,
        created_by=user,
    )
    if client_company is not None:
        from .assignments import add_assignment

        add_assignment(
            user,
            worker,
            client_company=client_company,
            position=position,
            start_date=assignment_start,
            end_date=resign_date if resigned else None,
            request=request,
        )
    if resigned:
        employment.work_status = WorkStatus.RESIGNED
        employment.resign_date = resign_date
        employment.resign_reason = resign_reason
        employment.save(update_fields=["work_status", "resign_date", "resign_reason", "updated_at"])
    worker.touch()
    log(
        AuditAction.UPDATE,
        user=user,
        obj=worker,
        changes={"employee_code": (None, employee_code)},
        note="Nhập mã nhân viên cũ từ Excel",
        request=request,
    )
    log(
        AuditAction.CREATE,
        user=user,
        obj=employment,
        changes={
            name: (None, _name(value))
            for name, value in {
                "received_date": received_date,
                "start_date": start_date,
                "section": section,
                "team": team,
                "position": position,
                "shift": shift,
                "work_status": work_status,
                "resign_date": resign_date if resigned else None,
                "resign_reason": resign_reason if resigned else "",
            }.items()
            if value not in (None, "")
        },
        note=f"Nhập thông tin làm việc từ Excel, mã nhân viên {employee_code}",
        request=request,
    )
    return employment


# --- Đổi thông tin làm việc (mục IV.5) -----------------------------------------------------------
STRUCT_FIELDS = ("section", "team", "position", "shift", "manager")


def _derive_change_type(changed):
    if "work_status" in changed:
        return EmploymentChangeType.STATUS_CHANGE
    if changed & {"section", "team", "manager"}:
        return EmploymentChangeType.TRANSFER
    if "position" in changed:
        return EmploymentChangeType.POSITION_CHANGE
    return EmploymentChangeType.SHIFT_CHANGE


def change_employment(
    user,
    worker,
    *,
    effective_date,
    section,
    team,
    position,
    shift,
    manager,
    work_status,
    decision_no="",
    reason="",
    resign_date=None,
    resign_reason="",
    resign_note="",
    request=None,
):
    """Ghi nhận thay đổi thông tin làm việc: cập nhật Employment và THÊM một dòng EmploymentHistory
    (chỉ ghi trường đổi). Không có gì đổi thì báo lỗi, không ghi gì. Trả dòng lịch sử."""
    _check_editable(user, worker)
    errors = {}
    with transaction.atomic():
        locked = _lock_worker(worker, user)
        employment = Employment.objects.select_for_update().filter(worker=locked).first()
        if employment is None:
            raise EmploymentError(
                message="Hồ sơ chưa có thông tin làm việc. Hãy tiếp nhận vào làm trước."
            )
        if employment.work_status == WorkStatus.RESIGNED:
            raise EmploymentError(
                message="Công nhân đã nghỉ việc. Muốn quay lại làm: Mở lại hồ sơ, thêm lần ứng "
                "tuyển, rồi Tiếp nhận vào làm (giữ mã nhân viên cũ)."
            )
        if not effective_date:
            errors["effective_date"] = "Nhập ngày hiệu lực."
        if work_status not in WorkStatus.values:
            errors["work_status"] = "Chọn trạng thái làm việc."
        _check_structure(section, team, position, shift, manager, locked, employment, errors)
        resigning = work_status == WorkStatus.RESIGNED
        if resigning:
            if not resign_date:
                errors["resign_date"] = "Nhập ngày nghỉ việc."
            elif resign_date < employment.start_date:
                errors["resign_date"] = "Ngày nghỉ việc không được trước ngày bắt đầu."
            if resign_reason not in ResignReason.values:
                errors["resign_reason"] = "Chọn lý do nghỉ việc."
        if errors:
            raise EmploymentError(errors)

        new = {
            "section": section,
            "team": team,
            "position": position,
            "shift": shift,
            "manager": manager,
            "work_status": work_status,
        }
        changed = {name for name, value in new.items() if getattr(employment, name) != value}
        resign_values = {
            "resign_date": resign_date if resigning else None,
            "resign_reason": resign_reason if resigning else "",
            "resign_note": _text(resign_note) if resigning else "",
        }
        resign_changed = {
            name for name, value in resign_values.items() if getattr(employment, name) != value
        }
        if not changed:
            raise EmploymentError(message="Không có thay đổi nào để ghi nhận.")

        history = EmploymentHistory(
            worker=locked,
            change_type=_derive_change_type(changed),
            effective_date=effective_date,
            decision_no=_text(decision_no),
            reason=_text(reason),
            created_by=user,
        )
        changes = {}
        for name in changed:
            old = getattr(employment, name)
            if name == "work_status":
                history.from_work_status, history.to_work_status = old, work_status
            else:
                setattr(history, f"from_{name}", old)
                setattr(history, f"to_{name}", new[name])
            changes[name] = (_name(old), _name(new[name]))
            setattr(employment, name, new[name])
        for name in resign_changed:
            changes[name] = (getattr(employment, name) or None, resign_values[name] or None)
            setattr(employment, name, resign_values[name])
        employment.save()
        history.save()
        locked.touch()
        log(
            AuditAction.UPDATE,
            user=user,
            obj=employment,
            changes=changes,
            note=f"{EmploymentChangeType(history.change_type).label}, ngày hiệu lực "
            f"{effective_date:%d/%m/%Y}",
            request=request,
        )
        if resigning:
            from . import assignments  # tránh import vòng; đóng đợt làm việc đang mở (câu 40)

            assignments.close_open_on_resign(user, locked, resign_date, request=request)
    return history


# --- Hợp đồng ---------------------------------------------------------------------------------
CONTRACT_FIELDS = (
    "contract_no",
    "contract_type",
    "signed_date",
    "effective_date",
    "expiry_date",
    "note",
)


def _contract_values(
    *, contract_no, contract_type, signed_date, effective_date, expiry_date, note, current=None
):
    errors = {}
    contract_no = _text(contract_no)
    if not contract_no:
        errors["contract_no"] = "Nhập số hợp đồng."
    elif len(contract_no) > 50:
        errors["contract_no"] = "Số hợp đồng tối đa 50 ký tự."
    else:
        clash = Contract.objects.filter(contract_no__iexact=contract_no)
        if current is not None:
            clash = clash.exclude(pk=current.pk)
        if clash.exists():
            errors["contract_no"] = "Số hợp đồng này đã được dùng."
    if contract_type not in ContractType.values:
        errors["contract_type"] = "Chọn loại hợp đồng."
    if not signed_date:
        errors["signed_date"] = "Nhập ngày ký."
    if not effective_date:
        errors["effective_date"] = "Nhập ngày hiệu lực."
    if contract_type == ContractType.INDEFINITE:
        expiry_date = None  # không xác định thời hạn thì không có ngày hết hạn
    elif contract_type in ContractType.values:
        if not expiry_date:
            errors["expiry_date"] = "Nhập ngày hết hạn."
        elif effective_date and expiry_date <= effective_date:
            errors["expiry_date"] = "Ngày hết hạn phải sau ngày hiệu lực."
    if errors:
        raise EmploymentError(errors)
    return {
        "contract_no": contract_no,
        "contract_type": contract_type,
        "signed_date": signed_date,
        "effective_date": effective_date,
        "expiry_date": expiry_date,
        "note": _text(note),
    }


def _contract_document(user, worker, uploaded, request):
    """Tải tệp hợp đồng lên thành WorkerDocument loại Hợp đồng (cùng quy tắc tài liệu, 4.4)."""
    from apps.documents import services as document_services

    if not rules.can_add_document(user, worker):
        raise EmploymentError(
            {
                "file": "Hồ sơ đang ở trạng thái không cho tải tài liệu. "
                "Tải tệp hợp đồng ở tab Tài liệu sau."
            }
        )
    doc_type = DocumentType.objects.get(system_code="CONTRACT")
    try:
        return document_services.upload_document(user, worker, doc_type, uploaded, request=request)
    except document_services.DocumentError as exc:
        raise EmploymentError({"file": exc.message}) from exc


def add_contract(user, worker, *, uploaded=None, request=None, **data):
    _check_editable(user, worker)
    with transaction.atomic():
        locked = _lock_worker(worker, user)
        if not Employment.objects.filter(worker=locked).exists():
            raise EmploymentError(
                message="Hồ sơ chưa có thông tin làm việc nên chưa thêm hợp đồng."
            )
        values = _contract_values(**data)
        contract = _create_contract_row(locked, user, values)
        if uploaded:
            # Tạo hợp đồng trước rồi mới tải tệp: số hợp đồng trùng (hai phiên cùng lúc) báo lỗi
            # trước khi có tệp nào ghi ra đĩa; tải tệp lỗi thì giao dịch hủy cả hợp đồng.
            document = _contract_document(user, locked, uploaded, request)
            try:
                contract.document = document
                contract.save(update_fields=["document"])
            except Exception:
                _discard_file(document)
                raise
        locked.touch()
        log(
            AuditAction.CREATE,
            user=user,
            obj=contract,
            changes={n: (None, v) for n, v in values.items() if v not in (None, "")},
            note="Thêm hợp đồng",
            request=request,
        )
    return contract


def _create_contract_row(worker, user, values):
    try:
        with transaction.atomic():
            return Contract.objects.create(worker=worker, created_by=user, **values)
    except IntegrityError as exc:  # hai phiên cùng thêm một số hợp đồng
        raise EmploymentError({"contract_no": "Số hợp đồng này đã được dùng."}) from exc


def _discard_file(document):
    """Xóa tệp vừa tải khi bước sau lỗi (giao dịch hủy dòng tài liệu, tệp thì không tự mất)."""
    if document is not None and document.stored_file:
        private_storage.delete(document.stored_file.name)


def update_contract(user, contract, *, uploaded=None, request=None, **data):
    """Sửa hợp đồng; có tệp mới thì gắn tệp mới (tệp cũ vẫn ở tab Tài liệu). True nếu có đổi."""
    worker = contract.worker
    _check_editable(user, worker)
    with transaction.atomic():
        locked = _lock_worker(worker, user)
        contract = Contract.objects.select_for_update().get(pk=contract.pk)
        values = _contract_values(current=contract, **data)
        changes = {
            name: (getattr(contract, name) or None, value or None)
            for name, value in values.items()
            if getattr(contract, name) != value
        }
        for name, value in values.items():
            setattr(contract, name, value)
        if changes:
            try:
                with transaction.atomic():
                    contract.save()
            except IntegrityError as exc:  # hai phiên cùng đổi sang một số hợp đồng
                raise EmploymentError({"contract_no": "Số hợp đồng này đã được dùng."}) from exc
        if uploaded:
            document = _contract_document(user, locked, uploaded, request)
            try:
                contract.document = document
                contract.save(update_fields=["document"])
            except Exception:
                _discard_file(document)
                raise
            changes["document"] = (None, "tệp mới")
        if changes:
            locked.touch()
            log(
                AuditAction.UPDATE,
                user=user,
                obj=contract,
                changes={k: v for k, v in changes.items() if k != "document"},
                note="Sửa hợp đồng" + (", gắn tệp mới" if uploaded else ""),
                request=request,
            )
    return bool(changes)


__all__ = [
    "EmploymentError",
    "add_contract",
    "can_onboard",
    "change_employment",
    "onboard",
    "update_contract",
]
