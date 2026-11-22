# Làm rõ yêu cầu – PA Worker

Ngày chốt: 21/11/2026 (mục F: 23/11/2026) · Kết quả Phase 0 và rà thiết kế Phase 1 · Áp dụng cho `docs/yeu-cau.md` v1.0 và phiếu thay đổi v1.1 (mục F)

Tài liệu này ghi các quyết định trả lời câu hỏi Phase 0 và các quyết định phát sinh khi thiết kế. `docs/yeu-cau.md` là bản khách hàng đã ký, **không sửa**. Khi tài liệu này khác `docs/yeu-cau.md` thì **theo tài liệu này**.

Ký hiệu:
- **[Đồng ý]**: theo đề xuất của đơn vị phát triển.
- **[Sửa]**: người phụ trách dự án sửa đề xuất.
- **[Nội bộ]**: quyết định nội bộ, chưa xác nhận với khách hàng.
- **[Giả định]**: chưa có căn cứ chắc chắn, cần kiểm chứng khi triển khai thật.

Các câu có [Sửa] hoặc [Nội bộ] được liệt kê ở mục E để xác nhận với khách hàng.

## A. Thiết kế dữ liệu

### 1. Mẫu che số CCCD [Đồng ý]
Mẫu ở mục III (`0791•••••2345`) dài 13 ký tự, không khớp 12 chữ số. Chốt: hiện 4 số đầu, 4 dấu `•`, 4 số cuối, ví dụ `0791••••2345`. Mẫu này dùng chung cho màn hình, file Excel và bản in.

### 2. Hủy hồ sơ hết hạn lưu trữ [Đồng ý + Nội bộ]
- Phần này nằm trong MVP.
- "Hủy" ở mục VIII nghĩa là **ẩn danh hóa**, không xóa cứng bản ghi. Cụ thể:
  - Xóa dữ liệu cá nhân và tệp đính kèm.
  - Giữ bản ghi khung, mã hồ sơ, mã nhân viên và nhật ký thao tác.
  - **[Nội bộ]** Trong nhật ký, giá trị trước/sau của các trường cá nhân nằm ở bảng riêng `AuditPersonalValue` (câu 30) và **bị xóa** khi ẩn danh hóa. Dòng nhật ký (ai, khi nào, hành động, trường nào thay đổi) **vẫn giữ**. Mỗi lần ẩn danh hóa ghi thêm một dòng nhật ký "Ẩn danh hóa".
- Admin duyệt hủy từ danh sách hồ sơ hết hạn. Mỗi lần hủy sinh **biên bản hủy** (ai, khi nào, những hồ sơ nào) và ghi nhật ký.
- Thời hạn lưu trữ theo mục VIII:
  - Ứng viên không đạt: 12 tháng kể từ ngày có kết quả.
  - Công nhân đã nghỉ: 10 năm kể từ ngày chấm dứt hợp đồng lao động cuối cùng với bên cung ứng (câu 44, v1.1); không tính từ ngày kết thúc một đợt làm việc.
  - Cả hai cấu hình được.
- **[Nội bộ] Mọi hồ sơ Lưu trữ đều có ngày hết hạn lưu trữ tính được.** Căn cứ xét theo thứ tự trong bảng, gặp dòng đầu tiên khớp thì dùng:

  | Căn cứ | Điều kiện | Mốc tính | Thời hạn |
  | --- | --- | --- | --- |
  | Công nhân đã nghỉ | Có mã NV và có ngày nghỉ việc | Ngày nghỉ việc (`Employment.resign_date` = ngày chấm dứt HĐLĐ với bên cung ứng, câu 44) | 10 năm |
  | Công nhân lưu trữ khác | Có mã NV, không có ngày nghỉ việc | Ngày chuyển Lưu trữ | 10 năm |
  | Ứng viên không được tuyển | Chưa có mã NV, lần ứng tuyển gần nhất Không đạt hoặc Ứng viên từ chối, có ngày kết quả | Ngày có kết quả | 12 tháng |
  | Hồ sơ bị từ chối | Chưa có mã NV, chuyển Lưu trữ từ Bị từ chối | Ngày chuyển Lưu trữ | 12 tháng |
  | Hồ sơ bỏ dở | Chưa có mã NV, tự Lưu trữ với lý do "Hồ sơ bỏ dở" (câu 9) | Ngày chuyển Lưu trữ | 12 tháng |
  | Ứng viên lưu trữ khác | Mọi trường hợp còn lại | Ngày chuyển Lưu trữ | 12 tháng |

  "Ngày chuyển Lưu trữ" lấy từ lần chuyển sang Lưu trữ gần nhất trong lịch sử trạng thái (luôn có, vì mọi lần chuyển trạng thái đều được ghi). "12 tháng" và "10 năm" là hai giá trị cấu hình ở trên. Phải có test chứng minh mọi hồ sơ Lưu trữ đều tính được ngày hết hạn.
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

