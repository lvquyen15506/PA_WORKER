#!/bin/sh
# Khởi động web: kiểm tra định dạng khóa, migrate, kiểm tra khóa khớp dữ liệu,
# rồi chạy lệnh được truyền vào (mặc định Gunicorn).
# Không nạp dữ liệu mẫu ở đây: mật khẩu tạm sẽ lọt vào nhật ký của container.
set -e
# Container chạy bằng người dùng app (không phải root). Volume tạo từ bản cũ (chạy bằng root)
# cần đổi chủ sở hữu một lần; Cap nhat.bat làm việc này tự động.
if [ "$(id -u)" != "0" ] && [ ! -w "${PRIVATE_MEDIA_ROOT:-/app/private_media}" ]; then
    echo "LỖI: Thư mục dữ liệu ${PRIVATE_MEDIA_ROOT:-/app/private_media} không ghi được." >&2
    echo "Dữ liệu tạo từ phiên bản cũ cần đổi quyền một lần. Chạy tệp 'Cap nhat.bat'," >&2
    echo "hoặc lệnh: docker compose run --rm --no-deps -u root --entrypoint chown web -R app:app /app/private_media" >&2
    exit 1
fi
python manage.py check_keys --format
# Chỉ web (Gunicorn) migrate; scheduler tự kiểm tra khóa và chờ migration trong run_scheduler.
if [ "$1" = "gunicorn" ]; then
    python manage.py migrate --noinput
    python manage.py check_keys
fi
exec "$@"
