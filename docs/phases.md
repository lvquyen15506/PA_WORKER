# Kế hoạch các phase – PA Worker

Mỗi phase làm trong **một phiên Claude Code riêng**. Bắt đầu phiên bằng `/clear`, bật plan mode (Shift+Tab đến khi thấy "plan mode"), dán câu lệnh mẫu của phase, duyệt kế hoạch rồi mới cho Claude code.

Cuối mỗi phase, theo thứ tự:
1. `docker compose exec web pytest` đạt hết.
2. Chụp màn hình các trang mới bằng skill `webapp-testing`.
3. `/code-review`.
4. Cập nhật `docs/tien-do.md`.
5. Commit.

---

## Phase 0 – Khởi động

**Mục tiêu:** Claude hiểu đúng dự án trước khi viết dòng code nào.

Câu lệnh mẫu:
```
Đọc CLAUDE.md, docs/yeu-cau.md, docs/phases.md và skill pa-ui.
Tóm tắt lại cho tôi: (1) phạm vi MVP, (2) 3 bộ trạng thái, (3) ma trận phân quyền,
(4) quy tắc giao diện. Liệt kê mọi chỗ trong tài liệu bạn thấy mâu thuẫn hoặc chưa rõ.
Chưa viết code.
```
**Xong khi:** bản tóm tắt đúng; các câu hỏi đã được trả lời và ghi vào `docs/tien-do.md` mục "Quyết định đã chốt".

## Phase 1 – Thiết kế

Câu lệnh mẫu:
```
Phase 1. Thiết kế, chưa viết code ứng dụng:
- docs/thiet-ke/erd.md: sơ đồ ERD bằng Mermaid, đủ các bảng ở mục VI của yêu cầu, ghi khóa chính, khóa ngoại, ràng buộc duy nhất, trường mã hóa.
- docs/thiet-ke/models.md: danh sách model Django theo từng app (theo cấu trúc trong CLAUDE.md), trường, kiểu, bắt buộc, TextChoices cho trạng thái.
- docs/thiet-ke/trang.md: danh sách URL và trang, vai trò nào vào được, component pa-ui nào dùng.
- docs/thiet-ke/kien-truc.md: sơ đồ kiến trúc (Mermaid): container web/db, volume, các app Django, luồng nhận diện CCCD/CV offline.
- docs/thiet-ke/phac-thao-trang.md: phác thảo bố cục 12 trang ở mục VII (khung chữ/ASCII, chỉ dùng component pa-ui) và 4 trang phụ ở câu 19 của docs/lam-ro-yeu-cau.md.
- docs/thiet-ke/mau-dong-y.md: nháp mẫu văn bản đồng ý xử lý dữ liệu cá nhân (để in).
- docs/thiet-ke/excel-mau.md: danh sách cột file Excel mẫu nhập hàng loạt (tên cột, bắt buộc, định dạng, ví dụ giả).
Áp dụng mọi quyết định trong docs/lam-ro-yeu-cau.md.
Dừng lại cho tôi duyệt.
```
**Xong khi:** bạn duyệt ERD, sơ đồ kiến trúc, danh sách và phác thảo trang, mẫu văn bản đồng ý, cột Excel mẫu.

## Phase 2 – Nền tảng và Docker

Câu lệnh mẫu:
```
Phase 2 theo docs/phases.md và thiết kế đã duyệt ở docs/thiet-ke/:
- Khởi tạo dự án Django theo cấu trúc trong CLAUDE.md, cấu hình qua .env (kèm .env.example).
- Dockerfile (Python 3.12, cài tesseract-ocr + tesseract-ocr-vie + libzbar0) và docker-compose.yml (web + db PostgreSQL 16, volume cho db và media).
- Tải Bootstrap 5, Bootstrap Icons, HTMX, Chart.js vào static/vendor/ (không CDN).
- App accounts: 4 vai trò, đăng nhập/đăng xuất/đổi mật khẩu, khóa 15 phút sau 5 lần sai, tự đăng xuất sau 30 phút, lịch sử đăng nhập, Admin đặt lại mật khẩu tạm.
- App audit: nhật ký thao tác chỉ thêm.
- App core: danh mục (phòng ban, bộ phận, tổ, chức danh, ca, loại tài liệu, nguồn ứng tuyển), cài đặt, sinh mã theo quy tắc, tiện ích mã hóa trường nhạy cảm.
- Lệnh seed_demo: 4 tài khoản mẫu, danh mục mẫu, ~500 hồ sơ giả lập (dùng Faker vi_VN, số CCCD giả).
- Test cho phân quyền, khóa tài khoản, sinh mã, mã hóa.
Giao diện tạm thời tối giản, phase 3 mới làm giao diện chuẩn.
```
Kiểm tra giao diện ở phase này (bước b của vòng lặp tự kiểm thử) được nới: chỉ đăng nhập, mở trang, thử form, đọc lỗi console, chụp màn hình; chưa áp checklist pa-ui (câu 24 của docs/lam-ro-yeu-cau.md).
**Xong khi:** `docker compose up` chạy trên máy sạch; 4 tài khoản mẫu đăng nhập được; test đạt. (Kịch bản nghiệm thu 1, 15)