### 9. Chuyển trạng thái xác minh [Đồng ý + Sửa + Nội bộ]

| Từ | Sang | Ai | Ghi chú |
| --- | --- | --- | --- |
| Nháp | Chờ duyệt | HR, QL, Admin | Kiểm tra đủ trường bắt buộc (câu 5) |
| Chờ duyệt | Đã xác minh / Cần bổ sung / Bị từ chối | QL, Admin | Cần bổ sung, Bị từ chối bắt buộc ghi lý do; áp dụng câu 8 |
| Cần bổ sung | Chờ duyệt | HR, QL, Admin | Sau khi bổ sung |
| Đã xác minh | Chờ duyệt | Tự động | Khi sửa họ tên, ngày sinh hoặc số CCCD |
| Bị từ chối | Lưu trữ | HR, QL, Admin; hoặc tự động | Chỉ được chuyển sang Lưu trữ |
| Nháp, Cần bổ sung | Lưu trữ | HR, QL, Admin; hoặc tự động | Có hộp xác nhận |
| Đã xác minh | Lưu trữ | QL, Admin; hoặc tự động | Có hộp xác nhận, **bắt buộc ghi lý do**. Máy chủ **chặn** khi trạng thái làm việc là Thử việc hoặc Đang làm việc |
| Lưu trữ | Nháp | HR, QL, Admin | "Mở lại hồ sơ" (câu 6) |

- **[Nội bộ] Chuyển Lưu trữ thủ công:** HR chỉ chuyển Lưu trữ khi hồ sơ ở Nháp, Cần bổ sung hoặc Bị từ chối. HR **không** chuyển Lưu trữ hồ sơ Đã xác minh; việc này chỉ QL hoặc Admin làm, theo dòng tương ứng trong bảng.
- **Chờ duyệt:** khóa phần được duyệt (xem câu 36). HR không sửa phần này; QL và Admin chỉ duyệt, trả lại hoặc từ chối. Tab Tuyển dụng và Quá trình làm việc vẫn thao tác được theo quyền thường.
- **Lưu trữ:** chỉ xem.
- **Tự động Lưu trữ** [Sửa + Nội bộ]: một tác vụ chạy hằng ngày, mỗi lần chuyển đều ghi nhật ký (người thực hiện là "Hệ thống"). Bốn quy tắc:
  1. [Sửa] Hồ sơ có trạng thái làm việc **Đã nghỉ việc**: tự Lưu trữ sau **30 ngày kể từ ngày nghỉ**, để HR còn bổ sung giấy tờ nghỉ việc.
  2. [Sửa] Hồ sơ **chưa có mã NV** mà lần ứng tuyển gần nhất là **Không đạt** hoặc **Ứng viên từ chối**: tự Lưu trữ sau **30 ngày kể từ ngày có kết quả**.
  3. [Nội bộ] Hồ sơ **Bị từ chối**: tự Lưu trữ sau **30 ngày kể từ ngày bị từ chối** (dùng chung số ngày với quy tắc 2).
  4. [Nội bộ] Hồ sơ **Nháp** hoặc **Cần bổ sung** không có thay đổi nào trong **6 tháng** (`stale_draft_months = 6`): tự Lưu trữ, lý do "Hồ sơ bỏ dở". "Thay đổi" gồm sửa hồ sơ và dữ liệu con (giấy tờ, liên hệ, đồng ý, tài liệu, ứng tuyển).
  - Số ngày (30, 30) và số tháng (6) cấu hình được trong Cài đặt.
  - **[Nội bộ]** Tự động Lưu trữ không áp dụng cho hồ sơ có trạng thái làm việc Thử việc hoặc Đang làm việc (giống chặn thủ công ở bảng trên), vì hồ sơ nhập từ Excel có thể ở Nháp mà người đó vẫn đang làm.

