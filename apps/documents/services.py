"""Nghiệp vụ tài liệu hồ sơ (models.md mục 3.5, 4.6). Bước 3 mới có phần chỉ số "thiếu giấy tờ";
tải lên, thay thế, xác minh thêm ở bước 4."""

from apps.core.choices import DocumentVerificationStatus
from apps.core.models import RequiredDocumentGroup

from .models import WorkerDocument


def missing_groups(worker):
    """Các nhóm tài liệu bắt buộc (đang dùng) mà hồ sơ chưa đủ (câu 4).

    Nhóm đủ khi có ít nhất một tài liệu hiện hành (is_current) thuộc loại trong nhóm và có trạng
    thái xác minh khác "Không hợp lệ". Trả danh sách RequiredDocumentGroup theo thứ tự hiển thị.
    """
    have = set(
        WorkerDocument.objects.filter(
            worker=worker, is_current=True, document_type__required_group__isnull=False
        )
        .exclude(verification_status=DocumentVerificationStatus.INVALID)
        .values_list("document_type__required_group_id", flat=True)
    )
    return [g for g in RequiredDocumentGroup.objects.filter(is_active=True) if g.pk not in have]