## Phase 3 – Bộ giao diện mẫu (quan trọng nhất cho UI đồng bộ)

Câu lệnh mẫu:
```
Phase 3. Dùng skill pa-ui:
- static/css/pa.css với token và ghi đè Bootstrap.
- templates/base.html (sidebar, thanh trên, chân trang) và toàn bộ component ở mục 3 của skill.
- Template filter status_badge theo bảng màu mục 5.
- Trang /ui-kit (chỉ Admin xem) trình bày mọi component với dữ liệu mẫu: đầu trang, 4 thẻ số liệu, thanh lọc, bảng 10 dòng có nhãn trạng thái đủ màu, phân trang, form 2 cột có lỗi mẫu, hộp xác nhận, empty state, tab, nhãn nguồn QR/OCR/Nhập tay, 1 biểu đồ cột.
- Chuyển trang đăng nhập và các trang phase 2 sang base.html.
Chụp màn hình /ui-kit ở 1366x768 và 390x844 bằng webapp-testing rồi dừng cho tôi duyệt.
```
**Xong khi:** bạn duyệt `/ui-kit`. **Từ đây không đổi kiểu dáng**; mọi trang sau chỉ lắp từ component này.

## Phase 4 – Hồ sơ và tài liệu

Câu lệnh mẫu:
```
Phase 4: mục IV.3 và IV.6 của yêu cầu, cùng quy trình duyệt ở mục II–III.
Danh sách hồ sơ (cột, lọc, tìm không dấu, phân trang), thêm/sửa/xem chi tiết (các tab), gửi duyệt,
duyệt/trả lại/từ chối có lý do, không tự duyệt hồ sơ mình nhập, sửa trường định danh thì quay về Chờ duyệt,
che số CCCD theo quyền, thư mục tài liệu (tải, xem trước, thay thế giữ bản cũ, danh sách còn thiếu),
ghi nhận đồng ý xử lý dữ liệu, kiểm tra trùng CCCD. Mọi thao tác ghi audit log.
Chỉ dùng component pa-ui. Viết test cho từng quy tắc.
```
**Xong khi:** kịch bản nghiệm thu 2, 5, 6, 7, 14 đạt.

## Phase 5 – Nhập từ CCCD và CV

Câu lệnh mẫu:
```
Phase 5: mục V của yêu cầu.
Trước tiên tạo bộ 15 ảnh CCCD giả (tests/fixtures/cccd/) có chữ "MẪU – KHÔNG CÓ GIÁ TRỊ", gồm 3 mẫu thẻ,
có QR giả cùng cấu trúc. Sau đó: kiểm tra chất lượng ảnh, đọc QR, OCR Tesseract cho trường còn thiếu,
màn hình đối chiếu 2 cột với nhãn nguồn và ngưỡng tin cậy, không lưu khi chưa xác nhận, trích văn bản CV và
gán vào trường bằng thao tác bôi đen. Viết script đo độ chính xác trên bộ ảnh giả và ghi kết quả vào docs/.
Cài đặt (chỉ Admin): khung /cai-dat/ có tab và tab OCR/QR (/cai-dat/ocr-qr/): ngưỡng tin cậy OCR,
QrFormat theo mẫu thẻ (thứ tự trường, ký tự phân cách, định dạng ngày), API OCR ngoài tắt mặc định
(bật thì cảnh báo gửi ảnh ra ngoài). Mọi thay đổi ghi nhật ký.
```
**Xong khi:** kịch bản 3, 4 đạt; có bảng độ chính xác; đổi cấu hình QR trên `/cai-dat/ocr-qr/` thì bộ tách trường dùng cấu hình mới mà không sửa code (câu 20).

## Phase 6 – Tuyển dụng và quá trình làm việc

