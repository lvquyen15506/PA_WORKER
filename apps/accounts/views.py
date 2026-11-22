"""Đăng nhập, đổi mật khẩu, quản lý tài khoản (giao diện tạm, Phase 2)."""

import datetime

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.core import badges
from apps.core.choices import RoleCode

from . import services
from .forms import (
    ChangePasswordForm,
    LoginForm,
    LoginHistoryFilterForm,
    UserCreateForm,
    UserEditForm,
)
from .models import LoginHistory, User
from .permissions import role_required

BACKEND = "django.contrib.auth.backends.ModelBackend"


def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = LoginForm(request.POST or None)
    error = None
    if request.method == "POST" and form.is_valid():
        user, error = services.attempt_login(
            request, form.cleaned_data["username"], form.cleaned_data["password"]
        )
        if user:
            login(request, user, backend=BACKEND)
            target = request.POST.get("next") or request.GET.get("next") or ""
            if not url_has_allowed_host_and_scheme(target, {request.get_host()}):
                target = ""
            return redirect(target or "home")
    return render(
        request,
        "accounts/login.html",
        {"form": form, "error": error, "next": request.GET.get("next", "")},
    )


@require_POST
def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def change_password(request):
    form = ChangePasswordForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        services.change_own_password(
            request.user, form.cleaned_data["new_password1"], request=request
        )
        update_session_auth_hash(request, request.user)  # không bị đăng xuất sau khi đổi
        messages.success(request, "Đã đổi mật khẩu.")
        return redirect("home")
    return render(
        request,
        "accounts/change_password.html",
        {"form": form, "forced": request.user.must_change_password},
    )


# --- Quản lý tài khoản: chỉ Admin ----------------------------------------------------------
admin_only = role_required(RoleCode.ADMIN)

USER_COLUMNS = [
    {"key": "username", "label": "Tên đăng nhập", "kind": "text", "nowrap": True},
    {"key": "full_name", "label": "Họ tên", "kind": "text"},
    {"key": "role", "label": "Vai trò", "kind": "text", "nowrap": True},
    {"key": "status", "label": "Trạng thái", "kind": "badge"},
    {"key": "last_login", "label": "Đăng nhập lần cuối", "kind": "datetime"},
    {"key": "actions", "label": "Thao tác", "kind": "actions"},
]
LOGIN_COLUMNS = [
    {"key": "at", "label": "Thời điểm", "kind": "datetime", "nowrap": True},
    {"key": "username", "label": "Tên đăng nhập", "kind": "text"},
    {"key": "ip", "label": "Địa chỉ IP", "kind": "text", "nowrap": True},
    {"key": "result", "label": "Kết quả", "kind": "badge"},
    {"key": "reason", "label": "Lý do", "kind": "text"},
]
ACCOUNT_CRUMBS = [("Tài khoản", "/tai-khoan/")]


def _account_tabs(active):
    return [
        {"label": "Danh sách", "url": reverse("user_list"), "active": active == "list"},
        {
            "label": "Lịch sử đăng nhập",
            "url": reverse("login_history"),
            "active": active == "history",
        },
    ]


def _menu_post(url, label, user, title, danger=False):
    """Mục menu "Thêm" gửi POST qua hộp xác nhận; chữ không chứa họ tên, chỉ tên đăng nhập."""
    return {
        "label": label,
        "post_url": url,
        "title": title,
        "message": f"{title} {user.username}?",
        "danger": danger,
    }


def _temp_password_page(request, target, temp):
    """Hiện mật khẩu tạm ngay trong phản hồi này, một lần; không lưu vào phiên hay thông báo."""
    context = {
        "target": target,
        "temp": temp,
        "crumbs": ACCOUNT_CRUMBS + [("Mật khẩu tạm", None)],
        "header_actions": [
            {"label": "Quay lại danh sách", "kind": "primary", "url": reverse("user_list")}
        ],
    }
    return render(request, "accounts/temp_password.html", context)


