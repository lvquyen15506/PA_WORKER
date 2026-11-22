"""Model tài khoản. Tạm thời chỉ có User; Role và các trường khác thêm ở bước 3a."""

from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    pass
