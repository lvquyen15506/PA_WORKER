# Chạy thử bằng SQLite (không cần Docker)

Chỉ để chạy thử nhanh trên máy chưa có Docker. Bản chạy thật dùng Docker + PostgreSQL (xem `docs/chay-dev.md`). Hướng dẫn đầy đủ cho người không chuyên IT làm ở Phase 8.

**Giới hạn của bản SQLite:** không có trigger chặn sửa/xóa nhật ký ở CSDL (vẫn chặn ở tầng ứng dụng), không có khóa chống chạy chồng của tác vụ định kỳ, và **không chạy `pytest` trên SQLite** (toàn bộ test bắt buộc dùng PostgreSQL).

## Trình tự bắt buộc

Cần Python 3.12. Chạy trong thư mục dự án:

```
python -m venv .venv
.venv\Scripts\activate            (macOS: source .venv/bin/activate)
pip install -r requirements.txt

python scripts/make_env.py        (tạo .env có khóa mã hóa; không ghi đè .env đã có)
```

Mở `.env`, **xóa dòng `POSTGRES_HOST=db`** (hoặc để trống giá trị). Không có `POSTGRES_HOST` thì ứng dụng dùng SQLite, tệp dữ liệu là `db.sqlite3`.

```
python manage.py migrate
python manage.py check_keys       (BẮT BUỘC trước runserver)
python manage.py collectstatic --noinput
python manage.py seed_demo        (tùy chọn: dữ liệu mẫu; in mật khẩu tạm MỘT lần)
python manage.py runserver
```

Mở `http://localhost:8000/dang-nhap/`.

## Vì sao phải chạy `check_keys` trước `runserver`

Docker tự chạy `check_keys` mỗi lần khởi động. `runserver` thì không, nên bản SQLite phải chạy tay: lệnh ghi giá trị kiểm tra khóa ở lần đầu và từ chối nếu `FIELD_ENCRYPTION_KEY` hoặc `HASH_KEY` không khớp dữ liệu đã có (sai khóa làm số CCCD không đọc được hoặc kiểm tra trùng sai). Hãy cất bản sao hai khóa ở nơi riêng; mất khóa là mất dữ liệu đã mã hóa.

## Vì sao có `collectstatic`

Với `DEBUG=0` (mặc định), tệp giao diện (Bootstrap...) được phục vụ từ thư mục `staticfiles/` do `collectstatic` tạo. Thiếu bước này trang hiện không có kiểu dáng.

## Chạy với tệp môi trường khác

Đặt biến `ENV_FILE` trỏ tới tệp khác `.env`, và `SQLITE_PATH` để đổi vị trí tệp dữ liệu, ví dụ để thử mà không đụng `.env` chính.