Câu lệnh mẫu:
```
Phase 6: mục IV.4 và IV.5 của yêu cầu. Ứng tuyển nhiều lần trên một hồ sơ, học vấn/kinh nghiệm/chứng chỉ,
nút "Tiếp nhận vào làm" sinh mã nhân viên, thông tin làm việc hiện tại, lịch sử điều chuyển không ghi đè,
hợp đồng và cảnh báo sắp hết hạn.
Cài đặt (chỉ Admin, thêm tab vào khung /cai-dat/ của Phase 5): danh mục 9 loại (/cai-dat/danh-muc/<loai>/:
thêm, sửa, ngừng/dùng lại, không xóa), quy tắc sinh mã (/cai-dat/sinh-ma/, xem trước mã kế tiếp),
ngưỡng (/cai-dat/nguong/: sắp hết hạn, hạn lưu trữ, số ngày tự Lưu trữ, số tháng hồ sơ bỏ dở,
thời hạn phiên nhận diện). Mọi thay đổi ghi nhật ký.

Phần v1.1 (phiếu thay đổi đã ký 23/11/2026, `docs/lam-ro-yeu-cau.md` câu 39–47) cũng làm ở Phase 6:
- Danh mục công ty khách hàng (tên + địa điểm; `/cai-dat/danh-muc/cong-ty-khach/`, loại thứ 10), data migration thêm loại tài liệu "Bản cam kết".
- Model `ClientCompany`, `WorkAssignment`, `SalaryHistory` (+ migration, trigger chặn UPDATE lịch sử lương, ràng buộc một đợt mở mỗi công nhân), `assignment_limit_months` ở Cài đặt (`/cai-dat/nguong/`).
- Tab Quá trình làm việc: đợt làm việc (thêm, sửa, không xóa, không chồng lấn, tự đóng khi nghỉ việc) và lịch sử lương (mọi vai trò xem, chỉ A, Q thêm dòng; mã hóa; nhật ký không chứa giá trị lương).
- Bộ lọc `/ho-so/` theo công ty khách và `?dot_sap_du_han=1`; chỉ báo đợt sắp đủ 12 tháng ở `apps.workers.indicators`.
- Cập nhật `PERSONAL_FIELDS`, `LOGICAL_TO_ATTR`, hàm `anonymize` (xóa lịch sử lương, xóa `note` của đợt), `seed_demo` (công ty khách, đợt, lương giả), và bổ sung ngoại lệ vào `CLAUDE.md` khi được duyệt.
- Test: quyền xem/thêm lương theo 4 vai trò (kể cả gọi thẳng URL), một công ty tại một lúc, không chồng lấn, cột lương không lộ giá trị rõ trong `AuditLog.changes` và trong CSDL, hạn lưu trữ 10 năm không đổi khi đợt kết thúc (câu 44), ẩn danh hóa xóa lịch sử lương.
- Khối "Đợt làm việc sắp đủ 12 tháng" ở Dashboard và loại báo cáo "Công nhân đang làm theo công ty khách hàng" thuộc trang của Phase 7; Phase 6 chỉ làm hàm tính để Phase 7 dùng lại.
```
**Xong khi:** kịch bản 8, 9, 10 đạt; đổi quy tắc sinh mã và ngưỡng sắp hết hạn trên giao diện thì có tác dụng ngay (mã đã cấp giữ nguyên). Phần v1.1: thêm công ty khách, thêm đợt làm việc, ghi lương bằng tài khoản Q thấy đúng ở cả 4 vai trò (V xem được, H và V không thêm được); lọc danh sách theo công ty khách đúng số người.

## Phase 7 – Tra cứu, Dashboard, báo cáo

Câu lệnh mẫu:
```
Phase 7: mục IV.2, IV.7, IV.8 của yêu cầu. Dashboard (thẻ số liệu bấm được, biểu đồ), ô tìm nhanh,
báo cáo theo thời gian và phòng ban, xuất Excel (che CCCD theo quyền, ghi nhật ký), in báo cáo,
nhập hồ sơ từ file Excel mẫu có báo lỗi từng dòng, trang nhật ký thao tác có bộ lọc.
Kiểm tra tốc độ với 500 hồ sơ (danh sách, lọc, tìm < 2 giây).
Cài đặt (chỉ Admin): tab Chờ hủy (/cai-dat/cho-huy/: hồ sơ Lưu trữ quá hạn, cột căn cứ và ngày hết hạn,
chọn nhiều rồi ẩn danh hóa qua hộp xác nhận) và Biên bản hủy (/cai-dat/bien-ban-huy/: danh sách, xem, in,
ghi nhật ký PRINT). Dùng lại expired_queryset và anonymize đã làm ở Phase 4.
v1.1: thêm vào Dashboard khối việc cần làm "Đợt làm việc sắp đủ 12 tháng" (không thêm thẻ) và loại báo cáo
"Công nhân đang làm theo công ty khách hàng" (câu 43, 45), dùng hàm đã làm ở Phase 6.
```
**Xong khi:** kịch bản 11, 12, 13, 16 đạt; ẩn danh hóa từ danh sách chờ hủy sinh biên bản đúng (câu 2); khối 12 tháng và báo cáo theo công ty khách có số liệu khớp danh sách đích.

## Phase 8 – Nghiệm thu và bàn giao

Câu lệnh mẫu:
```
Phase 8:
- Script sao lưu/phục hồi (scripts/), file khởi động nhanh PA Worker.bat (Windows) và PA Worker.command (macOS).
- Chạy đủ 17 kịch bản nghiệm thu ở mục X bằng webapp-testing, ghi docs/nghiem-thu.md: kịch bản, kết quả, ảnh chụp.
- docs/huong-dan-cai-dat.md cho người không chuyên IT (Windows và macOS, cài Docker Desktop, WSL 2, chạy, sao lưu, lỗi thường gặp) và phương án chạy không cần Docker.
- docs/huong-dan-su-dung.md theo từng vai trò.
- Rà soát bảo mật theo mục VIII.
```
**Xong khi:** 17/17 kịch bản đạt trên máy sạch.