### 10. Thêm tài liệu khi đã xác minh [Đồng ý]
HR được **thêm** tài liệu mới khi hồ sơ ở Đã xác minh, và trạng thái hồ sơ không đổi. Việc **thay thế** tài liệu vẫn theo ma trận mục III: HR chỉ thay thế khi hồ sơ ở Nháp hoặc Cần bổ sung.

### 11. Tab "Lịch sử thay đổi" [Đồng ý]
- Mọi vai trò xem được **dòng thời gian trạng thái**: thời điểm, trạng thái cũ, trạng thái mới, người thực hiện và lý do.
- Chi tiết **giá trị trước/sau từng trường** (lấy từ nhật ký thao tác) chỉ Admin và Quản lý nhân sự xem.

### 12. Xem số CCCD đầy đủ [Đồng ý]
- Số CCCD luôn hiện ở dạng che (câu 1).
- Vai trò có quyền bấm **"Hiện số đầy đủ"** thì mới thấy số đầy đủ, và mỗi lần bấm ghi một dòng nhật ký. Ảnh CCCD áp dụng tương tự: mở xem hoặc tải xuống đều ghi nhật ký.

### 13. Trường nhạy cảm ẩn với Viewer [Đồng ý + Nội bộ]
- **Viewer không thấy:**
  - Số CCCD (chỉ thấy dạng che)
  - Số CMND cũ
  - Địa chỉ thường trú/cư trú
  - Quê quán / nơi đăng ký khai sinh
  - Ảnh CCCD
  - **[Nội bộ]** Mức lương mong muốn (trang Tuyển dụng, tab Tuyển dụng trong chi tiết hồ sơ, file xuất)
- **Viewer vẫn thấy:** SĐT và nơi ở hiện tại.
- **[v1.1] Ngoại lệ cho dữ liệu lương (câu 42):** Viewer **được xem** lương tháng và đơn giá tháng (bảng `SalaryHistory`). Ngoại lệ này chỉ áp dụng cho hai trường mới đó; **mức lương mong muốn** của ứng viên (`Application.expected_salary`) vẫn ẩn với Viewer như trên **[Giả định, cần xác nhận]**.
- **Viewer không** xem trước và không tải được tài liệu.

### 14. Trình độ học vấn [Đồng ý]
EducationLevels là danh mục do Admin quản lý trong Cài đặt, có thứ tự cấp bậc. Bộ lọc và báo cáo theo trình độ lấy **trình độ cao nhất** của mỗi người.

### 15. Vị trí làm việc [Đồng ý + Nội bộ]
- Thông tin làm việc lưu **Bộ phận** và **Tổ (không bắt buộc)**. **[Giả định]** Bộ phận là bắt buộc. Nếu có chọn Tổ thì Tổ phải thuộc Bộ phận đã chọn.
- **[Nội bộ]** Dữ liệu mẫu (`seed_demo`) phải có phòng ban "Khối văn phòng" với bộ phận **"Văn phòng"** cho nhân viên khối văn phòng (vì Bộ phận bắt buộc), và có **ít nhất 1 tài khoản Quản lý nhân sự**.
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

## C. Quyết định bổ sung (Phase 1)

### 25. Kỹ năng [Nội bộ]
Kỹ năng lưu ở **một trường văn bản nhiều dòng "Kỹ năng"** trong hồ sơ, hiển thị ở tab Tuyển dụng & CV. Không thêm bảng riêng. Thao tác "Đưa vào trường…" ở màn hình CV (mục V) gán đoạn văn bản vào trường này.

### 26. Nhóm tuổi [Nội bộ]
Câu 16 cho lưu người từ 15 đến dưới 18 tuổi, nên Dashboard và báo cáo dùng **5 nhóm tuổi**: Dưới 18 · 18–25 · 26–35 · 36–45 · Trên 45. Hồ sơ chưa có ngày sinh (Nháp) vào nhóm "Chưa có ngày sinh", để tổng các nhóm luôn bằng tổng hồ sơ.

