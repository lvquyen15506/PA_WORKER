"""Nhập từ CCCD và CV (docs/thiet-ke/trang.md mục 5.6, phac-thao-trang.md mục 4).

Chỉ Admin, Quản lý nhân sự, Nhân viên HR vào được; mỗi phiên chỉ người tạo và Admin mở được, người
khác nhận 404 (không lộ phiên có tồn tại). Kiểm tra quyền ở máy chủ cho mọi view và lượt tải tệp.
"""

import os

from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.permissions import role_required
from apps.core.choices import RoleCode
from apps.documents.http import safe_content_disposition
from apps.documents.validators import FORMATS, INLINE_KINDS
from apps.recruitment.services import RecruitmentDataError
from apps.workers.forms import ContactFormSet, WorkerForm, contact_rows
from apps.workers.models import Worker
from apps.workers.services import WorkerDataError
from apps.workers.validation import DRAFT, validate_worker_data
from apps.workers.views import (
    _apply_contact_errors,
    _apply_errors,
    _contact_sections,
    worker_url,
)

from . import services
from .forms import (
    CertificateFormSet,
    CvViewForm,
    EducationFormSet,
    ExperienceFormSet,
    IntakeUploadForm,
    filled_rows,
)

staff_only = role_required(RoleCode.ADMIN, RoleCode.HR_MANAGER, RoleCode.HR_STAFF)
CRUMBS = [("Thêm hồ sơ", "/ho-so/them/"), ("Nhập từ CCCD và CV", None)]

# Ô nhận chữ khi HR bôi đen đoạn CV rồi chọn "Đưa vào trường…": (nhãn, id của ô).
CV_TARGETS = [
    ("Số điện thoại", "id_phone", "phone"),
    ("Email", "id_email", ""),
    ("Kỹ năng", "id_skills", ""),
    ("Học vấn – tên trường", "id_edu-0-school_name", ""),
    ("Học vấn – chuyên ngành", "id_edu-0-major", ""),
    ("Kinh nghiệm – công ty", "id_exp-0-company_name", ""),
    ("Kinh nghiệm – chức danh", "id_exp-0-job_title", ""),
    ("Kinh nghiệm – mô tả", "id_exp-0-description", ""),
    ("Chứng chỉ – tên", "id_cert-0-name", ""),
]


def _session(request, pk):
    session = services.get_session_for(request.user, pk)
    if session is None:
        raise Http404
    return session


# --- Tải ảnh -------------------------------------------------------------------------------
@staff_only
def upload(request):
    posting = request.method == "POST"
    form = IntakeUploadForm(request.POST if posting else None, request.FILES if posting else None)
    if posting and form.is_valid():
        try:
            session = services.create_session(
                request.user,
                front=form.cleaned_data["front_image"],
                back=form.cleaned_data["back_image"],
                cv=form.cleaned_data["cv_file"],
                doc_type=form.cleaned_data["doc_type"],
                request=request,
            )
        except services.IntakeError as exc:
            form.add_error(None, exc.message)
        else:
            return redirect(f"/nhap-cccd/{session.pk}/")
    return render(request, "intake/upload.html", {"form": form, "crumbs": CRUMBS})


# --- Đối chiếu -----------------------------------------------------------------------------
def _section_rows(formset, titles):
    """[(tiêu đề, [BoundField])] cho từng dòng của một formset nhập từ CV."""
    return [
        (titles if index == 0 else None, form.visible_fields())
        for index, form in enumerate(formset.forms)
    ]


def _tag_edited_fields(form, meta):
    """Gắn giá trị máy đọc gốc vào ô để trình duyệt đổi nhãn nguồn thành "Nhập tay" khi HR sửa."""
    initial = form.initial
    for name, info in meta.items():
        if name in form.fields and info["source"] in ("QR", "OCR"):
            value = initial.get(name)
            if hasattr(value, "strftime"):
                value = value.strftime("%d/%m/%Y")
            form.fields[name].widget.attrs["data-pa-orig"] = value or ""


def _initial_duplicates(initial):
    """Kiểm tra trùng ngay khi mở màn hình đối chiếu (kịch bản 5), dùng quy tắc như lúc lưu."""
    keys = ("full_name", "phone", "date_of_birth", "id_number")
    result = validate_worker_data({k: initial[k] for k in keys if k in initial}, level=DRAFT)
    return result.duplicate, result.warnings


