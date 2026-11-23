# So sánh thời gian xử lý một hồ sơ: thủ công và dùng PA Worker

Tài liệu phục vụ chương nghiệp vụ của khóa luận (yêu cầu mục XI: "Bảng so sánh thời gian xử lý một hồ sơ: thủ công và dùng phần mềm (đo trên dữ liệu giả lập)").

## 1. Phần đo được bằng máy: thời gian hệ thống xử lý

Đo ngày 24/11/2026 bằng `scripts/do_thoi_gian_xu_ly.py`. Trình duyệt tự động (Playwright, Chromium) thao tác như người dùng trên bản Demo: 500 hồ sơ giả lập, máy phát triển Windows 11 chạy Docker Desktop. Mỗi bước đo trên **5 hồ sơ** (5 thẻ CCCD giả có QR). Thời gian tính từ lúc bấm nút tới khi trang kết quả hiện xong, **không gồm thời gian người đọc và gõ**.

| Bước | Ai làm | Trung vị (giây) | Lớn nhất (giây) |
| --- | --- | --- | --- |
| Nhận diện ảnh CCCD hai mặt (kiểm tra ảnh, đọc QR, OCR, dựng màn hình đối chiếu) | Máy | 1,17 | 1,17 |
| Lưu hồ sơ Nháp (kiểm tra trùng, lưu hồ sơ, giấy tờ, ảnh, nhật ký) | Máy | 0,76 | 0,79 |
| Ghi nhận đồng ý xử lý dữ liệu | Máy | 0,66 | 0,69 |
| Gửi duyệt (kiểm tra đủ trường bắt buộc) | Máy | 0,64 | 0,69 |
| Quản lý duyệt hồ sơ | Máy | 0,64 | 0,66 |
| **Tổng thời gian máy xử lý một hồ sơ** | | **khoảng 3,9** | |

Các số liệu liên quan đã đo ở phase trước:
- Đọc một lượt ảnh CCCD (chỉ phần nhận diện): trung vị 0,46 giây, lớn nhất 0,59 giây (`docs/do-chinh-xac-nhan-dien.md`).
- Mở danh sách, lọc, tìm kiếm với 500 hồ sơ: dưới 0,4 giây mỗi trang (`docs/hieu-nang.md`; yêu cầu dưới 2 giây).
- Nhập 1.000 dòng từ file Excel: 13–22 giây (`docs/hieu-nang.md`).

Ảnh giả sạch nên đọc nhanh và chính xác hơn ảnh chụp thật. Khi viết khóa luận, đo lại trên máy và ảnh chụp tại doanh nghiệp.

## 2. Phần cần người viết khóa luận tự đo: thời gian thao tác của con người

Máy không đo được thời gian người đọc, đối chiếu và gõ, cũng không đo được cách làm thủ công. Cách đo đề xuất:
- Chọn **10 hồ sơ giả** (ảnh trong `tests/fixtures/cccd/`, CV trong `tests/fixtures/cv/`).
- Cùng một người làm hai cách, bấm giờ bằng đồng hồ bấm giây.
- Ghi từng hồ sơ, lấy trung vị.

| Bước | Thủ công (giây) | PA Worker (giây) | Ghi chú cách đo |
| --- | --- | --- | --- |
| Nhập thông tin CCCD (họ tên, số CCCD, ngày sinh, giới tính, quê quán, thường trú, ngày cấp…) | [cần đo] | [cần đo] | Thủ công: gõ vào Excel từ ảnh. PA Worker: từ lúc chọn ảnh tới khi tích xong các trường tô vàng |
| Kiểm tra trùng | [cần đo] | 0 (tự động) | Thủ công: tra trên file Excel tổng |
| Nhập thông tin từ CV (kỹ năng, học vấn, kinh nghiệm) | [cần đo] | [cần đo] | PA Worker: bôi đen, "Đưa vào trường…" |
| Lập bìa hồ sơ, đánh mã | [cần đo] | 0 (tự sinh mã) | |
| Chuyển duyệt và duyệt | [cần đo] | [cần đo] | Không tính thời gian chờ người duyệt |
| Lập báo cáo tháng (số công nhân theo bộ phận, giới tính, nhóm tuổi) | [cần đo] | [cần đo] | PA Worker: mở Báo cáo, chọn loại, Xuất Excel |
| **Tổng một hồ sơ** | [cần đo] | [cần đo] | |

Nếu không có điều kiện đo, có thể dùng số ước lượng nhưng phải ghi rõ **[Giả định]** và nguồn ước lượng (ví dụ phỏng vấn nhân viên HR).

## 3. Cách chạy lại phép đo của máy

```
py -3.12 scripts/do_thoi_gian_xu_ly.py
```

Cần bản Demo đang chạy ở `http://localhost:8000` và biến môi trường `PA_TEST_PASSWORD` là mật khẩu chung của tài khoản `hr`, `quanly`. Script tự sinh bộ thẻ giả mới (số CCCD không trùng lần trước), tạo 5 hồ sơ, rồi gửi duyệt và duyệt 5 hồ sơ Nháp có sẵn của dữ liệu mẫu.