### 27. File Excel mẫu nhập hàng loạt [Nội bộ]
- File có 2 phần: **thông tin cá nhân** (bắt buộc) và **thông tin làm việc** (không bắt buộc).
- Dòng **không có** thông tin làm việc: nhập như hồ sơ ứng viên, trạng thái Nháp, không có mã NV.
- Dòng **có** thông tin làm việc (công nhân hiện hữu): nhận mã NV cũ từ file, phòng ban, bộ phận, tổ, chức danh, ca, ngày vào làm, trạng thái làm việc. Hồ sơ vào trạng thái Nháp và vẫn phải qua duyệt như bình thường.
- **Quy tắc mã NV:**
  - Mã nhập từ file chỉ được nhận qua chức năng nhập Excel, phần thông tin làm việc (Admin/QL).
  - Nhận **mọi mã cũ không trùng**, dài **tối đa 20 ký tự**, chỉ gồm **chữ, số và dấu gạch ngang**. Mã trùng (với hồ sơ đã có hoặc dòng khác trong cùng file) hoặc sai các điều kiện này thì báo lỗi dòng đó.
  - Bộ đếm mã (`CodeSequence`) **chỉ được đẩy lên** khi mã cũ **khớp định dạng mã đang cấu hình** (ví dụ `CN-00456` khi cấu hình là `CN` + 5 chữ số): bộ đếm lấy số lớn hơn giữa số hiện tại và số của mã cũ. Mã cũ khác định dạng (ví dụ `NV2019-A12`) vẫn được nhận nhưng không ảnh hưởng bộ đếm.
  - Bộ sinh mã tự động, **trước khi cấp**, kiểm tra mã sinh ra chưa tồn tại; nếu đã tồn tại thì tăng tiếp cho tới khi gặp mã chưa dùng. Nhờ vậy không bao giờ cấp trùng.
- **Duyệt hồ sơ nhập từ Excel:** áp dụng câu 8: người nhập là người tạo nên không tự duyệt được. Không có chức năng duyệt hàng loạt (`docs/thiet-ke/excel-mau.md` mục 3.3).
- **Danh mục** (phòng ban, bộ phận, tổ, chức danh, ca) trong file phải khớp tên đã có trong hệ thống; không khớp thì báo lỗi dòng, không tự tạo danh mục mới.
- Cách hiểu chi tiết:
  - HR vẫn dùng được nhập Excel cho dòng chỉ có thông tin cá nhân. Dòng có thông tin làm việc mà người nhập là HR thì báo lỗi dòng: "Chỉ Admin hoặc Quản lý nhân sự được nhập thông tin làm việc."
  - Phòng ban ghi trong file phải khớp phòng ban của bộ phận; tổ (nếu có) phải thuộc bộ phận.
  - Trạng thái làm việc "Đã nghỉ việc" thì bắt buộc ngày nghỉ và lý do nghỉ.
- Danh sách cột chi tiết ở `docs/thiet-ke/excel-mau.md`.

## D. Quyết định bổ sung (rà thiết kế) [Nội bộ]

### 28. Hai cơ chế khóa tài khoản [Nội bộ]
| | Admin khóa | Khóa tạm do sai mật khẩu |
| --- | --- | --- |
| Lưu ở | `is_active = False` | `locked_until`, `failed_login_count` |
| Khi nào | Admin bấm "Khóa tài khoản" | Lần sai thứ 5 liên tiếp |
| Hết khóa | Chỉ khi Admin bấm "Mở khóa" (vô thời hạn) | Tự hết sau 15 phút, hoặc Admin bấm "Mở khóa" |
| Nhật ký | Khóa / Mở khóa tài khoản | Lịch sử đăng nhập |

"Mở khóa" của Admin bật lại `is_active`, đồng thời xóa `locked_until` và đặt `failed_login_count` về 0.

### 29. Bảo vệ quyền quản trị [Nội bộ]
- Admin không tự khóa và không tự đổi vai trò của chính mình.
- Không ai được khóa hoặc hạ vai trò **Admin cuối cùng đang hoạt động** (vai trò Admin và chưa bị khóa).
- Kiểm tra ở máy chủ, có test cho từng trường hợp.

