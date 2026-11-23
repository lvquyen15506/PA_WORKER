# Rà soát bảo mật – PA Worker v1.1.0

Phase 8 · Ngày 24/11/2026 · Căn cứ: `docs/yeu-cau.md` mục VIII, `docs/thiet-ke/trang.md`, `docs/thiet-ke/kien-truc.md` mục 6–7.

Rà soát làm ở bước 1 của Phase 8 (chỉ đọc). Mọi lần gọi thử chạy trong giao dịch được rollback, không ghi gì vào CSDL. Người phụ trách dự án duyệt sửa mục 1–12 ngày 24/11/2026; mục 13–14 giữ là giới hạn đã biết.

## 1. Cách rà

| Hạng mục | Cách làm |
| --- | --- |
| Phân quyền | Liệt kê mọi URL bằng `get_resolver()`, đọc vai trò khai báo trong `role_required` và phương thức trong `require_http_methods`. Gọi thử 76 URL với 5 trạng thái (chưa đăng nhập, A, Q, H, V) bằng test client, so với bảng quyền ở `trang.md` |
| GET làm đổi dữ liệu | Đếm số dòng mọi bảng trước và sau mỗi GET được phép |
| Dữ liệu nhạy cảm với Viewer | 25 hồ sơ có CCCD × 5 tab chi tiết: tìm giá trị số CCCD, CMND cũ, địa chỉ thường trú, quê quán, nơi đăng ký khai sinh trong HTML trả về Viewer; HR không thấy số đầy đủ khi chưa bấm "Hiện số đầy đủ"; Viewer tìm bằng đủ 12 số CCCD |
| CSRF, chèn mã | Tìm `csrf_exempt`, `mark_safe`, `|safe`, SQL thô; đọc cách htmx gửi token |
| Log, thông báo lỗi | Đọc `logger.*`; quét log container tìm số 12 chữ số và `q=`; xem hành vi lỗi 404/500 khi DEBUG=False |
| Tệp tải lên | Đọc kiểm tra định dạng thật, giới hạn 10 MB, giới hạn kích thước request |
| Settings | `manage.py check --deploy` với DEBUG=0 |
| Khóa, bí mật | Lịch sử git có `.env` không; giá trị 4 khóa thật có trong commit nào không (chỉ đếm, không in); mật khẩu viết cứng |
| Docker | Người dùng chạy tiến trình, cổng mở, biến môi trường từng container nhận, cấu hình log, tệp override |
| Thư viện | `pip-audit -r requirements.txt` trong container tạm; phiên bản thư viện JS trong `static/vendor/`; Trivy quét image `web` và `db` (mục 5) |

## 2. Vấn đề và cách sửa

