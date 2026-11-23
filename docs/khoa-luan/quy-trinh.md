# Quy trình tiếp nhận hồ sơ công nhân: trước và sau khi có PA Worker

Tài liệu phục vụ chương nghiệp vụ của khóa luận (yêu cầu mục XI). Quy trình "sau" lấy theo phần mềm đã nghiệm thu (yêu cầu mục IX). Quy trình "trước" là mô tả điển hình cách làm thủ công bằng giấy và bảng tính **[Giả định]**; người viết khóa luận cần đối chiếu với cách làm thực tế tại doanh nghiệp khảo sát và sửa lại cho đúng.

## 1. Trước khi có phần mềm (thủ công) [Giả định]

```mermaid
flowchart TD
    A["Ứng viên nộp bản photo CCCD, CV, đơn xin việc"] --> B["HR nhận hồ sơ giấy, kiểm tra đủ giấy tờ bằng mắt"]
    B --> C["HR gõ tay họ tên, số CCCD, ngày sinh, địa chỉ… vào Excel"]
    C --> D{"Tra trùng bằng Ctrl+F trên nhiều file Excel"}
    D -- "Trùng" --> E["Tìm bìa hồ sơ cũ trong tủ, cập nhật tay"]
    D -- "Không trùng" --> F["Lập bìa hồ sơ giấy, đánh số thủ công"]
    F --> G["Chuyển hồ sơ giấy cho Quản lý ký duyệt"]
    G --> H{"Quản lý xem hồ sơ"}
    H -- "Thiếu" --> I["Trả lại bằng lời hoặc ghi chú giấy, không lưu lý do"]
    I --> B
    H -- "Đạt" --> J["Ký duyệt trên giấy"]
    J --> K["Cấp mã nhân viên bằng sổ theo dõi"]
    K --> L["Cuối tháng tổng hợp báo cáo bằng tay từ nhiều file Excel"]
```

Điểm yếu thường gặp:
- Gõ tay số CCCD 12 chữ số dễ sai; tra trùng thủ công dễ sót.
- Bản photo CCCD để trong tủ và trong file Excel không bảo vệ, ai mở được file thì xem được số định danh; không biết ai đã xem.
- Lý do trả lại, lịch sử sửa đổi không được ghi lại.
- Không biết hồ sơ nào đến hạn hủy theo thời hạn lưu trữ.
- Báo cáo mất nhiều thời gian và dễ lệch số giữa các file.

## 2. Sau khi có PA Worker

```mermaid
flowchart TD
    A["Ứng viên nộp CCCD (chụp hai mặt) và CV"] --> B["HR tải ảnh CCCD, CV lên PA Worker"]
    B --> C["Máy kiểm tra chất lượng ảnh, đọc QR, OCR phần còn thiếu, trích văn bản CV (khoảng 1 giây, không cần Internet)"]
    C --> D["Màn hình đối chiếu: trường không chắc chắn tô vàng"]
    D --> E["ĐIỂM KIỂM SOÁT 1: HR đối chiếu với ảnh, sửa, tích Đã kiểm tra"]
    E --> F{"Trùng số CCCD? (tự kiểm tra bằng giá trị băm)"}
    F -- "Trùng" --> G["Mở hồ sơ cũ để cập nhật, không tạo hồ sơ mới"]
    F -- "Không trùng" --> H["Lưu Nháp, tự sinh mã hồ sơ, ghi nhật ký"]
    H --> I["Ghi nhận đồng ý xử lý dữ liệu cá nhân, gửi duyệt"]
    I --> J{"ĐIỂM KIỂM SOÁT 2: Quản lý nhân sự duyệt (không tự duyệt hồ sơ mình nhập)"}
    J -- "Cần bổ sung, có lý do" --> E
    J -- "Từ chối, có lý do" --> K["Bị từ chối, tự Lưu trữ sau 30 ngày"]
    J -- "Duyệt" --> L["Đã xác minh"]
    L --> M["Lần ứng tuyển Đạt: Tiếp nhận vào làm, tự sinh mã nhân viên"]
    M --> N["Theo dõi điều chuyển, hợp đồng, đợt làm việc tại công ty khách, lương"]
    N --> O["Dashboard, báo cáo, xuất Excel tức thời (CCCD che theo quyền)"]
    N --> P["Hết thời hạn lưu trữ: Admin duyệt hủy, ẩn danh hóa, biên bản hủy"]
```

## 3. So sánh

| Khía cạnh | Trước [Giả định] | Sau (PA Worker) |
| --- | --- | --- |
| Nhập thông tin CCCD | Gõ tay toàn bộ | Máy đọc QR/OCR, HR chỉ đối chiếu trường tô vàng |
| Kiểm tra trùng | Tra thủ công trên nhiều file | Tự động theo số CCCD (giá trị băm), cảnh báo theo SĐT, họ tên + ngày sinh |
| Duyệt hồ sơ | Ký giấy, lý do không lưu | Trạng thái rõ ràng, lý do bắt buộc, không tự duyệt, lịch sử đầy đủ |
| Bảo vệ dữ liệu cá nhân | Bản photo và file Excel không kiểm soát | Mã hóa số định danh, che theo quyền, nhật ký mọi lần xem/tải/xuất, ghi nhận đồng ý |
| Thời hạn lưu trữ | Không theo dõi | Tự tính hạn, danh sách chờ hủy, ẩn danh hóa có biên bản |
| Báo cáo | Tổng hợp tay cuối tháng | Dashboard và báo cáo tức thời, số khớp danh sách |
| Sao lưu | Phụ thuộc cá nhân | Tự sao lưu mỗi ngày, file mã hóa, đã thử phục hồi |
