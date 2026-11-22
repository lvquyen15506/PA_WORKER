"""Tài khoản, vai trò, lịch sử đăng nhập (docs/thiet-ke/models.md mục 3.1)."""

from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.choices import RoleCode
from apps.core.models_base import AppendOnlyModel


class Role(models.Model):
    """4 dòng cố định, nạp bằng data migration; không có giao diện thêm/xóa."""

    code = models.CharField("Mã vai trò", max_length=20, choices=RoleCode.choices, unique=True)
    name = models.CharField("Tên vai trò", max_length=50)

    def __str__(self):
        return self.name


class User(AbstractUser):
    """Kế thừa AbstractUser. first_name, last_name, email, is_staff, is_superuser giữ nguyên
    nhưng không dùng. Trang admin Django không bật."""

    full_name = models.CharField("Họ tên", max_length=100)
    role = models.ForeignKey(Role, on_delete=models.PROTECT, verbose_name="Vai trò")
    # is_active = False: Admin khóa vô thời hạn (câu 28).
    must_change_password = models.BooleanField("Phải đổi mật khẩu", default=True)
    # Khóa tạm do sai mật khẩu: đếm lần sai liên tiếp, và thời điểm hết khóa.
    failed_login_count = models.PositiveSmallIntegerField("Số lần sai liên tiếp", default=0)
    locked_until = models.DateTimeField("Khóa tạm đến", null=True, blank=True)

    def __str__(self):
        return self.full_name or self.username

    @property
    def role_code(self):
        return self.role.code


class LoginHistory(AppendOnlyModel):
    user = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.PROTECT, verbose_name="Tài khoản"
    )
    username_attempted = models.CharField("Tên đăng nhập đã nhập", max_length=150)
    ip_address = models.GenericIPAddressField("Địa chỉ IP")
    success = models.BooleanField("Thành công")
    failure_reason = models.CharField("Lý do thất bại", max_length=100, blank=True)
    created_at = models.DateTimeField("Thời điểm", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
