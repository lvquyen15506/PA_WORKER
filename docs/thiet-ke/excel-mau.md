# File Excel mẫu nhập hàng loạt – PA Worker

Phase 1 · Ngày 21/11/2026 · Cập nhật v1.1 ngày 23/11/2026 · Nháp để khách hàng duyệt (câu 21). Căn cứ: `docs/yeu-cau.md` mục IV.3, VI; `docs/lam-ro-yeu-cau.md` câu 1–47 (riêng câu 5, 8, 9, 13, 15, 16, 25, 27, 30, 37, 39, 40, 48 liên quan trực tiếp); `docs/thiet-ke/models.md` (tên trường, mục 4.5), `trang.md` 5.4 (`/ho-so/nhap-excel/`).

## 1. Cấu trúc file

- Định dạng `.xlsx`, đọc bằng `openpyxl.load_workbook(..., data_only=False)` để phát hiện được ô công thức (mục 3.1). Tải file mẫu ở `/ho-so/nhap-excel/file-mau/`; nhập ở `/ho-so/nhap-excel/`.
- Tối đa **1.000 dòng** dữ liệu và **10 MB** mỗi file.
- Ba sheet:

| Sheet | Nội dung |
| --- | --- |
| `Hồ sơ` | Dòng 1 là tiêu đề cột (đúng tên ở mục 2, không đổi tên, không đổi thứ tự). Dữ liệu bắt đầu từ dòng 2. File mẫu tải về **không có dòng dữ liệu** để tránh nhập nhầm dòng ví dụ |
| `Hướng dẫn` | Giải thích hai phần A, B; quy tắc từng cột; 2 dòng ví dụ (mục 5) |
| `Danh mục` | Giá trị hợp lệ lấy từ hệ thống lúc tải file mẫu: phòng ban, bộ phận (kèm phòng ban), tổ (kèm bộ phận), chức danh, ca, công ty khách (dạng "tên – địa điểm", v1.1), loại giấy tờ, giới tính, trạng thái làm việc, lý do nghỉ. Các ô tương ứng ở sheet `Hồ sơ` có danh sách thả xuống lấy từ sheet này |

- **Mọi cột ở sheet `Hồ sơ` định dạng Text** trong file mẫu, gồm cả số CCCD, CMND cũ, SĐT, mã NV (giữ số 0 đầu) và các cột ngày.
- **Cột ngày** (A3, A8, A10, B7, B8, B10, B13): chỉ nhận chuỗi `dd/mm/yyyy`. Nếu Excel vẫn đổi thành ô kiểu ngày, hệ thống vẫn đọc được nhưng kèm **cảnh báo** "Ô ngày của Excel có thể bị đảo ngày/tháng; kiểm tra lại", vì Excel có thể hiểu `03/04` là 4 tháng 3 hoặc 3 tháng 4 tùy cài đặt máy.
- File mẫu và mọi file Excel hệ thống xuất ra đều ghi giá trị qua `apps.core.excel.safe_cell()` (mục 3.1).
- Số dòng trong báo lỗi là **số dòng trong Excel** (dòng tiêu đề là dòng 1).

## 2. Danh sách cột

Ký hiệu cột "Bắt buộc": **Có** = bắt buộc mọi dòng; **Nếu có B** = bắt buộc khi dòng có điền bất kỳ cột nào của phần B; **Theo điều kiện** = xem cột Kiểm tra; trống = không bắt buộc.

Ô nào là công thức Excel thật đều bị báo lỗi, ở mọi cột (mục 3.1).

### Phần A – Thông tin cá nhân (bắt buộc)

Theo câu 5: hồ sơ nhập vào ở trạng thái Nháp, nên chỉ bắt buộc **họ tên + SĐT**. Các trường còn lại được bổ sung trước khi gửi duyệt.

