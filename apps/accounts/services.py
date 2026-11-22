"""Đăng nhập, khóa tài khoản, quản lý người dùng (models.md mục 4.6, trang.md mục 5.1).

Hai cơ chế khóa tách riêng (câu 28):
- Khóa tạm do sai mật khẩu: failed_login_count, locked_until; tự hết sau 15 phút.
- Admin khóa: is_active = False, vô thời hạn đến khi Admin mở.
Bảo vệ quyền quản trị (câu 29): kiểm tra ở đây, ở máy chủ.
"""

import datetime
import secrets
import string

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.sessions.models import Session
from django.db import transaction
from django.utils import timezone

from apps.audit.services import log
from apps.core.choices import AuditAction, RoleCode

from .models import LoginHistory, Role, User

MSG_BAD_CREDENTIALS = "Tên tài khoản hoặc mật khẩu không đúng."
MSG_ADMIN_LOCKED = "Tài khoản đã bị khóa. Liên hệ Admin."
MSG_SELF = "Bạn không thể khóa hoặc đổi vai trò của chính mình."
MSG_LAST_ADMIN = "Hệ thống phải còn ít nhất một Admin đang hoạt động."

REASON_BAD_PASSWORD = "Sai mật khẩu"
REASON_UNKNOWN_USER = "Tên tài khoản không tồn tại"
REASON_TEMP_LOCK = "Tài khoản đang khóa tạm"
REASON_ADMIN_LOCK = "Tài khoản bị Admin khóa"


class AccountError(Exception):
    """Thao tác tài khoản bị từ chối; thông báo tiếng Việt hiển thị cho người dùng."""


def client_ip(request):
    return (request.META.get("REMOTE_ADDR") if request else None) or "0.0.0.0"


def _temp_lock_message(until):
    return (
        f"Tài khoản tạm khóa do nhập sai nhiều lần. Thử lại sau {timezone.localtime(until):%H:%M}."
    )


def _record(request, user, username, ok, reason=""):
    LoginHistory.objects.create(
        user=user,
        username_attempted=username[:150],
        ip_address=client_ip(request),
        success=ok,
        failure_reason=reason,
    )


@transaction.atomic
def attempt_login(request, username, password):
    """Kiểm tra đăng nhập. Trả (user, None) khi đúng, hoặc (None, thông báo lỗi).

    Mọi lượt đều ghi LoginHistory. Trong lúc khóa tạm, mật khẩu đúng vẫn bị từ chối.
    """
    username = (username or "").strip()
    user = User.objects.select_for_update().select_related("role").filter(username=username).first()
    if user is None:
        # Vẫn băm một mật khẩu giả để thời gian phản hồi không lộ tài khoản có tồn tại hay không.
        check_password(password, make_password("x"))
        _record(request, None, username, False, REASON_UNKNOWN_USER)
        return None, MSG_BAD_CREDENTIALS

    now = timezone.now()
    if not user.is_active:
        _record(request, user, username, False, REASON_ADMIN_LOCK)
        return None, MSG_ADMIN_LOCKED

    if user.locked_until and user.locked_until <= now:  # khóa tạm đã hết hạn
        user.locked_until = None
        user.failed_login_count = 0
        user.save(update_fields=["locked_until", "failed_login_count"])
    if user.locked_until:
        _record(request, user, username, False, REASON_TEMP_LOCK)
        return None, _temp_lock_message(user.locked_until)

    if not user.check_password(password):
        user.failed_login_count += 1
        message = MSG_BAD_CREDENTIALS
        if user.failed_login_count >= settings.LOGIN_FAIL_LIMIT:
            user.locked_until = now + datetime.timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
            message = _temp_lock_message(user.locked_until)
        user.save(update_fields=["failed_login_count", "locked_until"])
        _record(request, user, username, False, REASON_BAD_PASSWORD)
        return None, message

    user.failed_login_count = 0
    user.locked_until = None
    user.save(update_fields=["failed_login_count", "locked_until"])
    _record(request, user, username, True)
    return user, None


# --- Quản lý tài khoản (chỉ Admin) ------------------------------------------------------------
def generate_temp_password(length=12):
    """Mật khẩu tạm ngẫu nhiên, luôn có chữ hoa, chữ thường và số; bỏ ký tự dễ nhầm."""
    letters = "".join(c for c in string.ascii_letters if c not in "lIO")
    digits = "".join(c for c in string.digits if c not in "01")
    chars = [secrets.choice(string.ascii_lowercase.replace("l", "")), secrets.choice(digits)]
    chars.append(secrets.choice(string.ascii_uppercase.replace("I", "").replace("O", "")))
    chars += [secrets.choice(letters + digits) for _ in range(length - 3)]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def _active_admins_locked():
    """Admin đang hoạt động, khóa dòng để hai thao tác đồng thời không cùng hạ Admin cuối."""
    return list(
        User.objects.select_for_update()
        .filter(role__code=RoleCode.ADMIN, is_active=True)
        .values_list("pk", flat=True)
    )


