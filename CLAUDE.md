# PA Worker – Phần mềm quản lý hồ sơ công nhân

Web app quản lý hồ sơ công nhân cho doanh nghiệp sản xuất. Đơn vị phát triển: QQIT. Phiên bản mục tiêu: 1.0.

## Nguồn sự thật

- `docs/yeu-cau.md`: tài liệu yêu cầu **đã được khách hàng duyệt**. Mọi chức năng, trường dữ liệu, trạng thái, phân quyền và tiêu chí nghiệm thu lấy từ đây. Không tự thêm chức năng ngoài tài liệu; thấy chỗ mâu thuẫn hoặc chưa rõ thì **hỏi lại**, không đoán.
- `docs/lam-ro-yeu-cau.md`: các quyết định làm rõ; câu gắn [Nội bộ] là quyết định nội bộ chưa xác nhận với khách hàng, vẫn áp dụng khi code. **Khi `docs/lam-ro-yeu-cau.md` khác `docs/yeu-cau.md` thì theo `docs/lam-ro-yeu-cau.md`.** Không sửa `docs/yeu-cau.md` (bản đã ký).
- `docs/thiet-ke/` (`erd.md`, `models.md`, `trang.md`, `kien-truc.md`): thiết kế đã duyệt. Tên model, trường, quan hệ, URL, quyền phải đúng như các file này; muốn đổi thì sửa thiết kế trước.
- `docs/phases.md`: kế hoạch từng phase và điều kiện "xong".
- `docs/tien-do.md`: nhật ký tiến độ. Cập nhật cuối mỗi phase (làm gì, còn gì, quyết định nào đã chốt).
- Giao diện: **luôn dùng skill `pa-ui`** (`.claude/skills/pa-ui/SKILL.md`) khi tạo hoặc sửa bất kỳ template, CSS, trang, form, bảng, nút nào.

## Cách làm việc

1. Chỉ làm **một phase** mỗi lần, đúng phạm vi ghi trong `docs/phases.md`.
2. Bắt đầu phase bằng kế hoạch ngắn (file sẽ tạo/sửa, cách kiểm tra), chờ duyệt rồi mới code.
3. Kết thúc phase: chạy test, chạy lint, chụp màn hình các trang mới (skill `webapp-testing`), cập nhật `docs/tien-do.md`, rồi **dừng lại báo cáo**. Không tự sang phase sau.
4. Không báo "xong" khi test còn lỗi hoặc chức năng chưa chạy thật trên Docker.
5. Commit sau mỗi phần hoàn chỉnh, thông điệp tiếng Việt, ngắn gọn.
6. Sửa mọi file (`.md`, `.py`, `.html`…) chỉ dùng công cụ Edit (từng đoạn), không dùng python/sed/regex để ghi đè file và không ghi lại cả file từ bộ nhớ, để không làm mất nội dung đã có. Tạo file mới thì dùng Write. Ngoại lệ: được chạy `ruff format .` (công cụ định dạng, kết quả xác định, chỉ đổi khoảng trắng); quy tắc này chỉ cấm tự viết lại file bằng python/sed/regex/Write.

## Công nghệ (đã chốt, không đổi nếu chưa được duyệt)

