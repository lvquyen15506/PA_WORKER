"""Sao lưu CSDL và tệp hồ sơ ra một file mã hóa có ngày giờ (kịch bản nghiệm thu 17).

    docker compose exec web python manage.py backup        (Sao luu.bat gọi lệnh này)

File ghi vào thư mục backups (cạnh docker-compose.yml), tự kiểm tra đọc lại được, giữ BACKUP_KEEP
bản mới nhất. File không chứa khóa; phục hồi cần đúng khóa đã cất riêng.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.core.backup import service
from apps.core.backup.stream import BackupError


class Command(BaseCommand):
    help = "Sao lưu CSDL và tệp hồ sơ ra file mã hóa trong thư mục backups."

    def add_arguments(self, parser):
        parser.add_argument("--dest", help="Thư mục lưu (mặc định BACKUP_DIR).")
        parser.add_argument("--no-prune", action="store_true", help="Không xóa bản cũ.")

    def handle(self, *args, **options):
        self.stdout.write("Đang sao lưu…")
        try:
            result = service.create_backup(options.get("dest"), prune=not options["no_prune"])
        except BackupError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Đã sao lưu: {result['path'].name}"))
        self.stdout.write(
            f"Dung lượng {service.human(result['bytes'])}, {result['files']} tệp hồ sơ; "
            "đã tự kiểm tra: đọc lại được, khớp nội dung."
        )
        if result["removed"]:
            self.stdout.write(f"Đã xóa {len(result['removed'])} bản sao lưu cũ.")
        self.stdout.write("")
        self.stdout.write(self.style.WARNING("LƯU Ý: " + service.REMINDER))
