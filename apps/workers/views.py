"""Hồ sơ công nhân: danh sách, thêm, sửa, chi tiết 5 tab (docs/thiet-ke/trang.md mục 5.4).

Quyền kiểm tra ở máy chủ cho mọi view: vai trò (role_required), rồi quyền theo trạng thái hồ sơ
(apps.workers.rules). Viewer không bao giờ nhận số CCCD đầy đủ, CMND cũ, địa chỉ thường trú, quê
quán, nơi đăng ký khai sinh, ảnh CCCD, mức lương mong muốn (câu 13): các giá trị này không được đưa
vào context của template khi người xem là Viewer.
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.permissions import ALL_ROLES, role_required
from apps.audit.models import AuditLog
from apps.audit.services import log
from apps.core import badges
from apps.core.choices import (
    AuditAction,
    ContractType,
    EmploymentChangeType,
    Gender,
    IdDocType,
    VerificationStatus,
    WorkStatus,
)
from apps.core.text import mask_id_number
from apps.documents import services as document_services
from apps.documents.forms import VerifyForm
from apps.documents.models import WorkerDocument
from apps.employment import assignments as assignment_services
from apps.employment import services as employment_services
from apps.employment.assignments import current_q
from apps.employment.models import WorkAssignment
from apps.workers import indicators, rules, workflow

from . import history_labels, services
from .forms import (
    AnonymizeForm,
    ConsentForm,
    ContactFormSet,
    ReasonForm,
    WorkerForm,
    contact_initial,
    contact_rows,
)
from .listing import PAGE_SIZE, WorkerFilterForm, build_queryset
from .models import Worker
from .rules import ALL_STAFF, MANAGERS, role_code

STAFF = tuple(ALL_STAFF)
SESSION_KEY = "worker_list_query"
DASH = "—"

TABS = [
    ("ca-nhan", "Thông tin cá nhân"),
    ("tuyen-dung", "Tuyển dụng & CV"),
    ("lam-viec", "Quá trình làm việc"),
    ("tai-lieu", "Tài liệu"),
    ("lich-su", "Lịch sử thay đổi"),
]
TAB_KEYS = [key for key, _ in TABS]
LIST_COLUMNS = [
    {"key": "stt", "label": "STT", "kind": "num"},
    {"key": "employee_code", "label": "Mã NV", "kind": "text"},
    {"key": "full_name", "label": "Họ và tên", "kind": "text"},
    {"key": "date_of_birth", "label": "Ngày sinh", "kind": "date"},
    {"key": "gender", "label": "Giới tính", "kind": "text"},
    {"key": "phone", "label": "SĐT", "kind": "text", "nowrap": True},
    # v1.1 (câu 48): cột "Bộ phận" của yêu cầu v1.0 thay bằng "Công ty khách" (đợt đang diễn ra).
    {"key": "client", "label": "Công ty khách", "kind": "text"},
    {"key": "position", "label": "Chức danh", "kind": "text"},
    {"key": "start_date", "label": "Ngày vào làm", "kind": "date"},
    # Tên viết tắt theo phác thảo đã duyệt (phac-thao-trang.md 2.3): 12 cột mới vừa khung 1366 px.
    {"key": "status", "label": "TT hồ sơ", "kind": "badge"},
    {"key": "work_status", "label": "TT làm việc", "kind": "badge"},
    {"key": "actions", "label": "Thao tác", "kind": "actions"},
]


# --- Tiện ích dùng chung ------------------------------------------------------------------
def worker_url(worker, tab=None):
    return f"/ho-so/{worker.pk}/" + (f"?tab={tab}" if tab else "")


def _fmt_date(value):
    return date_format(value, "d/m/Y") if value else None


def _label(choices, value):
    return choices(value).label if value else None


def _money(value):
    return f"{int(value):,}".replace(",", ".") + " đ" if value is not None else None


def _years(start, end):
    if start and end:
        return f"{start}–{end}"
    return str(start or end or "") or None


def _link(icon, tooltip, url):
    return {"kind": "link", "icon": icon, "tooltip": tooltip, "url": url}


def _form_data(request):
    return (request.POST, request.FILES) if request.method == "POST" else (None, None)


def _apply_errors(form, exc):
    """Đưa lỗi từ service xuống từng ô của form; lỗi không gắn ô thì thành lỗi chung."""
    for name, message in exc.errors.items():
        form.add_error(name if name in form.fields else None, message)
    if not exc.errors:
        form.add_error(None, exc.message)


# --- Danh sách ------------------------------------------------------------------------------
@role_required(*ALL_ROLES)
def worker_list(request):
    if "reset" in request.GET:  # "Xóa lọc"
        request.session.pop(SESSION_KEY, None)
        return redirect("worker_list")
    params = request.GET
    if params:
        # Giữ bộ lọc khi quay lại trang. Không lưu chữ tìm kiếm (có thể là số CCCD) vào phiên.
        saved = params.copy()
        saved.pop("q", None)
        if saved:  # chỉ tìm nhanh (?q=) thì giữ nguyên bộ lọc đã lưu
            request.session[SESSION_KEY] = saved.urlencode()
    elif request.session.get(SESSION_KEY):
        params = QueryDict(request.session[SESSION_KEY])
    form = WorkerFilterForm(params)
    form.is_valid()
    cleaned = {k: v for k, v in form.cleaned_data.items()}
    page = Paginator(build_queryset(request.user, cleaned), PAGE_SIZE).get_page(params.get("trang"))

    rows = []
    clients = {
        a.worker_id: a.client_company
        for a in WorkAssignment.objects.filter(
            current_q(timezone.localdate()), worker_id__in=[w.pk for w in page]
        )
        .select_related("client_company")
        .order_by("start_date", "id")
    }
    for number, worker in enumerate(page, start=page.start_index()):
        employment = getattr(worker, "employment", None)
        actions = [_link("bi-eye", "Xem", worker_url(worker))]
        if rules.can_edit_profile(request.user, worker):
            actions.append(_link("bi-pencil", "Sửa", f"/ho-so/{worker.pk}/sua/"))
        rows.append(
            {
                "stt": number,
                "employee_code": worker.employee_code,
                "full_name": worker.full_name,
                "date_of_birth": worker.date_of_birth,
                "gender": _label(Gender, worker.gender),
                "phone": worker.phone,
                "client": str(clients[worker.pk]) if worker.pk in clients else None,
                "position": employment.position.name if employment else None,
                "start_date": employment.start_date if employment else None,
                "status": worker.verification_status,
                "work_status": employment.work_status if employment else "",
                "actions": actions,
            }
        )
    query = params.copy()
    query.pop("trang", None)
    actions = []
    export_action = ""
    if role_code(request.user) in ALL_STAFF:  # Viewer không xuất Excel (câu 18)
        export_action = "/ho-so/xuat-excel/?" + query.urlencode()
        actions.append({"label": "Xuất Excel", "kind": "secondary", "url": export_action})
        if role_code(request.user) in MANAGERS:  # chỉ A, Q được chọn xuất kèm số CCCD đầy đủ
            actions.append(
                {"label": "Xuất kèm số CCCD", "kind": "secondary", "modal": "modal-export-full"}
            )
        actions.append({"label": "Thêm hồ sơ", "kind": "primary", "url": "/ho-so/them/"})
    return render(
        request,
        "workers/list.html",
        {
            "form": form,
            "columns": LIST_COLUMNS,
            "rows": rows,
            "page": page,
            "query": query.urlencode(),
            "header_actions": actions,
            "export_full_action": export_action if role_code(request.user) in MANAGERS else "",
        },
    )


# --- Thêm hồ sơ ---------------------------------------------------------------------------
@role_required(*STAFF)
def worker_add(request):
    return render(request, "workers/add.html")


def _contact_sections(formset):
    """[(tiêu đề, trường, form)] cho từng dòng liên hệ; ô "Xóa" chỉ có ở dòng đã lưu."""
    sections = []
    for index, cform in enumerate(formset.forms):
        saved = bool(cform["id"].value())
        fields = [f for f in cform.visible_fields() if f.name != "delete" or saved]
        sections.append(("Người liên hệ khẩn cấp" if index == 0 else None, fields, cform))
    return sections


def _form_page(request, form, formset, *, title, crumbs, cancel_url, duplicate=None, status=200):
    return render(
        request,
        "workers/worker_form.html",
        {
            "form": form,
            "formset": formset,
            "contact_sections": _contact_sections(formset),
            "page_title": title,
            "crumbs": crumbs,
            "cancel_url": cancel_url,
            "duplicate": duplicate or form.duplicate,
            "warnings": form.warnings,
        },
        status=status,
    )


def _apply_contact_errors(formset, contact_errors):
    for index, errors in contact_errors.items():
        if index < len(formset.forms):
            for name, message in errors.items():
                formset.forms[index].add_error(name, message)


@role_required(*STAFF)
def worker_create(request):
    data, _ = _form_data(request)
    form = WorkerForm(data, check_url="/ho-so/kiem-tra-trung/")
    formset = ContactFormSet(data, prefix="contacts")
    duplicate = None
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        try:
            worker = services.create_worker(
                request.user, form.service_data(), contact_rows(formset), request=request
            )
        except services.WorkerDataError as exc:
            _apply_errors(form, exc)
            _apply_contact_errors(formset, exc.contact_errors)
            duplicate = exc.duplicate
        else:
            messages.success(request, "Đã lưu hồ sơ ở trạng thái Nháp.")
            for warning in form.warnings:
                messages.warning(request, warning)
            return redirect(worker_url(worker))
    return _form_page(
        request,
        form,
        formset,
        title="Thêm hồ sơ – nhập tay",
        crumbs=[
            ("Hồ sơ công nhân", "/ho-so/"),
            ("Thêm hồ sơ", "/ho-so/them/"),
            ("Nhập tay", None),
        ],
        cancel_url="/ho-so/",
        duplicate=duplicate,
    )


@role_required(*STAFF)
@require_POST
def check_duplicate(request):
    """Mảnh HTMX khi rời ô họ tên / SĐT / ngày sinh / số CCCD: báo trùng, không ghi gì."""
    editing = request.GET.get("sua", "")
    instance = Worker.objects.filter(pk=int(editing)).first() if editing.isdigit() else None
    form = WorkerForm(request.POST, instance=instance)
    form.is_valid()
    errors = [
        form.errors[name][0]
        for name in ("id_number", "date_of_birth", "phone")
        if name in form.errors and request.POST.get(name, "").strip()
    ]
    return render(
        request,
        "workers/_duplicate_check.html",
        {"duplicate": form.duplicate, "warnings": form.warnings, "errors": errors},
    )


# --- Sửa ------------------------------------------------------------------------------------
@role_required(*STAFF)
def worker_edit(request, pk):
    worker = get_object_or_404(Worker, pk=pk)
    if not rules.can_edit_profile(request.user, worker):
        raise PermissionDenied
    level = (
        "submission" if worker.verification_status == VerificationStatus.VERIFIED else "draft"
    )  # sửa hồ sơ Đã xác minh phải giữ đủ trường gửi duyệt
    data, _ = _form_data(request)
    form = WorkerForm(
        data, instance=worker, level=level, check_url=f"/ho-so/kiem-tra-trung/?sua={worker.pk}"
    )
    formset = ContactFormSet(data, initial=contact_initial(worker), prefix="contacts")
    duplicate = None
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        try:
            result = services.update_worker(
                request.user,
                worker,
                form.service_data(),
                contacts=contact_rows(formset),
                request=request,
            )
        except services.WorkerDataError as exc:
            _apply_errors(form, exc)
            _apply_contact_errors(formset, exc.contact_errors)
            duplicate = exc.duplicate
        else:
            if result.back_to_pending:
                messages.warning(
                    request,
                    "Hồ sơ đã chuyển về Chờ duyệt vì có sửa họ tên, ngày sinh hoặc số CCCD.",
                )
            elif result.changed:
                messages.success(request, "Đã lưu hồ sơ.")
            else:
                messages.info(request, "Không có thay đổi nào để lưu.")
            for warning in form.warnings:
                messages.warning(request, warning)
            return redirect(worker_url(worker))
    return _form_page(
        request,
        form,
        formset,
        title=f"Sửa hồ sơ {worker.worker_code}",
        crumbs=[
            ("Hồ sơ công nhân", "/ho-so/"),
            (worker.worker_code, worker_url(worker)),
            ("Sửa hồ sơ", None),
        ],
        cancel_url=worker_url(worker),
        duplicate=duplicate,
    )


# --- Chi tiết -------------------------------------------------------------------------------
def header_actions(user, worker):
    """Nút ở đầu trang chi tiết theo trạng thái hồ sơ và vai trò (phac-thao-trang.md mục 3.2).
    Mỗi trạng thái chỉ có tối đa một nút chính. Ẩn nút chỉ là phần phụ: máy chủ kiểm tra lại."""
    role = role_code(user)
    if role not in ALL_STAFF or worker.anonymized_at is not None:
        return []
    status, base = worker.verification_status, f"/ho-so/{worker.pk}"
    actions = []
    if status in (VerificationStatus.DRAFT, VerificationStatus.NEEDS_INFO):
        actions.append({"label": "Gửi duyệt", "kind": "primary", "post_url": f"{base}/gui-duyet/"})
    reviewable = workflow.can_review(worker, user)
    if reviewable:
        actions.append({"label": "Duyệt hồ sơ", "kind": "primary", "post_url": f"{base}/duyet/"})
    if status == VerificationStatus.ARCHIVED:
        actions.append({"label": "Mở lại hồ sơ", "kind": "primary", "url": f"{base}/mo-lai/"})
    if rules.can_edit_profile(user, worker):
        actions.append({"label": "Sửa hồ sơ", "kind": "secondary", "url": f"{base}/sua/"})
    if reviewable:
        actions.append({"label": "Trả lại", "kind": "secondary", "modal": "return-modal"})
        actions.append({"label": "Từ chối", "kind": "danger", "modal": "reject-modal"})
    can_archive = status in (
        VerificationStatus.DRAFT,
        VerificationStatus.NEEDS_INFO,
        VerificationStatus.REJECTED,
    ) or (status == VerificationStatus.VERIFIED and role in MANAGERS)
    if can_archive:
        if _is_working(worker):  # nút tắt kèm lý do; không gắn hộp thoại vì không mở được
            actions.append(
                {
                    "label": "Lưu trữ",
                    "kind": "danger",
                    "disabled": True,
                    "tooltip": "Đang Thử việc hoặc Đang làm việc nên chưa Lưu trữ được.",
                }
            )
        else:
            actions.append({"label": "Lưu trữ", "kind": "danger", "modal": "archive-modal"})
    if role == "ADMIN" and status == VerificationStatus.ARCHIVED:
        actions.append(
            {
                "label": "Ẩn danh hóa theo yêu cầu",
                "kind": "danger",
                "modal": "anonymize-modal",
            }
        )
    return actions


def _is_working(worker):
    employment = getattr(worker, "employment", None)
    return bool(employment and employment.work_status in (WorkStatus.PROBATION, WorkStatus.ACTIVE))


def render_detail(request, worker, tab="ca-nhan", *, modal_forms=None, open_modal=None, status=200):
    """Dựng trang chi tiết. `modal_forms` (tên hộp -> form đã nộp có lỗi) và `open_modal` để các
    view nghiệp vụ hiện lại hộp thoại kèm lỗi ngay dưới ô bị sai."""
    user = request.user
    tab = tab if tab in TAB_KEYS else "ca-nhan"
    role = role_code(user)
    staff = role in ALL_STAFF
    employment = getattr(worker, "employment", None)
    identity = getattr(worker, "identity", None)
    actions = header_actions(user, worker)
    context = {
        "worker": worker,
        "tab": tab,
        "tabs": [
            {"label": label, "url": f"{worker_url(worker)}?tab={key}", "active": key == tab}
            for key, label in TABS
        ],
        "work_status": employment.work_status if employment else None,
        "actions": actions,
        "modal_ids": {a["modal"] for a in actions if a.get("modal")},
        "return_url": f"/ho-so/{worker.pk}/tra-lai/",
        "reject_url": f"/ho-so/{worker.pk}/tu-choi/",
        "archive_url": f"/ho-so/{worker.pk}/luu-tru/",
        "anonymize_url": f"/ho-so/{worker.pk}/an-danh-theo-yeu-cau/",
        "is_staff": staff,
        "crumbs": [("Hồ sơ công nhân", "/ho-so/"), (worker.worker_code, None)],
        "title": worker.full_name or DASH,
        "tab_template": f"workers/tabs/{tab}.html",
        "open_modal": open_modal,
        "own_pending": (
            worker.verification_status == VerificationStatus.PENDING
            and role in MANAGERS
            and not workflow.can_review(worker, user)
        ),
        "modals": _modals(worker, modal_forms or {}),
    }
    status_notes = _status_notes(worker)
    context.update(status_notes)
    context.update(_TAB_BUILDERS[tab](request, worker, employment, identity, staff, role))
    return render(request, "workers/detail.html", context, status=status)


def _status_notes(worker):
    """Ghi chú lý do gần nhất khi hồ sơ Cần bổ sung hoặc Bị từ chối."""
    status = worker.verification_status
    if status not in (VerificationStatus.NEEDS_INFO, VerificationStatus.REJECTED):
        return {"status_note": None}
    last = worker.status_changes.filter(to_status=status).order_by("-changed_at", "-id").first()
    if last is None or not last.reason:
        return {"status_note": None}
    prefix = "Trả lại" if status == VerificationStatus.NEEDS_INFO else "Từ chối"
    return {"status_note": f"{prefix}: {last.reason}"}


def _modals(worker, bound):
    """Các hộp xác nhận có trường lý do; form đã nộp (có lỗi) thay form trống."""
    return {
        "return": bound.get("return") or ReasonForm(prefix="return"),
        "reject": bound.get("reject") or ReasonForm(prefix="reject"),
        "archive": bound.get("archive")
        or ReasonForm(
            prefix="archive", required=worker.verification_status == VerificationStatus.VERIFIED
        ),
        "anonymize": bound.get("anonymize") or AnonymizeForm(prefix="anon", worker=worker),
        "document": VerifyForm(),  # không tiền tố: view xác minh đọc đúng tên trường status, note
    }


@role_required(*ALL_ROLES)
def worker_detail(request, pk):
    worker = get_object_or_404(
        Worker.objects.select_related("employment__section__department", "identity"), pk=pk
    )
    return render_detail(request, worker, request.GET.get("tab", "ca-nhan"))


# --- Nội dung từng tab ------------------------------------------------------------------------
def _personal_tab(request, worker, employment, identity, staff, role):
    anonymized = worker.anonymized_at is not None

    def personal(value):
        if value in (None, ""):
            return "(đã ẩn danh)" if anonymized else None
        return value

    basic = [
        ("Họ và tên", worker.full_name),
        ("Ngày sinh", personal(_fmt_date(worker.date_of_birth))),
        ("Giới tính", personal(_label(Gender, worker.gender))),
        ("Quốc tịch", worker.nationality),
        ("Số điện thoại", personal(worker.phone)),
        ("Email", personal(worker.email)),
        ("Nơi ở hiện tại", personal(worker.current_address)),
    ]
    papers = []
    id_available = False
    if identity is not None:
        id_available = bool(identity.id_number_enc)
        papers = [
            ("Loại giấy tờ", _label(IdDocType, identity.id_doc_type)),
            ("Số CCCD", personal(mask_id_number(identity.id_number_enc))),
            ("Ngày cấp", personal(_fmt_date(identity.issue_date))),
            ("Nơi cấp", personal(identity.issue_place)),
            ("Có giá trị đến", personal(_fmt_date(identity.expiry_date))),
        ]
        if staff:  # Viewer không nhận các giá trị này (câu 13), kể cả dạng che của CMND cũ
            papers += [
                ("Số CMND cũ", personal(mask_id_number(identity.old_id_number_enc))),
                ("Nơi thường trú", personal(identity.permanent_address_enc)),
                ("Quê quán", personal(identity.hometown)),
                ("Nơi đăng ký khai sinh", personal(identity.birth_registration_place)),
            ]
    contacts = [
        {"full_name": c.full_name, "relationship": c.relationship, "phone": c.phone}
        for c in worker.emergency_contacts.all()
    ]
    consent = worker.consents.select_related("recorded_by").first()
    consent_items = None
    if consent:
        consent_items = [
            ("Kết quả", "Đồng ý" if consent.consented else "Không đồng ý"),
            ("Hình thức", consent.get_method_display()),
            ("Ngày đồng ý", _fmt_date(consent.consent_date)),
            ("Người ghi nhận", consent.recorded_by.full_name),
        ]
    return {
        "basic_items": basic,
        "paper_items": papers,
        "show_full_id": staff and id_available and not anonymized,
        "contact_columns": [
            {"key": "full_name", "label": "Họ tên", "kind": "text"},
            {"key": "relationship", "label": "Quan hệ", "kind": "text"},
            {"key": "phone", "label": "Số điện thoại", "kind": "text", "nowrap": True},
        ],
        "contact_rows": contacts,
        "consent_items": consent_items,
        "can_record_consent": rules.can_edit_profile(request.user, worker),
        "can_print_consent": staff and not anonymized,
    }


def _recruitment_tab(request, worker, employment, identity, staff, role):
    # Từ v1.1 (câu 48) mức lương mong muốn hiện với mọi vai trò, kể cả Viewer.
    can_edit = rules.can_edit_work_tabs(request.user, worker)
    columns = [
        {"key": "position", "label": "Vị trí", "kind": "text"},
        {"key": "source", "label": "Nguồn", "kind": "text"},
        {"key": "applied_date", "label": "Ngày ứng tuyển", "kind": "date"},
        {"key": "salary", "label": "Mức lương mong muốn", "kind": "num"},
        {"key": "status", "label": "Trạng thái tuyển dụng", "kind": "badge"},
    ]

    def edit_action(url):
        return [_link("bi-pencil", "Sửa", url)] if can_edit else []

    def delete_menu(kind, pk, label):
        return {
            "kind": "menu",
            "label": "Thêm",
            "items": [
                {
                    "label": "Xóa dòng",
                    "post_url": f"/{kind}/{pk}/xoa/",
                    "title": f"Xóa dòng {label}",
                    "message": f"Xóa dòng {label} này? Giá trị cũ được ghi vào nhật ký.",
                    "danger": True,
                }
            ],
        }

    applications = []
    for app in worker.applications.select_related("position", "source"):
        actions = edit_action(f"/ung-tuyen/{app.pk}/sua/")
        # Nút chỉ hiện khi Đạt + Đã xác minh (câu 7); máy chủ kiểm tra lại ở service.
        if can_edit and employment_services.can_onboard(app, worker):
            actions.append(
                {
                    "kind": "menu",
                    "label": "Thêm",
                    "items": [
                        {"label": "Tiếp nhận vào làm", "url": f"/ung-tuyen/{app.pk}/tiep-nhan/"}
                    ],
                }
            )
        applications.append(
            {
                "position": app.position.name,
                "source": app.source.name,
                "applied_date": app.applied_date,
                "salary": _money(app.expected_salary),
                "status": app.status,
                "actions": actions,
            }
        )
    education, certificates, experiences = [], [], []
    for e in worker.education.select_related("education_level"):
        education.append(
            {
                "level": e.education_level.name,
                "school": e.school_name,
                "major": e.major,
                "years": _years(e.start_year, e.end_year),
                "actions": edit_action(f"/hoc-van/{e.pk}/sua/")
                + ([delete_menu("hoc-van", e.pk, "học vấn")] if can_edit else []),
            }
        )
    for c in worker.certificates.all():
        certificates.append(
            {
                "name": c.name,
                "issuer": c.issuer,
                "issue_date": c.issue_date,
                "expiry_date": c.expiry_date,
                "actions": edit_action(f"/chung-chi/{c.pk}/sua/")
                + ([delete_menu("chung-chi", c.pk, "chứng chỉ")] if can_edit else []),
            }
        )
    for x in worker.work_experiences.all():
        experiences.append(
            {
                "company": x.company_name,
                "job_title": x.job_title,
                "start_date": x.start_date,
                "end_date": x.end_date,
                "actions": edit_action(f"/kinh-nghiem/{x.pk}/sua/")
                + ([delete_menu("kinh-nghiem", x.pk, "kinh nghiệm")] if can_edit else []),
            }
        )
    actions_col = [{"key": "actions", "label": "Thao tác", "kind": "actions"}] if can_edit else []
    if can_edit:
        columns = columns + actions_col
    wid = worker.pk
    return {
        "can_edit_work": can_edit,
        "add_links": [
            ("Thêm lần ứng tuyển", f"/ho-so/{wid}/ung-tuyen/them/"),
            ("Thêm học vấn", f"/ho-so/{wid}/hoc-van/them/"),
            ("Thêm chứng chỉ", f"/ho-so/{wid}/chung-chi/them/"),
            ("Thêm kinh nghiệm", f"/ho-so/{wid}/kinh-nghiem/them/"),
        ],
        "app_columns": columns,
        "app_rows": applications,
        "education_columns": [
            {"key": "level", "label": "Trình độ", "kind": "text"},
            {"key": "school", "label": "Trường", "kind": "text"},
            {"key": "major", "label": "Ngành", "kind": "text"},
            {"key": "years", "label": "Năm", "kind": "text", "nowrap": True},
        ]
        + actions_col,
        "education_rows": education,
        "certificate_columns": [
            {"key": "name", "label": "Chứng chỉ", "kind": "text"},
            {"key": "issuer", "label": "Nơi cấp", "kind": "text"},
            {"key": "issue_date", "label": "Ngày cấp", "kind": "date"},
            {"key": "expiry_date", "label": "Ngày hết hạn", "kind": "date"},
        ]
        + actions_col,
        "certificate_rows": certificates,
        "experience_columns": [
            {"key": "company", "label": "Công ty", "kind": "text"},
            {"key": "job_title", "label": "Chức danh", "kind": "text"},
            {"key": "start_date", "label": "Từ ngày", "kind": "date"},
            {"key": "end_date", "label": "Đến ngày", "kind": "date"},
        ]
        + actions_col,
        "experience_rows": experiences,
        "skills": worker.skills.strip() if worker.skills else "",
    }


def _assignment_context(request, worker, employment, staff, can_edit):
    """Đợt làm việc và lịch sử lương (v1.1). Mọi vai trò xem được lương và đơn giá (câu 42); ghi
    chú của đợt và lý do đổi lương là trường cá nhân nên chỉ hiện cho nhân viên (A, Q, H)."""
    today = timezone.localdate()
    can_salary = assignment_services.can_add_salary(request.user, worker)
    assignments = list(worker.work_assignments.select_related("client_company", "position"))
    due = indicators.assignment_due_info(worker_ids=[worker.pk]).get(worker.pk)
    current = next(
        (
            a
            for a in assignments
            if a.start_date <= today and (a.end_date is None or a.end_date >= today)
        ),
        None,
    )
    columns = [
        {"key": "client", "label": "Công ty khách", "kind": "text"},
        {"key": "location", "label": "Địa điểm", "kind": "text"},
        {"key": "position", "label": "Vị trí", "kind": "text"},
        {"key": "start_date", "label": "Từ ngày", "kind": "date"},
        {"key": "end_date", "label": "Đến ngày", "kind": "date"},
    ]
    if staff:
        columns.append({"key": "note", "label": "Ghi chú", "kind": "text"})
    columns.append({"key": "warning", "label": "Cảnh báo", "kind": "badge"})
    if can_edit:
        columns.append({"key": "actions", "label": "Thao tác", "kind": "actions"})
    rows = []
    for a in assignments:
        actions = []
        if can_edit:
            actions.append(_link("bi-pencil", "Sửa đợt làm việc", f"/dot-lam-viec/{a.pk}/sua/"))
        if can_salary:
            actions.append(
                {
                    "kind": "menu",
                    "label": "Thêm",
                    "items": [
                        {
                            "label": "Ghi nhận thay đổi lương",
                            "url": f"/dot-lam-viec/{a.pk}/luong/them/",
                        }
                    ],
                }
            )
        rows.append(
            {
                "client": a.client_company.name,
                "location": a.client_company.location,
                "position": a.position.name,
                "start_date": a.start_date,
                "end_date": a.end_date,
                "note": a.note,
                "warning": badges.EXPIRING if due and due[2].pk == a.pk else "",
                "actions": actions,
            }
        )
    current_items = None
    if current is not None:
        current_items = [
            ("Công ty khách", current.client_company.name),
            ("Địa điểm", current.client_company.location),
            ("Vị trí", current.position.name),
            ("Từ ngày", _fmt_date(current.start_date)),
            ("Đến ngày", _fmt_date(current.end_date) or "Chưa kết thúc"),
        ]
    salary_rows = []
    salaries = (
        worker.salary_history.select_related("assignment__client_company", "created_by")
        .order_by("-effective_date", "-id")
        .all()
    )
    for s in salaries:
        salary_rows.append(
            {
                "assignment": f"{s.assignment.client_company.name} (từ "
                f"{s.assignment.start_date:%d/%m/%Y})",
                "effective_date": s.effective_date,
                "monthly_salary": _money(s.monthly_salary),
                "client_unit_price": _money(s.client_unit_price),
                "reason": s.reason,
                "created_by": s.created_by.full_name,
                "created_at": s.created_at,
            }
        )
    salary_columns = [
        {"key": "assignment", "label": "Đợt làm việc", "kind": "text"},
        {"key": "effective_date", "label": "Ngày áp dụng", "kind": "date"},
        {"key": "monthly_salary", "label": "Lương tháng", "kind": "num"},
        {"key": "client_unit_price", "label": "Đơn giá tháng", "kind": "num"},
    ]
    if staff:
        salary_columns.append({"key": "reason", "label": "Lý do", "kind": "text"})
    salary_columns += [
        {"key": "created_by", "label": "Người sửa", "kind": "text"},
        {"key": "created_at", "label": "Ngày ghi", "kind": "date"},
    ]
    now_salary = assignment_services.current_salary(current, today) if current else None
    salary_items = None
    if now_salary is not None:
        salary_items = [
            ("Lương tháng", _money(now_salary.monthly_salary)),
            ("Đơn giá tháng (tính cho công ty khách)", _money(now_salary.client_unit_price)),
            ("Áp dụng từ", _fmt_date(now_salary.effective_date)),
            ("Đợt làm việc", f"{current.client_company.name}, từ {_fmt_date(current.start_date)}"),
        ]
    links = []
    if can_edit and employment is not None:
        links.append(("Thêm đợt làm việc", f"/ho-so/{worker.pk}/dot-lam-viec/them/", True))
    target = current or (assignments[0] if assignments else None)
    if can_salary and target is not None:
        links.append(("Ghi nhận thay đổi lương", f"/dot-lam-viec/{target.pk}/luong/them/", True))
    return {
        "work_links": links,
        "assignment_columns": columns,
        "assignment_rows": rows,
        "assignment_current_items": current_items,
        "assignment_warning": (
            f"Đợt làm việc tại {due[2].client_company.name} (liền nhau từ "
            f"{due[1]:%d/%m/%Y}) đủ thời hạn vào {due[0]:%d/%m/%Y}."
            if due
            else ""
        ),
        "salary_items": salary_items,
        "salary_columns": salary_columns,
        "salary_rows": salary_rows,
        "salary_modal_id": "",
    }


def _employment_tab(request, worker, employment, identity, staff, role):
    items = None
    if employment is not None:
        items = [
            ("Phòng ban", employment.department.name if employment.section_id else None),
            ("Bộ phận", employment.section.name if employment.section_id else None),
            ("Tổ", employment.team.name if employment.team else None),
            ("Chức danh", employment.position.name),
            ("Ca làm việc", employment.shift.name if employment.shift else None),
            (
                "Người quản lý trực tiếp",
                employment.manager.full_name if employment.manager else None,
            ),
            ("Ngày tiếp nhận", _fmt_date(employment.received_date)),
            ("Ngày bắt đầu", _fmt_date(employment.start_date)),
            ("Trạng thái làm việc", WorkStatus(employment.work_status).label),
        ]
        if employment.work_status == WorkStatus.RESIGNED:
            items += [
                ("Ngày nghỉ việc", _fmt_date(employment.resign_date)),
                ("Lý do nghỉ việc", employment.get_resign_reason_display()),
            ]
    history = []
    for h in worker.employment_history.select_related(
        "from_section",
        "to_section",
        "from_team",
        "to_team",
        "from_position",
        "to_position",
        "from_shift",
        "to_shift",
        "from_manager",
        "to_manager",
    ):
        parts = []
        for label, old, new in (
            ("Bộ phận", h.from_section, h.to_section),
            ("Tổ", h.from_team, h.to_team),
            ("Chức danh", h.from_position, h.to_position),
            ("Ca", h.from_shift, h.to_shift),
            (
                "Người quản lý",
                h.from_manager.employee_code if h.from_manager else None,
                h.to_manager.employee_code if h.to_manager else None,
            ),
        ):
            if old or new:
                parts.append(f"{label}: {old or DASH} → {new or DASH}")
        if h.to_work_status:
            parts.append(
                f"Trạng thái: {_label(WorkStatus, h.from_work_status) or DASH} → "
                f"{WorkStatus(h.to_work_status).label}"
            )
        history.append(
            {
                "effective_date": h.effective_date,
                "change": EmploymentChangeType(h.change_type).label,
                "detail": "; ".join(parts) or None,
                "decision_no": h.decision_no,
                "reason": h.reason,
            }
        )
    contract_columns = [
        {"key": "type", "label": "Loại hợp đồng", "kind": "text"},
        {"key": "contract_no", "label": "Số hợp đồng", "kind": "text", "nowrap": True},
        {"key": "effective_date", "label": "Từ ngày", "kind": "date"},
        {"key": "expiry_date", "label": "Đến ngày", "kind": "date"},
    ]
    contract_columns.append({"key": "warning", "label": "Cảnh báo", "kind": "badge"})
    if staff:
        contract_columns.append({"key": "actions", "label": "Thao tác", "kind": "actions"})
    can_edit = rules.can_edit_work_tabs(request.user, worker)
    contracts = []
    expiring_pks = set(
        indicators.contract_expiring_q().filter(worker=worker).values_list("pk", flat=True)
    )
    for c in worker.contracts.select_related("document"):
        row = {
            "type": ContractType(c.contract_type).label,
            "contract_no": c.contract_no,
            "effective_date": c.effective_date,
            "expiry_date": c.expiry_date,
            "warning": badges.EXPIRING if c.pk in expiring_pks else "",
            "actions": [],
        }
        current = c.current_document  # bản hiện hành của chuỗi thay thế (câu 32)
        if staff and current is not None and current.stored_file:
            row["actions"].append(
                _link("bi-download", "Tải tệp hợp đồng", f"/tai-lieu/{current.pk}/tai-xuong/")
            )
        if can_edit:
            row["actions"].append(_link("bi-pencil", "Sửa hợp đồng", f"/hop-dong/{c.pk}/sua/"))
        contracts.append(row)
    assignment_context = _assignment_context(request, worker, employment, staff, can_edit)
    return {
        "can_edit_work": can_edit,
        "work_links": [
            ("Ghi nhận thay đổi", f"/ho-so/{worker.pk}/lam-viec/thay-doi/", employment is not None),
            ("Thêm hợp đồng", f"/ho-so/{worker.pk}/hop-dong/them/", employment is not None),
            *assignment_context.pop("work_links"),
        ],
        **assignment_context,
        "employment_items": items,
        "history_columns": [
            {"key": "effective_date", "label": "Ngày hiệu lực", "kind": "date"},
            {"key": "change", "label": "Thay đổi", "kind": "text"},
            {"key": "detail", "label": "Chi tiết", "kind": "text"},
            {"key": "decision_no", "label": "Số quyết định", "kind": "text"},
            {"key": "reason", "label": "Lý do", "kind": "text"},
        ],
        "history_rows": history,
        "contract_columns": contract_columns,
        "contract_rows": contracts,
    }


def _documents_tab(request, worker, employment, identity, staff, role):
    user = request.user
    can_replace = rules.can_replace_document(user, worker)
    can_verify = rules.can_verify_document(user, worker)
    columns = [{"key": "type", "label": "Loại tài liệu", "kind": "text"}]
    if staff:  # tên tệp gốc không hiện cho Viewer
        columns.append({"key": "name", "label": "Tên tệp", "kind": "text"})
    columns += [
        {"key": "uploaded_at", "label": "Ngày tải", "kind": "date"},
        {"key": "version", "label": "Phiên bản", "kind": "num"},
        {"key": "verification", "label": "Xác minh", "kind": "badge"},
    ]
    if staff:
        columns.append({"key": "actions", "label": "Thao tác", "kind": "actions"})

    def doc_row(doc, *, current):
        row = {
            "type": doc.document_type.name,
            "name": doc.original_name or ("(đã ẩn danh)" if worker.anonymized_at else None),
            "uploaded_at": doc.uploaded_at,
            "version": doc.version,
            "verification": doc.verification_status,
            "actions": [],
        }
        if staff and doc.stored_file:
            row["actions"].append(_link("bi-eye", "Xem", f"/tai-lieu/{doc.pk}/xem/"))
            row["actions"].append(
                _link("bi-download", "Tải xuống", f"/tai-lieu/{doc.pk}/tai-xuong/")
            )
        items = []
        if current and can_replace:
            items.append({"label": "Thay thế", "url": f"/tai-lieu/{doc.pk}/thay-the/"})
        if current and can_verify:
            items.append(
                {
                    "label": "Xác minh",
                    "post_url": f"/tai-lieu/{doc.pk}/xac-minh/",
                    "title": "Xác minh tài liệu",
                    "message": "Chọn trạng thái xác minh cho tài liệu này.",
                }
            )
        if items:
            row["actions"].append({"kind": "menu", "label": "Thêm", "items": items})
        return row

    documents = WorkerDocument.objects.filter(worker=worker).select_related(
        "document_type", "uploaded_by"
    )
    current_rows = [doc_row(d, current=True) for d in documents if d.is_current]
    old_rows = [doc_row(d, current=False) for d in documents if not d.is_current]
    missing = [g.name for g in document_services.missing_groups(worker)]
    return {
        "doc_columns": columns,
        "doc_rows": current_rows,
        "old_doc_rows": old_rows if staff else [],
        "missing_groups": missing,
        "missing_text": "Còn thiếu giấy tờ: " + ", ".join(missing) + ".",
        "can_verify": can_verify,
        "can_upload": rules.can_add_document(user, worker),
        "upload_url": f"/ho-so/{worker.pk}/tai-lieu/them/",
    }


def _history_tab(request, worker, employment, identity, staff, role):
    timeline = []
    for change in worker.status_changes.select_related("changed_by"):
        timeline.append(
            {
                "changed_at": change.changed_at,
                "who": change.changed_by.full_name if change.changed_by else "Hệ thống",
                "from": change.from_status or "",
                "to": change.to_status,
                "reason": change.reason,
            }
        )
    return {
        "timeline_columns": [
            {"key": "changed_at", "label": "Thời điểm", "kind": "datetime"},
            {"key": "who", "label": "Người thực hiện", "kind": "text"},
            {"key": "from", "label": "Từ", "kind": "badge"},
            {"key": "to", "label": "Sang", "kind": "badge"},
            {"key": "reason", "label": "Lý do", "kind": "text"},
        ],
        "timeline_rows": timeline,
        "can_see_changes": role in MANAGERS,
    }


_TAB_BUILDERS = {
    "ca-nhan": _personal_tab,
    "tuyen-dung": _recruitment_tab,
    "lam-viec": _employment_tab,
    "tai-lieu": _documents_tab,
    "lich-su": _history_tab,
}


# --- Mảnh HTMX và trang phụ ---------------------------------------------------------------------
@role_required(*STAFF)
@require_POST
def show_full_id(request, pk):
    """ "Hiện số đầy đủ" (câu 12): mỗi lần bấm ghi nhật ký VIEW_FULL_ID."""
    worker = get_object_or_404(Worker.objects.select_related("identity"), pk=pk)
    identity = getattr(worker, "identity", None)
    if worker.anonymized_at is not None or identity is None or not identity.id_number_enc:
        raise Http404
    log(AuditAction.VIEW_FULL_ID, user=request.user, obj=identity, request=request)
    response = render(
        request,
        "workers/_full_id.html",
        {"id_number": identity.id_number_enc, "old_id_number": identity.old_id_number_enc},
    )
    response["Cache-Control"] = "no-store"
    return response


@role_required(*MANAGERS)
@require_GET
def history_detail(request, pk):
    """Giá trị trước/sau từng trường (câu 11, 30); chỉ Admin và Quản lý nhân sự. Số CCCD và CMND cũ
    luôn hiện dạng che; hồ sơ đã ẩn danh hóa hiện "(đã ẩn danh)"."""
    worker = get_object_or_404(Worker, pk=pk)
    skipped = {"VIEW_FILE", "DOWNLOAD_FILE", "VIEW_FULL_ID", "PRINT"}
    entries = (
        AuditLog.objects.filter(worker=worker)
        .exclude(action__in=skipped)
        .prefetch_related("personal_values")
        .select_related("user")[:200]
    )
    masked = {"identity.id_number", "identity.old_id_number"}
    rows = []
    for entry in entries:
        values = {p.field_name: p for p in entry.personal_values.all()}
        base = {
            "at": entry.created_at,
            "who": entry.user.full_name if entry.user else entry.actor_label,
            "action": entry.get_action_display(),
        }
        if not entry.changes:
            rows.append({**base, "field": None, "old": None, "new": None})
        for field_name, value in entry.changes.items():
            if isinstance(value, list):  # trường không cá nhân: giá trị nằm ngay trong nhật ký
                old, new = value
            else:  # trường cá nhân: giải mã từ AuditPersonalValue
                saved = values.get(field_name)
                if saved is None:
                    old = new = "(đã ẩn danh)" if worker.anonymized_at else None
                else:
                    old, new = saved.old_value_enc, saved.new_value_enc
                    if field_name in masked:
                        old, new = mask_id_number(old) or None, mask_id_number(new) or None
            rows.append(
                {
                    **base,
                    "field": history_labels.field_label(field_name, entry.object_type),
                    "old": history_labels.value_label(field_name, entry.object_type, old),
                    "new": history_labels.value_label(field_name, entry.object_type, new),
                }
            )
    return render(
        request,
        "workers/_history_detail.html",
        {
            "rows": rows,
            "columns": [
                {"key": "at", "label": "Thời điểm", "kind": "datetime"},
                {"key": "who", "label": "Người thực hiện", "kind": "text"},
                {"key": "action", "label": "Hành động", "kind": "text"},
                {"key": "field", "label": "Trường", "kind": "text"},
                {"key": "old", "label": "Trước", "kind": "text"},
                {"key": "new", "label": "Sau", "kind": "text"},
            ],
        },
    )


# --- Đồng ý xử lý dữ liệu -----------------------------------------------------------------------
@role_required(*STAFF)
def consent(request, pk):
    worker = get_object_or_404(Worker, pk=pk)
    if not rules.can_edit_profile(request.user, worker):
        raise PermissionDenied
    data, files = _form_data(request)
    form = ConsentForm(data, files)
    if request.method == "POST" and form.is_valid():
        try:
            services.record_consent_with_file(
                request.user,
                worker,
                consented=form.cleaned_data["consented"],
                consent_date=form.cleaned_data["consent_date"],
                method=form.cleaned_data["method"],
                uploaded=form.cleaned_data["file"],
                request=request,
            )
        except services.WorkerDataError as exc:
            _apply_errors(form, exc)
        else:
            messages.success(request, "Đã ghi nhận đồng ý xử lý dữ liệu.")
            return redirect(worker_url(worker, "ca-nhan"))
    return render(
        request,
        "workers/consent_form.html",
        {
            "form": form,
            "worker": worker,
            "page_title": "Ghi nhận đồng ý xử lý dữ liệu",
            "crumbs": [
                ("Hồ sơ công nhân", "/ho-so/"),
                (worker.worker_code, worker_url(worker)),
                ("Ghi nhận đồng ý", None),
            ],
            "cancel_url": worker_url(worker, "ca-nhan"),
        },
    )


@role_required(*STAFF)
@require_GET
def consent_print(request, pk):
    """Văn bản đồng ý điền sẵn mã hồ sơ, họ tên, ngày sinh, SĐT (không có số CCCD); ghi PRINT."""
    worker = get_object_or_404(Worker, pk=pk)
    if worker.anonymized_at is not None:
        raise Http404
    log(AuditAction.PRINT, user=request.user, obj=worker, note="In mẫu đồng ý", request=request)
    return render(
        request,
        "workers/consent_print.html",
        {"worker": worker, "page_title": "Văn bản đồng ý xử lý dữ liệu cá nhân"},
    )