| # | Tên cột | Trường | Bắt buộc | Định dạng | Kiểm tra | Ví dụ giả |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | Họ và tên | `Worker.full_name` | Có | Chữ, tối đa 100 ký tự | Không để trống | Trần Thị Mẫu |
| A2 | Số điện thoại | `Worker.phone` | Có | Text, 10 chữ số | Đúng 10 chữ số, bắt đầu bằng 0. Trùng SĐT hồ sơ đã có → **cảnh báo** | 0900000001 |
| A3 | Ngày sinh | `Worker.date_of_birth` | | Text dd/mm/yyyy | Dưới 15 tuổi → **lỗi**; 15 đến dưới 18 → **cảnh báo** (câu 16). Trùng họ tên + ngày sinh (không dấu) → **cảnh báo** | 15/03/2000 |
| A4 | Giới tính | `Worker.gender` | | Nam / Nữ | Chỉ hai giá trị (câu 37) | Nữ |
| A5 | Quốc tịch | `Worker.nationality` | | Chữ | Để trống thì lấy "Việt Nam" | Việt Nam |
| A6 | Loại giấy tờ | `IdentityDocument.id_doc_type` | Theo điều kiện | Chọn từ danh sách | Bắt buộc khi có A7. Giá trị: CCCD gắn chip (mẫu 2021) / Thẻ Căn cước (từ 01/7/2024) / CCCD mã vạch (mẫu 2016) | CCCD gắn chip (mẫu 2021) |
| A7 | Số định danh | `IdentityDocument.id_number_enc` | | Text, 12 chữ số | Đúng 12 chữ số. Trùng hồ sơ đã có (so theo băm) **hoặc** trùng dòng khác trong cùng file → **lỗi** | 999000000001 |
| A8 | Ngày cấp | `IdentityDocument.issue_date` | | Text dd/mm/yyyy | Phải sau ngày sinh | 20/06/2023 |
| A9 | Nơi cấp | `IdentityDocument.issue_place` | | Chữ | | Cục Cảnh sát QLHC về TTXH |
| A10 | Ngày hết hạn | `IdentityDocument.expiry_date` | | Text dd/mm/yyyy | Phải sau ngày cấp | 15/03/2040 |
| A11 | Quê quán | `IdentityDocument.hometown` | | Chữ | Chỉ điền nếu giấy tờ có (mẫu cũ); không suy ra từ cột khác | Xã Mẫu Một, Tỉnh Mẫu |
| A12 | Nơi đăng ký khai sinh | `IdentityDocument.birth_registration_place` | | Chữ | Chỉ điền nếu giấy tờ có (mẫu mới) | |
| A13 | Nơi thường trú/cư trú | `IdentityDocument.permanent_address_enc` | | Chữ | Lưu mã hóa | Số 1 Đường Mẫu, Phường Mẫu |
| A14 | Số CMND cũ | `IdentityDocument.old_id_number_enc` | | Text, 9 hoặc 12 chữ số | Lưu mã hóa | 999000001 |
| A15 | Email | `Worker.email` | | email | Đúng định dạng email | mau.tran@example.com |
| A16 | Nơi ở hiện tại | `Worker.current_address` | | Chữ | | Khu trọ Mẫu, Phường Mẫu |
| A17 | Người liên hệ khẩn cấp – Họ tên | `EmergencyContact.full_name` | Theo điều kiện | Chữ | A17, A18, A19 điền đủ cả ba hoặc để trống cả ba | Trần Văn Mẫu |
| A18 | Người liên hệ khẩn cấp – Quan hệ | `EmergencyContact.relationship` | Theo điều kiện | Chữ | | Bố |
| A19 | Người liên hệ khẩn cấp – SĐT | `EmergencyContact.phone` | Theo điều kiện | Text, 10 chữ số | Đúng 10 chữ số, bắt đầu bằng 0 | 0900000002 |
| A20 | Kỹ năng | `Worker.skills` | | Chữ nhiều dòng | Câu 25. Được dùng gạch đầu dòng "- " | - Vận hành máy may công nghiệp |
| A21 | Ghi chú | `Worker.note` | | Chữ | | |

