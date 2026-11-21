# PA Worker – Phần mềm quản lý hồ sơ công nhân

Web app quản lý hồ sơ công nhân cho doanh nghiệp sản xuất. Đơn vị phát triển: QQIT. Phiên bản mục tiêu: 1.0.

## Nguồn sự thật

- `docs/yeu-cau.md`: tài liệu yêu cầu **đã được khách hàng duyệt**. Mọi chức năng, trường dữ liệu, trạng thái, phân quyền và tiêu chí nghiệm thu lấy từ đây. Không tự thêm chức năng ngoài tài liệu; thấy chỗ mâu thuẫn hoặc chưa rõ thì **hỏi lại**, không đoán.
- `docs/phases.md`: kế hoạch từng phase và điều kiện "xong".
- `docs/tien-do.md`: nhật ký tiến độ. Cập nhật cuối mỗi phase (làm gì, còn gì, quyết định nào đã chốt).
- Giao diện: **luôn dùng skill `pa-ui`** (`.claude/skills/pa-ui/SKILL.md`) khi tạo hoặc sửa bất kỳ template, CSS, trang, form, bảng, nút nào.

## Cách làm việc

1. Chỉ làm **một phase** mỗi lần, đúng phạm vi ghi trong `docs/phases.md`.
2. Bắt đầu phase bằng kế hoạch ngắn (file sẽ tạo/sửa, cách kiểm tra), chờ duyệt rồi mới code.
3. Kết thúc phase: chạy test, chạy lint, chụp màn hình các trang mới (skill `webapp-testing`), cập nhật `docs/tien-do.md`, rồi **dừng lại báo cáo**. Không tự sang phase sau.
4. Không báo "xong" khi test còn lỗi hoặc chức năng chưa chạy thật trên Docker.
5. Commit sau mỗi phần hoàn chỉnh, thông điệp tiếng Việt, ngắn gọn.

## Công nghệ (đã chốt, không đổi nếu chưa được duyệt)

- Python 3.12, Django 5.2 LTS, Gunicorn
- PostgreSQL 16 (trong Docker); SQLite chỉ dùng khi chạy thử không có Docker
- Django templates + Bootstrap 5 + Bootstrap Icons + HTMX + Chart.js — **tất cả để trong `static/vendor/`, không dùng CDN** (hệ thống phải chạy offline)
- QR: OpenCV + pyzbar. OCR: Tesseract (gói `vie`). CV: pdfplumber, python-docx. Excel: openpyxl
- Docker + Docker Compose. Test: pytest + pytest-django. Lint/format: ruff

## Cấu trúc thư mục dự kiến

```
config/            settings, urls, wsgi
apps/accounts/     tài khoản, vai trò, lịch sử đăng nhập
apps/core/         danh mục, cài đặt, sinh mã, mã hóa, component giao diện dùng chung
apps/workers/      hồ sơ, CCCD, người liên hệ, đồng ý xử lý dữ liệu, quy trình duyệt
apps/documents/    tài liệu hồ sơ, phiên bản, xem trước
apps/intake/       đọc QR, OCR, trích CV, màn hình đối chiếu
apps/recruitment/  ứng tuyển, học vấn, kinh nghiệm, chứng chỉ
apps/employment/   quá trình làm việc, điều chuyển, hợp đồng
apps/reports/      dashboard, thống kê, xuất/nhập Excel
apps/audit/        nhật ký thao tác
templates/         base.html, components/, từng app
static/css/pa.css  token và style riêng (theo skill pa-ui)
docs/              yêu cầu, phases, tiến độ, hướng dẫn
scripts/           sao lưu, phục hồi, khởi động nhanh
```

## Lệnh thường dùng

```
docker compose up -d --build                          # chạy hệ thống
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_demo    # dữ liệu giả lập (tạo ở phase 2)
docker compose exec web pytest
docker compose exec web ruff check . && ruff format .
docker compose logs -f web
```

## Quy tắc bắt buộc

