"""Phiên nhận diện CCCD/CV (docs/thiet-ke/kien-truc.md mục 4, 5; trang.md mục 5.6).

Quy tắc: trước khi HR bấm "Lưu hồ sơ" KHÔNG có gì được ghi vào hồ sơ; kết quả nhận diện nằm ở
`IntakeSession.result_enc` (mã hóa). Phiên chỉ người tạo và Admin mở được. Trường tô vàng phải
được tích "Đã kiểm tra" và máy chủ kiểm tra lại trước khi lưu. Mọi nhận diện chạy trong ngân
sách thời gian `Budget` (Gunicorn timeout 120 giây).
"""

import datetime
from collections import Counter

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.utils import timezone

from apps.audit.services import log
from apps.core.choices import AuditAction, FieldSource, IdDocType, RoleCode
from apps.core.models import DocumentType, SystemSetting
from apps.core.storage import private_storage
from apps.documents import services as document_services
from apps.documents.validators import validate_upload
from apps.recruitment import services as recruitment_services
from apps.workers.models import IdentityFieldSource
from apps.workers.services import create_worker

from . import imaging
from .budget import Budget
from .cv import CvError, extract_text, find_hints
from .fields import DATE_FIELDS, FIELD_LABELS
from .models import IntakeSession
from .pipeline import recognize

IMAGE_KINDS = {"JPG", "PNG"}
CV_KINDS = {"PDF", "DOC", "DOCX", "JPG", "PNG"}
# Địa chỉ trong URL -> (trường của phiên, mô tả, loại tài liệu hệ thống, tên tệp lưu vào hồ sơ)
SLOTS = {
    "mat-truoc": ("front_image", "Ảnh mặt trước", "CCCD_FRONT", "cccd-mat-truoc"),
    "mat-sau": ("back_image", "Ảnh mặt sau", "CCCD_BACK", "cccd-mat-sau"),
    "cv": ("cv_file", "CV", "CV", "cv"),
}
WORKER_LEVEL_FIELDS = {"full_name", "date_of_birth", "gender", "nationality"}


