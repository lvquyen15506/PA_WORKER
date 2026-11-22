"""Nghiệp vụ hồ sơ: tạo, sửa, người liên hệ, đồng ý, mở lại (models.md mục 3.4, 4.1–4.5).

Quyền theo ma trận 4.4 (apps.workers.rules), dữ liệu theo apps.workers.validation, mọi thay đổi
ghi nhật ký qua apps.audit.services.log (không họ tên trong note/object_repr, câu 30).
Đổi trạng thái chỉ qua apps.workers.workflow.transition.
"""

from collections import namedtuple

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.personal_fields import attr_name
from apps.audit.services import log
from apps.core.choices import AuditAction, CodeType, ConsentMethod, VerificationStatus
from apps.core.codes import next_code
from apps.core.models import ApplicationSource, DocumentType, Position
from apps.recruitment.models import Application

from . import rules, workflow
from .models import DataConsent, EmergencyContact, IdentityDocument, Worker
from .validation import (
    DRAFT,
    IDENTITY_FIELDS,
    SUBMISSION,
    WORKER_FIELDS,
    clean_id_number,
    validate_contacts,
    validate_worker_data,
)

IDENTITY_LABEL = {"full_name": "họ tên", "date_of_birth": "ngày sinh", "id_number": "số CCCD"}
IDENTITY_TRIGGER_FIELDS = tuple(IDENTITY_LABEL)  # sửa các trường này khi Đã xác minh -> Chờ duyệt
MSG_DUPLICATE = "Số CCCD này đã có hồ sơ khác."

UpdateResult = namedtuple("UpdateResult", ["changed", "back_to_pending"])


class WorkerDataError(Exception):
    """Dữ liệu không hợp lệ. `errors`: {tên trường: lỗi}; `contact_errors`: {chỉ số dòng: {...}};
    `duplicate`: hồ sơ đang giữ số CCCD trùng (để "Mở hồ sơ cũ")."""

    def __init__(self, errors=None, contact_errors=None, duplicate=None, message=""):
        self.errors = errors or {}
        self.contact_errors = contact_errors or {}
        self.duplicate = duplicate
        self.message = message or "Dữ liệu chưa hợp lệ."
        super().__init__(self.message)


def _require_staff(user):
    if user is None or not getattr(user, "is_authenticated", False):
        raise PermissionDenied
    if user.role.code not in rules.ALL_STAFF:
        raise PermissionDenied


def _norm(value):
    """Giá trị để so sánh trước/sau: chuỗi cắt khoảng trắng, rỗng ≡ None."""
    if isinstance(value, str):
        value = value.strip()
    return None if value in ("", None) else value


def _prepare(data):
    """Chuẩn hóa dữ liệu vào: cắt khoảng trắng, bỏ khoảng trắng trong số định danh."""
    cleaned = {}
    for name, value in data.items():
        if name not in WORKER_FIELDS + IDENTITY_FIELDS:
            raise ValueError(f"Trường không hợp lệ: {name!r}")
        if name in ("id_number", "old_id_number"):
            value = clean_id_number(value)
        elif isinstance(value, str):
            value = value.strip()
        cleaned[name] = value
    return cleaned


def _validate(data, contacts, *, instance=None, level=DRAFT):
    result = validate_worker_data(data, instance=instance, level=level)
    contact_errors = validate_contacts(contacts)
    if result.errors or contact_errors:
        raise WorkerDataError(result.errors, contact_errors, result.duplicate)
    return result


def _worker_values(data):
    values = {name: data[name] for name in WORKER_FIELDS if name in data}
    for name in ("gender", "email", "current_address", "skills", "note"):
        if name in values and values[name] is None:
            values[name] = ""
    return values


def _identity_values(data):
    values = {}
    for name in IDENTITY_FIELDS:
        if name not in data:
            continue
        attr = attr_name("workers.IdentityDocument", name)
        value = data[name]
        if attr.endswith("_enc"):
            value = value or None  # trường mã hóa: rỗng -> NULL
        elif value is None and name in (
            "id_doc_type",
            "issue_place",
            "hometown",
            "birth_registration_place",
        ):
            value = ""
        values[attr] = value
    return values


def _contact_rows(contacts):
    return [
        {
            "id": row.get("id"),
            "delete": bool(row.get("delete")),
            "full_name": (row.get("full_name") or "").strip(),
            "relationship": (row.get("relationship") or "").strip(),
            "phone": (row.get("phone") or "").strip(),
        }
        for row in contacts or ()
    ]


