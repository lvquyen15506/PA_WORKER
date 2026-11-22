#!/bin/sh
# Khởi động web: kiểm tra định dạng khóa, migrate, rồi chạy lệnh được truyền vào (mặc định Gunicorn).
# Kiểm tra khóa khớp dữ liệu (check_keys đầy đủ) thêm sau migrate ở bước 3a.
# Không nạp dữ liệu mẫu ở đây: mật khẩu tạm sẽ lọt vào nhật ký của container.
set -e
python manage.py check_keys --format
python manage.py migrate --noinput
exec "$@"
