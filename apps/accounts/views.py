"""Đăng nhập, đổi mật khẩu, quản lý tài khoản (giao diện tạm, Phase 2)."""

import datetime

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

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


@admin_only
def user_list(request):
    users = User.objects.select_related("role").order_by("username")
    page = Paginator(users, 20).get_page(request.GET.get("trang"))
    now = timezone.now()
    rows = [
        {
            "user": u,
            "status": services.lock_status(u, now),
            "is_self": u.pk == request.user.pk,
        }
        for u in page
    ]
    return render(request, "accounts/user_list.html", {"rows": rows, "page": page})


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
        return render(request, "accounts/temp_password.html", {"target": user, "temp": temp})
    return render(request, "accounts/user_form.html", {"form": form, "creating": True})


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
    return render(request, "accounts/user_form.html", {"form": form, "target": target})


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
    return render(request, "accounts/temp_password.html", {"target": target, "temp": temp})


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
    return render(request, "accounts/login_history.html", {"form": form, "page": page})