def create_worker(user, data, contacts=(), *, request=None):
    """Lưu Nháp: chỉ cần họ tên + SĐT (câu 5). Sinh mã hồ sơ, ghi dòng "tạo hồ sơ" của dòng thời
    gian trạng thái và nhật ký CREATE. Trả Worker."""
    _require_staff(user)
    data = _prepare(data)
    rows = _contact_rows(contacts)
    _validate(data, rows, level=DRAFT)
    identity_values = _identity_values(data)
    try:
        with transaction.atomic():
            worker = Worker.objects.create(
                worker_code=next_code(CodeType.WORKER), created_by=user, **_worker_values(data)
            )
            if any(value not in (None, "") for value in identity_values.values()):
                IdentityDocument.objects.create(worker=worker, **identity_values)
            usable = [
                r
                for r in rows
                if not r["delete"] and (r["full_name"] or r["relationship"] or r["phone"])
            ]
            for order, row in enumerate(usable):
                contact = EmergencyContact.objects.create(
                    worker=worker,
                    full_name=row["full_name"],
                    relationship=row["relationship"],
                    phone=row["phone"],
                    sort_order=order,
                )
                log(
                    AuditAction.CREATE,
                    user=user,
                    obj=contact,
                    changes={f: (None, row[f]) for f in ("full_name", "relationship", "phone")},
                    request=request,
                )
            workflow.record_creation(worker, user)
            log(AuditAction.CREATE, user=user, obj=worker, note="Tạo hồ sơ", request=request)
    except IntegrityError as exc:  # hai người nhập cùng số CCCD cùng lúc: ràng buộc unique chặn
        if "id_number_hash" not in str(exc):
            raise
        raise WorkerDataError({"id_number": MSG_DUPLICATE}) from exc
    return worker


def _current_identity_values(identity):
    return {
        name: getattr(identity, attr_name("workers.IdentityDocument", name), None)
        for name in IDENTITY_FIELDS
    }


def update_worker(user, worker, data, contacts=None, *, request=None):
    """Sửa hồ sơ theo ma trận 4.4. `data` có thể chỉ gồm một số trường. `contacts` (danh sách
    dict {id, delete, full_name, relationship, phone}) None = không đụng tới liên hệ.

    Sửa họ tên, ngày sinh hoặc số CCCD khi hồ sơ Đã xác minh thì hồ sơ tự về Chờ duyệt, người
    sửa được ghi là người gửi duyệt lần này (câu 8, mục 4.1). Trả UpdateResult.
    """
    _require_staff(user)
    data = _prepare(data)
    rows = _contact_rows(contacts) if contacts is not None else None
    try:
        with transaction.atomic():
            locked = Worker.objects.select_for_update().get(pk=worker.pk)
            if not rules.can_edit_profile(user, locked):
                raise PermissionDenied
            level = (
                SUBMISSION if locked.verification_status == VerificationStatus.VERIFIED else DRAFT
            )
            _validate(data, rows, instance=locked, level=level)

            changes = _apply_worker(locked, data)
            identity_changes = _apply_identity(user, locked, data, request)
            contact_changed = _sync_contacts(user, locked, rows, request) if rows else False

            touched_identity = [
                IDENTITY_LABEL[name]
                for name in IDENTITY_TRIGGER_FIELDS
                if name in changes or name in identity_changes
            ]
            if changes:
                log(AuditAction.UPDATE, user=user, obj=locked, changes=changes, request=request)
            changed = bool(changes or identity_changes or contact_changed)
            if changed and not changes:
                locked.touch()
            back = (
                bool(touched_identity) and locked.verification_status == VerificationStatus.VERIFIED
            )
            if back:
                workflow.transition(
                    locked,
                    VerificationStatus.PENDING,
                    user,
                    trigger=workflow.Trigger.IDENTITY_EDIT,
                    identity_fields=touched_identity,
                    request=request,
                )
            worker.refresh_from_db()  # đồng bộ đối tượng của người gọi (kể cả trạng thái mới)
            return UpdateResult(changed, back)
    except IntegrityError as exc:
        if "id_number_hash" not in str(exc):
            raise
        raise WorkerDataError({"id_number": MSG_DUPLICATE}) from exc


def _apply_worker(worker, data):
    """Ghi trường của hồ sơ; trả {tên logic: (cũ, mới)} cho trường thực sự đổi."""
    changes = {}
    for name, new in _worker_values(data).items():
        old = getattr(worker, name)
        if _norm(old) != _norm(new):
            changes[name] = (old, new)
            setattr(worker, name, new)
    if changes:
        worker.save(update_fields=[*changes, "name_search", "updated_at"])
    return changes


def _apply_identity(user, worker, data, request):
    values = _identity_values(data)
    if not values:
        return {}
    try:
        identity = worker.identity
    except IdentityDocument.DoesNotExist:
        identity = None
    created = identity is None
    if created:
        identity = IdentityDocument(worker=worker)
    current = _current_identity_values(identity)
    changes = {}
    for name in IDENTITY_FIELDS:
        attr = attr_name("workers.IdentityDocument", name)
        if attr not in values:
            continue
        new = values[attr]
        if _norm(current[name]) != _norm(new):
            changes[name] = (current[name], new)
            setattr(identity, attr, new)
    if changes:
        identity.save()  # tính lại giá trị băm
        log(AuditAction.UPDATE, user=user, obj=identity, changes=changes, request=request)
    return changes


