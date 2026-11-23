# PA Worker – Phần mềm quản lý hồ sơ công nhân

Phiên bản **1.1.0** · Đơn vị phát triển: **QQIT** · Bản quyền mã nguồn thuộc QQIT.

Web app quản lý hồ sơ công nhân cho doanh nghiệp sản xuất và cung ứng lao động: hồ sơ và tài liệu, nhập nhanh từ ảnh CCCD (đọc QR, OCR) và CV, quy trình duyệt hai bước, tuyển dụng, quá trình làm việc, hợp đồng, đợt làm việc tại công ty khách hàng và lịch sử lương, Dashboard, báo cáo, xuất/nhập Excel, nhật ký thao tác, bảo vệ dữ liệu cá nhân (mã hóa, che số CCCD, thời hạn lưu trữ, ẩn danh hóa).

Chạy cục bộ trên một máy Windows bằng Docker Desktop; các máy trong mạng nội bộ dùng trình duyệt. Mọi chức năng chạy **không cần Internet**.

## Chạy nhanh (Windows)

1. Cài Docker Desktop (bật WSL 2).
2. Giải nén PA Worker vào một thư mục, ví dụ `C:\PA Worker`.
3. Bấm đúp **`PA Worker.bat`**, chọn **Bản Thật** hoặc **Bản Demo**, làm theo hướng dẫn trên cửa sổ.
4. **Cất tệp `.env` (khóa mã hóa) vào USB riêng.** Mất khóa là mất dữ liệu đã mã hóa và không phục hồi được bản sao lưu.

Chi tiết: [docs/huong-dan-cai-dat.md](docs/huong-dan-cai-dat.md).

## Tài liệu

| Tài liệu | Nội dung |
| --- | --- |
| [Hướng dẫn cài đặt](docs/huong-dan-cai-dat.md) | Cài Docker Desktop, cài PA Worker, cất khóa, mạng nội bộ, sao lưu, phục hồi, cập nhật |
| [Hướng dẫn sử dụng](docs/huong-dan-su-dung.md) | Theo vai trò: Admin, Quản lý nhân sự, Nhân viên HR, Viewer |
| [Xử lý sự cố](docs/xu-ly-su-co.md) | Quên mật khẩu Admin, mất khóa, Docker không chạy, đầy đĩa… |
| [Danh sách bàn giao](docs/ban-giao.md) | Những gì được bàn giao, giới hạn đã biết, điểm cần khách xác nhận |
| [Kết quả nghiệm thu](docs/nghiem-thu.md) | 17 kịch bản ở mục X của yêu cầu và kịch bản v1.1 |
| [Rà soát bảo mật](docs/ra-soat-bao-mat.md) | Kết quả rà soát, quét lỗ hổng, giới hạn đã biết |
| [Kịch bản trình diễn 10 phút](docs/kich-ban-demo.md) | Trình diễn trước hội đồng |
| [Yêu cầu](docs/yeu-cau.md), [Làm rõ yêu cầu](docs/lam-ro-yeu-cau.md), [Thiết kế](docs/thiet-ke/) | Tài liệu yêu cầu đã duyệt và thiết kế |

## Công nghệ

Python 3.12, Django 5.2 LTS, Gunicorn, PostgreSQL 16, Bootstrap 5, HTMX, Chart.js (để trong `static/vendor/`, không dùng CDN), Tesseract (tiếng Việt), OpenCV, zxing-cpp, pyzbar, pdfplumber, python-docx, openpyxl, cryptography. Đóng gói bằng Docker Compose (ba container: `web`, `scheduler`, `db`).

## Cho người phát triển

```
python scripts/make_env.py --mode demo                       # tạo .env (một lần)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
docker compose exec web python manage.py seed_demo           # dữ liệu giả lập (chỉ bản Demo)
docker compose exec web pytest
docker compose exec web ruff check .
```

Xem thêm [docs/chay-dev.md](docs/chay-dev.md) và `CLAUDE.md`. Không commit tệp `.env`; dữ liệu mẫu và test chỉ dùng số CCCD giả bắt đầu bằng `999`.
