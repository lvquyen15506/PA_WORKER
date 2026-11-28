"""Quá trình làm việc (docs/thiet-ke/trang.md mục 5.8): tiếp nhận vào làm, ghi nhận thay đổi, hợp
đồng. Quyền kiểm tra ở máy chủ: vai trò (role_required A, Q, H) rồi trạng thái hồ sơ (câu 36);
nghiệp vụ nằm ở apps.employment.services."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.permissions import role_required
from apps.core.choices import RoleCode
from apps.core.models import ClientCompany
from apps.recruitment.models import Application
from apps.workers import rules
from apps.workers.models import Worker
from apps.workers.rules import ALL_STAFF

from . import assignments, services
from .forms import AssignmentForm, ChangeForm, ContractForm, OnboardForm, SalaryForm
from .models import Contract, Employment, WorkAssignment

STAFF = tuple(ALL_STAFF)
TAB_URL = "/ho-so/{}/?tab=lam-viec"


def _page(
    request,
    form,
    *,
    title,
    crumbs,
    cancel_url,
    submit_label,
    intro="",
    multipart=False,
    sections=None,
    notice=None,
):
    return render(
        request,
        "core/simple_form.html",
        {
            "form": form,
            "page_title": title,
            "crumbs": crumbs,
            "cancel_url": cancel_url,
            "submit_label": submit_label,
            "intro": intro,
            "multipart": multipart,
            "sections": sections,
            "notice": notice,
        },
    )


def _crumbs(worker, last):
    return [
        ("Hồ sơ công nhân", "/ho-so/"),
        (worker.worker_code, f"/ho-so/{worker.pk}/"),
        ("Quá trình làm việc", TAB_URL.format(worker.pk)),
        (last, None),
    ]


def _apply_errors(form, exc):
    for name, message in exc.errors.items():
        form.add_error(name if name in form.fields else None, message)
    if not exc.errors:
        form.add_error(None, exc.message)


# --- Tiếp nhận vào làm -------------------------------------------------------------------------
@role_required(*STAFF)
def onboard(request, pk):
    app = get_object_or_404(Application.objects.select_related("worker", "position"), pk=pk)
    worker = app.worker
    if not rules.can_edit_work_tabs(request.user, worker):
        raise PermissionDenied
    back = f"/ho-so/{worker.pk}/?tab=tuyen-dung"
    if not services.can_onboard(app, worker):
        messages.error(
            request,
            "Chỉ tiếp nhận vào làm khi lần ứng tuyển ở trạng thái Đạt và hồ sơ Đã xác minh, "
            "và công nhân chưa có thông tin làm việc đang hiệu lực.",
        )
        return redirect(back)
    form = OnboardForm(request.POST or None, application=app)
    if request.method == "POST" and form.is_valid():
        try:
            employment = services.onboard(request.user, app, request=request, **form.service_data())
        except services.EmploymentError as exc:
            _apply_errors(form, exc)
        else:
            code = Worker.objects.values_list("employee_code", flat=True).get(pk=worker.pk)
            messages.success(request, f"Đã tiếp nhận vào làm. Mã nhân viên {code}.")
            return redirect(TAB_URL.format(employment.worker_id))
    return _page(
        request,
        form,
        title="Tiếp nhận vào làm",
        crumbs=_crumbs(worker, "Tiếp nhận vào làm"),
        cancel_url=back,
        submit_label="Tiếp nhận vào làm",
        intro="Hệ thống cấp mã nhân viên theo cấu hình (người đã có mã nhân viên giữ mã cũ). "
        "Trạng thái làm việc ban đầu là Chờ nhận việc.",
        sections=[
            {"title": "Thông tin làm việc", "fields": form.main_fields()},
            {
                "title": "Gán công ty khách ngay (không bắt buộc)",
                "intro": "Chọn công ty thì hệ thống tạo đợt làm việc đầu tiên cùng lúc với tiếp "
                "nhận. Để trống thì gán sau ở tab Quá trình làm việc, nút Thêm đợt làm việc.",
                "fields": form.assign_fields(),
            },
        ],
    )


# --- Ghi nhận thay đổi -------------------------------------------------------------------------
@role_required(*STAFF)
def change(request, pk):
    worker = get_object_or_404(Worker, pk=pk)
    if not rules.can_edit_work_tabs(request.user, worker):
        raise PermissionDenied
    employment = Employment.objects.select_related("manager").filter(worker=worker).first()
    back = TAB_URL.format(worker.pk)
    if employment is None:
        messages.error(request, "Hồ sơ chưa có thông tin làm việc. Hãy tiếp nhận vào làm trước.")
        return redirect(back)
    form = ChangeForm(request.POST or None, employment=employment)
    if request.method == "POST" and form.is_valid():
        try:
            services.change_employment(request.user, worker, request=request, **form.service_data())
        except services.EmploymentError as exc:
            _apply_errors(form, exc)
        else:
            messages.success(request, "Đã ghi nhận thay đổi.")
            return redirect(back)
    return _page(
        request,
        form,
        title="Ghi nhận thay đổi làm việc",
        crumbs=_crumbs(worker, "Ghi nhận thay đổi"),
        cancel_url=back,
        submit_label="Ghi nhận thay đổi",
        intro="Điều chuyển, đổi chức danh, đổi ca hoặc đổi trạng thái làm việc. Mỗi lần ghi nhận "
        "thêm một dòng lịch sử, không ghi đè dòng cũ.",
    )


# --- Hợp đồng ----------------------------------------------------------------------------------
# --- Đợt làm việc và lương (v1.1) ---------------------------------------------------------------
@role_required(*STAFF)
def assignment_add(request, pk):
    worker = get_object_or_404(Worker, pk=pk)
    if not rules.can_edit_work_tabs(request.user, worker):
        raise PermissionDenied
    back = TAB_URL.format(worker.pk)
    form = AssignmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            assignments.add_assignment(request.user, worker, request=request, **form.service_data())
        except assignments.AssignmentError as exc:
            _apply_errors(form, exc)
        else:
            messages.success(request, "Đã thêm đợt làm việc.")
            return redirect(back)
    return _page(
        request,
        form,
        title="Thêm đợt làm việc",
        crumbs=_crumbs(worker, "Thêm đợt làm việc"),
        cancel_url=back,
        submit_label="Lưu đợt làm việc",
        intro="Mỗi lúc một công nhân chỉ làm cho một công ty khách hàng; các đợt không chồng lấn "
        "ngày và được giữ lại làm lịch sử.",
        notice=_no_client_notice(request.user),
    )


def _no_client_notice(user):
    """v1.1.1: danh mục công ty khách trống thì hướng dẫn; liên kết tới trang thêm chỉ cho Admin
    (trang đó máy chủ chỉ cho Admin)."""
    if ClientCompany.objects.filter(is_active=True).exists():
        return None
    if user.role.code == RoleCode.ADMIN:
        return {
            "text": "Danh mục công ty khách hàng chưa có công ty nào đang sử dụng. "
            "Thêm công ty khách trước, rồi quay lại thêm đợt làm việc.",
            "url": "/cai-dat/danh-muc/cong-ty-khach/them/",
            "label": "Thêm công ty khách",
        }
    return {
        "text": "Danh mục công ty khách hàng chưa có công ty nào đang sử dụng. "
        "Liên hệ Admin để thêm công ty khách (Cài đặt → Danh mục → Công ty khách), rồi quay lại "
        "thêm đợt làm việc."
    }


@role_required(*STAFF)
def assignment_edit(request, pk):
    assignment = get_object_or_404(
        WorkAssignment.objects.select_related("worker", "client_company", "position"), pk=pk
    )
    worker = assignment.worker
    if not rules.can_edit_work_tabs(request.user, worker):
        raise PermissionDenied
    back = TAB_URL.format(worker.pk)
    form = AssignmentForm(request.POST or None, instance=assignment)
    if request.method == "POST" and form.is_valid():
        try:
            changed = assignments.update_assignment(
                request.user, assignment, request=request, **form.service_data()
            )
        except assignments.AssignmentError as exc:
            _apply_errors(form, exc)
        else:
            messages.success(
                request, "Đã lưu đợt làm việc." if changed else "Không có thay đổi nào để lưu."
            )
            return redirect(back)
    return _page(
        request,
        form,
        title="Sửa đợt làm việc",
        crumbs=_crumbs(worker, "Sửa đợt làm việc"),
        cancel_url=back,
        submit_label="Lưu đợt làm việc",
        intro="Đợt làm việc không xóa được; nhập nhầm thì sửa (giá trị cũ được ghi vào nhật ký).",
    )


@role_required(*STAFF)
def salary_add(request, pk):
    assignment = get_object_or_404(
        WorkAssignment.objects.select_related("worker", "client_company"), pk=pk
    )
    worker = assignment.worker
    if not assignments.can_add_salary(request.user, worker):
        raise PermissionDenied  # chỉ Admin và Quản lý nhân sự (câu 42)
    back = TAB_URL.format(worker.pk)
    latest = assignment.salary_history.order_by("-effective_date", "-id").first()
    form = SalaryForm(request.POST or None, latest=latest)
    if request.method == "POST" and form.is_valid():
        try:
            assignments.add_salary(request.user, assignment, request=request, **form.service_data())
        except assignments.AssignmentError as exc:
            _apply_errors(form, exc)
        else:
            messages.success(request, "Đã ghi nhận thay đổi lương.")
            return redirect(back)
    return _page(
        request,
        form,
        title="Ghi nhận thay đổi lương",
        crumbs=_crumbs(worker, "Ghi nhận thay đổi lương"),
        cancel_url=back,
        submit_label="Ghi nhận thay đổi lương",
        intro=f"Đợt làm việc tại {assignment.client_company}, từ "
        f"{assignment.start_date:%d/%m/%Y}. Mỗi lần ghi nhận thêm một dòng lịch sử, không sửa hay "
        "xóa dòng cũ; ghi nhầm thì thêm dòng mới để sửa.",
    )


@role_required(*STAFF)
def contract_add(request, pk):
    worker = get_object_or_404(Worker, pk=pk)
    if not rules.can_edit_work_tabs(request.user, worker):
        raise PermissionDenied
    back = TAB_URL.format(worker.pk)
    form = ContractForm(
        request.POST or None,
        request.FILES or None,
        allow_file=rules.can_add_document(request.user, worker),
    )
    if request.method == "POST" and form.is_valid():
        try:
            services.add_contract(request.user, worker, request=request, **form.service_data())
        except services.EmploymentError as exc:
            _apply_errors(form, exc)
        else:
            messages.success(request, "Đã thêm hợp đồng.")
            return redirect(back)
    return _page(
        request,
        form,
        title="Thêm hợp đồng",
        crumbs=_crumbs(worker, "Thêm hợp đồng"),
        cancel_url=back,
        submit_label="Lưu hợp đồng",
        multipart=True,
    )


@role_required(*STAFF)
def contract_edit(request, pk):
    contract = get_object_or_404(Contract.objects.select_related("worker"), pk=pk)
    worker = contract.worker
    if not rules.can_edit_work_tabs(request.user, worker):
        raise PermissionDenied
    back = TAB_URL.format(worker.pk)
    form = ContractForm(
        request.POST or None,
        request.FILES or None,
        instance=contract,
        allow_file=rules.can_add_document(request.user, worker),
    )
    if request.method == "POST" and form.is_valid():
        try:
            changed = services.update_contract(
                request.user, contract, request=request, **form.service_data()
            )
        except services.EmploymentError as exc:
            _apply_errors(form, exc)
        else:
            messages.success(
                request, "Đã lưu hợp đồng." if changed else "Không có thay đổi nào để lưu."
            )
            return redirect(back)
    return _page(
        request,
        form,
        title="Sửa hợp đồng",
        crumbs=_crumbs(worker, "Sửa hợp đồng"),
        cancel_url=back,
        submit_label="Lưu hợp đồng",
        multipart=True,
        intro="Chọn tệp mới nếu muốn thay tệp đính kèm; tệp cũ vẫn giữ ở tab Tài liệu.",
    )