def _sync_contacts(user, worker, rows, request):
    existing = {c.pk: c for c in worker.emergency_contacts.all()}
    changed = False
    next_order = max([c.sort_order for c in existing.values()], default=-1) + 1
    for row in rows:
        contact = existing.get(row["id"]) if row["id"] else None
        if row["id"] and contact is None:
            raise PermissionDenied  # dòng liên hệ không thuộc hồ sơ này
        blank = not (row["full_name"] or row["relationship"] or row["phone"])
        if row["delete"]:
            if contact is not None:
                # Giá trị cũ ghi vào nhật ký trước khi xóa (dòng con được phép xóa cứng).
                log(
                    AuditAction.UPDATE,
                    user=user,
                    obj=contact,
                    changes={
                        f: (getattr(contact, f), None)
                        for f in ("full_name", "relationship", "phone")
                    },
                    note="Xóa người liên hệ khẩn cấp",
                    request=request,
                )
                contact.delete()
                changed = True
            continue
        if contact is None:
            if blank:
                continue
            contact = EmergencyContact.objects.create(
                worker=worker,
                full_name=row["full_name"],
                relationship=row["relationship"],
                phone=row["phone"],
                sort_order=next_order,
            )
            next_order += 1
            log(
                AuditAction.CREATE,
                user=user,
                obj=contact,
                changes={f: (None, row[f]) for f in ("full_name", "relationship", "phone")},
                request=request,
            )
            changed = True
            continue
        diff = {
            f: (getattr(contact, f), row[f])
            for f in ("full_name", "relationship", "phone")
            if _norm(getattr(contact, f)) != _norm(row[f])
        }
        if diff:
            for f, (_, new) in diff.items():
                setattr(contact, f, new)
            contact.save(update_fields=list(diff))
            log(AuditAction.UPDATE, user=user, obj=contact, changes=diff, request=request)
            changed = True
    return changed


def record_consent(user, worker, *, consented, consent_date, method, document=None, request=None):
    """Ghi nhận đồng ý xử lý dữ liệu (lịch sử, bản mới nhất là hiệu lực). Ký giấy thì bắt buộc
    có tệp biên bản loại Văn bản đồng ý của chính hồ sơ này."""
    _require_staff(user)
    method = ConsentMethod(method)
    if consent_date is None:
        raise WorkerDataError({"consent_date": "Nhập ngày đồng ý."})
    if consent_date > timezone.localdate():
        raise WorkerDataError({"consent_date": "Ngày đồng ý không được ở tương lai."})
    if method == ConsentMethod.PAPER:
        consent_type = DocumentType.objects.get(system_code="CONSENT")
        if (
            document is None
            or document.worker_id != worker.pk
            or document.document_type_id != consent_type.pk
        ):
            raise WorkerDataError({"document": "Ký giấy: tải lên tệp biên bản đã ký."})
    elif document is not None:
        raise WorkerDataError({"document": "Chỉ đính kèm biên bản khi chọn hình thức Ký giấy."})
    with transaction.atomic():
        locked = Worker.objects.select_for_update().get(pk=worker.pk)
        if not rules.can_edit_profile(user, locked):
            raise PermissionDenied
        consent = DataConsent.objects.create(
            worker=locked,
            consented=bool(consented),
            consent_date=consent_date,
            method=method,
            document=document,
            recorded_by=user,
        )
        locked.touch()
        log(
            AuditAction.CREATE,
            user=user,
            obj=consent,
            note="Đồng ý xử lý dữ liệu" if consented else "Không đồng ý xử lý dữ liệu",
            request=request,
        )
    return consent


def reopen_worker(user, worker, *, position, source, request=None):
    """Mở lại hồ sơ Lưu trữ (câu 6): về Nháp và tạo lần ứng tuyển mới (Mới nộp). Hồ sơ đã ẩn danh
    hóa không mở lại được. Người đã có mã nhân viên giữ mã cũ."""
    _require_staff(user)
    if not isinstance(position, Position) or not position.is_active:
        raise WorkerDataError({"position": "Chọn vị trí ứng tuyển đang sử dụng."})
    if not isinstance(source, ApplicationSource) or not source.is_active:
        raise WorkerDataError({"source": "Chọn nguồn ứng tuyển đang sử dụng."})
    with transaction.atomic():
        workflow.transition(worker, VerificationStatus.DRAFT, user, request=request)
        application = Application.objects.create(
            worker=worker,
            position=position,
            source=source,
            applied_date=timezone.localdate(),
            created_by=user,
        )
        worker.touch()
        log(
            AuditAction.CREATE,
            user=user,
            obj=application,
            note="Lần ứng tuyển mới khi mở lại hồ sơ",
            request=request,
        )
    return application
