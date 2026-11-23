"""Kiểm tra nhanh tình trạng hệ thống (Kiem tra.bat, docs/xu-ly-su-co.md).

    docker compose exec web python manage.py system_check

In: phiên bản, chế độ cài, khóa có khớp dữ liệu, migration, dung lượng đĩa còn trống, bản sao lưu
mới nhất. Có vấn đề thì in CẢNH BÁO và trả mã lỗi 1.
"""

import sys

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from apps.core import keys
from apps.core.backup import service


class Command(BaseCommand):
    help = "Kiểm tra khóa, migration, dung lượng đĩa và bản sao lưu mới nhất."

    def handle(self, *args, **options):
        problems = []
        out = self.stdout.write
        out(f"PA Worker phiên bản {settings.APP_VERSION}")
        out("Chế độ cài: " + ("Demo (dữ liệu giả lập)" if settings.DEMO_MODE else "Thật"))

        try:
            keys.check_format()
            keys.check_against_database()
            out("Khóa mã hóa: khớp với dữ liệu.")
        except keys.KeyConfigError as exc:
            problems.append(str(exc))

        executor = MigrationExecutor(connection)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            problems.append("Còn cập nhật CSDL (migration) chưa áp dụng; khởi động lại web.")
        else:
            out("CSDL: đã cập nhật đủ.")

        for label, path, free, total in service.disk_status():
            out(f"{label} ({path}): còn trống {service.human(free)} / {service.human(total)}")
            if free < settings.DISK_WARNING_BYTES:
                problems.append(
                    f"{label} còn dưới {service.human(settings.DISK_WARNING_BYTES)}. Xóa bớt bản "
                    "sao lưu cũ hoặc giải phóng dung lượng (xem Xử lý sự cố, mục Đầy đĩa)."
                )

        latest = service.latest_backup()
        if latest is None:
            problems.append("Chưa có bản sao lưu nào. Chạy Sao luu.bat.")
        else:
            age_hours = (timezone.now().timestamp() - latest.stat().st_mtime) / 3600
            out(
                f"Bản sao lưu mới nhất: {latest.name} ({service.human(latest.stat().st_size)}, "
                f"cách đây {age_hours:.0f} giờ)"
            )
            if age_hours > 48:
                problems.append("Bản sao lưu mới nhất đã quá 2 ngày. Chạy Sao luu.bat.")

        if problems:
            for text in problems:
                out(self.style.WARNING("CẢNH BÁO: " + text))
            sys.exit(1)
        out(self.style.SUCCESS("Hệ thống hoạt động bình thường."))