### Phần B – Thông tin làm việc (không bắt buộc, chỉ Admin và Quản lý nhân sự)

Dùng cho **công nhân hiện hữu** đang quản lý trên Excel (câu 27). Dòng để trống toàn bộ phần B được nhập như hồ sơ ứng viên, không có mã NV.

| # | Tên cột | Trường | Bắt buộc | Định dạng | Kiểm tra | Ví dụ giả |
| --- | --- | --- | --- | --- | --- | --- |
| B1 | Mã nhân viên | `Worker.employee_code` | Nếu có B | Text, tối đa 20 ký tự | Chỉ chữ, số, dấu gạch ngang (`^[A-Za-z0-9-]{1,20}$`). Trùng mã đã có hoặc trùng dòng khác trong file → **lỗi** | CN-00012 |
| B2 | Phòng ban | (suy ra từ bộ phận) | | Chọn từ danh sách | Nếu điền thì phải có B3 và đúng phòng ban của B3. Bắt buộc khi tên bộ phận ở B3 có ở hai phòng ban | Xưởng May |
| B3 | Bộ phận | `Employment.section` | | Chọn từ danh sách | **Không bắt buộc từ v1.1** (câu 48). Nếu điền thì phải khớp tên bộ phận đang dùng trong hệ thống; để trống thì hồ sơ vào nhóm "Chưa có bộ phận" | Chuyền May 1 |
| B4 | Tổ | `Employment.team` | | Chọn từ danh sách | Nếu điền thì phải có B3 và thuộc bộ phận ở B3 | Tổ 1 |
| B5 | Chức danh | `Employment.position` | Nếu có B | Chọn từ danh sách | Khớp tên chức danh đang dùng | Công nhân may |
| B6 | Ca làm việc | `Employment.shift` | | Chọn từ danh sách | Khớp tên ca đang dùng | Ca 1 |
| B7 | Ngày tiếp nhận | `Employment.received_date` | | Text dd/mm/yyyy | Để trống thì lấy bằng B8; không được sau B8 | 01/02/2023 |
| B8 | Ngày vào làm | `Employment.start_date` | Nếu có B | Text dd/mm/yyyy | Phải sau ngày sinh | 01/02/2023 |
| B9 | Trạng thái làm việc | `Employment.work_status` | Nếu có B | Chọn từ danh sách | Chờ nhận việc / Thử việc / Đang làm việc / Tạm hoãn / Đã nghỉ việc | Đang làm việc |
| B10 | Ngày nghỉ việc | `Employment.resign_date` | Theo điều kiện | Text dd/mm/yyyy | Bắt buộc khi B9 = Đã nghỉ việc; phải sau B8 | |
| B11 | Lý do nghỉ | `Employment.resign_reason` | Theo điều kiện | Chọn từ danh sách | Bắt buộc khi B9 = Đã nghỉ việc: Tự nghỉ / Hết hợp đồng / Chấm dứt hợp đồng / Khác | |
| B12 | Công ty khách | `WorkAssignment.client_company` | | Chọn từ danh sách | **v1.1, câu 48.** Khớp **cả tên và địa điểm** của một dòng công ty khách đang dùng trong danh mục (ghi dạng "tên – địa điểm" như ở sheet `Danh mục`). Không bắt buộc | Công ty Mẫu A – Tỉnh Mẫu |
| B13 | Ngày bắt đầu đợt | `WorkAssignment.start_date` | Nếu có B12 | Text dd/mm/yyyy | Bắt buộc khi có B12; phải sau ngày sinh. Không nhập khi không có B12 (báo lỗi). Đợt tạo ra có `end_date` rỗng (đang mở); nếu B9 = Đã nghỉ việc thì `end_date` = B10 | 01/03/2023 |

