"""Buộc đổi mật khẩu: người dùng có must_change_password bị chuyển tới /doi-mat-khau/
ở mọi URL khác (trừ đăng xuất và tệp tĩnh).

Tài khoản bị Admin khóa (is_active = False) tự bị đăng xuất ở request kế tiếp, vì backend
đăng nhập của Django không nạp người dùng không hoạt động.
"""

from django.shortcuts import redirect
from django.urls import reverse

ALLOWED_PATHS = ("/doi-mat-khau/", "/dang-xuat/", "/static/")


class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if (
            user.is_authenticated
            and user.must_change_password
            and not request.path.startswith(ALLOWED_PATHS)
        ):
            return redirect(reverse("change_password"))
        return self.get_response(request)
