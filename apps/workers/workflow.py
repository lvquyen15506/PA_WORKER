"""Quy trình duyệt hồ sơ (docs/thiet-ke/models.md mục 4.1–4.3; lam-ro-yeu-cau.md câu 8, 9).

transition() là ĐƯỜNG DUY NHẤT đổi Worker.verification_status. Mỗi lần chuyển luôn ghi một dòng
StatusChange và một dòng nhật ký (qua apps.audit.services.log). Có test quét mã nguồn khẳng định
không nơi nào khác gán verification_status (tests/test_verification_status_scan.py).

Hai loại lỗi:
- TransitionForbidden: không đủ quyền (vai trò, tự duyệt, tác nhân không được phép); view trả 403.
- TransitionError: vi phạm quy tắc nghiệp vụ (thiếu trường, thiếu lý do, cặp chuyển không có
  trong bảng, đang Thử việc/Đang làm việc...); view báo lỗi tiếng Việt, không đổi gì.
"""

import enum
from collections import namedtuple
from dataclasses import dataclass

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone

from apps.audit.services import log
from apps.core.choices import AuditAction, RoleCode, VerificationStatus, WorkStatus

from .models import StatusChange, Worker
from .rules import ALL_STAFF, MANAGERS, role_code

VS = VerificationStatus


class Trigger(enum.Enum):
    MANUAL = "manual"  # người dùng bấm nút
    SYSTEM = "system"  # tác vụ hằng ngày (user = None, "Hệ thống")
    IDENTITY_EDIT = "identity_edit"  # sửa họ tên/ngày sinh/số CCCD khi Đã xác minh


class TransitionError(Exception):
    """Vi phạm quy tắc nghiệp vụ. `issues` là danh sách SubmissionIssue khi thiếu trường."""

    def __init__(self, message, issues=()):
        super().__init__(message)
        self.message = message
        self.issues = tuple(issues)


class TransitionForbidden(TransitionError):
    """Không đủ quyền thực hiện chuyển này (view trả 403)."""


@dataclass(frozen=True)
class Rule:
    roles: frozenset  # vai trò được chuyển (không áp dụng cho Hệ thống)
    triggers: frozenset = frozenset({Trigger.MANUAL})
    reason_required: bool = False  # chỉ bắt buộc với chuyển thủ công
    submission: bool = False  # kiểm đủ trường "Gửi duyệt" (mục 4.3)
    self_approval: bool = False  # áp dụng quy tắc không tự duyệt (mục 4.2)
    to_archive: bool = False  # chuyển sang Lưu trữ: chặn khi Thử việc/Đang làm việc
    reopen: bool = False  # mở lại hồ sơ: ghi REOPEN, chặn khi đã ẩn danh hóa


_MANUAL = frozenset({Trigger.MANUAL})
_MANUAL_OR_SYSTEM = frozenset({Trigger.MANUAL, Trigger.SYSTEM})

# Bảng 4.1. Mọi cặp không có trong bảng đều bị từ chối. Viewer bị từ chối mọi chuyển.
TRANSITIONS = {
    (VS.DRAFT, VS.PENDING): Rule(ALL_STAFF, submission=True),
    (VS.PENDING, VS.VERIFIED): Rule(MANAGERS, self_approval=True),
    (VS.PENDING, VS.NEEDS_INFO): Rule(MANAGERS, reason_required=True, self_approval=True),
    (VS.PENDING, VS.REJECTED): Rule(MANAGERS, reason_required=True, self_approval=True),
    (VS.NEEDS_INFO, VS.PENDING): Rule(ALL_STAFF, submission=True),
    # Tự động khi sửa trường định danh; không có đường thủ công.
    (VS.VERIFIED, VS.PENDING): Rule(ALL_STAFF, triggers=frozenset({Trigger.IDENTITY_EDIT})),
    (VS.REJECTED, VS.ARCHIVED): Rule(ALL_STAFF, triggers=_MANUAL_OR_SYSTEM, to_archive=True),
    (VS.DRAFT, VS.ARCHIVED): Rule(ALL_STAFF, triggers=_MANUAL_OR_SYSTEM, to_archive=True),
    (VS.NEEDS_INFO, VS.ARCHIVED): Rule(ALL_STAFF, triggers=_MANUAL_OR_SYSTEM, to_archive=True),
    # HR không chuyển Lưu trữ hồ sơ Đã xác minh (câu 9 [Nội bộ]).
    (VS.VERIFIED, VS.ARCHIVED): Rule(
        MANAGERS, triggers=_MANUAL_OR_SYSTEM, reason_required=True, to_archive=True
    ),
    (VS.ARCHIVED, VS.DRAFT): Rule(ALL_STAFF, reopen=True),
}

