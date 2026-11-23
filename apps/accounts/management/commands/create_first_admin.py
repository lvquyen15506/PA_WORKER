"""Tạo tài khoản Admin đầu tiên của bản cài Thật (không qua seed_demo).

    docker compose exec web python manage.py create_first_admin
        [--username admin] [--full-name "Họ tên"]

- Chỉ chạy khi hệ thống chưa có Admin nào đang hoạt động (không dùng lệnh này để thêm Admin;
  Admin thêm tài khoản ở trang Tài khoản).
- Mật khẩu tạm sinh ngẫu nhiên, in ra màn hình MỘT lần, không ghi vào tệp nào; đăng nhập lần đầu
  phải đổi mật khẩu.
- Ghi nhật ký "Tạo tài khoản" với người thực hiện là Hệ thống.
"""

from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.accounts import services
from apps.accounts.models import User
from apps.core.choices import RoleCode


class Command(BaseCommand):
    help = "Tạo tài khoản Admin đầu tiên (bản cài Thật). Mật khẩu tạm in ra màn hình một lần."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="admin", help="Tên đăng nhập (mặc định admin).")
        parser.add_argument(
            "--full-name", default="Quản trị hệ thống", help="Họ tên hiển thị của tài khoản."
        )

    def handle(self, *args, **options):
        username = options["username"].strip()
        full_name = options["full_name"].strip() or "Quản trị hệ thống"
        if User.objects.filter(role__code=RoleCode.ADMIN, is_active=True).exists():
            raise CommandError(
                "Hệ thống đã có tài khoản Admin đang hoạt động; lệnh này chỉ dùng khi cài mới. "
                "Quên mật khẩu Admin thì dùng lệnh: python manage.py reset_admin_password"
            )
        try:
            UnicodeUsernameValidator()(username)
        except ValidationError as exc:
            raise CommandError(
                "Tên đăng nhập chỉ gồm chữ, số và các ký tự @ . + - _ (không có dấu cách)."
            ) from exc
        if not 3 <= len(username) <= 30:
            raise CommandError("Tên đăng nhập dài từ 3 đến 30 ký tự.")
        if User.objects.filter(username__iexact=username).exists():
            raise CommandError(
                f"Tên đăng nhập {username} đã có; hãy chọn tên khác bằng --username."
            )

        user, temp = services.create_user(
            None, username=username, full_name=full_name, role=services.get_role(RoleCode.ADMIN)
        )
        self.stdout.write(self.style.SUCCESS(f"Đã tạo tài khoản Admin: {user.username}"))
        self.stdout.write(f"Mật khẩu tạm (chỉ hiện một lần): {temp}")
        self.stdout.write(
            "Ghi lại mật khẩu tạm rồi đăng nhập; hệ thống sẽ yêu cầu đổi mật khẩu ngay lần đầu."
        )
