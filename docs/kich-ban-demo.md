# Kịch bản trình diễn 10 phút – PA Worker

Phiên bản 1.1.0 · Dành cho người trình diễn trước hội đồng (yêu cầu mục XI.8).

Trình diễn trên **bản Demo** (dữ liệu giả lập). Mọi tên người, số CCCD (bắt đầu bằng `999`) và ảnh thẻ đều là giả, có chữ "MẪU – KHÔNG CÓ GIÁ TRỊ".

## Chuẩn bị (trước buổi trình diễn, khoảng 15 phút)

1. Máy chủ đã cài bản Demo, chạy `PA Worker.bat`, `Kiem tra.bat` báo "Hệ thống hoạt động bình thường".
2. Đã đổi mật khẩu cho 4 tài khoản mẫu `admin`, `quanly`, `hr`, `viewer`; ghi mật khẩu ra giấy riêng (không chiếu lên màn hình).
3. Một trình duyệt mở sẵn **4 cửa sổ** (mỗi cửa sổ dùng một hồ sơ trình duyệt hoặc cửa sổ ẩn danh riêng), lần lượt đăng nhập `hr`, `quanly`, `viewer`, `admin`. Phóng to chữ 110–125% để hội đồng đọc được.
4. Tệp mẫu trên màn hình nền:
   - ảnh thẻ giả `tests\fixtures\cccd\01-cccd_2021-truoc.png` và `01-cccd_2021-sau.png` (có QR);
   - ảnh thẻ không QR `tests\fixtures\cccd\12-cccd_2016-truoc.png`;
   - CV giả `tests\fixtures\cv\cv-mau.pdf`.
   Ảnh 01 đã dùng ở buổi tập thì sinh bộ ảnh mới (số CCCD khác) bằng lệnh `docker compose exec web python manage.py make_fake_cccd --out /tmp/the_gia --offset 5000` rồi `docker compose cp web:/tmp/the_gia ./the-gia-moi`.
5. Chạy `Sao luu.bat` một lần để có bản sao lưu mới nhất (dùng ở phút 9).
6. Mạng: không cần Internet. Có thể rút dây mạng để chứng minh chạy offline.

## Kịch bản (10 phút)