Mã NV là bắt buộc khi có phần B vì thông tin làm việc chỉ tồn tại với hồ sơ có mã NV (`models.md` 3.8). Muốn hệ thống tự cấp mã thì không nhập phần B; sau khi hồ sơ được duyệt, dùng "Tiếp nhận vào làm" như bình thường.

**Quy tắc cột v1.1 (câu 48):** "Nếu có B" của B3 đã bỏ (Bộ phận không bắt buộc); các cột bắt buộc khi có phần B còn là B1, B5, B8, B9. Vị trí của đợt làm việc tạo từ B12 lấy từ **chức danh B5**. **Không nhập lương**: file mẫu không có cột lương hay đơn giá; lương ghi trên giao diện sau khi nhập (A, Q). Việc nhập lương hàng loạt từ Excel là câu hỏi mở cho khách (`docs/tien-do.md`).

## 3. Xử lý khi nhập

### 3.1 Theo từng dòng
- Mỗi dòng xử lý độc lập trong một giao dịch riêng: **dòng đúng được nhập, dòng có lỗi bị bỏ qua** và được báo rõ (kịch bản nghiệm thu 16).
- Dòng **trống hoàn toàn** bị bỏ qua, không tính là lỗi.
- Cảnh báo không chặn nhập; dòng vẫn được nhập và cảnh báo hiện trong kết quả.
- **Ô công thức:** chỉ báo lỗi khi ô là **công thức Excel thật** (openpyxl đọc ô có `data_type == "f"`; file mở với `data_only=False`, vì với `data_only=True` openpyxl trả về giá trị đã tính và không phát hiện được công thức) → lỗi dòng "Ô không được chứa công thức Excel." Chữ thường bắt đầu bằng `=` `+` `-` `@` (ví dụ gạch đầu dòng "- " trong Kỹ năng, Ghi chú) vẫn nhận bình thường (`models.md` 4.5).
- **Lớp bảo vệ chính khi xuất:** mọi file Excel hệ thống xuất ra (danh sách, báo cáo, file mẫu, biên bản; Phase 7) ghi giá trị qua `apps.core.excel.safe_cell()`, hàm này thêm dấu `'` trước giá trị chữ bắt đầu bằng `=` `+` `-` `@`, tab hoặc xuống dòng. Áp dụng cho dữ liệu từ mọi nguồn: form, Excel, OCR, CV.
- Dòng hợp lệ tạo ra:
  - `Worker` ở trạng thái **Nháp**, mã hồ sơ sinh tự động (`next_code`), `StatusChange` tạo hồ sơ, `created_by` = người nhập.
  - `IdentityDocument` nếu có bất kỳ cột A6–A14; `EmergencyContact` nếu có A17–A19.
  - Nếu có phần B: `Worker.employee_code` = B1; `Employment`; một dòng `EmploymentHistory` loại `IMPORT`; nếu có B12 thì thêm một `WorkAssignment` (công ty = B12, vị trí = B5, `start_date` = B13, `end_date` rỗng hoặc = B10 khi Đã nghỉ việc), ghi `CREATE` qua `log()`; **không tạo `SalaryHistory`**. Hồ sơ vẫn ở Nháp và phải qua duyệt như bình thường.
  - Dòng có trạng thái **Đã nghỉ việc** và ngày nghỉ quá 30 ngày (cấu hình `auto_archive_resigned_days`) sẽ được tác vụ hằng ngày tự chuyển Lưu trữ ở lần chạy kế tiếp, không cần duyệt (câu 9, quy tắc 1). Hạn lưu trữ 10 năm tính từ ngày nghỉ. Hồ sơ vẫn tra cứu được trong danh sách với bộ lọc Lưu trữ.
  - `IdentityFieldSource` **không** tạo (dữ liệu từ Excel coi như nhập tay).
