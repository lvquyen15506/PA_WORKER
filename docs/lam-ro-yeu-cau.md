# Làm rõ yêu cầu – PA Worker

Ngày chốt: 21/11/2026 · Kết quả Phase 0 · Áp dụng cho `docs/yeu-cau.md` v1.0

Tài liệu này ghi các quyết định trả lời câu hỏi Phase 0. `docs/yeu-cau.md` là bản khách hàng đã ký, **không sửa**. Khi tài liệu này khác `docs/yeu-cau.md` thì **theo tài liệu này**.

Ký hiệu:
- **[Đồng ý]**: theo đề xuất của đơn vị phát triển.
- **[Sửa]**: khách hàng sửa đề xuất.
- **[Giả định]**: chưa có căn cứ chắc chắn, cần kiểm chứng khi triển khai thật.

## A. Thiết kế dữ liệu

### 1. Mẫu che số CCCD [Đồng ý]
Mẫu ở mục III (`0791•••••2345`) dài 13 ký tự, không khớp 12 chữ số. Chốt: hiện 4 số đầu, 4 dấu `•`, 4 số cuối, ví dụ `0791••••2345`. Mẫu này dùng chung cho màn hình, file Excel và bản in.

### 2. Hủy hồ sơ hết hạn lưu trữ [Đồng ý]
- Phần này nằm trong MVP.
- "Hủy" ở mục VIII nghĩa là **ẩn danh hóa**, không xóa cứng bản ghi. Cụ thể:
  - Xóa dữ liệu cá nhân và tệp đính kèm.
  - Giữ bản ghi khung, mã hồ sơ, mã nhân viên và nhật ký thao tác.
- Admin duyệt hủy từ danh sách hồ sơ hết hạn. Mỗi lần hủy sinh **biên bản hủy** (ai, khi nào, những hồ sơ nào) và ghi nhật ký.
- Thời hạn lưu trữ theo mục VIII:
  - Ứng viên không đạt: 12 tháng kể từ ngày có kết quả.
  - Công nhân đã nghỉ: 10 năm kể từ ngày nghỉ.
  - Cả hai cấu hình được.
- "Chờ hủy" **không phải trạng thái mới**. Đây là danh sách tính tự động (hồ sơ Lưu trữ đã quá thời hạn). Hồ sơ vẫn ở trạng thái Lưu trữ.

### 3. Trạng thái xác minh tài liệu [Đồng ý]
- Đây là bộ trạng thái thứ 4, gồm: **Chưa xác minh · Đã đối chiếu bản gốc · Không hợp lệ**.
- Khai báo bằng `TextChoices`. Chỉ dùng trong tab Tài liệu; không đưa vào dashboard, bộ lọc danh sách hồ sơ hay báo cáo.
- Màu nhãn lần lượt: xám, xanh lá, đỏ (đã ghi vào skill `pa-ui` mục 5).

### 4. Nhóm tài liệu bắt buộc [Đồng ý]
- Loại tài liệu có thêm trường **nhóm bắt buộc**. Hồ sơ đủ giấy tờ khi mỗi nhóm có ít nhất một tài liệu. **[Giả định]** Tài liệu ở trạng thái "Không hợp lệ" không được tính.
- Mặc định có 4 nhóm:
  - CCCD mặt trước
  - CCCD mặt sau
  - Ảnh chân dung
  - CV hoặc Đơn xin việc (hai loại chung một nhóm)
- Ảnh chân dung của hồ sơ chính là tài liệu loại "Ảnh chân dung", không lưu riêng hai nơi.

### 5. Trường bắt buộc theo giai đoạn [Sửa]
- **Lưu Nháp:** chỉ bắt buộc **họ tên + số điện thoại**, để nhận được ứng viên chỉ có CV.
- **Gửi duyệt:** bắt buộc thêm số định danh, ngày sinh, giới tính, liên hệ khẩn cấp và đồng ý xử lý dữ liệu. Các trường khác theo bảng ở mục VI.
- **Kiểm tra trùng:**
  - Đã nhập số CCCD: kiểm tra trùng ngay theo giá trị băm. Nếu trùng thì hiện hồ sơ cũ và cho chọn "Mở hồ sơ cũ".
  - Chưa có số CCCD: cảnh báo trùng theo **SĐT**, hoặc theo **họ tên + ngày sinh** (so khớp không dấu). Chỉ cảnh báo, không chặn.
- Mã hồ sơ vẫn sinh khi lưu Nháp lần đầu.