| # | Mức | Vị trí | Vấn đề | Cách sửa | Trạng thái |
| --- | --- | --- | --- | --- | --- |
| 1 | Cao | `docker-compose.override.yml` | Tệp cấu hình dev nằm trong repo: khách gõ `docker compose up` sẽ chạy bản dev (mount mã nguồn cho ghi, `--reload`) | Đổi tên thành `docker-compose.dev.yml`; dev chạy với `-f docker-compose.yml -f docker-compose.dev.yml` | Đã sửa |
| 2 | Cao | `apps/core/management/commands/seed_demo.py` | `seed_demo` chạy được trên bản thật (tạo 500 hồ sơ giả lẫn dữ liệu thật); ngoài `seed_demo` không có cách tạo Admin đầu tiên | `DEMO_MODE` trong `.env`, `seed_demo` từ chối khi không phải bản Demo; lệnh `create_first_admin`, `reset_admin_password` | Đã sửa: `DEMO_MODE` (mặc định 0 = bản Thật) do `make_env.py --mode` ghi khi cài; hai lệnh mới ghi nhật ký với người thực hiện "Hệ thống", mật khẩu tạm chỉ in ra màn hình, buộc đổi khi đăng nhập |
| 3 | Cao | (chưa có) | Chưa có sao lưu, phục hồi (mục VIII) | Lệnh `backup`, `verify_backup`, `restore`; file sao lưu mã hóa; sao lưu tự động hằng ngày | Chưa sửa |
| 4 | Trung bình | `Dockerfile` (CMD) | Gunicorn worker `sync`: kết nối mở sẵn mà chưa gửi gì của trình duyệt giữ worker tới hết timeout 120 giây (log có `WORKER TIMEOUT … no URI read`); chỉ 3 worker nên vài kết nối là treo cả hệ thống | `--worker-class gthread --threads 4`, giữ `--workers 3 --timeout 120` | Đã sửa |
| 5 | Trung bình | `Dockerfile` | Container chạy bằng root, `private_media` thuộc root | `web`, `scheduler` chạy bằng người dùng `app` (UID 1000, `USER app`); mã nguồn thuộc root (chỉ đọc), chỉ `private_media` và `/backups` thuộc `app`; volume mới lấy quyền từ image, volume cũ đổi quyền một lần (`Cap nhat.bat`), entrypoint báo lỗi tiếng Việt nếu chưa đổi. `db` chạy bằng `postgres` (mục 5) | Đã sửa |
| 6 | Trung bình | `config/settings.py` | Không có `LOGGING`: khi DEBUG=False lỗi 500 không được ghi ra log container | `LOGGING` ra stdout cho `django.request` và `apps`; chỉ ghi đường dẫn (không có chuỗi truy vấn) và traceback; Gunicorn tiếp tục không bật access log | Đã sửa: `LOGGING` ở `config/settings.py`, bộ định dạng `apps/core/log_format.py` che mọi dãy từ 9 chữ số trở lên (số CCCD, CMND, SĐT) kể cả trong traceback; `runserver` chỉ ghi dòng request khi lỗi |
| 7 | Trung bình | `templates/` | Chỉ có `403.html`; lỗi 404 và 500 hiện trang mặc định tiếng Anh | `404.html`, `500.html` tiếng Việt | Đã sửa: thêm cả `400.html` (sai `ALLOWED_HOSTS`, có hướng dẫn) và `413.html`; khung chung `error_base.html` không cần request hay CSDL |
| 8 | Trung bình | `docker-compose.yml` | Không đặt `name:`: giải nén bản mới vào thư mục tên khác sẽ tạo volume trống, trông như mất dữ liệu | `name: pa_worker` | Đã sửa |
| 9 | Trung bình | `docker-compose.yml` | Không giới hạn log (Docker Desktop mặc định `json-file` không giới hạn) | `json-file`, `max-size 10m`, `max-file 5` cho cả 3 service | Đã sửa |
| 10 | Trung bình | `config/settings.py` | `check --deploy` còn 4 cảnh báo HTTPS (HSTS, chuyển hướng SSL, cookie Secure) | Cờ `HTTPS=1` bật cookie Secure, HSTS, chuyển hướng SSL, `CSRF_TRUSTED_ORIGINS`, `SECURE_PROXY_SSL_HEADER`; mặc định tắt vì bản bàn giao chạy HTTP trong LAN | Đã sửa: `HTTPS=1` thì `check --deploy` không còn cảnh báo; tắt có lý do W008 (proxy chuyển hướng, nếu Django chuyển hướng thì healthcheck nội bộ hỏng), W005 và W021 (HSTS tên miền con/preload chỉ cho tên miền công khai). `HTTPS=0` còn đúng 4 cảnh báo HTTPS (có test). Thêm `SECURE_REFERRER_POLICY`, `SAMESITE=Lax` |
| 11 | Thấp | `config/settings.py` | Không giới hạn tổng kích thước request: tệp rất lớn vẫn được ghi ra thư mục tạm trước khi form từ chối | Middleware từ chối `Content-Length` > 35 MB, trả 413 tiếng Việt | Đã sửa: `apps/core/middleware.py`, `MAX_REQUEST_BYTES` |
| 12 | Thấp | `templates/workers/detail.html`, 3 trang in | Không có CSP cho toàn trang; còn 4 chỗ JS viết thẳng trong HTML | Chuyển vào `static/js/pa.js`; CSP `default-src 'self'` cho mọi trang (trang xem tài liệu giữ `sandbox` riêng); không nới CSP | Đã sửa: `ContentSecurityPolicyMiddleware` (`default-src 'self'`, `script-src 'self'`, `style-src 'self'`, `img-src 'self' data:`, `object-src 'none'`, `frame-ancestors 'none'`…), không có `unsafe-inline`/`unsafe-eval`; nút in và mở lại hộp xác nhận chuyển vào `pa.js`; htmx tắt `includeIndicatorStyles`, `allowEval`, `allowScriptTags`. Chạy lại kiểm thử giao diện Phase 3–7 (81 + 111 + 88 + 149 + 173 bước) và Phase 8 (21 bước): không có lỗi CSP ở console; đã thử chắc chắn rằng vi phạm CSP hiện thành lỗi console. Trình xem PDF của Edge và Chrome mở được tệp PDF thật dưới `sandbox` (việc tồn Phase 4, ảnh `docs/screenshots/phase-8/06-*`) |

