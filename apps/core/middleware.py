"""Middleware bảo mật dùng chung (docs/ra-soat-bao-mat.md mục 11, 12).

- `RequestSizeLimitMiddleware`: mỗi tệp tối đa 10 MB và được kiểm tra trong form, nhưng Django
  vẫn ghi toàn bộ request ra thư mục tạm trước khi form chạy. Từ chối sớm request có
  Content-Length vượt `MAX_REQUEST_BYTES` (một lượt nhập CCCD có tối đa 3 tệp 10 MB) với trang
  413 tiếng Việt.
- `ContentSecurityPolicyMiddleware`: CSP cho mọi trang; chỉ chạy script, CSS, phông, ảnh từ
  chính máy chủ (thư viện nằm trong static/vendor/). Không có script hay style nội tuyến.
"""

from django.conf import settings
from django.shortcuts import render

# Không nới chính sách này: trang nào lỗi CSP thì sửa trang đó (bỏ script/style nội tuyến).
# img-src có data: vì CSS của Bootstrap vẽ mũi tên ô chọn, ô tích bằng ảnh SVG data:.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "frame-src 'none'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
    ]
)


class ContentSecurityPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Giữ CSP riêng của view (ví dụ "sandbox" khi xem tài liệu, ảnh phiên nhận diện).
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        return response


class RequestSizeLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            length = int(request.META.get("CONTENT_LENGTH") or 0)
        except ValueError:
            length = 0
        if length > settings.MAX_REQUEST_BYTES:
            return render(request, "413.html", status=413)
        return self.get_response(request)
