# Chạy khi phát triển và khi nghiệm thu

## Phát triển (có `docker-compose.dev.yml`)

```
python scripts/make_env.py            # một lần, không ghi đè .env đã có
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
docker compose exec web pytest        # sửa code xong chạy ngay, không build lại image
docker compose exec web ruff check .
```

Tệp dev mount mã nguồn vào `web` (`.:/app`, trừ `staticfiles`) và chạy gunicorn `--reload`.
Đổi `requirements.txt` hoặc `Dockerfile` thì phải chạy lại lệnh `up -d --build` ở trên.
`scheduler` không được mount nên vẫn chạy mã trong image.
Từ Phase 8 tệp này **không** còn tên `docker-compose.override.yml`, nên `docker compose up` không tự đọc nó (bản bàn giao không chạy nhầm chế độ dev).

Container chạy bằng người dùng `app`: thư mục mã nguồn mount từ Windows cho sửa tệp có sẵn nhưng **không cho tạo tệp mới**. Lệnh tạo tệp trong mã nguồn chạy bằng root, ví dụ:

```
docker compose exec -u root web python manage.py makemigrations audit -n ten_migration
```

Sau khi sửa tệp trong `static/` phải dựng lại kèm `-V` (bỏ volume `staticfiles` cũ):
`docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build -V`.

## Nghiệm thu và cài thật

Kịch bản nghiệm thu 1 (cài mới) chạy bằng file compose gốc, trên volume sạch:

```
docker compose down -v
docker compose up -d --build
```

Container chạy bằng người dùng `app` (UID 1000). Volume `media` tạo từ bản trước Phase 8 (chạy bằng root) cần đổi quyền một lần: `Cap nhat.bat` làm tự động, hoặc chạy `docker compose run --rm --no-deps -u root --entrypoint chown web -R app:app /app/private_media`.

## Dữ liệu mẫu

`seed_demo` không chạy lúc khởi động container; chỉ chạy tay để mật khẩu tạm không nằm trong `docker compose logs`:

```
docker compose exec web python manage.py seed_demo
```

## Chạy thử bằng SQLite (không Docker)

Xem `docs/chay-sqlite.md` (trình tự: `make_env.py`, `migrate`, `check_keys` bắt buộc trước `runserver`, `collectstatic`, `seed_demo`, `runserver`).