class IntakeError(Exception):
    """Lỗi nghiệp vụ của phiên nhận diện; `message` là tiếng Việt."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


# ----- tạo phiên -----


def _read_upload(uploaded, allowed, label):
    try:
        detected = validate_upload(uploaded)
    except ValidationError as exc:
        raise IntakeError(f"{label}: {exc.messages[0]}") from exc
    if detected.kind not in allowed:
        raise IntakeError(f"{label}: chỉ nhận " + ", ".join(sorted(allowed)) + ".")
    return uploaded.read(), detected


def _open(data, label):
    try:
        return imaging.load_image(data)
    except imaging.ImageRejected as exc:
        raise IntakeError(f"{label}: {exc}") from exc


def _count_sources(recognition):
    counts = Counter(f["source"] for f in (recognition or {}).get("fields", {}).values())
    return counts.get("QR", 0), counts.get("OCR", 0)


def create_session(user, *, front=None, back=None, cv=None, doc_type="", request=None):
    """Tạo phiên: kiểm tra tệp -> kiểm tra ảnh -> QR -> OCR -> trích CV, trong một ngân sách thời
    gian. Chưa ghi gì vào hồ sơ. Trả IntakeSession. Ném IntakeError (tiếng Việt)."""
    if not any((front, back, cv)):
        raise IntakeError("Chọn ít nhất một tệp: ảnh mặt trước, ảnh mặt sau hoặc CV.")
    if doc_type and doc_type not in IdDocType.values:
        raise IntakeError("Chọn loại giấy tờ trong danh sách.")
    budget = Budget()
    files = {}  # khe -> (bytes, DetectedFile)
    for slot, uploaded, allowed in (
        ("mat-truoc", front, IMAGE_KINDS),
        ("mat-sau", back, IMAGE_KINDS),
        ("cv", cv, CV_KINDS),
    ):
        if uploaded:
            files[slot] = _read_upload(uploaded, allowed, SLOTS[slot][1])
    images = {
        slot: _open(files[slot][0], SLOTS[slot][1])
        for slot in ("mat-truoc", "mat-sau")
        if slot in files
    }

    threshold = SystemSetting.load().ocr_confidence_threshold
    recognition = None
    if images:
        recognition = recognize(
            images.get("mat-truoc"),
            images.get("mat-sau"),
            doc_type,
            threshold=threshold,
            budget=budget,
        )
    cv_info = None
    if "cv" in files:
        data, detected = files["cv"]
        try:
            text = extract_text(data, detected.kind, budget)
            cv_info = {**text.as_dict(), "hints": find_hints(text.text)}
        except (CvError, imaging.ImageRejected) as exc:
            if not images:
                raise IntakeError(f"CV: {exc}") from exc
            cv_info = {"text": "", "warnings": [f"CV: {exc}"], "ocr_used": False, "hints": {}}

    session = IntakeSession(
        created_by=user,
        expires_at=timezone.now() + datetime.timedelta(hours=SystemSetting.load().intake_ttl_hours),
    )
    session.set_result({"recognition": recognition, "cv": cv_info, "doc_type_choice": doc_type})
    saved = []
    try:
        with transaction.atomic():
            for slot, (data, detected) in files.items():
                field = getattr(session, SLOTS[slot][0])
                field.save(f"tep{detected.ext}", ContentFile(data), save=False)
                saved.append(field.name)
            session.save()
            qr, ocr = _count_sources(recognition)
            log(
                AuditAction.INTAKE_CREATE,
                user=user,
                obj=session,
                note=f"Nhận diện: {len(files)} tệp, {qr} trường từ QR, {ocr} trường từ OCR",
                request=request,
            )
    except Exception:
        for name in saved:
            private_storage.delete(name)
        raise
    return session


def get_session_for(user, pk):
    """Phiên còn hạn mà `user` được mở (người tạo hoặc Admin), nếu không thì None (để trả 404,
    không lộ phiên có tồn tại)."""
    if not getattr(user, "is_authenticated", False):
        return None
    session = IntakeSession.objects.filter(pk=pk, expires_at__gt=timezone.now()).first()
    if session is None:
        return None
    if session.created_by_id != user.pk and user.role.code != RoleCode.ADMIN:
        return None
    return session


def stored_file(session, slot):
    """FieldFile của khe `slot` nếu phiên có tệp đó, ngược lại None."""
    if slot not in SLOTS:
        return None
    field = getattr(session, SLOTS[slot][0])
    return field if field else None


def rotate_image(user, session, slot, *, request=None):
    """Xoay ảnh của phiên 90 độ rồi nhận diện lại; dùng Budget riêng của request này."""
    if slot not in ("mat-truoc", "mat-sau") or not stored_file(session, slot):
        raise IntakeError("Phiên không có ảnh này.")
    field = getattr(session, SLOTS[slot][0])
    with field.open("rb") as handle:
        data = handle.read()
    kind = "PNG" if field.name.lower().endswith(".png") else "JPG"
    rotated = imaging.strip_metadata(imaging.rotate(_open(data, SLOTS[slot][1])), kind)
    old_name = field.name
    field.save(f"tep.{kind.lower()}", ContentFile(rotated), save=False)
    private_storage.delete(old_name)

    images = {}
    for name in ("mat-truoc", "mat-sau"):
        current = stored_file(session, name)
        if current:
            with current.open("rb") as handle:
                images[name] = _open(handle.read(), SLOTS[name][1])
    result = session.get_result()
    threshold = SystemSetting.load().ocr_confidence_threshold
    result["recognition"] = recognize(
        images.get("mat-truoc"),
        images.get("mat-sau"),
        result.get("doc_type_choice", ""),
        threshold=threshold,
        budget=Budget(),  # ngân sách riêng của lần xoay này
    )
    session.set_result(result)
    session.save()
    return session


# ----- đối chiếu -----


def review_initial(session):
    """(initial của WorkerForm, meta nguồn/độ tin cậy cho _form_section, các trường tô vàng)."""
    recognition = session.get_result().get("recognition") or {}
    initial, meta, low = {}, {}, []
    for name, field in recognition.get("fields", {}).items():
        value = field["value"]
        if value:
            initial[name] = datetime.date.fromisoformat(value) if name in DATE_FIELDS else value
        meta[name] = {
            "source": field["source"] or FieldSource.MANUAL,
            "low_confidence": field["low"],
        }
        if field["low"]:
            low.append(name)
    initial["id_doc_type"] = recognition.get("doc_type") or ""
    return initial, meta, low


def _cmp(value):
    if isinstance(value, datetime.date):
        return value.isoformat()
    value = (value or "").strip() if isinstance(value, str) else value
    return value or None


def _field_sources(user, worker, fields, data, now):
    rows = []
    for name, field in fields.items():
        machine, final = _cmp(field["value"]), _cmp(data.get(name))
        if machine is None and final is None:
            continue
        if machine is None:
            source, edited = FieldSource.MANUAL, False
        else:
            edited = final != machine
            source = FieldSource.MANUAL if edited else field["source"]
        rows.append(
            IdentityFieldSource(
                worker=worker,
                field_name=name if name in WORKER_LEVEL_FIELDS else f"identity.{name}",
                source=source,
                confidence=field["confidence"],
                edited_by_user=edited,
                confirmed_by=user,
                confirmed_at=now,
            )
        )
    IdentityFieldSource.objects.bulk_create(rows)
    return Counter(row.source for row in rows)


def _attach_documents(user, worker, session, request, saved):
    """Ảnh/CV của phiên thành tài liệu hồ sơ; ảnh được xoay theo EXIF và xóa EXIF/GPS.
    Tên tệp đã lưu được thêm ngay vào `saved` để người gọi dọn khi giao dịch lỗi giữa chừng."""
    for attr, _label, system_code, base in SLOTS.values():
        field = getattr(session, attr)
        if not field:
            continue
        with field.open("rb") as handle:
            data = handle.read()
        ext = "." + field.name.rsplit(".", 1)[-1].lower()
        if ext in (".jpg", ".jpeg", ".png"):
            kind = "PNG" if ext == ".png" else "JPG"
            data = imaging.strip_metadata(imaging.load_image(data), kind)
        document_type = DocumentType.objects.get(system_code=system_code)
        document = document_services.upload_document(
            user, worker, document_type, SimpleUploadedFile(base + ext, data), request=request
        )
        saved.append(document.stored_file.name)


def save_session(
    user,
    session,
    data,
    contacts,
    checked,
    *,
    education=(),
    experience=(),
    certificates=(),
    request=None,
):
    """Lưu hồ sơ Nháp từ phiên (một giao dịch). `data`: giá trị đã kiểm tra của WorkerForm;
    `checked`: tên các trường HR đã tích "Đã kiểm tra". Máy chủ kiểm tra lại mọi trường tô vàng.
    Ném IntakeError, WorkerDataError (trùng CCCD, dữ liệu sai) hoặc RecruitmentDataError."""
    result = session.get_result()
    fields = (result.get("recognition") or {}).get("fields", {})
    unchecked = [FIELD_LABELS[n] for n, f in fields.items() if f["low"] and n not in set(checked)]
    if unchecked:
        raise IntakeError(
            "Cần tích Đã kiểm tra cho các trường tô vàng: " + ", ".join(unchecked) + "."
        )
    now = timezone.now()
    saved_files = []
    try:
        with transaction.atomic():
            locked = IntakeSession.objects.select_for_update().filter(pk=session.pk).first()
            if locked is None:
                raise IntakeError("Phiên nhận diện đã đóng.")
            worker = create_worker(user, data, contacts, request=request)
            counts = _field_sources(user, worker, fields, data, now)
            _attach_documents(user, worker, locked, request, saved_files)
            for row in education:
                recruitment_services.add_education(user, worker, request=request, **row)
            for row in experience:
                recruitment_services.add_work_experience(user, worker, request=request, **row)
            for row in certificates:
                recruitment_services.add_certificate(user, worker, request=request, **row)
            log(
                AuditAction.INTAKE_SAVE,
                user=user,
                obj=worker,
                note=(
                    f"Lưu hồ sơ {worker.worker_code} từ phiên nhận diện: "
                    f"{counts.get('QR', 0)} trường QR, {counts.get('OCR', 0)} OCR, "
                    f"{counts.get('MANUAL', 0)} nhập tay"
                ),
                request=request,
            )
            locked.close(after_commit=True)
    except Exception:
        for name in saved_files:
            private_storage.delete(name)
        raise
    return worker


def cancel_session(user, session, *, request=None):
    """Hủy phiên: xóa ảnh và kết quả ngay."""
    with transaction.atomic():
        log(
            AuditAction.INTAKE_CANCEL,
            user=user,
            obj=session,
            note="Hủy phiên nhận diện",
            request=request,
        )
        session.close()


def open_existing(user, session, worker, *, request=None):
    """ "Mở hồ sơ cũ" khi trùng CCCD: đóng phiên, không tạo hồ sơ mới, không lưu ảnh lại."""
    if user.role.code not in (RoleCode.ADMIN, RoleCode.HR_MANAGER, RoleCode.HR_STAFF):
        raise PermissionDenied
    with transaction.atomic():
        log(
            AuditAction.INTAKE_CANCEL,
            user=user,
            obj=session,
            worker=worker,
            note=f"Trùng hồ sơ {worker.worker_code}, mở hồ sơ cũ",
            request=request,
        )
        session.close()