- Python 3.12, Django 5.2 LTS, Gunicorn
- PostgreSQL 16 (trong Docker); SQLite chỉ dùng khi chạy thử không có Docker
- Django templates + Bootstrap 5 + Bootstrap Icons + HTMX + Chart.js — **tất cả để trong `static/vendor/`, không dùng CDN** (hệ thống phải chạy offline)
- QR: OpenCV + pyzbar. OCR: Tesseract (gói `vie`). CV: pdfplumber, python-docx, `antiword` (gói apt, đọc `.doc`). Excel: openpyxl
- Mã hóa trường nhạy cảm: `cryptography` (Fernet). Phục vụ tệp tĩnh: `whitenoise` (duyệt 21/11/2026, `docs/thiet-ke/kien-truc.md` mục 8)
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
docker compose exec web ruff check .
docker compose exec web ruff format .
docker compose logs -f web
```

## Quy tắc bắt buộc

- **Ngôn ngữ:** mọi chữ hiển thị cho người dùng bằng tiếng Việt có dấu. Tên biến, hàm, model, bảng bằng tiếng Anh. Chú thích nghiệp vụ bằng tiếng Việt.
- **Định dạng:** ngày dd/mm/yyyy, múi giờ Asia/Ho_Chi_Minh, `LANGUAGE_CODE = "vi"`.
- **Dữ liệu cá nhân:** không bao giờ dùng số CCCD, ảnh CCCD hay thông tin người thật trong code, test, dữ liệu mẫu. Số CCCD giả trong dữ liệu mẫu và test **luôn bắt đầu bằng `999`** (không trùng mã tỉnh nào); tên người là tên hư cấu. Số định danh, CMND cũ, địa chỉ thường trú được mã hóa khi lưu; kiểm tra trùng bằng giá trị băm riêng.
- **Phân quyền:** kiểm tra ở phía máy chủ cho mọi view, API và lượt tải tệp. Ẩn nút trên giao diện chỉ là phần phụ.
- **Nhật ký:** mọi thao tác tạo, sửa, đổi trạng thái, xem đầy đủ CCCD, tải tệp, xuất báo cáo đều ghi vào audit log qua **`apps.audit.services.log()`** (không tạo `AuditLog` trực tiếp). Trường cá nhân (`PERSONAL_FIELDS`, `docs/thiet-ke/models.md` mục 3.2) **không** ghi giá trị rõ vào `AuditLog.changes` (chỉ ghi "(xem giá trị chi tiết)"); giá trị trước/sau lưu mã hóa ở `AuditPersonalValue`. `object_repr` và lý do hệ thống tự điền chỉ dùng mã hồ sơ, không họ tên (`docs/lam-ro-yeu-cau.md` câu 30). `AuditLog` chỉ thêm, không sửa, không xóa; `AuditPersonalValue` chỉ bị xóa khi ẩn danh hóa hồ sơ. Lý do do người dùng gõ khi đổi trạng thái xác minh là trường cá nhân (khóa ảo `status_reason` ở `AuditPersonalValue`, không ghi vào `AuditLog.note`); ngoại lệ có kiểm soát duy nhất của bảng chỉ thêm `StatusChange`: `anonymize()` thay `reason` của các dòng `reason_by_user` bằng "(đã ẩn danh)".
- **Không xóa cứng** bản ghi có liên kết; dùng trạng thái Lưu trữ hoặc cờ ngừng sử dụng. Ngoại lệ: `IntakeSession` (bản ghi tạm), `AuditPersonalValue` và `SalaryHistory` khi ẩn danh hóa (chỉ trong `anonymize()`), và dòng con học vấn / chứng chỉ / kinh nghiệm / người liên hệ khẩn cấp (không bảng nào trỏ tới, giá trị cũ ghi nhật ký; xem `docs/thiet-ke/trang.md`).
- **Kết quả OCR/QR** không bao giờ tự lưu vào hồ sơ khi HR chưa xác nhận. Không đoán chữ mờ hoặc thiếu.
- **Tệp tải lên:** lưu ngoài thư mục public, tên ngẫu nhiên, kiểm tra định dạng thật của tệp, tối đa 10 MB, chỉ tải qua view có kiểm tra quyền.
- **Không bao giờ ghi mật khẩu, khóa, token vào báo cáo, commit, tài liệu hay tin nhắn trả lời.** Khi cần, chỉ nói "đã in ra console" hoặc hướng dẫn lệnh để người dùng tự xem.
- **Bí mật:** SECRET_KEY, mật khẩu CSDL, khóa mã hóa chỉ nằm trong `.env`. Không commit `.env`.
- **Khóa mã hóa** (`docs/lam-ro-yeu-cau.md` câu 31): `FIELD_ENCRYPTION_KEY` và `HASH_KEY` sinh một lần khi cài, **không** nằm trong file sao lưu; script sao lưu (Phase 8) nhắc người dùng cất bản sao khóa riêng (USB/giấy niêm phong). Thiếu hoặc sai khóa thì ứng dụng từ chối khởi động với thông báo tiếng Việt rõ ràng. MVP không hỗ trợ đổi khóa (giới hạn đã biết).
- **Không gọi dịch vụ ngoài Internet** trong chức năng bắt buộc. API OCR trả phí chỉ là tùy chọn, tắt mặc định.
- **Trạng thái:** chỉ dùng đúng ba bộ trạng thái và ba chỉ số tự tính ở mục II của `docs/yeu-cau.md`, cộng bộ thứ tư **trạng thái xác minh tài liệu** (Chưa xác minh / Đã đối chiếu bản gốc / Không hợp lệ), bộ này chỉ dùng trong tab Tài liệu (`docs/lam-ro-yeu-cau.md` câu 3). Khai báo bằng `TextChoices`, không viết chuỗi trạng thái rải rác. "Chờ hủy" không phải trạng thái, chỉ là danh sách tính tự động. Quy tắc 4 bộ trạng thái áp dụng cho trạng thái nghiệp vụ được lưu; nhãn hiển thị ở pa-ui mục 5 không tính.

## Kiểm thử

- Mỗi chức năng có test: phân quyền (vai trò được/không được), sinh mã, kiểm tra trùng, chuyển trạng thái, ghi audit log.
- 17 kịch bản nghiệm thu ở mục X của `docs/yeu-cau.md` là thước đo cuối cùng; phase nào liên quan kịch bản nào thì phải chạy kịch bản đó.
- Thay đổi giao diện: chụp màn hình bằng skill `webapp-testing` và so với trang `/ui-kit`.

## Vòng lặp tự kiểm thử và sửa lỗi

Áp dụng cho mọi phase. Sau mỗi phần code (một tính năng, một trang, hoặc một nhóm model), tự chạy vòng lặp:

a. **Logic:** chạy `docker compose exec web pytest` và `docker compose exec web ruff check .`. Mỗi quy tắc nghiệp vụ mới phải có test (phân quyền đúng/sai vai trò, chuyển trạng thái, sinh mã, kiểm tra trùng, ghi audit log).
b. **Giao diện:** dùng skill `webapp-testing` đăng nhập bằng từng tài khoản mẫu liên quan, mở các trang vừa làm, bấm thử các nút và form chính (cả trường hợp nhập sai), đọc lỗi console trình duyệt, chụp màn hình ở 1366x768 và 390x844 lưu vào `docs/screenshots/<phase>/`. Đối chiếu với checklist mục 10 của skill `pa-ui` và với trang `/ui-kit` (khi đã có). Riêng Phase 2 (giao diện tạm) chỉ cần đăng nhập, mở trang, thử form, đọc lỗi console và chụp màn hình; checklist pa-ui áp dụng từ Phase 3.
c. **Nếu có lỗi:** tìm nguyên nhân gốc, sửa, rồi chạy lại cả a và b. Lặp tối đa 3 lần cho cùng một lỗi; quá 3 lần thì dừng và báo: lỗi gì, đã thử gì, đề xuất hướng xử lý.
d. **Cấm** để test "xanh" bằng cách: xóa hoặc nới test, thêm skip, bắt ngoại lệ rồi bỏ qua, sửa dữ liệu mong đợi cho khớp kết quả sai, đổi giao diện chuẩn `/ui-kit` hoặc quy tắc `pa-ui`.
e. Chỉ khi a và b đều đạt mới commit (thông điệp tiếng Việt, mô tả việc đã làm) và push lên `origin`.
f. **Cuối phase:** chạy lại toàn bộ test, chạy các kịch bản nghiệm thu liên quan ở mục X của `docs/yeu-cau.md`, cập nhật `docs/tien-do.md` (đã làm gì, kết quả test, ảnh chụp, việc tồn), commit + push, rồi dừng chờ duyệt.

Ghi chú môi trường máy phát triển (Windows): Playwright cài cho Python 3.12 64-bit, chạy script kiểm thử giao diện bằng `py -3.12 ...` (bản Python 3.15 32-bit mặc định không cài được Playwright).