- Bộ đếm mã NV (`CodeSequence`): chỉ đẩy lên khi B1 khớp định dạng đang cấu hình (ví dụ `CN-00012` khi cấu hình là `CN` + 5 chữ số); mã khác định dạng (ví dụ `NV2019-A12`) vẫn được nhận nhưng không ảnh hưởng bộ đếm (câu 27).

### 3.2 Quyền
| Người nhập | Dòng chỉ có phần A | Dòng có phần B |
| --- | --- | --- |
| Admin, Quản lý nhân sự | Nhập | Nhập |
| Nhân viên HR | Nhập | **Lỗi dòng**: "Chỉ Admin hoặc Quản lý nhân sự được nhập thông tin làm việc." |
| Viewer | Không vào được trang nhập | |

### 3.3 Người duyệt phải khác người nhập
- Người nhập file là `created_by` của mọi hồ sơ được tạo, nên theo câu 8 **không tự duyệt được** các hồ sơ đó (kể cả Admin, Quản lý nhân sự).
- Vì vậy người nhập và người duyệt phải là **hai tài khoản khác nhau**. Ví dụ: Quản lý nhân sự A nhập file công nhân hiện hữu thì Admin hoặc Quản lý nhân sự B duyệt. Doanh nghiệp cần ít nhất hai tài khoản có quyền duyệt nếu Quản lý nhân sự tự nhập.
- **Không có chức năng duyệt hàng loạt**; mỗi hồ sơ duyệt riêng ở `/duyet-ho-so/` (câu 27). Điểm này nằm ở mục E (ưu tiên 4) của `docs/lam-ro-yeu-cau.md` để xác nhận với khách hàng.

### 3.4 Nhật ký
- Một dòng `AuditLog` hành động `IMPORT` cho cả lần nhập: `note` ghi số dòng đọc được, số dòng nhập, số dòng lỗi. Không ghi tên tệp gốc hay họ tên (câu 30).
- Mỗi hồ sơ tạo ra có dòng `CREATE` riêng qua `apps.audit.services.log()`; giá trị trường cá nhân nằm ở `AuditPersonalValue`.

### 3.5 Lỗi cả file (không nhập dòng nào)
| Tình huống | Thông báo |
| --- | --- |
| Không phải tệp `.xlsx` thật (kiểm tra chữ ký tệp) | "Tệp phải là file Excel .xlsx. Hãy tải file mẫu và nhập lại." |
| Quá 10 MB hoặc quá 1.000 dòng | "Tệp vượt giới hạn 10 MB hoặc 1.000 dòng. Hãy chia thành nhiều tệp nhỏ hơn." |
| Thiếu sheet `Hồ sơ` hoặc tiêu đề cột không khớp mẫu | "Tiêu đề cột không khớp file mẫu (cột X). Hãy dùng file mẫu mới nhất." (thiếu sheet: "Không thấy sheet “Hồ sơ”. Hãy dùng file mẫu mới nhất.") |
| Zip hỏng, nội dung không đọc được, hoặc nghi zip bomb: tổng dung lượng giải nén > 100 MB, hoặc tỉ lệ nén > 100 lần (kiểm tra danh sách mục trong zip và đếm lại dung lượng thật khi giải nén **trước khi** openpyxl mở tệp; mục nhỏ dưới 1 MiB không xét tỉ lệ) | "Tệp Excel không hợp lệ." |

Đã đo ở Phase 7 (`docs/hieu-nang.md`): nhập 1.000 dòng mất khoảng 13 giây (chỉ phần A) và 24 giây (có phần B và đợt làm việc), dưới ngưỡng 90 giây nên giữ giới hạn 1.000 dòng.

## 4. Màn hình kết quả

Hiển thị trên `/ho-so/nhap-excel/` sau khi nhập:

- Tóm tắt: "Đã đọc 120 dòng. Nhập thành công 117 hồ sơ. 3 dòng lỗi. 5 cảnh báo."
- Bảng lỗi (`_table`): Dòng · Cột · Nội dung lỗi. Mẫu câu: **"Dòng 7 – Số định danh: Số CCCD phải gồm 12 chữ số."**
- Bảng cảnh báo cùng dạng.
- Liên kết tới danh sách hồ sơ vừa nhập (`/ho-so/?trang_thai_ho_so=DRAFT&tao_tu=<hôm nay>`).
- Nhắc: "Các hồ sơ vừa nhập cần một tài khoản khác duyệt."

Danh mục thông báo lỗi và cảnh báo:

| Mức | Cột | Thông báo |
| --- | --- | --- |
| Lỗi | Mọi cột | Ô không được chứa công thức Excel. |
| Lỗi | A1 | Họ và tên không được để trống. |
| Lỗi | A2 | Số điện thoại phải gồm 10 chữ số, bắt đầu bằng 0. |
| Lỗi | A3 | Người dưới 15 tuổi không được nhập vào hệ thống. |
| Lỗi | A3, A8, A10, B7, B8, B10, B13 | Ngày phải theo dạng dd/mm/yyyy. |
| Lỗi | A4 | Giới tính chỉ nhận Nam hoặc Nữ. |
| Lỗi | A6 | Cần chọn loại giấy tờ khi đã nhập số định danh. |
| Lỗi | A7 | Số CCCD phải gồm 12 chữ số. |
| Lỗi | A7 | Số CCCD đã có trong hồ sơ HS-2026-00031. |
| Lỗi | A7 | Số CCCD trùng với dòng 12 trong cùng tệp. |
| Lỗi | A8 | Ngày cấp phải sau ngày sinh. |
| Lỗi | A14 | Số CMND cũ phải gồm 9 hoặc 12 chữ số. |
| Lỗi | A15 | Email không đúng định dạng. |
| Lỗi | A17–A19 | Thông tin người liên hệ khẩn cấp phải điền đủ họ tên, quan hệ và SĐT. |
| Lỗi | B1 | Mã nhân viên tối đa 20 ký tự, chỉ gồm chữ, số và dấu gạch ngang. |
| Lỗi | B1 | Mã nhân viên CN-00012 đã được dùng. |
| Lỗi | B1 | Cần nhập mã nhân viên khi có thông tin làm việc. |
| Lỗi | B1–B13 | Chỉ Admin hoặc Quản lý nhân sự được nhập thông tin làm việc. |
| Lỗi | B2, B3, B4, B5, B6, B12 | Không tìm thấy "…" trong danh mục. Hãy chọn từ sheet Danh mục. |
| Lỗi | B12 | Công ty khách "…" đã ngừng sử dụng (hoặc không khớp cả tên và địa điểm). |
| Lỗi | B13 | Cần nhập ngày bắt đầu đợt khi có công ty khách. |
| Lỗi | B13 | Chỉ nhập ngày bắt đầu đợt khi có công ty khách. |
| Lỗi | B2, B4 | Cần nhập bộ phận (B3) khi có phòng ban hoặc tổ. |
| Lỗi | B2 | Bộ phận "…" không thuộc phòng ban "…". |
| Lỗi | B2 | Có nhiều bộ phận tên "…"; hãy ghi thêm phòng ban. |
| Lỗi | B4 | Tổ "…" không thuộc bộ phận "…". |
| Lỗi | B10, B11 | Trạng thái Đã nghỉ việc cần ngày nghỉ và lý do nghỉ. |
| Cảnh báo | A3, A8, A10, B7, B8, B10, B13 | Ô ngày của Excel có thể bị đảo ngày/tháng; kiểm tra lại. |
| Cảnh báo | A2 | Số điện thoại trùng hồ sơ HS-2026-00045. Kiểm tra có phải cùng một người. |
| Cảnh báo | A1, A3 | Họ tên và ngày sinh trùng hồ sơ HS-2026-00045. Kiểm tra có phải cùng một người. |
| Cảnh báo | A3 | Người dưới 18 tuổi. Kiểm tra quy định sử dụng lao động chưa thành niên. |