| Phút | Vai trò | Thao tác | Điểm nhấn với hội đồng |
| --- | --- | --- | --- |
| 0:00–1:00 | – | Giới thiệu bài toán: hồ sơ giấy, nhập tay số CCCD, khó tra cứu, rủi ro lộ dữ liệu cá nhân. Chiếu trang Tổng quan của `admin` | Một máy chủ trong công ty, máy khác dùng trình duyệt; không cần Internet, không tốn phí |
| 1:00–3:30 | HR | **Thêm hồ sơ → Từ CCCD và CV**: tải ảnh 01 mặt trước, mặt sau và CV → **Nhận diện** | Máy đọc QR điền họ tên, ngày sinh, số CCCD… trong khoảng 1 giây; nhãn nguồn QR/OCR |
| | | Bôi đen đoạn "Kỹ năng" trong CV → **Đưa vào trường…** | Trích CV có kiểm soát, không tự bịa thông tin |
| | | Nhập số điện thoại → **Lưu hồ sơ** → hồ sơ Nháp có mã | Kết quả máy đọc không tự lưu khi HR chưa xác nhận |
| 3:30–4:30 | HR | Tải ảnh thẻ 12 (không QR) → **Nhận diện** | Trường không chắc chắn tô vàng; chưa tích **Đã kiểm tra** thì không lưu được |
| | | Thử tải lại ảnh 01 | Báo trùng CCCD, nút **Mở hồ sơ cũ**, không tạo hồ sơ mới (kịch bản 5) |
| 4:30–6:00 | HR → Quản lý | HR: ghi nhận đồng ý xử lý dữ liệu → **Gửi duyệt**. Quản lý: **Duyệt hồ sơ** → mở hồ sơ → **Trả lại** có lý do. HR bổ sung, gửi lại; Quản lý **Duyệt hồ sơ** | Hai điểm kiểm soát của con người; lý do và lịch sử ở tab Lịch sử thay đổi (kịch bản 6) |
| | HR | Thử duyệt hồ sơ chính mình nhập | Bị chặn (kịch bản 7) |
| 6:00–7:00 | HR | Tab Tuyển dụng: lần ứng tuyển **Đạt** → **Tiếp nhận vào làm** → mã nhân viên. Tab Quá trình làm việc: **Thêm đợt làm việc** tại công ty khách hàng | Sinh mã tự động; theo dõi công nhân cung ứng (v1.1) |
| 7:00–8:00 | Viewer | Mở cùng hồ sơ | Số CCCD bị che, không có nút sửa, không xem tài liệu; gõ thẳng địa chỉ sửa → trang "Không có quyền" (kịch bản 2) |
| 8:00–9:00 | Quản lý | Tổng quan: bấm thẻ **Thiếu giấy tờ** → danh sách đúng số dòng. Ô tìm nhanh gõ `nguyen van` không dấu. **Xuất Excel** danh sách đang lọc | Số trên thẻ khớp danh sách (kịch bản 11, 12, 13); CCCD trong file Excel bị che |
| 9:00–10:00 | Admin | **Nhật ký thao tác**: lọc theo mã hồ sơ vừa tạo, xem các bước vừa làm. Mở thư mục `backups`, chỉ file sao lưu mã hóa có ngày giờ | Mọi thao tác có nhật ký; dữ liệu cá nhân trong nhật ký được che; sao lưu tự động mỗi ngày, file sao lưu được mã hóa |

## Câu hỏi hội đồng hay hỏi

| Câu hỏi | Trả lời ngắn |
| --- | --- |
| Đọc CCCD có chính xác không? | Trên bộ ảnh giả: QR đúng 100% trường, OCR 87% trường; trường không chắc chắn luôn tô vàng để HR kiểm tra (`docs/do-chinh-xac-nhan-dien.md`). Thẻ thật cần thử tại chỗ |
| Dữ liệu có bị lộ không? | Số CCCD, CMND, địa chỉ thường trú, lương mã hóa khi lưu; che số theo quyền; mọi lần xem số đầy đủ, xem/tải tài liệu, xuất báo cáo đều ghi nhật ký; tệp chỉ tải qua trang có kiểm tra quyền |
| Máy hỏng thì sao? | Sao lưu tự động mỗi ngày, chép ra ổ ngoài; phục hồi trên máy mới bằng `Phuc hoi.bat` (đã thử: xóa sạch rồi phục hồi, dữ liệu và tệp khớp hoàn toàn) |
| Mất khóa thì sao? | Không đọc lại được dữ liệu đã mã hóa và bản sao lưu; vì vậy quy trình bắt buộc cất khóa ra USB/giấy niêm phong ngay khi cài |
| Có cần Internet, có tốn phí không? | Không; mọi chức năng chạy trên máy (Tesseract, OpenCV, PostgreSQL), phần mềm nguồn mở |
| Hết hạn lưu trữ thì xóa thế nào? | Admin duyệt hủy ở Cài đặt → Chờ hủy: ẩn danh hóa (xóa dữ liệu cá nhân và tệp, giữ mã và nhật ký), sinh biên bản hủy |

## Dự phòng khi có sự cố trong lúc trình diễn

- Nhận diện chậm hoặc lỗi: dùng hồ sơ đã nhập sẵn trước buổi trình diễn, chuyển sang phần duyệt.
- Mạng nội bộ lỗi: trình diễn trên chính máy chủ (`http://localhost:8000`).
- Hệ thống không chạy: mở `docs/nghiem-thu.md` và ảnh chụp trong `docs/screenshots/` để trình bày kết quả nghiệm thu.
