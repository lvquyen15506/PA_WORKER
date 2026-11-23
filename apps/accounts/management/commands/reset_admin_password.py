"""Đặt lại mật khẩu tạm cho tài khoản Admin khi quên mật khẩu (docs/xu-ly-su-co.md).

    docker compose exec web python manage.py reset_admin_password [tên đăng nhập]

- Chỉ dùng cho tài khoản vai trò Admin; tài khoản khác do Admin đặt lại ở trang Tài khoản.
- Không ghi tên đăng nhập: nếu hệ thống chỉ có một Admin thì dùng tài khoản đó, nếu có nhiều thì
  liệt kê tên đăng nhập để chọn.
- Mở khóa tài khoản (cả khóa do Admin và khóa tạm do nhập sai), đặt mật khẩu tạm mới (in ra màn
  hình một lần, buộc đổi khi đăng nhập), hủy các phiên đang đăng nhập. Ghi nhật ký "Mở khóa tài
  khoản" và "Đặt lại mật khẩu" với người thực hiện là Hệ thống.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts import services
from apps.accounts.models import User
from apps.core.choices import RoleCode


class Command(BaseCommand):
    help = "Đặt lại mật khẩu tạm và mở khóa một tài khoản Admin (khi quên mật khẩu Admin)."

    def add_arguments(self, parser):
        parser.add_argument("username", nargs="?", help="Tên đăng nhập của Admin.")

    def handle(self, *args, **options):
        admins = User.objects.filter(role__code=RoleCode.ADMIN).order_by("username")
        username = (options.get("username") or "").strip()
        if not username:
            names = list(admins.values_list("username", flat=True))
            if not names:
                raise CommandError(
                    "Hệ thống chưa có tài khoản Admin. Tạo bằng lệnh: "
                    "python manage.py create_first_admin"
                )
            if len(names) > 1:
                raise CommandError(
                    "Hệ thống có nhiều Admin: "
                    + ", ".join(names)
                    + ". Ghi rõ tên đăng nhập, ví dụ: python manage.py reset_admin_password "
                    + names[0]
                )
            username = names[0]
        target = admins.filter(username=username).first()
        if target is None:
            raise CommandError(
                f"Không có tài khoản Admin tên {username}. Lệnh này chỉ dùng cho Admin; "
                "tài khoản khác do Admin đặt lại mật khẩu ở trang Tài khoản."
            )
        with transaction.atomic():
            if not target.is_active or target.locked_until or target.failed_login_count:
                services.unlock_user(None, target)
            temp = services.reset_password(None, target)
        self.stdout.write(self.style.SUCCESS(f"Đã đặt lại mật khẩu cho Admin: {target.username}"))
        self.stdout.write(f"Mật khẩu tạm (chỉ hiện một lần): {temp}")
        self.stdout.write("Đăng nhập bằng mật khẩu tạm; hệ thống sẽ yêu cầu đổi mật khẩu ngay.")