## 3. Giới hạn đã biết (không sửa)

| # | Mức | Vấn đề | Lý do |
| --- | --- | --- | --- |
| 13 | Thấp | Khóa đăng nhập theo từng tài khoản (5 lần sai, 15 phút), không giới hạn theo địa chỉ IP: kẻ tấn công thử một mật khẩu cho nhiều tài khoản thì không bị khóa | Đúng yêu cầu mục IV.1; hệ thống chỉ chạy trong mạng nội bộ với 5–10 người dùng |
| 14 | Thông tin | Image chạy thật có cả gói chỉ dùng để kiểm thử (`pytest`, `pytest-django`, `ruff`) | `CLAUDE.md` chạy test và lint trong container `web`; các gói này không mở cổng, không được gọi khi chạy |

## 4. Đã kiểm tra, đạt

- **Phân quyền:** 76 URL × 5 trạng thái khớp `trang.md`. Chưa đăng nhập → chuyển `/dang-nhap/`; sai vai trò → 403; phiên nhận diện của người khác → 404; URL chỉ nhận POST thì GET → 405. `document_verify` và `salary_add` khai báo HR ở decorator nhưng view vẫn trả 403 cho HR (đúng câu 34, 42).
- **GET làm đổi dữ liệu:** chỉ ghi `AuditLog` (`EXPORT`, `PRINT`, `VIEW_FILE`, `DOWNLOAD_FILE`), đúng thiết kế (`trang.md` 5.4, 5.5, 5.9).
- **Viewer:** không thấy số CCCD, CMND cũ, địa chỉ thường trú, quê quán, nơi đăng ký khai sinh (25 hồ sơ × 5 tab); tìm bằng đủ 12 số CCCD không ra hồ sơ. HR không thấy số đầy đủ khi chưa bấm "Hiện số đầy đủ".
- **CSRF, chèn mã:** không có `csrf_exempt`; htmx gửi `X-CSRFToken` (`static/js/pa.js`); không ghép chuỗi SQL; không dùng `|safe` với dữ liệu người dùng.
- **Log:** không có số 12 chữ số, không có `q=`; logger chỉ ghi `pk` và mã hồ sơ; Gunicorn không bật access log.
- **Bí mật:** lịch sử git chưa từng chứa `.env`; giá trị 4 khóa thật xuất hiện ở 0 commit; không có mật khẩu viết cứng. Hai khóa giả trong `Dockerfile` chỉ dùng cho `collectstatic` lúc build.
- **Docker:** `db` không mở cổng, chỉ nhận 3 biến CSDL.
- **Thư viện Python:** `pip-audit` không thấy lỗ hổng đã biết. Thư viện JS: Bootstrap 5.3.9, htmx 2.0.11, Chart.js 4.6.1.
- **`check --deploy`** (DEBUG=0): chỉ còn 4 cảnh báo HTTPS (mục 10).

## 5. Quét image bằng Trivy

Trivy 0.58.1 chạy trong container tạm (`aquasec/trivy`, không cài vào image của dự án), cơ sở dữ liệu lỗ hổng cập nhật 23/11/2026, chỉ lấy mức HIGH và CRITICAL.

| Image | Trước khi sửa | Có bản sửa | Sau khi sửa | Có bản sửa |
| --- | --- | --- | --- | --- |
| `web` (`python:3.12-slim`, Debian 13) | 141 | 57 (`krb5` ×4 gói, `zlib1g`) | 84 | **0** |
| `db` (`postgres:16`, Debian 13) | 156 | 83 (`krb5` ×4 gói, `zlib1g`, `gosu`) | 73 | **0** |

**Đã sửa:**
- `docker pull` cả hai image gốc: digest không đổi (đã là bản mới nhất ngày 24/11/2026). Ghim digest trong `Dockerfile` (`python:3.12-slim@sha256:5e2bdb1b…`) và `docker/db.Dockerfile` (`postgres:16.16@sha256:3950ad7c…`) để build lại ra đúng image đã quét.
- `web`: `apt-get upgrade -y` khi build lấy bản vá Debian (`krb5` 1.21.3-5+deb13u2, `zlib1g` 1:1.3.dfsg+really1.3.1-1+deb13u1).
- `db`: image con `docker/db.Dockerfile` chỉ nâng đúng các gói `krb5` và `zlib1g` (không đổi phiên bản PostgreSQL); xóa `gosu` (biên dịch bằng Go 1.24.6, 26 lỗ hổng thư viện chuẩn Go) và chạy thẳng bằng người dùng `postgres` (entrypoint gốc chỉ dùng `gosu` để hạ quyền từ root). Đã thử khởi động trên volume cũ và volume mới tạo.

