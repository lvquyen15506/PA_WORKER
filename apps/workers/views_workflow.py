"""Nút quy trình của hồ sơ: gửi duyệt, duyệt, trả lại, từ chối, lưu trữ, mở lại, ẩn danh hóa theo
yêu cầu, và hàng đợi Duyệt hồ sơ (trang.md mục 5.4, 5.9).

Mọi đổi trạng thái đi qua apps.workers.workflow.transition. Không đủ quyền (vai trò, tự duyệt) thì
trả 403; vi phạm quy tắc nghiệp vụ (thiếu trường, thiếu lý do...) thì không đổi gì và báo lỗi tiếng
Việt. Hộp lý do có lỗi thì hiện lại trang chi tiết với hộp mở sẵn, lỗi ngay dưới ô.
"""

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import OuterRef, Subquery
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.accounts.permissions import role_required
from apps.core.choices import VerificationStatus

from . import indicators, retention, services, workflow
from .forms import AnonymizeForm, ReasonForm, ReopenForm
from .listing import PAGE_SIZE
from .models import StatusChange, Worker
from .rules import ALL_STAFF, MANAGERS
from .views import render_detail, worker_url

STAFF = tuple(ALL_STAFF)
MANAGER_ROLES = tuple(MANAGERS)
VS = VerificationStatus


def _worker(pk):
    return get_object_or_404(Worker.objects.select_related("employment", "identity"), pk=pk)


def _flash_error(request, exc):
    text = exc.message
    if exc.issues:
        text += " " + " ".join(issue.message for issue in exc.issues)
    messages.error(request, text)


def _run(request, worker, to_status, success, *, reason=""):
    """Gọi workflow.transition: 403 khi không đủ quyền, báo lỗi khi vi phạm quy tắc nghiệp vụ."""
    try:
        workflow.transition(worker, to_status, request.user, reason, request=request)
    except workflow.TransitionForbidden as exc:
        raise PermissionDenied from exc
    except workflow.TransitionError as exc:
        _flash_error(request, exc)
        return False
    messages.success(request, success)
    return True


@role_required(*STAFF)
@require_POST
def submit(request, pk):
    worker = _worker(pk)
    _run(request, worker, VS.PENDING, "Đã gửi duyệt hồ sơ.")
    return redirect(worker_url(worker))


@role_required(*MANAGER_ROLES)
@require_POST
def approve(request, pk):
    worker = _worker(pk)
    _run(request, worker, VS.VERIFIED, "Đã duyệt hồ sơ. Hồ sơ chuyển sang Đã xác minh.")
    return redirect(worker_url(worker))


def _reason_action(request, pk, *, to_status, prefix, modal, success, required=True):
    worker = _worker(pk)
    form = ReasonForm(request.POST, prefix=prefix, required=required)
    if not form.is_valid():
        return render_detail(request, worker, modal_forms={prefix: form}, open_modal=modal)
    _run(request, worker, to_status, success, reason=form.cleaned_data["reason"])
    return redirect(worker_url(worker, "lich-su"))


@role_required(*MANAGER_ROLES)
@require_POST
def send_back(request, pk):
    return _reason_action(
        request,
        pk,
        to_status=VS.NEEDS_INFO,
        prefix="return",
        modal="return-modal",
        success="Đã trả lại hồ sơ. Hồ sơ chuyển sang Cần bổ sung.",
    )


@role_required(*MANAGER_ROLES)
@require_POST
def reject(request, pk):
    return _reason_action(
        request,
        pk,
        to_status=VS.REJECTED,
        prefix="reject",
        modal="reject-modal",
        success="Đã từ chối hồ sơ.",
    )


@role_required(*STAFF)
@require_POST
def archive(request, pk):
    worker = _worker(pk)
    # Lý do bắt buộc khi Lưu trữ hồ sơ Đã xác minh (câu 9); các trạng thái khác không bắt buộc.
    return _reason_action(
        request,
        pk,
        to_status=VS.ARCHIVED,
        prefix="archive",
        modal="archive-modal",
        success="Đã chuyển hồ sơ sang Lưu trữ.",
        required=worker.verification_status == VS.VERIFIED,
    )


@role_required(*STAFF)
def reopen(request, pk):
    worker = _worker(pk)
    if worker.verification_status != VS.ARCHIVED or worker.anonymized_at is not None:
        messages.error(request, "Chỉ mở lại được hồ sơ Lưu trữ chưa ẩn danh hóa.")
        return redirect(worker_url(worker))
    form = ReopenForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            services.reopen_worker(
                request.user,
                worker,
                position=form.cleaned_data["position"],
                source=form.cleaned_data["source"],
                request=request,
            )
        except workflow.TransitionForbidden as exc:
            raise PermissionDenied from exc
        except workflow.TransitionError as exc:
            _flash_error(request, exc)
            return redirect(worker_url(worker))
        except services.WorkerDataError as exc:
            for name, message in exc.errors.items():
                form.add_error(name if name in form.fields else None, message)
        else:
            messages.success(request, "Đã mở lại hồ sơ. Hồ sơ về Nháp và có lần ứng tuyển mới.")
            return redirect(worker_url(worker))
    return render(
        request,
        "workers/reopen_form.html",
        {
            "form": form,
            "worker": worker,
            "page_title": "Mở lại hồ sơ",
            "crumbs": [
                ("Hồ sơ công nhân", "/ho-so/"),
                (worker.worker_code, worker_url(worker)),
                ("Mở lại hồ sơ", None),
            ],
            "cancel_url": worker_url(worker),
        },
    )