- **Ngôn ngữ:** mọi chữ hiển thị cho người dùng bằng tiếng Việt có dấu. Tên biến, hàm, model, bảng bằng tiếng Anh. Chú thích nghiệp vụ bằng tiếng Việt.
- **Định dạng:** ngày dd/mm/yyyy, múi giờ Asia/Ho_Chi_Minh, `LANGUAGE_CODE = "vi"`.
- **Dữ liệu cá nhân:** không bao giờ dùng số CCCD, ảnh CCCD hay thông tin người thật trong code, test, dữ liệu mẫu. Số định danh, CMND cũ, địa chỉ thường trú được mã hóa khi lưu; kiểm tra trùng bằng giá trị băm riêng.
- **Phân quyền:** kiểm tra ở phía máy chủ cho mọi view, API và lượt tải tệp. Ẩn nút trên giao diện chỉ là phần phụ.
- **Nhật ký:** mọi thao tác tạo, sửa, đổi trạng thái, xem đầy đủ CCCD, tải tệp, xuất báo cáo đều ghi vào audit log (giá trị trước/sau). Audit log chỉ thêm, không sửa, không xóa.
- **Không xóa cứng** bản ghi có liên kết; dùng trạng thái Lưu trữ hoặc cờ ngừng sử dụng.
- **Kết quả OCR/QR** không bao giờ tự lưu vào hồ sơ khi HR chưa xác nhận. Không đoán chữ mờ hoặc thiếu.
- **Tệp tải lên:** lưu ngoài thư mục public, tên ngẫu nhiên, kiểm tra định dạng thật của tệp, tối đa 10 MB, chỉ tải qua view có kiểm tra quyền.
- **Bí mật:** SECRET_KEY, mật khẩu CSDL, khóa mã hóa chỉ nằm trong `.env`. Không commit `.env`.
- **Không gọi dịch vụ ngoài Internet** trong chức năng bắt buộc. API OCR trả phí chỉ là tùy chọn, tắt mặc định.
- **Trạng thái:** chỉ dùng đúng ba bộ trạng thái và ba chỉ số tự tính ở mục II của `docs/yeu-cau.md`. Khai báo bằng `TextChoices`, không viết chuỗi trạng thái rải rác.

## Kiểm thử

- Mỗi chức năng có test: phân quyền (vai trò được/không được), sinh mã, kiểm tra trùng, chuyển trạng thái, ghi audit log.
- 17 kịch bản nghiệm thu ở mục X của `docs/yeu-cau.md` là thước đo cuối cùng; phase nào liên quan kịch bản nào thì phải chạy kịch bản đó.
- Thay đổi giao diện: chụp màn hình bằng skill `webapp-testing` và so với trang `/ui-kit`.

## Vòng lặp tự kiểm thử và sửa lỗi

Áp dụng cho mọi phase. Sau mỗi phần code (một tính năng, một trang, hoặc một nhóm model), tự chạy vòng lặp:

a. **Logic:** chạy `docker compose exec web pytest` và `ruff check .`. Mỗi quy tắc nghiệp vụ mới phải có test (phân quyền đúng/sai vai trò, chuyển trạng thái, sinh mã, kiểm tra trùng, ghi audit log).
b. **Giao diện:** dùng skill `webapp-testing` đăng nhập bằng từng tài khoản mẫu liên quan, mở các trang vừa làm, bấm thử các nút và form chính (cả trường hợp nhập sai), đọc lỗi console trình duyệt, chụp màn hình ở 1366x768 và 390x844 lưu vào `docs/screenshots/<phase>/`. Đối chiếu với checklist mục 10 của skill `pa-ui` và với trang `/ui-kit` (khi đã có).
c. **Nếu có lỗi:** tìm nguyên nhân gốc, sửa, rồi chạy lại cả a và b. Lặp tối đa 3 lần cho cùng một lỗi; quá 3 lần thì dừng và báo: lỗi gì, đã thử gì, đề xuất hướng xử lý.
d. **Cấm** để test "xanh" bằng cách: xóa hoặc nới test, thêm skip, bắt ngoại lệ rồi bỏ qua, sửa dữ liệu mong đợi cho khớp kết quả sai, đổi giao diện chuẩn `/ui-kit` hoặc quy tắc `pa-ui`.
e. Chỉ khi a và b đều đạt mới commit (thông điệp tiếng Việt, mô tả việc đã làm) và push lên `origin`.
f. **Cuối phase:** chạy lại toàn bộ test, chạy các kịch bản nghiệm thu liên quan ở mục X của `docs/yeu-cau.md`, cập nhật `docs/tien-do.md` (đã làm gì, kết quả test, ảnh chụp, việc tồn), commit + push, rồi dừng chờ duyệt.

Ghi chú môi trường máy phát triển (Windows): Playwright cài cho Python 3.12 64-bit, chạy script kiểm thử giao diện bằng `py -3.12 ...` (bản Python 3.15 32-bit mặc định không cài được Playwright).
