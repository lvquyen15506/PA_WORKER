"""Tuyển dụng (docs/thiet-ke/trang.md mục 5.7): danh sách lần ứng tuyển, thêm/sửa lần ứng tuyển,
học vấn, chứng chỉ, kinh nghiệm. Quyền kiểm tra ở máy chủ: vai trò (role_required) rồi quyền theo
trạng thái hồ sơ (apps.workers.rules.can_edit_work_tabs, câu 36). Viewer chỉ xem danh sách."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.permissions import ALL_ROLES, role_required
from apps.workers import rules
from apps.workers.models import Worker
from apps.workers.rules import ALL_STAFF

from . import services
from .forms import (
    ApplicationForm,
    CertificateForm,
    EducationForm,
    ExperienceForm,
    RecruitmentFilterForm,
)
from .models import Application, Certificate, Education, WorkExperience

STAFF = tuple(ALL_STAFF)
PAGE_SIZE = 20
TAB_URL = "/ho-so/{}/?tab=tuyen-dung"

LIST_COLUMNS = [
    {"key": "stt", "label": "STT", "kind": "num"},
    {"key": "worker_code", "label": "Mã hồ sơ", "kind": "text", "nowrap": True},
    {"key": "full_name", "label": "Họ và tên", "kind": "text"},
    {"key": "position", "label": "Vị trí", "kind": "text"},
    {"key": "source", "label": "Nguồn", "kind": "text"},
    {"key": "applied_date", "label": "Ngày ứng tuyển", "kind": "date"},
    {"key": "salary", "label": "Mức lương mong muốn", "kind": "num"},
    {"key": "status", "label": "Trạng thái tuyển dụng", "kind": "badge"},
    {"key": "actions", "label": "Thao tác", "kind": "actions"},
]

# Loại dòng con: (form, model, nhãn danh từ, hàm thêm, hàm sửa). Khóa trùng URL.
CHILDREN = {
    "hoc-van": (EducationForm, Education, "học vấn", "add_education", "update_education"),
    "chung-chi": (
        CertificateForm,
        Certificate,
        "chứng chỉ",
        "add_certificate",
        "update_certificate",
    ),
    "kinh-nghiem": (
        ExperienceForm,
        WorkExperience,
        "kinh nghiệm làm việc",
        "add_work_experience",
        "update_work_experience",
    ),
}


def _money(value):
    return f"{int(value):,}".replace(",", ".") + " đ" if value is not None else None


def _apply_errors(form, exc):
    for name, message in exc.errors.items():
        form.add_error(name if name in form.fields else None, message)


def _form_page(request, form, *, title, crumbs, cancel_url, submit_label, status=200):
    return render(
        request,
        "core/simple_form.html",
        {
            "form": form,
            "page_title": title,
            "crumbs": crumbs,
            "cancel_url": cancel_url,
            "submit_label": submit_label,
        },
        status=status,
    )


def _crumbs(worker, last):
    return [
        ("Hồ sơ công nhân", "/ho-so/"),
        (worker.worker_code, f"/ho-so/{worker.pk}/"),
        ("Tuyển dụng & CV", TAB_URL.format(worker.pk)),
        (last, None),
    ]


def _require_edit(user, worker):
    if not rules.can_edit_work_tabs(user, worker):
        raise PermissionDenied


# --- Danh sách /tuyen-dung/ ----------------------------------------------------------------
@role_required(*ALL_ROLES)
def recruitment_list(request):
    form = RecruitmentFilterForm(request.GET)
    form.is_valid()
    qs = form.filter_queryset(Application.objects.select_related("worker", "position", "source"))
    page = Paginator(qs.order_by("-applied_date", "-id"), PAGE_SIZE).get_page(
        request.GET.get("trang")
    )
    staff = request.user.role.code in ALL_STAFF
    rows = []
    for number, app in enumerate(page, start=page.start_index()):
        actions = [
            {
                "kind": "link",
                "icon": "bi-eye",
                "tooltip": "Xem hồ sơ",
                "url": TAB_URL.format(app.worker_id),
            }
        ]
        if staff and rules.can_edit_work_tabs(request.user, app.worker):
            actions.append(
                {
                    "kind": "link",
                    "icon": "bi-pencil",
                    "tooltip": "Sửa lần ứng tuyển",
                    "url": f"/ung-tuyen/{app.pk}/sua/",
                }
            )
        rows.append(
            {
                "stt": number,
                "worker_code": app.worker.worker_code,
                "full_name": app.worker.full_name,
                "position": app.position.name,
                "source": app.source.name,
                "applied_date": app.applied_date,
                "salary": _money(app.expected_salary),
                "status": app.status,
                "actions": actions,
            }
        )
    query = request.GET.copy()
    query.pop("trang", None)
    return render(
        request,
        "recruitment/list.html",
        {
            "form": form,
            "columns": LIST_COLUMNS,
            "rows": rows,
            "page": page,
            "query": query.urlencode(),
        },
    )


# --- Lần ứng tuyển -----------------------------------------------------------------------------
@role_required(*STAFF)
def application_add(request, worker_id):
    worker = get_object_or_404(Worker, pk=worker_id)
    _require_edit(request.user, worker)
    form = ApplicationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.add_application(request.user, worker, request=request, **form.service_data())
        except services.RecruitmentDataError as exc:
            _apply_errors(form, exc)
        else:
            messages.success(request, "Đã thêm lần ứng tuyển.")
            return redirect(TAB_URL.format(worker.pk))
    return _form_page(
        request,
        form,
        title="Thêm lần ứng tuyển",
        crumbs=_crumbs(worker, "Thêm lần ứng tuyển"),
        cancel_url=TAB_URL.format(worker.pk),
        submit_label="Lưu lần ứng tuyển",
    )


@role_required(*STAFF)
def application_edit(request, pk):
    app = get_object_or_404(Application.objects.select_related("worker"), pk=pk)
    worker = app.worker
    _require_edit(request.user, worker)
    form = ApplicationForm(request.POST or None, instance=app)
    if request.method == "POST" and form.is_valid():
        try:
            changed = services.update_application(
                request.user, app, request=request, **form.service_data()
            )
        except services.RecruitmentDataError as exc:
            _apply_errors(form, exc)
        else:
            if changed:
                messages.success(request, "Đã lưu lần ứng tuyển.")
            else:
                messages.info(request, "Không có thay đổi nào để lưu.")
            return redirect(TAB_URL.format(worker.pk))
    return _form_page(
        request,
        form,
        title="Sửa lần ứng tuyển",
        crumbs=_crumbs(worker, "Sửa lần ứng tuyển"),
        cancel_url=TAB_URL.format(worker.pk),
        submit_label="Lưu lần ứng tuyển",
    )


# --- Học vấn, chứng chỉ, kinh nghiệm ----------------------------------------------------------
def _child_spec(kind):
    return CHILDREN[kind]


@role_required(*STAFF)
def child_add(request, worker_id, kind):
    form_class, _, noun, add_name, _ = _child_spec(kind)
    worker = get_object_or_404(Worker, pk=worker_id)
    _require_edit(request.user, worker)
    form = form_class(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            getattr(services, add_name)(
                request.user, worker, request=request, **form.service_data()
            )
        except services.RecruitmentDataError as exc:
            _apply_errors(form, exc)
        else:
            messages.success(request, f"Đã thêm {noun}.")
            return redirect(TAB_URL.format(worker.pk))
    return _form_page(
        request,
        form,
        title=f"Thêm {noun}",
        crumbs=_crumbs(worker, f"Thêm {noun}"),
        cancel_url=TAB_URL.format(worker.pk),
        submit_label=f"Lưu {noun}",
    )


@role_required(*STAFF)
def child_edit(request, kind, pk):
    form_class, model, noun, _, update_name = _child_spec(kind)
    row = get_object_or_404(model.objects.select_related("worker"), pk=pk)
    worker = row.worker
    _require_edit(request.user, worker)
    form = form_class(request.POST or None, instance=row)
    if request.method == "POST" and form.is_valid():
        try:
            changed = getattr(services, update_name)(
                request.user, row, request=request, **form.service_data()
            )
        except services.RecruitmentDataError as exc:
            _apply_errors(form, exc)
        else:
            messages.success(
                request, f"Đã lưu {noun}." if changed else "Không có thay đổi nào để lưu."
            )
            return redirect(TAB_URL.format(worker.pk))
    return _form_page(
        request,
        form,
        title=f"Sửa {noun}",
        crumbs=_crumbs(worker, f"Sửa {noun}"),
        cancel_url=TAB_URL.format(worker.pk),
        submit_label=f"Lưu {noun}",
    )


@role_required(*STAFF)
@require_POST
def child_delete(request, kind, pk):
    _, model, noun, _, _ = _child_spec(kind)
    row = get_object_or_404(model.objects.select_related("worker"), pk=pk)
    worker = row.worker
    _require_edit(request.user, worker)
    services.delete_child(request.user, row, request=request)
    messages.success(request, f"Đã xóa dòng {noun}.")
    return redirect(TAB_URL.format(worker.pk))
