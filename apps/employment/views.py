"""Quá trình làm việc (docs/thiet-ke/trang.md mục 5.8): tiếp nhận vào làm, ghi nhận thay đổi, hợp
đồng. Quyền kiểm tra ở máy chủ: vai trò (role_required A, Q, H) rồi trạng thái hồ sơ (câu 36);
nghiệp vụ nằm ở apps.employment.services."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.permissions import role_required
from apps.recruitment.models import Application
from apps.workers import rules
from apps.workers.models import Worker
from apps.workers.rules import ALL_STAFF

from . import services
from .forms import ChangeForm, ContractForm, OnboardForm
from .models import Contract, Employment

STAFF = tuple(ALL_STAFF)
TAB_URL = "/ho-so/{}/?tab=lam-viec"


def _page(request, form, *, title, crumbs, cancel_url, submit_label, intro="", multipart=False):
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