@staff_only
def review(request, pk):
    session = _session(request, pk)
    result = session.get_result()
    recognition = result.get("recognition") or {}
    initial, meta, _low = services.review_initial(session)
    posting = request.method == "POST"
    data = request.POST if posting else None
    form = WorkerForm(data, initial=initial, check_url=f"/nhap-cccd/{session.pk}/kiem-tra-trung/")
    _tag_edited_fields(form, meta)
    contacts = ContactFormSet(data, prefix="contacts")
    education = EducationFormSet(data, prefix="edu")
    experience = ExperienceFormSet(data, prefix="exp")
    certificates = CertificateFormSet(data, prefix="cert")
    duplicate, warnings = (None, []) if posting else _initial_duplicates(initial)

    if posting:
        valid = all(
            [form.is_valid(), contacts.is_valid(), education.is_valid(), experience.is_valid()]
            + [certificates.is_valid()]
        )
        if valid:
            checked = {
                n for n in recognition.get("fields", {}) if request.POST.get(f"{n}__checked")
            }
            try:
                worker = services.save_session(
                    request.user,
                    session,
                    form.service_data(),
                    contact_rows(contacts),
                    checked,
                    education=filled_rows(education),
                    experience=filled_rows(experience),
                    certificates=filled_rows(certificates),
                    request=request,
                )
            except services.IntakeError as exc:
                form.add_error(None, exc.message)
            except WorkerDataError as exc:
                _apply_errors(form, exc)
                _apply_contact_errors(contacts, exc.contact_errors)
                duplicate = exc.duplicate
            except RecruitmentDataError as exc:
                form.add_error(None, "; ".join(exc.errors.values()))
            else:
                messages.success(request, "Đã lưu hồ sơ ở trạng thái Nháp.")
                for warning in form.warnings:
                    messages.warning(request, warning)
                return redirect(worker_url(worker))
        duplicate = duplicate or form.duplicate
        warnings = form.warnings

    cv = result.get("cv") or {}
    notes = list((recognition.get("warnings") or [])) + list(cv.get("warnings") or [])
    cv_form = CvViewForm(initial={"cv_text": cv.get("text", "")})
    context = {
        "session": session,
        "cancel_action": f"/nhap-cccd/{session.pk}/huy/",
        "form": form,
        "meta": meta,
        "contacts": contacts,
        "contact_sections": _contact_sections(contacts),
        "education": education,
        "experience": experience,
        "certificates": certificates,
        "education_sections": _section_rows(education, "Học vấn (từ CV)"),
        "experience_sections": _section_rows(experience, "Kinh nghiệm (từ CV)"),
        "certificate_sections": _section_rows(certificates, "Chứng chỉ (từ CV)"),
        "has_front": bool(services.stored_file(session, "mat-truoc")),
        "has_back": bool(services.stored_file(session, "mat-sau")),
        "has_cv": bool(services.stored_file(session, "cv")),
        "cv_form": cv_form,
        "cv_hints": cv.get("hints") or {},
        "cv_targets": CV_TARGETS,
        "notes": notes,
        "duplicate": duplicate,
        "warnings": warnings,
        "has_low": any(m["low_confidence"] for m in meta.values()),
        "external_enabled": _external_enabled(),
        "crumbs": [*CRUMBS[:1], ("Nhập từ CCCD", None)],
    }
    return render(request, "intake/review.html", context)


def _external_enabled():
    from .external_ocr import is_enabled

    return is_enabled()


# --- Tệp của phiên, kiểm tra trùng, hủy, xoay, mở hồ sơ cũ ---------------------------------
@staff_only
def session_file(request, pk, slot):
    """Ảnh/CV của phiên: chỉ người tạo phiên và Admin; ảnh và PDF xem trực tiếp, còn lại tải về."""
    session = _session(request, pk)
    stored = services.stored_file(session, slot)
    if stored is None:
        raise Http404
    ext = os.path.splitext(stored.name)[1].lower()
    kind = next((k for k, (_, e, aliases) in FORMATS.items() if ext in aliases), None)
    if kind is None:
        raise Http404
    mime = FORMATS[kind][0]
    try:
        handle = stored.open("rb")
    except FileNotFoundError as exc:
        raise Http404 from exc
    inline = kind in INLINE_KINDS
    response = FileResponse(handle, content_type=mime)
    base = services.SLOTS[slot][3]
    response["Content-Disposition"] = safe_content_disposition(
        "inline" if inline else "attachment", base + FORMATS[kind][1], FORMATS[kind][1]
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    if inline:
        response["Content-Security-Policy"] = "sandbox"
    return response


@staff_only
@require_POST
def check_duplicate(request, pk):
    """Mảnh HTMX khi rời ô họ tên / SĐT / ngày sinh / số CCCD: báo trùng, không ghi gì."""
    session = _session(request, pk)
    form = WorkerForm(request.POST)
    form.is_valid()
    errors = [
        form.errors[name][0]
        for name in ("id_number", "date_of_birth", "phone")
        if name in form.errors and request.POST.get(name, "").strip()
    ]
    return render(
        request,
        "intake/_duplicate.html",
        {
            "session": session,
            "duplicate": form.duplicate,
            "warnings": form.warnings,
            "errors": errors,
        },
    )


@staff_only
@require_POST
def cancel(request, pk):
    session = _session(request, pk)
    services.cancel_session(request.user, session, request=request)
    messages.success(request, "Đã hủy phiên nhận diện, ảnh và kết quả đã bị xóa.")
    return redirect("/ho-so/them/")


@staff_only
@require_POST
def rotate(request, pk, slot):
    session = _session(request, pk)
    try:
        services.rotate_image(request.user, session, slot, request=request)
    except services.IntakeError as exc:
        messages.error(request, exc.message)
    else:
        messages.success(request, "Đã xoay ảnh và nhận diện lại.")
    return redirect(f"/nhap-cccd/{session.pk}/")


@staff_only
@require_POST
def open_existing(request, pk, worker_pk):
    session = _session(request, pk)
    worker = get_object_or_404(Worker, pk=worker_pk, anonymized_at__isnull=True)
    services.open_existing(request.user, session, worker, request=request)
    return redirect(worker_url(worker))