### 30. Nhật ký và dữ liệu cá nhân [Nội bộ]
- Thêm bảng `AuditPersonalValue` (dòng nhật ký, hồ sơ, tên trường, giá trị cũ, giá trị mới); giá trị cũ/mới **mã hóa** như trường nhạy cảm.
- Với trường cá nhân (họ tên, ngày sinh, giới tính, SĐT, email, nơi ở, giấy tờ, liên hệ khẩn cấp, ghi chú, kỹ năng, mức lương mong muốn…), dòng nhật ký chỉ ghi tên trường và "(xem giá trị chi tiết)"; giá trị trước/sau nằm ở `AuditPersonalValue`, chỉ Admin và QL xem (câu 11).
- Nhật ký vẫn chỉ thêm, không sửa, không xóa. Ngoại lệ duy nhất: ẩn danh hóa (câu 2, 38) xóa mọi `AuditPersonalValue` của hồ sơ đó và ghi một dòng nhật ký "Ẩn danh hóa".
- Phần mô tả đối tượng của nhật ký và lý do do hệ thống tự điền **không chứa họ tên**, chỉ dùng mã hồ sơ. Ô lý do hiện gợi ý "Không ghi họ tên, chỉ dùng mã hồ sơ"; không chặn lưu.

### 31. Cất giữ khóa mã hóa [Nội bộ]
- `FIELD_ENCRYPTION_KEY` (mã hóa) và `HASH_KEY` (băm) được sinh **một lần khi cài đặt** và nằm trong `.env`.
- Hai khóa **không nằm trong file sao lưu**. Script sao lưu (Phase 8) nhắc người dùng cất bản sao khóa ở nơi riêng (USB hoặc giấy niêm phong). Mất khóa thì không đọc lại được dữ liệu đã mã hóa từ bản sao lưu.
- Thiếu khóa, khóa sai định dạng, hoặc khóa không khớp dữ liệu hiện có (kiểm tra bằng giá trị kiểm tra lưu trong Cài đặt, xem `docs/thiet-ke/kien-truc.md` mục 7) thì ứng dụng **từ chối khởi động** với thông báo rõ ràng bằng tiếng Việt.
- **Giới hạn đã biết:** MVP không hỗ trợ đổi khóa.

### 32. Tệp đính kèm hợp đồng [Nội bộ]
Hợp đồng trỏ tới một tài liệu; nếu tài liệu đó đã bị thay thế, màn hình hợp đồng luôn hiển thị và mở **bản hiện hành** của chuỗi thay thế (đi theo các lần thay thế tới bản đang dùng).

### 33. Thời hạn lưu trữ của "Ứng viên từ chối" [Nội bộ]
Hồ sơ ứng viên có lần ứng tuyển gần nhất là "Ứng viên từ chối" dùng chung thời hạn lưu trữ 12 tháng với "Không đạt" (căn cứ "Ứng viên không được tuyển" ở câu 2), vì câu 9 đã gộp hai trường hợp này cho tự Lưu trữ.

### 34. Ai đổi trạng thái xác minh tài liệu [Nội bộ]
Chỉ QL và Admin đổi trạng thái xác minh tài liệu (theo mục II: "Quản lý đã đối chiếu với bản gốc"), kể cả khi hồ sơ đang Chờ duyệt.

### 35. Hồ sơ Bị từ chối chỉ xem [Nội bộ]
Hồ sơ Bị từ chối không sửa được; thao tác duy nhất là chuyển Lưu trữ (câu 9).

### 36. Chờ duyệt chỉ khóa phần được duyệt [Nội bộ]
Khi hồ sơ Chờ duyệt, chỉ khóa phần được duyệt: thông tin cá nhân, giấy tờ, liên hệ, đồng ý xử lý dữ liệu, tài liệu. Tab Tuyển dụng và Quá trình làm việc vẫn thao tác được vì ba bộ trạng thái độc lập. Hồ sơ Bị từ chối và Lưu trữ thì khóa toàn bộ.

### 37. Giới tính [Nội bộ]
Giới tính chỉ có hai giá trị Nam, Nữ, khớp thông tin trên CCCD.

