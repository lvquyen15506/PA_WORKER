"""Phân quyền theo vai trò, kiểm tra ở máy chủ cho mọi view.

Chưa đăng nhập -> chuyển tới /dang-nhap/. Đã đăng nhập nhưng không đủ quyền -> 403.
"""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from apps.core.choices import RoleCode


def role_required(*codes):
    allowed = {str(c.value if hasattr(c, "value") else c) for c in codes}

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if user.role.code not in allowed:
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


ALL_ROLES = tuple(RoleCode.values)
