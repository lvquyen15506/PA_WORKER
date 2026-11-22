FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PRIVATE_MEDIA_ROOT=/app/private_media

# Tesseract (tiếng Việt), zbar (đọc QR), antiword (đọc .doc) dùng từ Phase 5.
# fonts-dejavu-core: phông có dấu tiếng Việt cho ảnh/CV giả; libglib2.0-0: OpenCV cần.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-vie libzbar0 antiword fonts-dejavu-core libglib2.0-0 \
    && apt-get clean

WORKDIR /app

# Copy requirements trước để tận dụng cache lớp khi chỉ đổi mã nguồn.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x docker/entrypoint.sh \
    && mkdir -p /app/private_media \
    && SECRET_KEY=chi-dung-luc-build \
       FIELD_ENCRYPTION_KEY=QUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUE= \
       HASH_KEY=QkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkI= \
       python manage.py collectstatic --noinput
# Hai khóa ở dòng trên chỉ để lệnh collectstatic lúc build qua kiểm tra khởi động; không dùng khi chạy.

EXPOSE 8000
# Gọi qua sh để không phụ thuộc quyền thực thi khi mã nguồn được mount từ Windows.
ENTRYPOINT ["sh", "docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
