from django.http import HttpResponse


def login_stub(request):
    """Trang tạm cho healthcheck; thay bằng trang đăng nhập thật ở bước 5."""
    return HttpResponse("PA Worker – đăng nhập", content_type="text/html; charset=utf-8")
