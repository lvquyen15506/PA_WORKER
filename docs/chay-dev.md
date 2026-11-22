# Chạy khi phát triển và khi nghiệm thu

## Phát triển (có `docker-compose.override.yml`)

```
python scripts/make_env.py            # một lần, không ghi đè .env đã có
docker compose up -d --build          # tự đọc docker-compose.override.yml
docker compose exec web pytest        # sửa code xong chạy ngay, không build lại image
docker compose exec web ruff check .
```

Override mount mã nguồn vào `web` (`.:/app`, trừ `staticfiles`) và chạy gunicorn `--reload`.
Đổi `requirements.txt` hoặc `Dockerfile` thì vẫn phải `docker compose up -d --build`.
`scheduler` không được mount nên vẫn chạy mã trong image.

## Nghiệm thu và cài thật (KHÔNG có override)

Kịch bản nghiệm thu 1 (cài mới) bắt buộc chạy bằng file compose gốc, trên volume sạch:

```
docker compose -f docker-compose.yml down -v
docker compose -f docker-compose.yml up -d --build
```

Cờ `-f docker-compose.yml` làm Compose bỏ qua override, nên chạy đúng mã đã đóng vào image.

## Dữ liệu mẫu

`seed_demo` không chạy lúc khởi động container; chỉ chạy tay để mật khẩu tạm không nằm trong `docker compose logs`:

```
docker compose exec web python manage.py seed_demo
```

## Chạy thử bằng SQLite (không Docker)

Xem `docs/chay-sqlite.md` (trình tự: `make_env.py`, `migrate`, `check_keys` bắt buộc trước `runserver`, `collectstatic`, `seed_demo`, `runserver`).
