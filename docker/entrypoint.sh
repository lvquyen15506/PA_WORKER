#!/bin/sh
# Khởi động web: migrate rồi chạy lệnh được truyền vào (mặc định Gunicorn).
# Bước kiểm tra khóa mã hóa (check_keys) thêm ở bước 2.
set -e
python manage.py migrate --noinput
exec "$@"