# Trường định danh: sửa khi Đã xác minh thì hồ sơ tự về Chờ duyệt.
IDENTITY_FIELD_LABELS = ("họ tên", "ngày sinh", "số CCCD")

# --- Trường bắt buộc khi gửi duyệt (mục 4.3) ----------------------------------------------
SubmissionIssue = namedtuple("SubmissionIssue", ["field", "message"])


def submission_errors(worker):
    """Danh sách SubmissionIssue còn thiếu để gửi duyệt; rỗng = đủ.

    Thiếu giấy tờ (tài liệu) KHÔNG chặn gửi duyệt: đó là chỉ số, không phải điều kiện.
    """
    issues = []

    def missing(field_name, message):
        issues.append(SubmissionIssue(field_name, message))

    if not (worker.full_name or "").strip():
        missing("full_name", "Thiếu họ và tên.")
    if not (worker.phone or "").strip():
        missing("phone", "Thiếu số điện thoại.")
    if worker.date_of_birth is None:
        missing("date_of_birth", "Thiếu ngày sinh.")
    if not worker.gender:
        missing("gender", "Thiếu giới tính.")
    if not (worker.nationality or "").strip():
        missing("nationality", "Thiếu quốc tịch.")
    if not (worker.current_address or "").strip():
        missing("current_address", "Thiếu nơi ở hiện tại.")

    try:
        identity = worker.identity
    except ObjectDoesNotExist:
        identity = None
    if identity is None or not identity.id_doc_type:
        missing("id_doc_type", "Thiếu loại giấy tờ.")
    if identity is None or not identity.id_number_enc:
        missing("id_number", "Thiếu số CCCD.")

    complete_contact = any(
        (c.full_name or "").strip() and (c.relationship or "").strip() and (c.phone or "").strip()
        for c in worker.emergency_contacts.all()
    )
    if not complete_contact:
        missing(
            "emergency_contact",
            "Cần ít nhất một người liên hệ khẩn cấp có đủ họ tên, quan hệ và số điện thoại.",
        )

    latest_consent = worker.consents.order_by("-recorded_at", "-id").first()
    if latest_consent is None or not latest_consent.consented:
        missing("consent", "Chưa ghi nhận đồng ý xử lý dữ liệu cá nhân.")
    return issues


# --- Không tự duyệt (mục 4.2) -------------------------------------------------------------
def is_own_submission(worker, user):
    """True nếu user là người tạo hồ sơ hoặc người gửi duyệt lần gần nhất."""
    if user is None:
        return False
    if worker.created_by_id == user.pk:
        return True
    last = (
        StatusChange.objects.filter(worker=worker, to_status=VS.PENDING)
        .order_by("-changed_at", "-id")
        .first()
    )
    return last is not None and last.changed_by_id == user.pk


def can_review(worker, user):
    """Người này duyệt/trả lại/từ chối được hồ sơ Chờ duyệt này không (kể cả Admin)."""
    return (
        worker.verification_status == VS.PENDING
        and role_code(user) in MANAGERS
        and not is_own_submission(worker, user)
    )


# --- Chuyển trạng thái -------------------------------------------------------------------
def _has_active_work(worker):
    from apps.employment.models import Employment

    return Employment.objects.filter(
        worker=worker, work_status__in=[WorkStatus.PROBATION, WorkStatus.ACTIVE]
    ).exists()


def _authorize(worker, from_status, to_status, user, trigger):
    """Trả Rule nếu tác nhân được phép chuyển; nếu không thì ném lỗi."""
    if trigger == Trigger.SYSTEM:
        if user is not None:
            raise TransitionForbidden("Tác vụ hệ thống không có người thực hiện.")
        role = None
    else:
        role = role_code(user)
        if role is None:
            raise TransitionForbidden("Bạn cần đăng nhập để thực hiện thao tác này.")
        if role == RoleCode.VIEWER.value:
            raise TransitionForbidden("Bạn không có quyền thực hiện thao tác này.")

    rule = TRANSITIONS.get((from_status, to_status))
    if rule is None:
        raise TransitionError(
            f"Không thể chuyển hồ sơ từ “{from_status.label}” sang “{to_status.label}”."
        )
    if trigger not in rule.triggers or (trigger != Trigger.SYSTEM and role not in rule.roles):
        raise TransitionForbidden("Bạn không có quyền thực hiện thao tác này.")
    if rule.self_approval and is_own_submission(worker, user):
        raise TransitionForbidden(
            "Bạn không được duyệt hồ sơ do chính mình tạo hoặc gửi duyệt. Hãy nhờ người khác."
        )
    return rule


