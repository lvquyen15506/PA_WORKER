#!/bin/sh
# Khởi động web: kiểm tra định dạng khóa, migrate, kiểm tra khóa khớp dữ liệu,
# rồi chạy lệnh được truyền vào (mặc định Gunicorn).
# Không nạp dữ liệu mẫu ở đây: mật khẩu tạm sẽ lọt vào nhật ký của container.
set -e
python manage.py check_keys --format
python manage.py migrate --noinput
python manage.py check_keys
exec "$@"