**Còn lại, chưa có bản sửa của Debian 13 (ghi nhận, quét lại khi cập nhật phiên bản):**

| Gói | Image | Số lỗ hổng | Mức độ liên quan |
| --- | --- | --- | --- |
| `libxml2` (1 CRITICAL CVE-2026-6653, 7 HIGH) | web, db | 8 | `web`: chỉ có vì `libarchive13` (phụ thuộc của Tesseract); ứng dụng không đưa XML vào thư viện này. Đọc `.docx` dùng `lxml` cài từ wheel có `libxml2` riêng (`pip-audit` không báo lỗ hổng). `db`: PostgreSQL dùng `libxml2` cho kiểu `xml`, CSDL của ứng dụng không có cột hay hàm XML. Không có đường nhận XML từ người dùng |
| `tesseract-ocr`, `libtesseract5` | web | 12 | **Có liên quan**: OCR ảnh CCCD và CV do HR tải lên. Giảm thiểu: chỉ người dùng đã đăng nhập có quyền A, Q, H tải ảnh; kiểm tra định dạng thật (JPG/PNG/PDF), tối đa 10 MB, tối đa 40 triệu điểm ảnh từ header, ảnh được Pillow/OpenCV đọc lại trước OCR; Tesseract chạy bằng người dùng `app` không phải root, có timeout |
| `libtiff6` | web | 2 | Phụ thuộc của Leptonica (Tesseract). Ứng dụng chỉ nhận JPG/PNG/PDF (kiểm tra chữ ký tệp), không đưa TIFF vào |
| `openssl`, `libssl3t64`, `openssl-provider-legacy` | web, db | 6 mỗi image | Ứng dụng không mở kết nối TLS ra ngoài; kết nối `web` → `db` nằm trong mạng Docker nội bộ, không TLS; HTTPS (khi bật) do reverse proxy ngoài phụ trách |
| `libcurl4t64` | web | 2 | Phụ thuộc của Tesseract (đọc ảnh qua URL); ứng dụng chỉ đưa tệp cục bộ |
| `util-linux` và các thư viện cùng gói (`mount`, `login`, `bsdutils`, `libblkid1`, `libmount1`, `libuuid1`, `libsmartcols1`, `liblastlog2-2`, `libacl1`) | web, db | 30 mỗi image | Công cụ hệ thống không được ứng dụng gọi; container không có đăng nhập, không gắn ổ đĩa |
| `libx11-6`, `libx11-data`, `libxrender1` | web | 3 | Phụ thuộc của `libzbar0` và `libcairo2`; container không có giao diện đồ họa |
| `libexpat1` | web | 4 | Phụ thuộc của `fontconfig`, chỉ dùng khi sinh ảnh thẻ giả cho kiểm thử |
| `libsqlite3-0` | web, db | 3 | Phụ thuộc của `liblastlog2`; ứng dụng dùng PostgreSQL |
| `perl`, `perl-base`, `libperl5.40`, `perl-modules-5.40` | web, db | 1–4 | Script hệ thống của Debian; không chạy khi ứng dụng hoạt động |
| `ncurses-*`, `libtinfo6`, `libncursesw6` | web, db | 4 | Thư viện màn hình dòng lệnh |
| `libsystemd0`, `libudev1`, `systemd`, `libsystemd-shared` | web, db | 2–4 | Container không chạy systemd |
| `gnupg`, `gpg*`, `dirmngr` | db | 7 | Chỉ dùng khi cài gói apt lúc build |

Quét lại khi đổi digest image gốc (cùng lệnh, ghi kết quả vào mục này):

```
docker run --rm -v //var/run/docker.sock:/var/run/docker.sock -v trivy-cache:/root/.cache/ aquasec/trivy:0.58.1 image --scanners vuln --severity HIGH,CRITICAL pa_worker-web
docker run --rm -v //var/run/docker.sock:/var/run/docker.sock -v trivy-cache:/root/.cache/ aquasec/trivy:0.58.1 image --scanners vuln --severity HIGH,CRITICAL pa_worker-db
```