def transition(
    worker,
    to_status,
    user=None,
    reason="",
    *,
    trigger=Trigger.MANUAL,
    identity_fields=None,
    request=None,
):
    """Đổi trạng thái xác minh của hồ sơ; trả StatusChange vừa ghi.

    user      người thực hiện; None khi trigger = SYSTEM ("Hệ thống").
    reason    lý do do người dùng nhập; hệ thống tự điền cho SYSTEM và IDENTITY_EDIT (chỉ dùng
              mã hồ sơ, không họ tên, câu 30).
    identity_fields   tên các trường định danh vừa sửa (chỉ cho IDENTITY_EDIT).

    Chạy trong một giao dịch, khóa dòng hồ sơ rồi đọc lại trạng thái hiện tại: hai người bấm cùng
    lúc thì chỉ một lần thành công.
    """
    to_status = VS(to_status)
    with transaction.atomic():
        locked = Worker.objects.select_for_update().get(pk=worker.pk)
        from_status = VS(locked.verification_status)
        rule = _authorize(locked, from_status, to_status, user, trigger)

        if rule.reopen and locked.anonymized_at is not None:
            raise TransitionError("Hồ sơ đã ẩn danh hóa, không mở lại được.")
        if rule.to_archive and _has_active_work(locked):
            raise TransitionError(
                "Hồ sơ đang ở trạng thái làm việc Thử việc hoặc Đang làm việc, "
                "không chuyển Lưu trữ được."
            )

        reason_text = (reason or "").strip()
        if trigger == Trigger.IDENTITY_EDIT:
            labels = ", ".join(identity_fields or IDENTITY_FIELD_LABELS)
            reason_text = f"Sửa trường định danh: {labels}"
        elif trigger == Trigger.SYSTEM and not reason_text:
            reason_text = f"Hệ thống tự chuyển hồ sơ {locked.worker_code} sang {to_status.label}"
        elif rule.reason_required and not reason_text:
            raise TransitionError("Cần ghi lý do.")

        if rule.submission:
            issues = submission_errors(locked)
            if issues:
                raise TransitionError("Hồ sơ chưa đủ thông tin để gửi duyệt.", issues)

        now = timezone.now()
        Worker.objects.filter(pk=locked.pk).update(
            verification_status=to_status.value, updated_at=now
        )
        # Lý do do người dùng gõ có thể chứa họ tên (câu 30): đánh dấu để ẩn danh hóa thay bằng
        # "(đã ẩn danh)", và ghi vào nhật ký như trường cá nhân (AuditPersonalValue, bị xóa khi
        # ẩn danh hóa) thay vì AuditLog.note. Lý do hệ thống tự điền chỉ có mã hồ sơ nên giữ ở note.
        reason_by_user = trigger == Trigger.MANUAL and bool(reason_text)
        change = StatusChange.objects.create(
            worker=locked,
            from_status=from_status.value,
            to_status=to_status.value,
            reason=reason_text,
            reason_by_user=reason_by_user,
            changed_by=user,
        )
        changes = {"verification_status": (from_status.value, to_status.value)}
        if reason_by_user:
            changes["status_reason"] = (None, reason_text)
        log(
            AuditAction.REOPEN if rule.reopen else AuditAction.STATUS_CHANGE,
            user=user,
            obj=locked,
            changes=changes,
            note="" if reason_by_user else reason_text,
            request=request,
        )
        worker.verification_status = to_status.value
        worker.updated_at = now
        return change


def record_creation(worker, user):
    """Ghi dòng đầu của dòng thời gian trạng thái: tạo hồ sơ (từ trống sang Nháp)."""
    return StatusChange.objects.create(
        worker=worker, from_status="", to_status=VS.DRAFT.value, reason="", changed_by=user
    )