@admin_only
def user_list(request):
    users = User.objects.select_related("role").order_by("username")
    page = Paginator(users, 20).get_page(request.GET.get("trang"))
    now = timezone.now()
    rows = []
    for u in page:
        code, label = services.lock_status(u, now)
        items = []
        if code != "ok":
            items.append(
                _menu_post(f"/tai-khoan/{u.pk}/mo-khoa/", "Mở khóa", u, "Mở khóa tài khoản")
            )
        if code != "admin" and u.pk != request.user.pk:
            items.append(
                _menu_post(
                    f"/tai-khoan/{u.pk}/khoa/", "Khóa tài khoản", u, "Khóa tài khoản", danger=True
                )
            )
        items.append(
            _menu_post(
                f"/tai-khoan/{u.pk}/dat-lai-mat-khau/", "Đặt lại mật khẩu", u, "Đặt lại mật khẩu"
            )
        )
        rows.append(
            {
                "username": u.username,
                "full_name": u.full_name,
                "role": u.role.name,
                "status": {"value": badges.ACCOUNT_LOCK_BADGE[code], "label": label},
                "last_login": u.last_login,
                "actions": [
                    {
                        "kind": "link",
                        "icon": "bi-pencil",
                        "tooltip": "Sửa",
                        "url": reverse("user_edit", args=[u.pk]),
                    },
                    {"kind": "menu", "label": "Thêm", "items": items},
                ],
            }
        )
    context = {
        "rows": rows,
        "columns": USER_COLUMNS,
        "page": page,
        "tabs": _account_tabs("list"),
        "header_actions": [
            {"label": "Thêm tài khoản", "kind": "primary", "url": reverse("user_create")}
        ],
    }
    return render(request, "accounts/user_list.html", context)


@admin_only
def user_create(request):
    form = UserCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user, temp = services.create_user(
            request.user,
            username=form.cleaned_data["username"],
            full_name=form.cleaned_data["full_name"],
            role=form.cleaned_data["role"],
            request=request,
        )
        # Hiện mật khẩu tạm ngay trong phản hồi này, một lần; không lưu vào phiên hay thông báo.
        return _temp_password_page(request, user, temp)
    context = {
        "form": form,
        "creating": True,
        "page_title": "Thêm tài khoản",
        "crumbs": ACCOUNT_CRUMBS + [("Thêm tài khoản", None)],
    }
    return render(request, "accounts/user_form.html", context)


@admin_only
def user_edit(request, pk):
    target = get_object_or_404(User.objects.select_related("role"), pk=pk)
    is_self = target.pk == request.user.pk
    form = UserEditForm(
        request.POST or None,
        initial={"full_name": target.full_name, "role": target.role_id},
        editing_self=is_self,
    )
    if request.method == "POST" and form.is_valid():
        try:
            services.update_user(
                request.user,
                target,
                full_name=form.cleaned_data["full_name"],
                role=form.cleaned_data["role"],
                request=request,
            )
        except services.AccountError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Đã lưu tài khoản.")
            return redirect("user_list")
    context = {
        "form": form,
        "target": target,
        "page_title": f"Sửa tài khoản {target.username}",
        "crumbs": ACCOUNT_CRUMBS + [(target.username, None)],
    }
    return render(request, "accounts/user_form.html", context)


def _post_action(request, pk, action, success):
    target = get_object_or_404(User, pk=pk)
    try:
        action(request.user, target, request=request)
    except services.AccountError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, success)
    return redirect("user_list")


@admin_only
@require_POST
def user_lock(request, pk):
    return _post_action(request, pk, services.lock_user, "Đã khóa tài khoản.")


@admin_only
@require_POST
def user_unlock(request, pk):
    return _post_action(request, pk, services.unlock_user, "Đã mở khóa tài khoản.")


@admin_only
@require_POST
def user_reset_password(request, pk):
    target = get_object_or_404(User, pk=pk)
    temp = services.reset_password(request.user, target, request=request)
    return _temp_password_page(request, target, temp)


@admin_only
def login_history(request):
    form = LoginHistoryFilterForm(request.GET or None)
    qs = LoginHistory.objects.select_related("user")
    if form.is_valid():
        d = form.cleaned_data
        if d["username"]:
            qs = qs.filter(username_attempted__icontains=d["username"])
        if d["result"]:
            qs = qs.filter(success=d["result"] == "ok")
        tz = timezone.get_current_timezone()
        if d["date_from"]:
            qs = qs.filter(
                created_at__gte=datetime.datetime.combine(d["date_from"], datetime.time.min, tz)
            )
        if d["date_to"]:
            qs = qs.filter(
                created_at__lt=datetime.datetime.combine(
                    d["date_to"] + datetime.timedelta(days=1), datetime.time.min, tz
                )
            )
    page = Paginator(qs, 20).get_page(request.GET.get("trang"))
    rows = [
        {
            "at": h.created_at,
            "username": h.username_attempted,
            "ip": h.ip_address,
            "result": badges.LOGIN_OK if h.success else badges.LOGIN_FAILED,
            "reason": h.failure_reason,
        }
        for h in page
    ]
    params = request.GET.copy()
    params.pop("trang", None)
    context = {
        "form": form,
        "page": page,
        "rows": rows,
        "columns": LOGIN_COLUMNS,
        "tabs": _account_tabs("history"),
        "query": params.urlencode(),
    }
    return render(request, "accounts/login_history.html", context)