### 6. Công nhân quay lại làm việc [Đồng ý]
- Hồ sơ Lưu trữ có thao tác **"Mở lại hồ sơ"**: hồ sơ về Nháp và tạo một lần ứng tuyển mới. Thao tác này được ghi nhật ký.
- Người đã có mã nhân viên **giữ mã cũ** khi được tiếp nhận lại.
- Mã đã cấp (mã hồ sơ, mã NV) **không bao giờ cấp cho người khác**, kể cả sau khi hồ sơ bị ẩn danh hóa.
- **[Giả định]** Hồ sơ đã ẩn danh hóa (câu 2) thì không mở lại được.

### 7. Điều kiện "Tiếp nhận vào làm" [Đồng ý]
Nút "Tiếp nhận vào làm" chỉ hiện, và máy chủ chỉ chấp nhận, khi lần ứng tuyển ở trạng thái **Đạt** và hồ sơ ở trạng thái **Đã xác minh**.

### 8. Không tự duyệt [Đồng ý]
- Người không được duyệt hoặc trả lại một lần gửi duyệt gồm: **người tạo hồ sơ** và **người gửi duyệt lần đó**.
- Admin duyệt thay được. **[Giả định]** Nếu Admin chính là người tạo hoặc người gửi lần đó thì Admin cũng bị chặn.

### 9. Chuyển trạng thái xác minh [Đồng ý + Sửa]

| Từ | Sang | Ai | Ghi chú |
| --- | --- | --- | --- |
| Nháp | Chờ duyệt | HR, QL, Admin | Kiểm tra đủ trường bắt buộc (câu 5) |
| Chờ duyệt | Đã xác minh / Cần bổ sung / Bị từ chối | QL, Admin | Cần bổ sung, Bị từ chối bắt buộc ghi lý do; áp dụng câu 8 |
| Cần bổ sung | Chờ duyệt | HR, QL, Admin | Sau khi bổ sung |
| Đã xác minh | Chờ duyệt | Tự động | Khi sửa họ tên, ngày sinh hoặc số CCCD |
| Bị từ chối | Lưu trữ | HR, QL, Admin | Chỉ được chuyển sang Lưu trữ |
| Nháp, Cần bổ sung, Đã xác minh | Lưu trữ | HR, QL, Admin; hoặc tự động | Có hộp xác nhận. **[Giả định]** Được chuyển thủ công từ ba trạng thái này |
| Lưu trữ | Nháp | HR, QL, Admin | "Mở lại hồ sơ" (câu 6) |

- **Chờ duyệt:** HR không sửa được hồ sơ. QL và Admin chỉ thao tác duyệt, trả lại hoặc từ chối.
- **Lưu trữ:** chỉ xem.
- **Tự động Lưu trữ** [Sửa]: một tác vụ chạy hằng ngày, mỗi lần chuyển đều ghi nhật ký (người thực hiện là "Hệ thống").
  - Hồ sơ có trạng thái làm việc **Đã nghỉ việc**: tự Lưu trữ sau **30 ngày kể từ ngày nghỉ**, để HR còn bổ sung giấy tờ nghỉ việc.
  - Hồ sơ **chưa có mã NV** mà lần ứng tuyển gần nhất là **Không đạt** hoặc **Ứng viên từ chối**: tự Lưu trữ sau **30 ngày kể từ ngày có kết quả**.
  - Cả hai số ngày cấu hình được trong Cài đặt.

### 10. Thêm tài liệu khi đã xác minh [Đồng ý]
HR được **thêm** tài liệu mới khi hồ sơ ở Đã xác minh, và trạng thái hồ sơ không đổi. Việc **thay thế** tài liệu vẫn theo ma trận mục III: HR chỉ thay thế khi hồ sơ ở Nháp hoặc Cần bổ sung.

### 11. Tab "Lịch sử thay đổi" [Đồng ý]
- Mọi vai trò xem được **dòng thời gian trạng thái**: thời điểm, trạng thái cũ, trạng thái mới, người thực hiện và lý do.
- Chi tiết **giá trị trước/sau từng trường** (lấy từ nhật ký thao tác) chỉ Admin và Quản lý nhân sự xem.

### 12. Xem số CCCD đầy đủ [Đồng ý]
- Số CCCD luôn hiện ở dạng che (câu 1).
- Vai trò có quyền bấm **"Hiện số đầy đủ"** thì mới thấy số đầy đủ, và mỗi lần bấm ghi một dòng nhật ký. Ảnh CCCD áp dụng tương tự: mở xem hoặc tải xuống đều ghi nhật ký.

### 13. Trường nhạy cảm ẩn với Viewer [Đồng ý]
- **Viewer không thấy:**
  - Số CCCD (chỉ thấy dạng che)
  - Số CMND cũ
  - Địa chỉ thường trú/cư trú
  - Quê quán / nơi đăng ký khai sinh
  - Ảnh CCCD
- **Viewer vẫn thấy:** SĐT và nơi ở hiện tại.
- **Viewer không** xem trước và không tải được tài liệu.