@role_required("ADMIN")
@require_POST
def anonymize_on_request(request, pk):
    worker = _worker(pk)
    form = AnonymizeForm(request.POST, prefix="anon", worker=worker)
    if form.is_valid():
        try:
            record = retention.anonymize_on_request(
                worker,
                request.user,
                reason=form.cleaned_data["reason"],
                request_ref=form.cleaned_data["request_ref"],
                confirm_code=form.cleaned_data["confirm_code"],
                request=request,
            )
        except retention.RetentionForbidden as exc:
            raise PermissionDenied from exc
        except retention.RetentionError as exc:
            if "không khớp" in exc.message:  # máy chủ kiểm tra lại mã gõ lại
                form.add_error("confirm_code", exc.message)
            else:
                messages.error(request, exc.message)
                return redirect(worker_url(worker))
        else:
            messages.success(
                request, f"Đã ẩn danh hóa hồ sơ. Biên bản {record.record_no} đã được lập."
            )
            return redirect(worker_url(worker))
    return render_detail(
        request, worker, modal_forms={"anonymize": form}, open_modal="anonymize-modal"
    )


# --- Hàng đợi duyệt hồ sơ -----------------------------------------------------------------------
class ReviewFilterForm(forms.Form):
    nguoi_gui = forms.ChoiceField(label="Người gửi duyệt", required=False)
    tu_ngay = forms.DateField(
        label="Từ ngày",
        required=False,
        input_formats=["%d/%m/%Y"],
        widget=forms.DateInput(format="%d/%m/%Y", attrs={"placeholder": "dd/mm/yyyy"}),
        error_messages={"invalid": "Nhập ngày đúng định dạng dd/mm/yyyy."},
    )
    den_ngay = forms.DateField(
        label="Đến ngày",
        required=False,
        input_formats=["%d/%m/%Y"],
        widget=forms.DateInput(format="%d/%m/%Y", attrs={"placeholder": "dd/mm/yyyy"}),
        error_messages={"invalid": "Nhập ngày đúng định dạng dd/mm/yyyy."},
    )

    def __init__(self, *args, senders=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nguoi_gui"].choices = [("", "Tất cả")] + [
            (str(u.pk), u.full_name) for u in senders
        ]


REVIEW_COLUMNS = [
    {"key": "worker_code", "label": "Mã hồ sơ", "kind": "text", "nowrap": True},
    {"key": "full_name", "label": "Họ và tên", "kind": "text"},
    {"key": "submitted_by", "label": "Người gửi duyệt", "kind": "text"},
    {"key": "submitted_at", "label": "Ngày gửi", "kind": "date"},
    {"key": "documents", "label": "Giấy tờ", "kind": "badge"},
    {"key": "note", "label": "Ghi chú", "kind": "text"},
    {"key": "actions", "label": "Thao tác", "kind": "actions"},
]


@role_required(*MANAGER_ROLES)
def review_queue(request):
    last = StatusChange.objects.filter(worker=OuterRef("pk"), to_status=VS.PENDING).order_by(
        "-changed_at", "-id"
    )
    queue = indicators.annotate_documents(
        Worker.objects.filter(verification_status=VS.PENDING).annotate(
            submitted_at=Subquery(last.values("changed_at")[:1]),
            submitted_by_id=Subquery(last.values("changed_by")[:1]),
            submitted_by_name=Subquery(last.values("changed_by__full_name")[:1]),
        )
    )
    sender_ids = [pk for pk in queue.values_list("submitted_by_id", flat=True).distinct() if pk]
    form = ReviewFilterForm(request.GET, senders=User.objects.filter(pk__in=sender_ids))
    form.is_valid()
    cleaned = form.cleaned_data
    if cleaned.get("nguoi_gui"):
        queue = queue.filter(submitted_by_id=int(cleaned["nguoi_gui"]))
    if cleaned.get("tu_ngay"):
        queue = queue.filter(submitted_at__date__gte=cleaned["tu_ngay"])
    if cleaned.get("den_ngay"):
        queue = queue.filter(submitted_at__date__lte=cleaned["den_ngay"])
    page = Paginator(queue.order_by("submitted_at", "id"), PAGE_SIZE).get_page(
        request.GET.get("trang")
    )
    rows = []
    for worker in page:
        own = worker.created_by_id == request.user.pk or worker.submitted_by_id == request.user.pk
        rows.append(
            {
                "worker_code": worker.worker_code,
                "full_name": worker.full_name,
                "submitted_by": worker.submitted_by_name or "Hệ thống",
                "submitted_at": worker.submitted_at,
                "documents": "missing_docs" if worker.missing_documents else "",
                "note": "Bạn không duyệt được hồ sơ này" if own else None,
                "actions": [
                    {"kind": "link", "icon": "bi-eye", "tooltip": "Xem", "url": worker_url(worker)}
                ],
            }
        )
    query = request.GET.copy()
    query.pop("trang", None)
    return render(
        request,
        "workers/review_queue.html",
        {
            "form": form,
            "columns": REVIEW_COLUMNS,
            "rows": rows,
            "page": page,
            "query": query.urlencode(),
        },
    )
