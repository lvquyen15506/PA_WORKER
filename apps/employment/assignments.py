"""Đợt làm việc tại công ty khách hàng (v1.1, câu 40, 43, 48; models.md mục 3.9) và lịch sử lương
(câu 41, 42). Phase 6 bước 4 chỉ có hàm đóng đợt khi nghỉ việc; phần còn lại ở bước 5."""

from apps.audit.services import log
from apps.core.choices import AuditAction

from .models import WorkAssignment


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
