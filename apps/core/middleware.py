"""Giới hạn tổng kích thước request (docs/ra-soat-bao-mat.md mục 11).

Mỗi tệp tối đa 10 MB và được kiểm tra trong form, nhưng Django vẫn ghi toàn bộ request ra thư
mục tạm trước khi form chạy. Middleware từ chối sớm request có Content-Length vượt
`MAX_REQUEST_BYTES` (một lượt nhập CCCD có tối đa 3 tệp 10 MB) với trang 413 tiếng Việt.
"""

from django.conf import settings
from django.shortcuts import render


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
