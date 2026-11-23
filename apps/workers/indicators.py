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


def assignment_due_info(today=None, days=None, months=None, worker_ids=None):
    """Đợt làm việc sắp đủ thời hạn (câu 43, 48): {worker_id: (ngày đủ hạn, ngày bắt đầu chuỗi,
    đợt hiện tại)} của công nhân đang có đợt và đủ điều kiện cảnh báo.

    Chuỗi = các đợt liền nhau có cùng TÊN công ty khách, bỏ qua địa điểm (so không phân biệt hoa
    thường, gộp khoảng trắng, giữ dấu); đợt sau bắt đầu không quá 1 ngày sau khi đợt trước kết thúc.
    12 tháng tính từ ngày bắt đầu của đợt đầu chuỗi. Cảnh báo khi ngày đủ hạn nằm trong `days` ngày
    tới (hoặc đã qua) và đợt hiện tại chưa kết thúc hoặc kết thúc sau ngày đủ hạn [Giả định]."""
    from apps.core.dates import add_months
    from apps.core.text import normalize_key
    from apps.employment.assignments import current_q
    from apps.employment.models import WorkAssignment

    setting = SystemSetting.load()
    today = today or timezone.localdate()
    days = setting.expiry_warning_days if days is None else days
    months = setting.assignment_limit_months if months is None else months
    horizon = today + datetime.timedelta(days=days)
    scope = WorkAssignment.objects.filter(current_q(today))
    if worker_ids is not None:
        scope = scope.filter(worker_id__in=worker_ids)
    current = {}
    for a in scope.select_related("client_company").order_by("start_date", "id"):
        # Một công nhân chỉ có một đợt đang diễn ra (service chặn chồng lấn); nếu dữ liệu cũ có
        # nhiều đợt thì lấy đợt bắt đầu sớm nhất để chuỗi không bị tính muộn.
        current.setdefault(a.worker_id, a)
    if not current:
        return {}
    by_worker = {}
    for a in (
        WorkAssignment.objects.filter(worker_id__in=current)
        .select_related("client_company")
        .order_by("worker_id", "start_date", "id")
    ):
        by_worker.setdefault(a.worker_id, []).append(a)
    result = {}
    one_day = datetime.timedelta(days=1)
    for worker_id, cur in current.items():
        name = normalize_key(cur.client_company.name)
        chain_start, nxt = cur.start_date, cur
        for prev in reversed(by_worker[worker_id]):
            if prev.pk == nxt.pk or prev.start_date > nxt.start_date:
                continue
            if prev.end_date is None or normalize_key(prev.client_company.name) != name:
                continue
            if nxt.start_date <= prev.end_date + one_day:
                chain_start, nxt = prev.start_date, prev
        due = add_months(chain_start, months)
        if due <= horizon and (cur.end_date is None or cur.end_date > due):
            result[worker_id] = (due, chain_start, cur)
    return result


def assignment_due_soon(queryset, today=None, days=None, months=None):
    """Hồ sơ có đợt làm việc sắp đủ thời hạn (dùng cho ?dot_sap_du_han=1 và việc cần làm)."""
    return queryset.filter(pk__in=list(assignment_due_info(today, days, months)))


def expiring(queryset, today=None, days=None):
    """Sắp hết hạn: CCCD hoặc hợp đồng."""
    start, end = _window(today, days)
    contracts = Contract.objects.filter(expiry_date__range=(start, end), worker=OuterRef("pk"))
    return queryset.filter(Q(identity__expiry_date__range=(start, end)) | Exists(contracts))
