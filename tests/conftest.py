"""Khóa cố định cho test; không bao giờ dùng khóa thật của .env."""

import base64

import pytest

TEST_FIELD_KEY = base64.urlsafe_b64encode(b"T" * 32).decode()
TEST_HASH_KEY = base64.urlsafe_b64encode(b"H" * 32).decode()


@pytest.fixture(autouse=True)
def khoa_test(settings, tmp_path):
    settings.FIELD_ENCRYPTION_KEY = TEST_FIELD_KEY
    settings.HASH_KEY = TEST_HASH_KEY
    settings.PRIVATE_MEDIA_ROOT = tmp_path / "private_media"
    # Băm nhanh chỉ trong test để chạy nhanh; cấu hình thật dùng PBKDF2 (có test riêng).
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    # Môi trường test là bản Demo (seed_demo được chạy); test chặn ở bản Thật tự đặt False.
    settings.DEMO_MODE = True
    # Sao lưu trong test ghi vào thư mục tạm; scheduler không tự sao lưu (test sao lưu bật riêng).
    settings.BACKUP_DIR = tmp_path / "backups"
    settings.BACKUP_AUTO = False
