"""Tác vụ định kỳ (kien-truc.md mục 2.1). Mỗi bước idempotent: chạy lại bao nhiêu lần cũng
chỉ đổi những bản ghi đã đủ điều kiện."""

import logging

from django.db import transaction
from django.utils import timezone

from apps.audit.services import log
from apps.core.choices import AuditAction
from apps.intake.models import IntakeSession

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


def auto_archive(now=None):
    """Bước 2: tự Lưu trữ theo 4 quy tắc (câu 9). KHUNG: cần apps.workers.workflow.transition
    (Phase 4); Phase 2 chưa thay đổi hồ sơ nào."""
    return 0


def run_daily_jobs(now=None):
    """Chạy lần lượt các bước; trả số lượng đã xử lý của từng bước."""
    return {
        "intake_expired": expire_intake_sessions(now),
        "auto_archived": auto_archive(now),
    }