### 14. Trình độ học vấn [Đồng ý]
EducationLevels là danh mục do Admin quản lý trong Cài đặt, có thứ tự cấp bậc. Bộ lọc và báo cáo theo trình độ lấy **trình độ cao nhất** của mỗi người.

### 15. Vị trí làm việc [Đồng ý]
- Thông tin làm việc lưu **Bộ phận** và **Tổ (không bắt buộc)**. **[Giả định]** Bộ phận là bắt buộc. Nếu có chọn Tổ thì Tổ phải thuộc Bộ phận đã chọn.
- Phòng ban suy ra từ Bộ phận.
- "Người quản lý trực tiếp" liên kết tới một **hồ sơ công nhân khác**, không bắt buộc.

## B. Mặc định

### 16. Kiểm tra tuổi [Sửa]
- **Dưới 15 tuổi:** chặn lưu.
- **Từ 15 đến dưới 18 tuổi:** hiện cảnh báo, vẫn lưu được.
- Chỉ kiểm tra khi đã nhập ngày sinh.

### 17. Thẻ "Hợp đồng sắp hết hạn" [Đồng ý]
Thẻ này trên Dashboard chỉ đếm hợp đồng. CCCD sắp hết hạn hiện trong "danh sách việc cần làm" trên Dashboard. Cả hai dùng chung ngưỡng số ngày trong Cài đặt.

### 18. Viewer và in báo cáo [Đồng ý]
In báo cáo được coi như xuất báo cáo. Viewer chỉ xem thống kê, không xuất Excel và không in.

### 19. Trang ngoài danh sách 12 trang [Đồng ý]

| Trang | Vị trí | Ai xem |
| --- | --- | --- |
| Giới thiệu | Liên kết ở chân trang | Mọi người đã đăng nhập |
| Đổi mật khẩu | Menu người dùng ở thanh trên | Mọi người đã đăng nhập |
| Lịch sử đăng nhập | Tab trong trang Tài khoản | Admin |
| Danh sách chờ hủy (câu 2) | Tab trong trang Cài đặt | Admin |

### 20. Cấu trúc QR của CCCD [Đồng ý + Giả định]
- **[Giả định]** QR của CCCD gắn chip mẫu 2021 theo định dạng công khai phổ biến, phân cách bằng `|`:
  `số CCCD|số CMND cũ|họ tên|ngày sinh (ddmmyyyy)|giới tính|nơi thường trú|ngày cấp (ddmmyyyy)`.
  Định dạng này chưa được kiểm chứng bằng thẻ thật.
- **Thứ tự trường và ký tự phân cách cấu hình được trong Cài đặt**, không hard-code. Mỗi mẫu thẻ có cấu hình riêng:
  - CCCD 2021
  - Thẻ Căn cước 2024: **[Giả định]** cấu hình ban đầu giống mẫu 2021 cho tới khi kiểm chứng.
- Khi thử bằng thẻ thật tại chỗ khách hàng, chỉ cần sửa cấu hình, không sửa code. Không ghi dữ liệu thẻ thật vào code, test hay tài liệu.
- Bộ ảnh CCCD giả (Phase 5) sinh QR theo đúng cấu hình đang dùng. Vì vậy kịch bản nghiệm thu 3 chỉ chứng minh bộ tách trường khớp với cấu hình, chưa chứng minh khớp thẻ thật.
- CCCD mẫu 2016 không có QR chứa thông tin, nên chỉ đọc bằng OCR.

### 21. Mẫu văn bản đồng ý và file Excel mẫu [Đồng ý]
Ở Phase 1, đơn vị phát triển soạn nháp hai thứ để khách hàng duyệt:
- Mẫu văn bản đồng ý xử lý dữ liệu cá nhân.
- Danh sách cột của file Excel mẫu dùng để nhập hàng loạt.

### 22. Kế hoạch giai đoạn [Đồng ý]
- Làm theo `docs/phases.md` (Phase 0–8), không theo 8 giai đoạn ở mục XI.
- Phase 1 bổ sung **sơ đồ kiến trúc**, **phác thảo 12 trang**, **mẫu văn bản đồng ý** và **cột file Excel mẫu**.

### 23. Lệnh ruff [Đồng ý]
Cả `ruff check` và `ruff format` đều chạy trong container `web` (đã sửa trong CLAUDE.md).

### 24. Kiểm tra giao diện ở Phase 2 [Đồng ý]
Phase 2 dùng giao diện tạm. Ở phase này, bước b của vòng lặp tự kiểm thử chỉ gồm: đăng nhập, mở trang, thử form, đọc lỗi console và chụp màn hình. Checklist mục 10 của skill `pa-ui` áp dụng đầy đủ từ Phase 3.
