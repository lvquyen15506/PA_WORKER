"""Kiểm tra một file sao lưu đọc được và nguyên vẹn (không thay đổi dữ liệu nào).

docker compose exec web python manage.py verify_backup /backups/pa-worker-....pawbk
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.backup import service
from apps.core.backup.stream import BackupError


class Command(BaseCommand):
    help = "Kiểm tra file sao lưu: giải mã, toàn vẹn, bản dump CSDL đọc được, tệp khớp manifest."

    def add_arguments(self, parser):
        parser.add_argument("file", help="Tên file trong thư mục backups hoặc đường dẫn đầy đủ.")

    def handle(self, *args, **options):
        path = resolve(options["file"])
        try:
            manifest = service.verify_backup(path)
        except BackupError as exc:
            raise CommandError(str(exc)) from exc
        rows = sum(manifest["tables"].values())
        self.stdout.write(self.style.SUCCESS(f"File sao lưu {path.name} đọc được và nguyên vẹn."))
        self.stdout.write(
            f"Tạo lúc {manifest['created_at']}, phiên bản {manifest['app_version']}, "
            f"{len(manifest['tables'])} bảng ({rows} dòng), {len(manifest['media'])} tệp."
        )


def resolve(name):
    """Tên file trong BACKUP_DIR, hoặc đường dẫn có sẵn."""
    path = Path(name)
    if not path.is_absolute() and not path.exists():
        path = Path(settings.BACKUP_DIR) / name
    if not path.is_file():
        raise CommandError(f"Không tìm thấy file sao lưu {name} trong thư mục backups.")
    return path
