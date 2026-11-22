"""Cấu hình PA Worker. Mọi giá trị bí mật đọc từ biến môi trường / tệp .env."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path):
    """Nạp tệp .env (KEY=VALUE) vào os.environ nếu biến chưa có sẵn.

    Docker Compose đã truyền biến qua env_file; hàm này phục vụ chạy trực tiếp
    (SQLite dự phòng, pytest ngoài Docker). Không ghi đè biến đã đặt.
    """
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_dotenv(BASE_DIR / ".env")


def _env(name, default=""):
    return os.environ.get(name, default)


def _env_list(name, default):
    return [item.strip() for item in _env(name, default).split(",") if item.strip()]


DEBUG = _env("DEBUG", "0") == "1"

SECRET_KEY = _env("SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "khoa-chi-dung-khi-phat-trien"
    else:
        from django.core.exceptions import ImproperlyConfigured

        raise ImproperlyConfigured(
            "Thiếu SECRET_KEY trong tệp .env. Chạy 'python scripts/make_env.py' để tạo tệp .env."
        )

ALLOWED_HOSTS = _env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")

# Khóa mã hóa trường nhạy cảm và khóa băm. Kiểm tra định dạng và khớp dữ liệu
# ở apps.core.keys (từ chối khởi động khi thiếu hoặc sai).
FIELD_ENCRYPTION_KEY = _env("FIELD_ENCRYPTION_KEY")
HASH_KEY = _env("HASH_KEY")
EXTERNAL_OCR_API_KEY = _env("EXTERNAL_OCR_API_KEY")

INSTALLED_APPS = [
    # Không bật django.contrib.admin: tránh đường sửa dữ liệu không qua nhật ký.
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.accounts",
    "apps.audit",
    "apps.workers",
    "apps.documents",
    "apps.intake",
    "apps.recruitment",
    "apps.employment",
    "apps.reports",
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# PostgreSQL khi có POSTGRES_HOST (Docker); SQLite chỉ để chạy thử không có Docker.
if _env("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _env("POSTGRES_DB", "pa_worker"),
            "USER": _env("POSTGRES_USER", "pa_worker"),
            "PASSWORD": _env("POSTGRES_PASSWORD"),
            "HOST": _env("POSTGRES_HOST"),
            "PORT": _env("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = []  # Bổ sung validator riêng (≥ 8 ký tự, có chữ và số) ở apps.accounts.

LANGUAGE_CODE = "vi"
TIME_ZONE = "Asia/Ho_Chi_Minh"
USE_I18N = True
USE_TZ = True
DATE_FORMAT = "d/m/Y"
DATETIME_FORMAT = "d/m/Y H:i"
SHORT_DATE_FORMAT = "d/m/Y"
SHORT_DATETIME_FORMAT = "d/m/Y H:i"
DATE_INPUT_FORMATS = ["%d/%m/%Y", "%Y-%m-%d"]

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Tệp tải lên: ngoài thư mục public, không có MEDIA_URL (chỉ tải qua view kiểm tra quyền).
PRIVATE_MEDIA_ROOT = Path(_env("PRIVATE_MEDIA_ROOT", str(BASE_DIR / "private_media")))
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

# Đăng nhập, phiên (ngưỡng cố định theo yêu cầu).
LOGIN_URL = "/dang-nhap/"
LOGIN_REDIRECT_URL = "/"
SESSION_COOKIE_AGE = 30 * 60  # tự đăng xuất sau 30 phút không thao tác
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
LOGIN_FAIL_LIMIT = 5
LOGIN_LOCK_MINUTES = 15

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
