"""Hạn lưu trữ và ẩn danh hóa hồ sơ (lam-ro-yeu-cau.md câu 2, 30, 38; models.md mục 4.6–4.7).

- retention_info(): hồ sơ Lưu trữ nào cũng tính được căn cứ và ngày hết hạn (6 căn cứ, xét theo
  thứ tự, gặp căn cứ đầu tiên khớp thì dùng).
- expired_entries() / expired_queryset(): danh sách chờ hủy (không phải trạng thái; chỉ là danh sách
  tính tự động).
- anonymize(): "hủy" = ẩn danh hóa, không xóa cứng bản ghi. Chỉ Admin.
- anonymize_on_request(): Admin ẩn danh hóa sớm theo yêu cầu của chủ thể dữ liệu (câu 38).
"""

import logging
from collections import namedtuple

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit.models import AuditPersonalValue
from apps.audit.services import log
from apps.core.choices import (
    AnonymizationKind,
    AuditAction,
    RecruitmentStatus,
    RetentionBasis,
    RoleCode,
    VerificationStatus,
)
from apps.core.dates import add_months, add_years
from apps.core.models import SystemSetting
from apps.core.storage import private_storage
from apps.documents.models import WorkerDocument
from apps.employment.models import Contract, Employment, SalaryHistory, WorkAssignment
from apps.recruitment.models import Application, Certificate, Education, WorkExperience

from .models import (
    AnonymizationItem,
    AnonymizationRecord,
    EmergencyContact,
    IdentityDocument,
    StatusChange,
    Worker,
)

logger = logging.getLogger(__name__)

# Lý do tác vụ hằng ngày ghi khi tự Lưu trữ hồ sơ bỏ dở (quy tắc 4 của câu 9), dạng
# "Hồ sơ bỏ dở (hồ sơ <mã>)". Căn cứ "Hồ sơ bỏ dở" nhận ra bằng lý do bắt đầu bằng chuỗi này kèm
# người thực hiện là Hệ thống (người dùng gõ tay cùng chữ vẫn không tính).
ABANDONED_REASON = "Hồ sơ bỏ dở"
ANONYMIZED_NAME = "(Đã ẩn danh)"

Retention = namedtuple("Retention", ["basis", "expires_on"])


