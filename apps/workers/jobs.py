"""Tác vụ định kỳ (kien-truc.md mục 2.1). Mỗi bước idempotent: chạy lại bao nhiêu lần cũng
chỉ đổi những bản ghi đã đủ điều kiện."""

import datetime
import logging

from django.db import transaction
from django.utils import timezone

from apps.audit.services import log
from apps.core.choices import AuditAction, RecruitmentStatus, VerificationStatus, WorkStatus
from apps.core.dates import add_months
from apps.core.models import SystemSetting
from apps.intake.models import IntakeSession

from .models import StatusChange, Worker
from .retention import ABANDONED_REASON
from .workflow import TransitionError, Trigger, transition

logger = logging.getLogger(__name__)


def expire_intake_sessions(now=None):
    """Bước 1: xóa phiên nhận diện hết hạn (tệp, kết quả mã hóa, dòng phiên), ghi nhật ký
    INTAKE_EXPIRE với người thực hiện "Hệ thống". Mỗi phiên một giao dịch; lỗi ở một phiên
    được ghi vào log và không chặn phiên khác. Trả số phiên đã xóa."""
    now = now or timezone.now()
    removed = 0
    for session in IntakeSession.objects.filter(expires_at__lt=now):
        try:
            with transaction.atomic():
                log(
                    AuditAction.INTAKE_EXPIRE,
                    obj=session,
                    note="Phiên nhận diện hết hạn, đã xóa tệp và kết quả",
                )
                session.close()
            removed += 1
        except Exception:
            logger.exception("Không xóa được phiên nhận diện %s", session.pk)
    return removed


def _archive_candidates(now):
    """Trả {pk hồ sơ: lý do} theo 4 quy tắc tự Lưu trữ (câu 9); quy tắc nào khớp trước thì dùng.

    Không bao giờ xét: Chờ duyệt, hồ sơ đã ẩn danh, hồ sơ có trạng thái làm việc Thử việc hoặc
    Đang làm việc (hồ sơ nhập từ Excel có thể ở Nháp mà người đó vẫn đang làm).
    """
    setting = SystemSetting.load()
    today = timezone.localdate(now)
    VS = VerificationStatus
    base = Worker.objects.filter(anonymized_at__isnull=True).exclude(
        employment__work_status__in=[WorkStatus.PROBATION, WorkStatus.ACTIVE]
    )
    open_states = [
        VS.DRAFT,
        VS.NEEDS_INFO,
        VS.VERIFIED,
    ]  # quy tắc 1–2 áp dụng cho các trạng thái này
    found = {}

    def add(worker, reason):
        found.setdefault(worker.pk, reason)

    # 1. Đã nghỉ việc quá N ngày kể từ ngày nghỉ.
    days = setting.auto_archive_resigned_days
    for worker in base.filter(
        verification_status__in=open_states,
        employment__work_status=WorkStatus.RESIGNED,
        employment__resign_date__isnull=False,
        employment__resign_date__lt=today - datetime.timedelta(days=days),
    ):
        add(worker, f"Tự Lưu trữ: đã nghỉ việc quá {days} ngày (hồ sơ {worker.worker_code})")

    # 2. Chưa có mã NV, lần ứng tuyển gần nhất Không đạt / Ứng viên từ chối quá N ngày.
    days = setting.auto_archive_failed_days
    failed = [RecruitmentStatus.FAILED, RecruitmentStatus.DECLINED]
    for worker in base.filter(
        verification_status__in=open_states,
        employee_code__isnull=True,
        applications__status__in=failed,
    ).distinct():
        latest = worker.applications.order_by("-applied_date", "-id").first()
        if (
            latest.status in failed
            and latest.result_date is not None
            and latest.result_date < today - datetime.timedelta(days=days)
        ):
            add(
                worker,
                f"Tự Lưu trữ: không đạt hoặc từ chối quá {days} ngày (hồ sơ {worker.worker_code})",
            )

    # 3. Bị từ chối quá N ngày kể từ lúc bị từ chối (dùng chung số ngày với quy tắc 2).
    for worker in base.filter(verification_status=VS.REJECTED):
        rejected = (
            StatusChange.objects.filter(worker=worker, to_status=VS.REJECTED)
            .order_by("-changed_at", "-id")
            .first()
        )
        if rejected and timezone.localtime(rejected.changed_at).date() < today - datetime.timedelta(
            days=days
        ):
            add(worker, f"Tự Lưu trữ: bị từ chối quá {days} ngày (hồ sơ {worker.worker_code})")

    # 4. Nháp / Cần bổ sung không có thay đổi nào trong N tháng: hồ sơ bỏ dở.
    cutoff = add_months(today, -setting.stale_draft_months)
    start_of_cutoff = timezone.make_aware(datetime.datetime.combine(cutoff, datetime.time.min))
    for worker in base.filter(
        verification_status__in=[VS.DRAFT, VS.NEEDS_INFO], updated_at__lt=start_of_cutoff
    ):
        add(worker, f"{ABANDONED_REASON} (hồ sơ {worker.worker_code})")
    return found


def auto_archive(now=None):
    """Bước 2: tự Lưu trữ theo 4 quy tắc (câu 9), người thực hiện là "Hệ thống". Mỗi hồ sơ một
    giao dịch; lỗi ở một hồ sơ được ghi log và không chặn hồ sơ khác. Trả số hồ sơ đã Lưu trữ."""
    now = now or timezone.now()
    archived = 0
    for pk, reason in _archive_candidates(now).items():
        try:
            with transaction.atomic():
                worker = Worker.objects.get(pk=pk)
                transition(
                    worker, VerificationStatus.ARCHIVED, None, reason, trigger=Trigger.SYSTEM
                )
            archived += 1
        except TransitionError:
            # Hồ sơ vừa đổi trạng thái (ví dụ vừa gửi duyệt) hoặc vừa bắt đầu đi làm: bỏ qua.
            logger.info("Bỏ qua tự Lưu trữ hồ sơ pk=%s: không còn đủ điều kiện", pk)
        except Exception:
            logger.exception("Không tự Lưu trữ được hồ sơ pk=%s", pk)
    return archived


def run_daily_jobs(now=None):
    """Chạy lần lượt các bước; trả số lượng đã xử lý của từng bước."""
    return {
        "intake_expired": expire_intake_sessions(now),
        "auto_archived": auto_archive(now),
    }
