# Ghim digest để build lại ra đúng image đã kiểm thử (docs/ra-soat-bao-mat.md mục 5).
# Đổi digest: docker pull python:3.12-slim rồi lấy RepoDigests, quét lại bằng Trivy.
FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PRIVATE_MEDIA_ROOT=/app/private_media \
    RUFF_CACHE_DIR=/tmp/ruff-cache \
    PYTEST_ADDOPTS="-p no:cacheprovider"

# Tesseract (tiếng Việt), zbar (đọc QR), antiword (đọc .doc) dùng từ Phase 5.
# fonts-dejavu-core: phông có dấu tiếng Việt cho ảnh/CV giả; libglib2.0-0: OpenCV cần.
# apt-get upgrade: lấy bản vá bảo mật Debian mới hơn image gốc (krb5, zlib…).
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-vie libzbar0 antiword fonts-dejavu-core libglib2.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Người dùng chạy ứng dụng (không chạy bằng root). UID cố định để volume giữ đúng chủ sở hữu.
RUN groupadd --gid 1000 app && useradd --uid 1000 --gid app --create-home app

WORKDIR /app

# Copy requirements trước để tận dụng cache lớp khi chỉ đổi mã nguồn.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Mã nguồn thuộc root (người dùng app chỉ đọc); chỉ thư mục dữ liệu thuộc app. Volume mới tạo
# lần đầu lấy chủ sở hữu từ thư mục trong image.
RUN chmod +x docker/entrypoint.sh \
    && mkdir -p /app/private_media /backups \
    && chown app:app /app/private_media /backups \
    && SECRET_KEY=chi-dung-luc-build \
       FIELD_ENCRYPTION_KEY=QUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUE= \
       HASH_KEY=QkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkI= \
       python manage.py collectstatic --noinput
# Hai khóa ở dòng trên chỉ để lệnh collectstatic lúc build qua kiểm tra khởi động; không dùng khi chạy.

USER app
EXPOSE 8000
# Gọi qua sh để không phụ thuộc quyền thực thi khi mã nguồn được mount từ Windows.
ENTRYPOINT ["sh", "docker/entrypoint.sh"]
# gthread: kết nối mở sẵn của trình duyệt không giữ chết worker tới hết timeout (worker sync bị treo).
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--worker-class", "gthread", "--threads", "4", "--timeout", "120"]
