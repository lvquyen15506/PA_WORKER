import sys

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    verbose_name = "Lõi dùng chung"

    def ready(self):
        # Thiếu hoặc sai định dạng khóa: mọi tiến trình (web, scheduler, runserver, test)
        # từ chối khởi động với thông báo tiếng Việt.
        from .keys import KeyConfigError, check_format

        try:
            check_format()
        except KeyConfigError as exc:
            sys.stderr.write(f"\nLỖI KHÓA MÃ HÓA: {exc}\n\n")
            sys.exit(1)