### 38. Ẩn danh hóa theo yêu cầu của chủ thể dữ liệu [Nội bộ]
- Để đáp ứng quyền yêu cầu xóa trong văn bản đồng ý (`docs/thiet-ke/mau-dong-y.md` mục 6, 7), **Admin** được ẩn danh hóa sớm một hồ sơ **Lưu trữ** chưa hết hạn lưu trữ khi chủ thể dữ liệu yêu cầu xóa.
- Bắt buộc ghi **lý do** (không ghi họ tên, chỉ dùng mã hồ sơ) và **số/ngày đơn yêu cầu**.
- Dùng chung hàm ẩn danh hóa và sinh **biên bản hủy** như ẩn danh hóa hết hạn (câu 2). Biên bản ghi "Xóa sớm theo yêu cầu – lẽ ra lưu đến dd/mm/yyyy" (ngày hết hạn tính theo câu 2) và số đơn.
- Hồ sơ chưa Lưu trữ phải chuyển Lưu trữ trước, theo đúng câu 9 (không chuyển được khi trạng thái làm việc là Thử việc hoặc Đang làm việc).
- Thao tác không hoàn tác được; hộp xác nhận yêu cầu gõ lại mã hồ sơ, máy chủ kiểm tra lại.

## E. Cần xác nhận với khách hàng

Ưu tiên cao (ảnh hưởng trực tiếp tới dữ liệu của khách):
1. **Hủy = ẩn danh hóa** (câu 2, 30): không xóa cứng; giữ mã và nhật ký, xóa dữ liệu cá nhân, tệp và giá trị cá nhân trong nhật ký. Kèm bảng căn cứ hạn lưu trữ (câu 2).
2. **Tự Lưu trữ** (câu 9): 30 ngày sau nghỉ việc; 30 ngày sau kết quả Không đạt/Ứng viên từ chối; 30 ngày sau Bị từ chối; hồ sơ Nháp/Cần bổ sung bỏ dở 6 tháng.
3. **Chặn nhập người dưới 15 tuổi** (câu 16); 15 đến dưới 18 chỉ cảnh báo.
4. **Hồ sơ nhập Excel phải do người khác người nhập duyệt** từng hồ sơ, không có duyệt hàng loạt (câu 8, 27).
5. **Ẩn danh hóa theo yêu cầu** (câu 38): Admin xóa sớm dữ liệu cá nhân khi người lao động yêu cầu; chỉ với hồ sơ Lưu trữ, không hoàn tác được.

Các điểm khác:
- Câu 5: Nháp chỉ cần họ tên + SĐT; điều kiện gửi duyệt; cảnh báo trùng theo SĐT, họ tên + ngày sinh.
- Câu 9: HR không chuyển Lưu trữ hồ sơ Đã xác minh; QL/Admin chuyển phải ghi lý do, bị chặn khi Thử việc/Đang làm việc.
- Câu 13: ẩn mức lương mong muốn với Viewer.
- Câu 15: dữ liệu mẫu có bộ phận "Văn phòng" và ít nhất 1 tài khoản QL.
- Câu 25: kỹ năng là một trường văn bản.
- Câu 26: 5 nhóm tuổi (thêm Dưới 18) và nhóm "Chưa có ngày sinh".
- Câu 27: file Excel 2 phần; nhận mã NV cũ (tối đa 20 ký tự, chữ/số/gạch ngang).
- Câu 28: hai cơ chế khóa tài khoản.
- Câu 29: bảo vệ Admin cuối cùng.
- Câu 31: khóa mã hóa không nằm trong file sao lưu, phải cất riêng; chưa hỗ trợ đổi khóa.
- Câu 32: hợp đồng hiển thị bản tài liệu hiện hành.
- Câu 33–37: "Ứng viên từ chối" lưu 12 tháng; chỉ QL/Admin xác minh tài liệu; Bị từ chối chỉ xem; Chờ duyệt chỉ khóa phần được duyệt; giới tính Nam/Nữ.
- Câu 9 (làm rõ ở Phase 4) [Nội bộ]: chặn Lưu trữ khi trạng thái làm việc là Thử việc hoặc Đang làm việc áp dụng cho **mọi** đường chuyển sang Lưu trữ (thủ công từ Nháp, Cần bổ sung, Bị từ chối, Đã xác minh, và tự động), không chỉ từ Đã xác minh.
- Câu 5/9 (làm rõ ở Phase 4) [Nội bộ]: sửa hồ sơ đang Đã xác minh phải giữ đủ các trường bắt buộc khi gửi duyệt (không cho xóa trắng ngày sinh, giới tính, nơi ở, loại giấy tờ, số CCCD...).
- **v1.1 (mục F) đã ký ngày 23/11/2026: không cần xác nhận lại** các câu 39–47. Riêng các chi tiết thiết kế do đơn vị phát triển điền thêm, đánh dấu [Nội bộ] hoặc [Giả định] trong mục F, vẫn cần xác nhận cùng các điểm trên (danh sách ở cuối mục F).