def _would_remove_last_admin(target):
    """Thao tác sẽ làm target không còn là Admin đang hoạt động; còn Admin khác hoạt động không?"""
    admins = _active_admins_locked()
    return target.pk in admins and len(admins) <= 1


def end_sessions(user):
    """Xóa mọi phiên đăng nhập còn hiệu lực của người dùng."""
    for session in Session.objects.filter(expire_date__gt=timezone.now()):
        if session.get_decoded().get("_auth_user_id") == str(user.pk):
            session.delete()


@transaction.atomic
def create_user(actor, *, username, full_name, role, request=None):
    """Tạo tài khoản với mật khẩu tạm (hiện một lần). Trả (user, mật khẩu tạm)."""
    temp = generate_temp_password()
    user = User(username=username, full_name=full_name, role=role, must_change_password=True)
    user.set_password(temp)
    user.save()
    log(AuditAction.CREATE, user=actor, obj=user, request=request, note="Tạo tài khoản")
    return user, temp


@transaction.atomic
def update_user(actor, target, *, full_name, role, request=None):
    """Sửa họ tên, vai trò. Admin không tự đổi vai trò; không hạ Admin cuối cùng."""
    target = User.objects.select_for_update().select_related("role").get(pk=target.pk)
    role_changed = role.pk != target.role_id
    if role_changed:
        if actor.pk == target.pk:
            raise AccountError(MSG_SELF)
        if target.role.code == RoleCode.ADMIN and _would_remove_last_admin(target):
            raise AccountError(MSG_LAST_ADMIN)
    changes = {"role": (target.role.code, role.code)} if role_changed else {}
    note = "Sửa tài khoản" + (", đổi họ tên" if full_name != target.full_name else "")
    target.full_name = full_name
    target.role = role
    target.save(update_fields=["full_name", "role"])
    log(AuditAction.UPDATE, user=actor, obj=target, changes=changes, request=request, note=note)
    return target


@transaction.atomic
def lock_user(actor, target, *, request=None):
    """Admin khóa vô thời hạn (is_active = False)."""
    target = User.objects.select_for_update().select_related("role").get(pk=target.pk)
    if actor.pk == target.pk:
        raise AccountError(MSG_SELF)
    if target.role.code == RoleCode.ADMIN and _would_remove_last_admin(target):
        raise AccountError(MSG_LAST_ADMIN)
    target.is_active = False
    target.save(update_fields=["is_active"])
    end_sessions(target)  # phiên cũ không được "sống lại" khi mở khóa
    log(AuditAction.ACCOUNT_LOCK, user=actor, obj=target, request=request, note="Admin khóa")
    return target


@transaction.atomic
def unlock_user(actor, target, *, request=None):
    """Mở khóa cả hai kiểu: bật is_active, xóa locked_until, đặt failed_login_count về 0."""
    target = User.objects.select_for_update().get(pk=target.pk)
    target.is_active = True
    target.locked_until = None
    target.failed_login_count = 0
    target.save(update_fields=["is_active", "locked_until", "failed_login_count"])
    log(AuditAction.ACCOUNT_UNLOCK, user=actor, obj=target, request=request, note="Admin mở khóa")
    return target


@transaction.atomic
def reset_password(actor, target, *, request=None):
    """Đặt mật khẩu tạm mới, buộc đổi ở lần đăng nhập sau. Trả mật khẩu tạm (hiện một lần)."""
    target = User.objects.select_for_update().get(pk=target.pk)
    temp = generate_temp_password()
    target.set_password(temp)
    target.must_change_password = True
    target.save(update_fields=["password", "must_change_password"])
    log(
        AuditAction.PASSWORD_RESET,
        user=actor,
        obj=target,
        request=request,
        note="Đặt lại mật khẩu tạm",
    )
    return temp


@transaction.atomic
def change_own_password(user, new_password, *, request=None):
    user.set_password(new_password)
    user.must_change_password = False
    user.save(update_fields=["password", "must_change_password"])
    log(AuditAction.UPDATE, user=user, obj=user, request=request, note="Đổi mật khẩu")


def lock_status(user, now=None):
    """Trạng thái hiển thị: ('ok'|'admin'|'temp', nhãn)."""
    now = now or timezone.now()
    if not user.is_active:
        return "admin", "Bị khóa (Admin khóa)"
    if user.locked_until and user.locked_until > now:
        return "temp", f"Khóa tạm đến {timezone.localtime(user.locked_until):%H:%M}"
    return "ok", "Đang hoạt động"


def get_role(code):
    return Role.objects.get(code=code)