class RetentionError(Exception):
    """Vi phạm quy tắc nghiệp vụ (hồ sơ chưa Lưu trữ, chưa hết hạn, thiếu lý do...)."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class RetentionForbidden(RetentionError):
    """Không đủ quyền (chỉ Admin được ẩn danh hóa); view trả 403."""


# --- Hạn lưu trữ (câu 2) ------------------------------------------------------------------
def _archived_change(worker):
    """Lần chuyển sang Lưu trữ gần nhất trong lịch sử trạng thái."""
    change = (
        StatusChange.objects.filter(worker=worker, to_status=VerificationStatus.ARCHIVED)
        .order_by("-changed_at", "-id")
        .first()
    )
    if change is None:
        raise RetentionError(f"Hồ sơ {worker.worker_code} không có lịch sử chuyển sang Lưu trữ.")
    return change


def _resign_date(worker):
    return (
        Employment.objects.filter(worker=worker, resign_date__isnull=False)
        .values_list("resign_date", flat=True)
        .first()
    )


def _latest_application(worker):
    return worker.applications.order_by("-applied_date", "-id").first()


def retention_info(worker, setting=None):
    """(căn cứ lưu trữ, ngày hết hạn lưu trữ) của hồ sơ đang Lưu trữ.

    Báo RetentionError nếu hồ sơ chưa Lưu trữ hoặc không tính được. "Ngày chuyển Lưu trữ" lấy từ
    StatusChange gần nhất sang Lưu trữ theo giờ Việt Nam. Hết hạn đúng ngày `expires_on`; sang
    ngày hôm sau hồ sơ vào danh sách chờ hủy.
    """
    if worker.verification_status != VerificationStatus.ARCHIVED:
        raise RetentionError(f"Hồ sơ {worker.worker_code} chưa ở trạng thái Lưu trữ.")
    setting = setting or SystemSetting.load()
    archived = _archived_change(worker)
    archived_on = timezone.localtime(archived.changed_at).date()
    years, months = setting.resigned_retention_years, setting.failed_retention_months

    if worker.employee_code:  # công nhân
        resign_date = _resign_date(worker)
        if resign_date is not None:
            return Retention(RetentionBasis.RESIGNED, add_years(resign_date, years))
        return Retention(RetentionBasis.EMPLOYEE_OTHER, add_years(archived_on, years))

    # ứng viên (chưa có mã NV)
    application = _latest_application(worker)
    if (
        application is not None
        and application.status in (RecruitmentStatus.FAILED, RecruitmentStatus.DECLINED)
        and application.result_date is not None
    ):
        return Retention(
            RetentionBasis.FAILED_CANDIDATE, add_months(application.result_date, months)
        )
    if archived.from_status == VerificationStatus.REJECTED:
        return Retention(RetentionBasis.REJECTED, add_months(archived_on, months))
    if archived.changed_by_id is None and archived.reason.startswith(ABANDONED_REASON):
        return Retention(RetentionBasis.ABANDONED, add_months(archived_on, months))
    return Retention(RetentionBasis.CANDIDATE_OTHER, add_months(archived_on, months))


def expired_entries(today=None):
    """Danh sách chờ hủy: [(hồ sơ, Retention)] của hồ sơ Lưu trữ, chưa ẩn danh, quá hạn lưu trữ,
    hết hạn sớm nhất trước."""
    today = today or timezone.localdate()
    setting = SystemSetting.load()
    entries = []
    archived = Worker.objects.filter(
        verification_status=VerificationStatus.ARCHIVED, anonymized_at__isnull=True
    )
    for worker in archived:
        try:
            info = retention_info(worker, setting)
        except RetentionError:
            # Một hồ sơ hỏng (Lưu trữ nhưng không có lịch sử chuyển, ví dụ do sửa dữ liệu tay) không
            # được làm hỏng cả danh sách; ghi lỗi để người vận hành xử lý.
            logger.error("Hồ sơ %s Lưu trữ nhưng không tính được hạn lưu trữ", worker.worker_code)
            continue
        if info.expires_on < today:
            entries.append((worker, info))
    entries.sort(key=lambda entry: (entry[1].expires_on, entry[0].pk))
    return entries


def expired_queryset(today=None):
    return Worker.objects.filter(pk__in=[w.pk for w, _ in expired_entries(today)])


# --- Ẩn danh hóa (câu 2, 30, 38; models.md mục 4.7) --------------------------------------
def _next_record_no(now):
    """BBH-YYYY-NNN: số lớn nhất của năm + 1. Khóa dòng Cài đặt để hai lần hủy không trùng số
    (ràng buộc unique của record_no là lớp chặn cuối)."""
    SystemSetting.objects.select_for_update().get(pk=1)
    year = timezone.localtime(now).year
    prefix = f"BBH-{year}-"
    numbers = [
        int(no[len(prefix) :])
        for no in AnonymizationRecord.objects.filter(record_no__startswith=prefix).values_list(
            "record_no", flat=True
        )
        if no[len(prefix) :].isdigit()
    ]
    return f"{prefix}{max(numbers, default=0) + 1:03d}"


def _delete_files(names):
    for name in names:
        try:
            private_storage.delete(name)
        except Exception:
            logger.exception("Không xóa được tệp %s khi ẩn danh hóa", name)


def _wipe(worker, now):
    """Xóa dữ liệu cá nhân theo bảng 4.7; trả danh sách đường dẫn tệp cần xóa khỏi đĩa."""
    Worker.objects.filter(pk=worker.pk).update(
        full_name=ANONYMIZED_NAME,
        name_search="",
        date_of_birth=None,
        gender="",
        phone="",
        email="",
        current_address="",
        skills="",
        note="",
        anonymized_at=now,
        updated_at=now,
    )
    IdentityDocument.objects.filter(worker=worker).update(
        id_number_enc=None,
        id_number_hash=None,
        old_id_number_enc=None,
        issue_date=None,
        issue_place="",
        expiry_date=None,
        hometown="",
        birth_registration_place="",
        permanent_address_enc=None,
    )
    EmergencyContact.objects.filter(worker=worker).update(full_name="", relationship="", phone="")
    Application.objects.filter(worker=worker).update(
        expected_salary=None, interview_notes="", reject_reason=""
    )
    Education.objects.filter(worker=worker).update(school_name="", major="", note="")
    Certificate.objects.filter(worker=worker).update(name="", issuer="", note="")
    WorkExperience.objects.filter(worker=worker).update(
        company_name="", job_title="", description=""
    )
    Employment.objects.filter(worker=worker).update(resign_note="")
    Contract.objects.filter(worker=worker).update(note="")
    # v1.1: giữ công ty khách, vị trí, ngày của đợt (thống kê); xóa ghi chú. Lịch sử lương bị xóa
    # toàn bộ: ngoại lệ có kiểm soát của bảng chỉ thêm, CHỈ ở đây (CLAUDE.md, models.md 4.7).
    WorkAssignment.objects.filter(worker=worker).update(note="")
    SalaryHistory.objects.filter(worker=worker).delete()

    # Tài liệu: MỌI phiên bản (kể cả bản đã bị thay thế), biên bản đồng ý và tệp hợp đồng.
    documents = WorkerDocument.objects.filter(
        Q(worker=worker) | Q(consents__worker=worker) | Q(contracts__worker=worker)
    ).distinct()
    names = [d.stored_file.name for d in documents if d.stored_file]
    # note là chữ người dùng tự gõ nên có thể chứa tên: xóa cùng tên tệp gốc.
    WorkerDocument.objects.filter(pk__in=[d.pk for d in documents]).update(
        stored_file=None, original_name="", note=""
    )
    # Giá trị trước/sau của trường cá nhân trong nhật ký (câu 30). Dòng nhật ký vẫn giữ.
    AuditPersonalValue.objects.filter(worker=worker).delete()
    return names


def anonymize(workers, kind, user, *, note="", request_ref="", request=None, today=None):
    """Ẩn danh hóa các hồ sơ Lưu trữ, sinh một biên bản; trả AnonymizationRecord.

    Chỉ Admin. Mọi hồ sơ phải đang Lưu trữ và chưa ẩn danh; với kind = EXPIRED còn phải đã quá
    hạn lưu trữ. Thao tác không hoàn tác được. Tệp trên đĩa chỉ bị xóa sau khi giao dịch
    commit, nên giao dịch lỗi thì không mất tệp.
    """
    kind = AnonymizationKind(kind)
    if user is None or getattr(user, "role", None) is None or user.role.code != RoleCode.ADMIN:
        raise RetentionForbidden("Chỉ Admin được ẩn danh hóa hồ sơ.")
    workers = list(workers)
    if not workers:
        raise RetentionError("Chưa chọn hồ sơ nào.")
    today = today or timezone.localdate()
    note = (note or "").strip()
    request_ref = (request_ref or "").strip()
    if kind == AnonymizationKind.SUBJECT_REQUEST and not (note and request_ref):
        raise RetentionError("Cần ghi lý do và số hoặc ngày đơn yêu cầu.")

    with transaction.atomic():
        pks = [w.pk for w in workers]
        locked = list(Worker.objects.select_for_update().filter(pk__in=pks).order_by("pk"))
        if len(locked) != len(set(pks)):
            raise RetentionError("Có hồ sơ không tồn tại.")
        setting = SystemSetting.load()
        now = timezone.now()
        plan = []
        for worker in locked:
            if worker.anonymized_at is not None:
                raise RetentionError(f"Hồ sơ {worker.worker_code} đã được ẩn danh hóa.")
            info = retention_info(worker, setting)  # báo lỗi nếu chưa Lưu trữ
            if kind == AnonymizationKind.EXPIRED and info.expires_on >= today:
                raise RetentionError(f"Hồ sơ {worker.worker_code} chưa hết hạn lưu trữ.")
            plan.append((worker, info))

        record = AnonymizationRecord.objects.create(
            record_no=_next_record_no(now),
            kind=kind,
            request_ref=request_ref,
            performed_by=user,
            worker_count=len(plan),
            note=note,
        )
        file_names = []
        for worker, info in plan:
            AnonymizationItem.objects.create(
                record=record,
                worker=worker,
                worker_code=worker.worker_code,
                employee_code=worker.employee_code or "",
                retention_basis=info.basis,
                retention_expired_on=info.expires_on,
            )
            file_names += _wipe(worker, now)
            # Chỉ mã hồ sơ và số biên bản, không họ tên (câu 30).
            log(
                AuditAction.ANONYMIZE,
                user=user,
                obj=worker,
                note=f"{kind.label}; biên bản {record.record_no}",
                request=request,
            )
        transaction.on_commit(lambda: _delete_files(file_names))
    return record


def anonymize_on_request(worker, user, *, reason, request_ref, confirm_code, request=None):
    """Ẩn danh hóa sớm theo yêu cầu của chủ thể dữ liệu (câu 38). Chỉ Admin; hồ sơ phải Lưu trữ
    và chưa ẩn danh; bắt buộc lý do, số đơn và mã hồ sơ gõ lại khớp (kiểm tra ở máy chủ)."""
    if user is None or getattr(user, "role", None) is None or user.role.code != RoleCode.ADMIN:
        raise RetentionForbidden("Chỉ Admin được ẩn danh hóa hồ sơ.")
    current = Worker.objects.get(pk=worker.pk)
    if current.anonymized_at is not None:
        raise RetentionError("Hồ sơ này đã được ẩn danh hóa.")
    if current.verification_status != VerificationStatus.ARCHIVED:
        raise RetentionError("Chỉ ẩn danh hóa hồ sơ đã chuyển Lưu trữ. Hãy chuyển Lưu trữ trước.")
    if not (reason or "").strip():
        raise RetentionError("Cần ghi lý do.")
    if not (request_ref or "").strip():
        raise RetentionError("Cần ghi số hoặc ngày đơn yêu cầu.")
    if (confirm_code or "").strip() != current.worker_code:
        raise RetentionError("Mã hồ sơ gõ lại không khớp.")
    return anonymize(
        [current],
        AnonymizationKind.SUBJECT_REQUEST,
        user,
        note=reason,
        request_ref=request_ref,
        request=request,
    )


__all__ = [
    "ABANDONED_REASON",
    "Retention",
    "RetentionError",
    "RetentionForbidden",
    "anonymize",
    "anonymize_on_request",
    "expired_entries",
    "expired_queryset",
    "retention_info",
]
