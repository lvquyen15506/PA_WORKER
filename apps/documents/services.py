"""Nghiệp vụ tài liệu hồ sơ (models.md mục 3.5, 4.4, 4.5, 4.6).

Quyền theo ma trận 4.4 (apps.workers.rules). Tệp lưu ngoài thư mục public, tên ngẫu nhiên, định
dạng nhận theo nội dung thật. Mọi thao tác ghi nhật ký qua log(); object_repr là mã hồ sơ + loại
tài liệu + phiên bản, không có tên tệp gốc hay họ tên (câu 30).
"""

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.services import log
from apps.core.choices import AuditAction, DocumentVerificationStatus
from apps.core.models import DocumentType, RequiredDocumentGroup
from apps.core.storage import private_storage
from apps.workers import rules
from apps.workers.models import Worker

from .http import safe_filename
from .models import WorkerDocument
from .validators import validate_upload


class DocumentError(Exception):
    """Vi phạm quy tắc nghiệp vụ hoặc tệp không hợp lệ; `message` là tiếng Việt."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


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


def version_chain(document):
    """Mọi phiên bản của một tài liệu, cũ nhất trước (đi theo replaces và replaced_by)."""
    chain, current = [document], document
    while current.replaces_id:
        current = current.replaces
        chain.insert(0, current)
    current = document
    while True:
        try:
            current = current.replaced_by
        except ObjectDoesNotExist:
            break
        chain.append(current)
    return chain


def _checked_upload(uploaded):
    try:
        return validate_upload(uploaded)
    except ValidationError as exc:
        raise DocumentError(exc.messages[0]) from exc


def _new_document(worker, document_type, uploaded, detected, user, note, **extra):
    document = WorkerDocument(
        worker=worker,
        document_type=document_type,
        original_name=safe_filename(uploaded.name, detected.ext)[:255],
        mime_type=detected.mime,
        size_bytes=uploaded.size,
        uploaded_by=user,
        note=(note or "").strip(),
        **extra,
    )
    # Tên người dùng đặt không bao giờ thành tên tệp trên đĩa: storage đổi thành chuỗi ngẫu nhiên.
    document.stored_file.save(f"tai-lieu{detected.ext}", uploaded, save=False)
    return document


def upload_document(user, worker, document_type, uploaded, *, note="", request=None):
    """Tải tài liệu mới lên hồ sơ. Trả WorkerDocument. HR được thêm cả khi Đã xác minh (câu 10)."""
    if not isinstance(document_type, DocumentType) or not document_type.is_active:
        raise DocumentError("Chọn loại tài liệu đang sử dụng.")
    detected = _checked_upload(uploaded)
    saved_name = None
    try:
        with transaction.atomic():
            locked = Worker.objects.select_for_update().get(pk=worker.pk)
            if not rules.can_add_document(user, locked):
                raise PermissionDenied
            document = _new_document(locked, document_type, uploaded, detected, user, note)
            saved_name = document.stored_file.name
            document.save()
            locked.touch()
            log(AuditAction.UPLOAD_FILE, user=user, obj=document, request=request)
    except Exception:
        if saved_name:
            private_storage.delete(saved_name)
        raise
    return document


def replace_document(user, document, uploaded, *, note="", request=None):
    """Thay thế tài liệu: bản mới (version + 1, trỏ replaces) là bản hiện hành; bản cũ giữ lại,
    ẩn khỏi danh sách nhưng vẫn xem được trong lịch sử. Trả bản mới."""
    detected = _checked_upload(uploaded)
    saved_name = None
    try:
        with transaction.atomic():
            old = WorkerDocument.objects.select_for_update().get(pk=document.pk)
            worker = Worker.objects.select_for_update().get(pk=old.worker_id)
            if not rules.can_replace_document(user, worker):
                raise PermissionDenied
            if not old.is_current:
                raise DocumentError("Chỉ thay thế được bản hiện hành của tài liệu.")
            new = _new_document(
                worker,
                old.document_type,
                uploaded,
                detected,
                user,
                note,
                version=old.version + 1,
                replaces=old,
            )
            saved_name = new.stored_file.name
            old.is_current = False
            old.save(update_fields=["is_current"])
            new.save()
            worker.touch()
            log(
                AuditAction.REPLACE_FILE,
                user=user,
                obj=new,
                note=f"Thay thế bản v{old.version}",
                request=request,
            )
    except Exception:
        if saved_name:
            private_storage.delete(saved_name)
        raise
    return new


def set_verification(user, document, status, *, note="", request=None):
    """Đổi trạng thái xác minh của tài liệu (bộ trạng thái thứ tư). Chỉ QL, Admin (câu 34);
    chỉ bản hiện hành."""
    status = DocumentVerificationStatus(status)
    with transaction.atomic():
        locked_doc = WorkerDocument.objects.select_for_update().get(pk=document.pk)
        worker = Worker.objects.select_for_update().get(pk=locked_doc.worker_id)
        if not rules.can_verify_document(user, worker):
            raise PermissionDenied
        if not locked_doc.is_current:
            raise DocumentError("Chỉ đổi trạng thái xác minh của bản hiện hành.")
        old_status = locked_doc.verification_status
        locked_doc.verification_status = status.value
        verified = status != DocumentVerificationStatus.UNVERIFIED
        locked_doc.verified_by = user if verified else None
        locked_doc.verified_at = timezone.now() if verified else None
        if (note or "").strip():
            locked_doc.note = note.strip()
        locked_doc.save(update_fields=["verification_status", "verified_by", "verified_at", "note"])
        worker.touch()
        log(
            AuditAction.UPDATE,
            user=user,
            obj=locked_doc,
            changes={"verification_status": (old_status, status.value)},
            request=request,
        )
    document.refresh_from_db()
    return locked_doc