## F. Thay đổi v1.1 (đã ký 23/11/2026)

Nguồn: phiếu thay đổi v1.1 đã ký (`docs/yeu-cau-thay-doi-v1.1.pdf`). Câu 39–47 là nội dung phiếu; phần đánh dấu [Nội bộ] hoặc [Giả định] là chi tiết đơn vị phát triển điền thêm để thiết kế, chưa có trong phiếu. **Khi mục F khác câu 2 hoặc câu 13 thì theo mục F.** Bối cảnh: bên cung ứng đưa công nhân sang làm tại công ty khách hàng; `Employment` vẫn là quan hệ lao động giữa công nhân và bên cung ứng.

### 39. Công ty khách hàng
- Danh mục **công ty khách hàng** chỉ có **tên** và **địa điểm** (tỉnh/thành). Mỗi địa điểm là **một dòng** (một công ty có hai địa điểm thì có hai dòng).
- **Ngừng sử dụng** thay cho xóa (như các danh mục khác).
- **[Nội bộ]** Do Admin quản lý trong Cài đặt như mọi danh mục. Hai dòng không được trùng cả tên lẫn địa điểm. Địa điểm là văn bản tự nhập, không phải danh sách tỉnh/thành cố định.

### 40. Đợt làm việc
- **Mỗi lúc một công nhân chỉ làm cho một công ty khách hàng.**
- Mỗi đợt gồm: công ty khách hàng, vị trí, ngày bắt đầu, ngày kết thúc (**không bắt buộc**), ghi chú.
- **Giữ lịch sử các đợt**: không ghi đè, không xóa; đợt cũ vẫn xem được.
- **[Nội bộ]** Các đợt của một công nhân không chồng lấn ngày; ngày kết thúc là ngày làm cuối cùng của đợt đó. Chỉ có đợt cho người đã có mã NV và chưa Đã nghỉ việc. Khi trạng thái làm việc chuyển sang Đã nghỉ việc, đợt đang mở tự kết thúc vào ngày nghỉ việc.
- **[Giả định]** "Vị trí" lấy từ danh mục Chức danh sẵn có (`Position`), không tạo danh mục mới. Thêm và sửa đợt: Admin, Quản lý nhân sự, Nhân viên HR; Viewer chỉ xem.

### 41. Lương và đơn giá
- Lưu hai khoản: **lương tháng** của công nhân và **đơn giá tháng** tính cho công ty khách hàng.
- Mỗi thay đổi **thêm một dòng lịch sử** gồm: mức, ngày áp dụng, người sửa, lý do. **Không sửa, không xóa dòng cũ**; nhập sai thì thêm dòng mới sửa lại.
- **Mã hóa khi lưu** (như số định danh) và **ghi nhật ký** qua `apps.audit.services.log()`; giá trị lương là trường cá nhân nên nhật ký chỉ ghi "(xem giá trị chi tiết)".
- **[Nội bộ]** Mỗi dòng lịch sử ghi cả hai khoản tại ngày áp dụng (đổi một khoản thì khoản kia giữ giá trị cũ). Mức hiện tại là dòng có ngày áp dụng lớn nhất không quá hôm nay. Ẩn danh hóa hồ sơ thì xóa toàn bộ lịch sử lương (đã thống nhất; cần thêm vào danh sách ngoại lệ "không xóa cứng" của `CLAUDE.md`).

