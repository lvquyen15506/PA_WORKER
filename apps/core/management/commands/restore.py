"""Phục hồi CSDL và tệp hồ sơ từ một file sao lưu (kịch bản nghiệm thu 17).

    docker compose stop web scheduler
    docker compose run --rm web python manage.py restore pa-worker-....pawbk --yes
    docker compose up -d                                   (Phuc hoi.bat làm cả ba bước)

- Kiểm tra toàn bộ file trước khi đụng vào dữ liệu; sai khóa, file hỏng hay bản sao lưu của phiên
  bản mới hơn đều bị từ chối, dữ liệu đang có giữ nguyên.
- Nếu đang có dữ liệu, tự sao lưu dữ liệu đó trước (file pa-worker-truoc-phuc-hoi-....pawbk).
- Cần đúng FIELD_ENCRYPTION_KEY và HASH_KEY đã cất khi cài trong tệp .env.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.core.backup import service
from apps.core.backup.stream import BackupError

from .verify_backup import resolve


class Command(BaseCommand):
    help = "Phục hồi dữ liệu từ file sao lưu (thay toàn bộ dữ liệu đang có)."

    def add_arguments(self, parser):
        parser.add_argument("file", help="Tên file trong thư mục backups hoặc đường dẫn đầy đủ.")
        parser.add_argument(
            "--yes", action="store_true", help="Xác nhận thay toàn bộ dữ liệu đang có."
        )
        parser.add_argument(
            "--no-safety-backup",
            action="store_true",
            help="Không sao lưu dữ liệu đang có trước khi phục hồi.",
        )

    def handle(self, *args, **options):
        path = resolve(options["file"])
        if not options["yes"]:
            raise CommandError(
                "Phục hồi sẽ THAY TOÀN BỘ dữ liệu đang có bằng dữ liệu trong file sao lưu. "
                "Chạy lại kèm --yes để xác nhận (Phuc hoi.bat hỏi xác nhận trước khi chạy)."
            )
        try:
            manifest = service.restore_backup(
                path, safety_backup=not options["no_safety_backup"], stdout=self.stdout
            )
        except BackupError as exc:
            raise CommandError(str(exc)) from exc
        rows = sum(manifest["tables"].values())
        self.stdout.write(self.style.SUCCESS(f"Đã phục hồi từ {path.name}."))
        self.stdout.write(
            f"Bản sao lưu tạo lúc {manifest['created_at']}: {rows} dòng dữ liệu, "
            f"{len(manifest['media'])} tệp; số dòng và tệp đã đối chiếu khớp, khóa khớp."
        )
