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


# ENV_FILE cho phép trỏ tới tệp môi trường khác (ví dụ bản chạy thử SQLite) thay vì .env.
_load_dotenv(Path(os.environ.get("ENV_FILE") or BASE_DIR / ".env"))


def _env(name, default=""):
    return os.environ.get(name, default)


def _env_list(name, default):
    return [item.strip() for item in _env(name, default).split(",") if item.strip()]


APP_VERSION = "1.1.0"

DEBUG = _env("DEBUG", "0") == "1"
# Bản Demo (dữ liệu giả lập, nghiệm thu, trình diễn) hay bản Thật (dữ liệu của doanh nghiệp).
# Chỉ bản Demo được chạy seed_demo (docs/lam-ro-yeu-cau.md câu 49).
DEMO_MODE = _env("DEMO_MODE", "0") == "1"
# Chỉ bật khi đã có reverse proxy cấp HTTPS phía trước (docs/ra-soat-bao-mat.md mục 10).
HTTPS = _env("HTTPS", "0") == "1"

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
    "apps.core.middleware.RequestSizeLimitMiddleware",
    "apps.core.middleware.ContentSecurityPolicyMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.ForcePasswordChangeMiddleware",
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
                "apps.core.context_processors.navigation",
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
            "NAME": _env("SQLITE_PATH") or BASE_DIR / "db.sqlite3",
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Mật khẩu: tối thiểu 8 ký tự, có chữ và số.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "apps.accounts.validators.MinLengthValidator"},
    {"NAME": "apps.accounts.validators.LetterAndDigitValidator"},
]

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
# Tổng một request: 3 tệp 10 MB (ảnh mặt trước, mặt sau, CV) + phần dư cho trường form.
MAX_REQUEST_BYTES = 35 * 1024 * 1024

# Nhận diện CCCD/CV (Phase 5). Gunicorn timeout 120 giây nên toàn bộ một lượt nhận diện chỉ được
# dùng tối đa 90 giây (mỗi giai đoạn lấy phần còn lại); hết thì trường chưa đọc để trống, tô vàng.
INTAKE_TOTAL_BUDGET_SECONDS = 90
OCR_TIMEOUT_SECONDS = 30  # tối đa cho một lần gọi Tesseract (còn bị giới hạn bởi ngân sách)
ANTIWORD_TIMEOUT_SECONDS = 20
MAX_IMAGE_PIXELS = 40_000_000  # ảnh lớn hơn bị từ chối trước khi giải nén
CV_MAX_TEXT_PAGES = 10  # PDF: số trang tối đa đọc lớp chữ
CV_MAX_OCR_PAGES = 3  # PDF scan / ảnh: số trang tối đa vẽ ra để OCR
CV_MAX_DPI = 300

# Đăng nhập, phiên (ngưỡng cố định theo yêu cầu).
LOGIN_URL = "/dang-nhap/"
LOGIN_REDIRECT_URL = "/"
# apps.accounts.services.end_sessions() đọc bảng Session nên phụ thuộc backend CSDL này.
# Đổi SESSION_ENGINE thì phải sửa end_sessions() (nếu không, khóa tài khoản và đặt lại
# mật khẩu sẽ không còn hủy được phiên đang đăng nhập).
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = 30 * 60  # tự đăng xuất sau 30 phút không thao tác
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
LOGIN_FAIL_LIMIT = 5
LOGIN_LOCK_MINUTES = 15

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
# CSRF_COOKIE_HTTPONLY giữ False: static/js/pa.js đọc cookie csrftoken để gửi kèm request htmx.

# HTTPS (tắt mặc định): bản bàn giao chạy HTTP trong mạng nội bộ. Bật HTTPS=1 khi đặt reverse
# proxy (Caddy/Nginx) cấp HTTPS phía trước; proxy phải gửi X-Forwarded-Proto.
if HTTPS:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = 31_536_000
    CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS]
    # Chuyển hướng HTTP -> HTTPS do reverse proxy làm. Bật ở Django thì healthcheck nội bộ
    # (http://localhost:8000) bị chuyển hướng và container bị coi là hỏng.
    # HSTS cho tên miền con và danh sách preload chỉ dành cho tên miền công khai; máy chủ trong
    # LAN truy cập bằng IP hoặc tên máy nội bộ, không có tên miền con.
    SILENCED_SYSTEM_CHECKS = ["security.W008", "security.W005", "security.W021"]

# Log ra stdout của container (docker compose logs). Che dãy số dài (apps/core/log_format.py);
# Gunicorn không bật access log vì URL có thể chứa chữ tìm kiếm (?q=).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "pa": {
            "()": "apps.core.log_format.RedactingFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s: %(message)s",
        },
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "pa"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        # runserver (bản SQLite) ghi dòng request kèm chuỗi truy vấn: chỉ ghi khi có lỗi.
        "django.server": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