Thông báo chỉ dẫn mã hồ sơ, không in họ tên của hồ sơ khác.

## 5. Dữ liệu ví dụ (sheet `Hướng dẫn`)

Toàn bộ là **dữ liệu hư cấu**. Số định danh và CMND cũ bắt đầu bằng `999` (không trùng mã tỉnh nào, chắc chắn không phải số thật; CLAUDE.md). Tên người, địa chỉ đều là tên mẫu.

| Cột | Ví dụ 1: ứng viên (chỉ phần A) | Ví dụ 2: công nhân hiện hữu (A + B) |
| --- | --- | --- |
| Họ và tên | Trần Thị Mẫu | Lê Văn Thử |
| Số điện thoại | 0900000001 | 0900000003 |
| Ngày sinh | 15/03/2000 | 02/09/1990 |
| Giới tính | Nữ | Nam |
| Quốc tịch | Việt Nam | Việt Nam |
| Loại giấy tờ | CCCD gắn chip (mẫu 2021) | Thẻ Căn cước (từ 01/7/2024) |
| Số định danh | 999000000001 | 999000000002 |
| Ngày cấp | 20/06/2023 | 10/08/2024 |
| Nơi cấp | Cục Cảnh sát QLHC về TTXH | Bộ Công an |
| Ngày hết hạn | 15/03/2040 | 02/09/2030 |
| Quê quán | Xã Mẫu Một, Tỉnh Mẫu | |
| Nơi đăng ký khai sinh | | Xã Mẫu Hai, Tỉnh Mẫu |
| Nơi thường trú/cư trú | Số 1 Đường Mẫu, Phường Mẫu | Số 2 Đường Mẫu, Phường Mẫu |
| Số CMND cũ | 999000001 | |
| Email | mau.tran@example.com | |
| Nơi ở hiện tại | Khu trọ Mẫu, Phường Mẫu | Khu trọ Mẫu, Phường Mẫu |
| Người liên hệ khẩn cấp – Họ tên | Trần Văn Mẫu | Lê Thị Thử |
| Người liên hệ khẩn cấp – Quan hệ | Bố | Vợ |
| Người liên hệ khẩn cấp – SĐT | 0900000002 | 0900000004 |
| Kỹ năng | - Vận hành máy may công nghiệp | |
| Ghi chú | | |
| Mã nhân viên | | CN-00012 |
| Phòng ban | | Xưởng May |
| Bộ phận | | Chuyền May 1 |
| Tổ | | Tổ 1 |
| Chức danh | | Công nhân may |
| Ca làm việc | | Ca 1 |
| Công ty khách | | Công ty Mẫu A – Tỉnh Mẫu |
| Ngày bắt đầu đợt | | 01/03/2023 |
| Ngày tiếp nhận | | 01/02/2023 |
| Ngày vào làm | | 01/02/2023 |
| Trạng thái làm việc | | Đang làm việc |
| Ngày nghỉ việc | | |
| Lý do nghỉ | | |

Tên phòng ban, bộ phận, tổ, chức danh, ca ở ví dụ là dữ liệu mẫu của `seed_demo`; khi dùng thật phải khớp danh mục của doanh nghiệp (sheet `Danh mục`).

## 6. Không có trong file mẫu

- Mã hồ sơ: luôn do hệ thống sinh.
- Trạng thái xác minh: luôn là Nháp.
- Đồng ý xử lý dữ liệu, tài liệu, ảnh: ghi nhận trên từng hồ sơ sau khi nhập (bắt buộc trước khi gửi duyệt).
- Ứng tuyển, học vấn, chứng chỉ, kinh nghiệm, hợp đồng: nhập trên giao diện.
- Tình trạng hôn nhân, dân tộc: không thu thập (mục VI).
