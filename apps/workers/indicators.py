"""Ba chỉ số tự tính (yeu-cau.md mục II; models.md mục 4.6): không phải trạng thái.

- Thiếu giấy tờ: còn nhóm tài liệu bắt buộc chưa đủ (documents.services.missing_groups là bản
  tính cho MỘT hồ sơ; ở đây là bản cho cả danh sách, hai bản phải cho cùng kết quả, có test).
- Hoàn thiện: Đã xác minh và không thiếu giấy tờ.
- Sắp hết hạn: CCCD hoặc hợp đồng hết hạn trong N ngày tới (N = SystemSetting.expiry_warning_days).
"""

import datetime

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from apps.core.choices import DocumentVerificationStatus, VerificationStatus
from apps.core.models import RequiredDocumentGroup, SystemSetting
from apps.documents.models import WorkerDocument
from apps.employment.models import Contract


def annotate_documents(queryset):
    """Thêm cột `missing_documents` (True nếu còn nhóm bắt buộc chưa đủ) vào queryset hồ sơ."""
    qualifying = WorkerDocument.objects.filter(
        worker=OuterRef(OuterRef("pk")),
        is_current=True,
        document_type__required_group=OuterRef("pk"),
    ).exclude(verification_status=DocumentVerificationStatus.INVALID)
    incomplete_groups = (
        RequiredDocumentGroup.objects.filter(is_active=True)
        .annotate(has_document=Exists(qualifying))
        .filter(has_document=False)
    )
    return queryset.annotate(missing_documents=Exists(incomplete_groups))


def missing_documents(queryset):
    return annotate_documents(queryset).filter(missing_documents=True)


def complete(queryset):
    """Hoàn thiện: Đã xác minh và không thiếu giấy tờ."""
    return annotate_documents(queryset).filter(
        verification_status=VerificationStatus.VERIFIED, missing_documents=False
    )


def _window(today=None, days=None):
    today = today or timezone.localdate()
    days = SystemSetting.load().expiry_warning_days if days is None else days
    return today, today + datetime.timedelta(days=days)


def id_expiring(queryset, today=None, days=None):
    """Hồ sơ có CCCD hết hạn từ hôm nay tới hôm nay + N ngày (đã hết hạn thì không tính)."""
    start, end = _window(today, days)
    return queryset.filter(identity__expiry_date__range=(start, end))


def contract_expiring_q(today=None, days=None):
    start, end = _window(today, days)
    return Contract.objects.filter(expiry_date__range=(start, end))


def contract_expiring(queryset, today=None, days=None):
    """Hồ sơ có hợp đồng hết hạn từ hôm nay tới hôm nay + N ngày."""
    contracts = contract_expiring_q(today, days).filter(worker=OuterRef("pk"))
    return queryset.filter(Exists(contracts))


def expiring(queryset, today=None, days=None):
    """Sắp hết hạn: CCCD hoặc hợp đồng."""
    start, end = _window(today, days)
    contracts = Contract.objects.filter(expiry_date__range=(start, end), worker=OuterRef("pk"))
    return queryset.filter(Q(identity__expiry_date__range=(start, end)) | Exists(contracts))
