# Đối chiếu biện pháp bảo vệ dữ liệu cá nhân của PA Worker với quy định pháp luật

Tài liệu phục vụ chương nghiệp vụ của khóa luận (yêu cầu mục XI). Căn cứ (yêu cầu mục VIII):
- **Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15**, Quốc hội thông qua ngày 26/06/2025, hiệu lực từ 01/01/2026.
- **Nghị định 356/2025/NĐ-CP** ngày 31/12/2025, quy định chi tiết một số điều và biện pháp thi hành Luật.

> **Lưu ý quan trọng.** Đơn vị phát triển phần mềm không phải đơn vị tư vấn pháp lý. Bảng dưới xếp theo **nhóm nghĩa vụ** của văn bản, **không ghi số điều** vì chưa đối chiếu được với văn bản gốc. Người viết khóa luận và pháp chế doanh nghiệp cần đọc toàn văn hai văn bản và điền cột "Điều khoản" trước khi sử dụng. Toàn văn tham khảo:
> - Luật 91/2025/QH15: [Cổng thông tin Bộ Công an](https://mps.gov.vn/chinh-sach-phap-luat/co-so-du-lieu-van-ban/luat-bao-ve-du-lieu-ca-nhan-1753688803), [Thư viện số Quốc hội](https://thuvienso.quochoi.vn/handle/11742/103334), [Thư viện pháp luật](https://thuvienphapluat.vn/van-ban/Bo-may-hanh-chinh/Luat-Bao-ve-du-lieu-ca-nhan-2025-so-91-2025-QH15-625628.aspx)
> - Nghị định 356/2025/NĐ-CP: [Thư viện pháp luật](https://thuvienphapluat.vn/phap-luat/toan-van-nghi-dinh-3562025ndcp-quy-dinh-chi-tiet-luat-bao-ve-du-lieu-ca-nhan-chi-tiet-ra-sao-249247.html)

Cột "Ai thực hiện": **PM** = phần mềm đã có chức năng; **DN** = doanh nghiệp phải tự tổ chức thực hiện (phần mềm không thay thế được); **PM + DN** = phần mềm hỗ trợ, doanh nghiệp vận hành.

## 1. Bảng đối chiếu

| # | Nhóm nghĩa vụ | Điều khoản | Biện pháp trong PA Worker | Ai thực hiện | Bằng chứng |
| --- | --- | --- | --- | --- | --- |
| 1 | Nguyên tắc xử lý: đúng mục đích, tối thiểu dữ liệu | [cần pháp chế kiểm tra] | Chỉ thu thập các trường cần cho quản lý nhân sự (yêu cầu mục VI); không có trường tôn giáo, sức khỏe, sinh trắc học; không dùng AI, không gửi dữ liệu ra ngoài | PM | `docs/thiet-ke/models.md`; yêu cầu mục VI |
| 2 | Sự đồng ý của chủ thể dữ liệu | [cần pháp chế kiểm tra] | Ghi nhận đồng ý (ngày, hình thức, người ghi nhận, tệp biên bản ký giấy) **bắt buộc trước khi gửi duyệt**; mẫu văn bản đồng ý in sẵn họ tên, mã hồ sơ | PM + DN | `docs/thiet-ke/mau-dong-y.md` (pháp chế duyệt 5 câu hỏi cuối tệp); kịch bản 6 |
| 3 | Phân loại dữ liệu cơ bản, nhạy cảm | [cần pháp chế kiểm tra] (Nghị định 356 mở rộng danh mục) | Số định danh, số CMND cũ, địa chỉ thường trú, lương và đơn giá, giá trị chi tiết trong nhật ký được **mã hóa khi lưu** (Fernet/AES); ảnh CCCD chỉ xem qua trang có kiểm tra quyền. DN xác định trường nào là dữ liệu nhạy cảm theo danh mục | PM + DN | `docs/thiet-ke/kien-truc.md` mục 6; test mã hóa |
| 4 | Quyền được biết, truy cập, chỉnh sửa | [cần pháp chế kiểm tra] (Nghị định 356 quy định thời hạn phản hồi yêu cầu) | HR xem, in và sửa thông tin hồ sơ; lịch sử thay đổi từng trường có người, thời điểm | PM + DN | Tab Lịch sử thay đổi; nhật ký thao tác |
| 5 | Quyền yêu cầu xóa dữ liệu | [cần pháp chế kiểm tra] | **Ẩn danh hóa theo yêu cầu của chủ thể**: Admin xóa dữ liệu cá nhân và tệp của hồ sơ, bắt buộc lý do và số/ngày đơn, sinh biên bản hủy (`docs/lam-ro-yeu-cau.md` câu 38) | PM + DN | Test ẩn danh hóa; biên bản hủy |
| 6 | Quyền rút lại sự đồng ý | [cần pháp chế kiểm tra] | Chưa có nút "rút lại đồng ý" riêng. Quy trình đề xuất: ghi nhận đơn, chuyển hồ sơ Lưu trữ, ẩn danh hóa theo yêu cầu khi không còn căn cứ xử lý khác | DN (PM hỗ trợ một phần) | Ghi vào giới hạn đã biết (`docs/ban-giao.md`) |
| 7 | Biện pháp bảo vệ kỹ thuật | [cần pháp chế kiểm tra] | Phân quyền 4 vai trò kiểm tra ở máy chủ (76 URL × 5 trạng thái đã rà); che số CCCD theo quyền trên màn hình, file Excel, bản in; mật khẩu băm PBKDF2, tối thiểu 8 ký tự có chữ và số, khóa 15 phút sau 5 lần sai, tự đăng xuất 30 phút; chống SQL injection, XSS (CSP), CSRF, kiểm tra định dạng thật của tệp tải lên; container không chạy bằng root; quét lỗ hổng định kỳ | PM | `docs/ra-soat-bao-mat.md` |
| 8 | Ghi nhật ký xử lý dữ liệu | [cần pháp chế kiểm tra] | Nhật ký chỉ thêm, không sửa, không xóa (có trigger CSDL) cho mọi thao tác tạo, sửa, đổi trạng thái, **xem số CCCD đầy đủ, xem/tải tài liệu, xuất, in, sao lưu, phục hồi**; giá trị cá nhân trong nhật ký được mã hóa và chỉ Admin, Quản lý xem | PM | Trang Nhật ký thao tác; `apps/audit/` |
| 9 | Thời hạn lưu trữ, xóa, hủy dữ liệu | [cần pháp chế kiểm tra] | Tự tính hạn lưu trữ cho mọi hồ sơ Lưu trữ (ứng viên không đạt 12 tháng; công nhân đã nghỉ 10 năm từ ngày chấm dứt hợp đồng lao động); danh sách chờ hủy; Admin duyệt hủy = ẩn danh hóa kèm biên bản hủy | PM + DN | `docs/lam-ro-yeu-cau.md` câu 2, 44; kịch bản Phase 7 |
| 10 | Sao lưu, bảo đảm khả năng phục hồi | [cần pháp chế kiểm tra] | Tự sao lưu mỗi ngày; file sao lưu **mã hóa**, không chứa khóa; tự kiểm tra đọc lại được; đã thử phục hồi trên bản cài trống (kịch bản 17) | PM + DN | `docs/nghiem-thu.md` kịch bản 17 |
| 11 | Chuyển dữ liệu ra nước ngoài, thuê bên thứ ba xử lý | [cần pháp chế kiểm tra] | Mọi chức năng chạy trên máy chủ trong doanh nghiệp, không gọi dịch vụ Internet; API OCR ngoài **tắt mặc định**, bật thì cảnh báo và ghi nhật ký từng lần gửi | PM + DN | `docs/thiet-ke/kien-truc.md` mục 4 |
| 12 | Thông báo khi lộ, mất dữ liệu | [cần pháp chế kiểm tra] (Nghị định 356 có quy định thời hạn thông báo, ví dụ 72 giờ trong lĩnh vực ngân hàng) | Nhật ký thao tác và nhật ký hệ thống giúp xác định ai đã xem, tải, xuất dữ liệu gì, khi nào | DN (PM hỗ trợ điều tra) | Quy trình nội bộ của DN |
| 13 | Bộ phận/nhân sự bảo vệ dữ liệu cá nhân, đánh giá tác động | [cần pháp chế kiểm tra] | Tài liệu thiết kế, rà soát bảo mật và bảng này là đầu vào cho hồ sơ đánh giá tác động | DN | `docs/thiet-ke/`, `docs/ra-soat-bao-mat.md` |
| 14 | Bảo mật đường truyền | [cần pháp chế kiểm tra] | Bản bàn giao chạy HTTP trong mạng nội bộ; khi triển khai thật bật HTTPS qua reverse proxy (`HTTPS=1`: cookie bảo mật, HSTS) | PM + DN | `docs/huong-dan-cai-dat.md` mục 12 |

## 2. Việc doanh nghiệp cần làm thêm (ngoài phần mềm)

- Ban hành quy định nội bộ về bảo vệ dữ liệu cá nhân: ai được cấp vai trò nào, quy trình cấp và thu hồi tài khoản khi nhân viên nghỉ.
- Cất giữ khóa mã hóa và bản sao lưu theo quy trình (`docs/huong-dan-cai-dat.md` mục 5, 9).
- Pháp chế duyệt mẫu văn bản đồng ý (`docs/thiet-ke/mau-dong-y.md`) và thời hạn lưu trữ trong Cài đặt.
- Lập quy trình tiếp nhận yêu cầu của chủ thể dữ liệu (truy cập, chỉnh sửa, xóa, rút lại đồng ý) và thời hạn phản hồi theo Nghị định 356.
- Lập quy trình xử lý sự cố lộ, mất dữ liệu và thông báo cho cơ quan chức năng.
- Bản gốc hợp đồng lao động, bản cam kết, bảng lương vẫn lưu ngoài phần mềm theo quy định (`docs/lam-ro-yeu-cau.md` câu 47).
