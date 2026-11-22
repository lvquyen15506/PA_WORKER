"""Tải lên, xem trước, tải xuống, thay thế, xác minh tài liệu (trang.md mục 5.5).

Mọi view đều kiểm tra quyền ở máy chủ: vai trò (Viewer không bao giờ xem/tải được) rồi quyền theo
trạng thái hồ sơ (apps.workers.rules). Tệp chỉ đi qua các view này, không có URL công khai.
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.permissions import role_required
from apps.audit.services import log
from apps.core.choices import AuditAction
from apps.workers import rules
from apps.workers.models import Worker

from . import services
from .forms import ReplaceForm, UploadForm, VerifyForm
from .http import file_response
from .models import WorkerDocument
from .validators import FORMATS, INLINE_KINDS

STAFF = tuple(rules.ALL_STAFF)  # Admin, Quản lý nhân sự, Nhân viên HR: không có Viewer

HISTORY_COLUMNS = [
    {"key": "version", "label": "Phiên bản", "kind": "text", "nowrap": True},
    {"key": "uploaded_at", "label": "Ngày tải", "kind": "datetime"},
    {"key": "uploaded_by", "label": "Người tải", "kind": "text"},
    {"key": "verification", "label": "Xác minh", "kind": "badge"},
    {"key": "actions", "label": "Thao tác", "kind": "actions"},
]


def _form_data(request):
    """(POST, FILES) khi đã nộp form, (None, None) khi mới mở trang. Không dùng `POST or None`
    vì POST rỗng (không có trường nào) vẫn là một lần nộp và phải hiện lỗi bắt buộc."""
    if request.method == "POST":
        return request.POST, request.FILES
    return None, None


def _documents_tab(worker):
    return f"/ho-so/{worker.pk}/?tab=tai-lieu"


def _document_or_404(pk):
    return get_object_or_404(
        WorkerDocument.objects.select_related("worker", "document_type"), pk=pk
    )


def _stored(document):
    """Tệp phải còn (hồ sơ đã ẩn danh hóa thì tệp đã bị xóa)."""
    if not document.stored_file:
        raise Http404
    return document


def _kind_of(document):
    return next((k for k, (mime, _, _) in FORMATS.items() if mime == document.mime_type), None)


@role_required(*STAFF)
def upload(request, worker_id):
    worker = get_object_or_404(Worker, pk=worker_id)
    if not rules.can_add_document(request.user, worker):
        raise PermissionDenied
    form = UploadForm(*_form_data(request))
    if request.method == "POST" and form.is_valid():
        try:
            services.upload_document(
                request.user,
                worker,
                form.cleaned_data["document_type"],
                form.cleaned_data["file"],
                note=form.cleaned_data["note"],
                request=request,
            )
        except services.DocumentError as exc:
            form.add_error(None, exc.message)
        else:
            messages.success(request, "Đã tải tài liệu lên.")
            return redirect(_documents_tab(worker))
    return render(
        request,
        "documents/upload_form.html",
        {
            "form": form,
            "worker": worker,
            "page_title": "Tải tài liệu lên",
            "crumbs": [
                ("Hồ sơ công nhân", "/ho-so/"),
                (worker.worker_code, f"/ho-so/{worker.pk}/"),
                ("Tải tài liệu lên", None),
            ],
            "cancel_url": _documents_tab(worker),
        },
    )


@role_required(*STAFF)
@require_GET
def view_file(request, pk):
    """Xem trước ảnh và PDF ngay trên trình duyệt. DOC/DOCX không xem trước được: chuyển sang
    tải xuống (và ghi nhật ký tải xuống)."""
    document = _stored(_document_or_404(pk))
    if _kind_of(document) not in INLINE_KINDS:
        return redirect("document_download", pk=document.pk)
    response = file_response(document, inline=True)  # 404 nếu tệp không còn trên đĩa
    log(AuditAction.VIEW_FILE, user=request.user, obj=document, request=request)
    return response


@role_required(*STAFF)
@require_GET
def download_file(request, pk):
    document = _stored(_document_or_404(pk))
    response = file_response(document, inline=False)  # 404 nếu tệp không còn trên đĩa
    log(AuditAction.DOWNLOAD_FILE, user=request.user, obj=document, request=request)
    return response


@role_required(*STAFF)
def replace(request, pk):
    document = _document_or_404(pk)
    if not rules.can_replace_document(request.user, document.worker):
        raise PermissionDenied
    form = ReplaceForm(*_form_data(request))
    if request.method == "POST" and form.is_valid():
        try:
            services.replace_document(
                request.user,
                document,
                form.cleaned_data["file"],
                note=form.cleaned_data["note"],
                request=request,
            )
        except services.DocumentError as exc:
            form.add_error(None, exc.message)
        else:
            messages.success(request, "Đã thay thế tài liệu. Bản cũ vẫn được giữ trong lịch sử.")
            return redirect(_documents_tab(document.worker))
    worker = document.worker
    return render(
        request,
        "documents/upload_form.html",
        {
            "form": form,
            "worker": worker,
            "document": document,
            "page_title": f"Thay thế {document.document_type.name}",
            "crumbs": [
                ("Hồ sơ công nhân", "/ho-so/"),
                (worker.worker_code, f"/ho-so/{worker.pk}/"),
                ("Thay thế tài liệu", None),
            ],
            "cancel_url": _documents_tab(worker),
            "replacing": True,
        },
    )


@role_required(*STAFF)
@require_POST
def verify(request, pk):
    document = _document_or_404(pk)
    if not rules.can_verify_document(request.user, document.worker):
        raise PermissionDenied
    form = VerifyForm(request.POST)
    if form.is_valid():
        try:
            services.set_verification(
                request.user,
                document,
                form.cleaned_data["status"],
                note=form.cleaned_data["note"],
                request=request,
            )
        except services.DocumentError as exc:
            messages.error(request, exc.message)
        else:
            messages.success(request, "Đã cập nhật trạng thái xác minh tài liệu.")
    else:
        messages.error(request, "Chọn trạng thái xác minh hợp lệ.")
    return redirect(_documents_tab(document.worker))


@role_required(*STAFF)
@require_GET
def history(request, pk):
    """Mảnh HTML (HTMX): các phiên bản của tài liệu, kể cả bản đã bị thay thế."""
    document = _document_or_404(pk)
    rows = []
    for version in reversed(services.version_chain(document)):
        actions = []
        if version.stored_file:  # tệp bị xóa sau khi ẩn danh hóa thì không còn gì để mở
            actions = [
                {
                    "kind": "link",
                    "icon": "bi-eye",
                    "tooltip": "Xem",
                    "url": reverse("document_view", args=[version.pk]),
                },
                {
                    "kind": "link",
                    "icon": "bi-download",
                    "tooltip": "Tải xuống",
                    "url": reverse("document_download", args=[version.pk]),
                },
            ]
        rows.append(
            {
                "version": f"v{version.version}{' (hiện hành)' if version.is_current else ''}",
                "uploaded_at": version.uploaded_at,
                "uploaded_by": version.uploaded_by.full_name,
                "verification": version.verification_status,
                "actions": actions,
            }
        )
    return render(request, "documents/_history.html", {"columns": HISTORY_COLUMNS, "rows": rows})