### 42. Quyền xem và sửa lương
- **Mọi vai trò (Admin, Quản lý nhân sự, Nhân viên HR, Viewer) được XEM** lương và đơn giá.
- **Chỉ Admin và Quản lý nhân sự được THÊM/SỬA** (thêm dòng lịch sử mới).
- **Đây là thay đổi so với câu 13** đối với dữ liệu lương: câu 13 ẩn mức lương mong muốn với Viewer, còn lương tháng và đơn giá thì Viewer thấy. Mức lương mong muốn của ứng viên **không** nằm trong thay đổi này **[Giả định, cần xác nhận]**.
- **[Nội bộ]** Xem lương không ghi nhật ký (khác xem số CCCD đầy đủ); thêm dòng lương thì ghi nhật ký. Lương không đưa vào file xuất Excel và không có chức năng nhập lương từ Excel trong v1.1.

### 43. Cảnh báo đợt làm việc sắp đủ 12 tháng
- Đợt làm việc **sắp đủ 12 tháng** kể từ ngày bắt đầu được cảnh báo ở Dashboard, trong **danh sách việc cần làm**.
- Dùng **chung ngưỡng số ngày `expiry_warning_days`** với CCCD và hợp đồng sắp hết hạn (câu 17).
- **[Nội bộ]** Không thêm thẻ số liệu mới (9 thẻ ở mục VII giữ nguyên), theo cách đã làm với CCCD sắp hết hạn. Đợt đã quá 12 tháng mà chưa kết thúc vẫn hiện trong danh sách cho đến khi có ngày kết thúc. Con số 12 tháng cấu hình được (`assignment_limit_months`, mặc định 12).

### 44. Hạn lưu trữ công nhân đã nghỉ
- **Giữ 10 năm như v1.0** (`resigned_retention_years = 10`). Mốc tính là **ngày chấm dứt hợp đồng lao động cuối cùng với bên cung ứng** (`Employment.resign_date`); **không** tính từ ngày kết thúc một đợt làm việc.
- **Ứng viên không được tuyển giữ 12 tháng**, không đổi.
- Lý do: quy định lưu hợp đồng lao động 10 năm kể từ ngày chấm dứt (khách hàng đã đồng ý đổi từ 1 năm, có ký nháy).
- Quay lại làm việc = **"Mở lại hồ sơ"** (câu 6); dùng được trong suốt thời hạn lưu trữ, tới khi hồ sơ bị ẩn danh hóa.
- Không thêm căn cứ lưu trữ mới (`RetentionBasis` giữ 6 căn cứ ở câu 2).

### 45. Bản cam kết, báo cáo và bộ lọc theo công ty khách
- Thêm loại tài liệu **"Bản cam kết"** vào danh mục loại tài liệu (không thuộc nhóm bắt buộc **[Giả định]**).
- Báo cáo thêm **số công nhân đang làm theo công ty khách hàng**.
- Danh sách hồ sơ công nhân **lọc được theo công ty khách hàng** (theo đợt đang diễn ra **[Giả định]**).

### 46. Ngoài phạm vi v1.1
Chấm công; tính lương; bảng lương; hóa đơn, công nợ; tài khoản đăng nhập cho công ty khách hàng; thông tin công ty khách hàng ngoài tên và địa điểm.

### 47. Lưu bản gốc ngoài phần mềm
Bản gốc hợp đồng lao động, bản cam kết và bảng lương do bên cung ứng lưu ngoài phần mềm theo quy định. Phần mềm **không thay thế** việc lưu trữ đó. **[Nội bộ]** Tệp tải lên (hợp đồng, bản cam kết) được coi là bản số tham khảo, không phải bản gốc.

### Điểm [Nội bộ]/[Giả định] của mục F cần xác nhận
1. Địa điểm công ty khách là văn bản tự nhập; vị trí của đợt dùng danh mục Chức danh (câu 39, 40).
2. HR được thêm/sửa đợt làm việc; chỉ A, Q thêm lương (câu 40, 42).
3. Mức lương mong muốn vẫn ẩn với Viewer (câu 13, 42).
4. Mỗi dòng lương ghi cả lương tháng và đơn giá; xem lương không ghi nhật ký; lương không vào file xuất Excel (câu 41, 42).
5. Đợt tự kết thúc khi nghỉ việc; con số 12 tháng cấu hình được; đợt quá 12 tháng vẫn cảnh báo (câu 40, 43).
