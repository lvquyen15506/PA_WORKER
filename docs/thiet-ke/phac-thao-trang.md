# Phác thảo trang – PA Worker

Phase 3 · Ngày 22/11/2026 · Dựa trên `docs/thiet-ke/trang.md` mục 2–5 và skill `pa-ui`. Phác thảo **bố cục**, không phải giao diện cuối: không màu, không icon ngoài quy định pa-ui mục 6. Tên model, URL, quyền lấy từ `trang.md`; file này không đổi các thứ đó.

## 0. Quy ước

**Vai trò:** A = Admin · Q = Quản lý nhân sự · H = Nhân viên HR · V = Viewer.

**Ký hiệu khung:**

| Ký hiệu | Nghĩa |
| --- | --- |
| `[_ten_component]` | Include component trong `templates/components/` |
| `[ Nút ]` | Nút; `[*Nút*]` là nút chính (tối đa một mỗi màn hình) |
| `(ô)` | Ô nhập / ô chọn |
| `{vai trò}` | Chỉ hiện với các vai trò này; không ghi = mọi vai trò vào được trang |
| `<icon>` | Icon Bootstrap Icons (chỉ ở vị trí cho phép) |

**Quy tắc chung (không vẽ lại ở từng trang):**
- Mọi trang (trừ Đăng nhập) kế thừa `base.html` và bắt đầu bằng `[_page_header]`: breadcrumb nhỏ phía trên, tiêu đề, nút thao tác căn phải.
- Thông báo sau thao tác dùng `[_alert]` ngay dưới đầu trang, tự ẩn sau 5 giây; lỗi kiểm tra tóm tắt ở đầu form và hiện lại dưới từng ô (`_form_field`).
- Danh sách trống dùng `[_empty_state]`: một câu giải thích và một nút (nếu vai trò có quyền thực hiện hành động đó).
- Hộp xác nhận mọi thao tác không hoàn tác được dùng `[_confirm_modal]`. Modal chỉ là giao diện: nút xác nhận gửi form POST có CSRF, máy chủ kiểm tra lại mọi trường.
- Nút ẩn với vai trò không có quyền chỉ là phần phụ; máy chủ vẫn trả 403 (`trang.md` mục 1).
- Ô trống trong bảng hiện "—"; ngày dd/mm/yyyy; cột Mã và Trạng thái không xuống dòng; cột Thao tác căn phải, tối đa 3 nút icon mỗi dòng.
- Viewer không thấy: số CCCD đầy đủ (chỉ dạng che), CMND cũ, địa chỉ thường trú/cư trú, quê quán, ảnh CCCD. (Mức lương mong muốn: từ v1.1 Viewer cũng xem được, câu 48.)

## 1. Khung chung (`base.html`)

Màn hình rộng (≥ 992px):

```
+-----------------+------------------------------------------------------+
| PA Worker       | (Tìm nhanh <bi-search> ...)     Họ tên · Vai trò  [Menu v]|  thanh trên
|-----------------|------------------------------------------------------|
| <>  Tổng quan   |                                                      |
| <>  Hồ sơ CN    |   Vùng nội dung (nền xám nhạt, padding 24px)         |
| <>  Thêm hồ sơ  |   [_page_header]                                     |
| <>  Tuyển dụng  |   [_alert]                                           |
| <>  Duyệt hồ sơ |   ...nội dung trang...                               |
| <>  Báo cáo     |                                                      |
| <>  Nhật ký     |                                                      |
| <>  Tài khoản   |                                                      |
| <>  Cài đặt     |------------------------------------------------------|
|   (sidebar 240) | PA Worker v1.0 · Phát triển bởi QQIT · Giới thiệu    |  chân trang
+-----------------+------------------------------------------------------+
```

- Menu người dùng (`Menu v`): Đổi mật khẩu, Đăng xuất (POST). Tên + vai trò viết chữ, không icon.
- Mục đang chọn: nền trắng 10% + vạch trái 3px (kiểu dáng ở `pa.css`).
- Mục menu theo vai trò: A thấy cả 9; Q thấy 7 (không Tài khoản, Cài đặt); H thấy 5 (Tổng quan, Hồ sơ công nhân, Thêm hồ sơ, Tuyển dụng, Báo cáo); V thấy 4 (Tổng quan, Hồ sơ công nhân, Tuyển dụng, Báo cáo).

Màn hình hẹp (< 992px, ví dụ 390px): sidebar ẩn, thanh trên có nút chữ "Menu" (không icon, đã chốt 22/11/2026 vì dễ hiểu với người dùng không rành máy tính) bên trái; ô tìm nhanh nằm trong menu mở ra; bảng cuộn ngang trong khung riêng (không cuộn ngang cả trang).

```
+------------------------------------+
| [Menu]  PA Worker   [Tên v]        |
|------------------------------------|
| [_page_header]  (nút xuống dòng)   |
| nội dung xếp một cột               |
| PA Worker v1.0 · Phát triển bởi QQIT|
+------------------------------------+
```

**Khung tối giản (`{% block shell %}` rỗng):** dùng cho Đăng nhập; không sidebar, không thanh trên.

## 2. 12 trang chính

### 2.1 Đăng nhập `/dang-nhap/` (khung tối giản)

```
+------------------------------------------+
|                PA Worker                 |
|        Phần mềm quản lý hồ sơ công nhân  |
|  +------------------------------------+  |
|  | Đăng nhập                          |  |
|  | [_alert] (lỗi / khóa tạm / đã khóa)|  |
|  | [_form_field] Tên tài khoản *      |  |
|  | [_form_field] Mật khẩu *           |  |
|  |                  [*Đăng nhập*]     |  |
|  +------------------------------------+  |
|        Phát triển bởi QQIT               |
+------------------------------------------+
```

Thông báo lỗi đúng chữ ở `trang.md` mục 5.1 (sai mật khẩu, bị khóa, khóa tạm đến hh:mm). Không có `_page_header` (ngoại lệ đã ghi ở `trang.md` mục 1).

### 2.2 Dashboard `/`

```
[_page_header] Tổng quan
[_stat_card] x9   (lưới 3 hàng x 3 thẻ; mỗi thẻ là liên kết tới danh sách đã lọc)
  Tổng số hồ sơ | Đang làm việc | Hồ sơ mới trong tháng
  Chờ duyệt | Thiếu giấy tờ | Hoàn thiện
  Đang tuyển dụng | Nghỉ việc trong tháng | Hợp đồng sắp hết hạn
+-------------------------------+-------------------------------+
| Biểu đồ cột: Vào làm / nghỉ    | Biểu đồ: theo phòng ban / bộ   |
| việc 12 tháng (người)          | phận (người)                   |
+-------------------------------+-------------------------------+
| Biểu đồ: giới tính, 5 nhóm tuổi| Biểu đồ: theo trạng thái xác   |
| + "Chưa có ngày sinh", trình độ| minh                           |
+-------------------------------+-------------------------------+
Việc cần làm: 4 khối  [_table] nhỏ + [_status_badge]
  Chờ duyệt {A,Q} | Cần bổ sung | CCCD sắp hết hạn
  Đợt làm việc sắp đủ 12 tháng   (v1.1; hàng thứ hai, khối cuối; không thêm thẻ số liệu)
     cột: Mã NV | Công ty khách | Ngày bắt đầu | Đủ 12 tháng ngày [_status_badge: Sắp hết hạn]
  (trống -> [_empty_state] một câu, không nút)
```

Mỗi biểu đồ có tiêu đề nói kết quả và đơn vị. Khối "Chờ duyệt" chỉ hiện với A, Q (H, V không duyệt). Số dòng trong danh sách đích bằng số trên thẻ.

### 2.3 Danh sách công nhân `/ho-so/`

```
[_page_header] Hồ sơ công nhân     [ Xuất Excel ]{A,Q,H}  [*Thêm hồ sơ*]{A,Q,H}
[_filter_bar] (Phòng ban)(Bộ phận)(Chức danh)(Trình độ)(Công ty khách)   <- v1.1, theo đợt đang diễn ra
              (TT hồ sơ)(TT làm việc)(Thiếu giấy tờ)(Hoàn thiện)
              (Tiếp nhận từ)(đến)         [ Lọc ] [ Xóa lọc ]
[_table]
 STT | Mã NV | Họ và tên | Ngày sinh | Giới tính | SĐT | Công ty khách | Chức danh |   <- v1.1: cột "Bộ phận" đổi thành "Công ty khách" (đợt đang diễn ra, "—" nếu chưa có)
 Ngày vào làm | TT hồ sơ [_status_badge] | TT làm việc [_status_badge] | Thao tác
 ...                                   <bi-eye> <bi-pencil>{A,Q,H}
[_pagination] Hiển thị 1–20 / 512
(không có kết quả -> [_empty_state] "Không có hồ sơ phù hợp." + [ Xóa lọc ])
```

**Đã chốt ở Phase 4 (22/11/2026):**
- Sắp xếp dùng ô chọn "Sắp xếp" trong thanh lọc (Họ tên, Mã NV, Ngày sinh, Ngày vào làm, tăng/giảm), vì `_table` không có tiêu đề bấm được và `/ui-kit/` đã đóng kiểu dáng.
- Nút trên dòng chỉ có Xem và Sửa; Lưu trữ làm ở trang chi tiết (cần hộp xác nhận và lý do).
- Tiêu đề hai cột trạng thái viết tắt "TT hồ sơ" và "TT làm việc" để 12 cột vừa khung ở 1366 px (đã đo: đủ chỗ, không cuộn ngang).
- Bộ lọc thêm "Trạng thái tuyển dụng" (xét lần ứng tuyển gần nhất), "Hoàn thiện", khoảng ngày tiếp nhận; tham số URL tiếng Việt không dấu trùng với liên kết thẻ Dashboard.
- Bộ lọc được giữ trong phiên, **trừ chữ tìm kiếm** (có thể là số CCCD, không lưu vào phiên); "Xóa lọc" là `?reset=1`.

**v1.1 (quyết định 23/11/2026, câu 48):** thêm ô lọc "Công ty khách" (hiện "tên – địa điểm", `_form_field` dạng chọn trong `_filter_bar`) và tham số `?dot_sap_du_han=1` từ Dashboard; bộ lọc Bộ phận có thêm lựa chọn "Chưa có bộ phận". **Cột "Bộ phận" được thay bằng cột "Công ty khách"**, vẫn 12 cột nên vừa khung 1366 px; bộ phận nội bộ xem ở tab Quá trình làm việc.

Ô tìm nhanh ở thanh trên gửi tới `?q=`. Viewer: không tìm theo CCCD, không có nút Xuất Excel, Thêm hồ sơ, Sửa.

### 2.4 Thêm hồ sơ `/ho-so/them/` {A,Q,H}

```
[_page_header] Thêm hồ sơ
+------------------+ +----------------------+ +---------------------+
| [_stat_card]     | | [_stat_card]         | | [_stat_card]        |
| (không số liệu)  | | (không số liệu)      | | (không số liệu)     |
| Nhập tay         | | Từ CCCD và CV        | | Từ file Excel       |
| dòng phụ 1 câu   | | dòng phụ 1 câu       | | dòng phụ 1 câu      |
+------------------+ +----------------------+ +---------------------+
```

Mỗi thẻ là liên kết tới `/ho-so/them/nhap-tay/`, `/nhap-cccd/`, `/ho-so/nhap-excel/`. Không số, không icon trong thẻ.

**Form nhập tay `/ho-so/them/nhap-tay/`:**

```
[_page_header] Thêm hồ sơ – nhập tay
[_form_section] Thông tin cá nhân   (lưới 2 cột)
  [_form_field] Họ và tên *        [_form_field] Số điện thoại *
  [_form_field] Ngày sinh          [_form_field] Giới tính
  [_form_field] Số CCCD            (kiểm tra trùng khi rời ô: HTMX, khung lỗi + [ Mở hồ sơ cũ ])
  [_form_field] Ngày cấp, Nơi cấp, Quê quán, Địa chỉ thường trú...
[_form_section] Liên hệ khẩn cấp   (mỗi người một khối; dòng đã lưu có ô "Xóa người liên hệ này")
                                              [ Hủy ]  [*Lưu hồ sơ*]
```

Nháp chỉ cần họ tên + SĐT (câu 5). **Đã chốt ở Phase 4 (22/11/2026):** bỏ khối "Thông tin ban đầu (chỉ A, Q)" vì thông tin làm việc chỉ có khi hồ sơ có mã NV: nhập qua "Tiếp nhận vào làm" (Phase 6) hoặc file Excel (Phase 7). Form chia 3 nhóm trường (Thông tin cá nhân, Giấy tờ, Khác) rồi tới Liên hệ khẩn cấp.

### 2.5 Nhập từ CCCD và CV `/nhap-cccd/` → `/nhap-cccd/<uuid>/` {A,Q,H}

Vẽ kỹ ở mục 4.

### 2.6 Chi tiết hồ sơ `/ho-so/<id>/`

Vẽ kỹ ở mục 3.

### 2.7 Tuyển dụng `/tuyen-dung/`

```
[_page_header] Tuyển dụng
[_filter_bar] (TT tuyển dụng)(Vị trí)(Nguồn)(Từ ngày)(đến)   [ Lọc ] [ Xóa lọc ]
[Phỏng đoán – chốt ở Phase 6: cột và bộ lọc]
[_table]
 Mã hồ sơ | Họ và tên | Vị trí | Nguồn | Ngày ứng tuyển | Mức lương mong muốn |
 Trạng thái [_status_badge] | Thao tác <bi-eye> <bi-pencil>{A,Q,H}
[_pagination]    ([_empty_state] khi trống)
```

Viewer: thấy cột Mức lương mong muốn từ v1.1 (câu 48, bỏ ẩn ở câu 13).

### 2.8 Duyệt hồ sơ `/duyet-ho-so/` {A,Q}

```
[_page_header] Duyệt hồ sơ
[_filter_bar] (Người gửi)(Nguồn nhập)(Từ ngày)(đến)   [ Lọc ] [ Xóa lọc ]
[Đã chốt ở Phase 4, 22/11/2026]
[_table]  cũ nhất trước (theo lần gửi duyệt gần nhất)
 Mã hồ sơ | Họ và tên | Người gửi duyệt | Ngày gửi | Giấy tờ [_status_badge: Thiếu giấy tờ] |
 Ghi chú | Thao tác <bi-eye>
 (dòng do chính bạn tạo/gửi: Ghi chú "Bạn không duyệt được hồ sơ này")
[_pagination]    ([_empty_state] "Không có hồ sơ chờ duyệt.")
```

Bộ lọc: Người gửi duyệt, Từ ngày, Đến ngày (ngày gửi). **Bỏ cột "Nguồn nhập" và "Trạng thái"**: chưa có trường nào lưu nguồn nhập; mọi dòng đều Chờ duyệt.

Nút Duyệt / Trả lại / Từ chối nằm ở trang chi tiết (mục 3), không đặt trong bảng.

### 2.9 Thống kê báo cáo `/bao-cao/`

```
[_page_header] Thống kê báo cáo    [ In ]{A,Q,H}  [ Xuất Excel ]{A,Q,H}
[_filter_bar] (Loại báo cáo)(Từ ngày)(đến)(Phòng ban)   [ Xem ] [ Xóa lọc ]
Biểu đồ Chart.js (1 hoặc 2 tùy loại, có tiêu đề kết quả + đơn vị)
[_table]  số liệu cùng nội dung biểu đồ
([_empty_state] khi không có dữ liệu trong khoảng đã chọn)
```

Viewer xem được, không có nút Xuất Excel và In. Danh mục loại báo cáo chốt ở Phase 7. v1.1: có loại "Công nhân đang làm theo công ty khách hàng": biểu đồ cột (người) + `_table` Công ty | Địa điểm | Số công nhân đang làm; mỗi số liên kết tới `/ho-so/?cong_ty_khach=<id>`.

### 2.10 Nhật ký thao tác `/nhat-ky/` {A,Q}

```
[_page_header] Nhật ký thao tác
[_filter_bar] (Người thực hiện)(Hồ sơ)(Hành động)(Từ ngày)(đến)  [ Lọc ] [ Xóa lọc ]
[Phỏng đoán – chốt ở Phase 7: cột và bộ lọc]
[_table]
 Thời điểm | Người thực hiện | Hành động | Đối tượng | Nội dung thay đổi
 (trường cá nhân: "(xem giá trị chi tiết)" -> mở giá trị trước/sau, giải mã, chỉ A, Q)
[_pagination]    ([_empty_state])
```

Không có nút sửa, xóa. Hồ sơ đã ẩn danh hiện "(đã ẩn danh)".

### 2.11 Quản lý tài khoản `/tai-khoan/` {A}

```
[_page_header] Quản lý tài khoản                          [*Thêm tài khoản*]
[_tabs]  Danh sách | Lịch sử đăng nhập
[Phỏng đoán – chốt ở Phase 3: giữ cột đã có từ Phase 2; Thao tác dạng icon + tooltip theo pa-ui mục 4]
[_table]
 Tên đăng nhập | Họ tên | Vai trò | Trạng thái [_status_badge: nhãn hiển thị] | Đăng nhập lần cuối |
 Thao tác  <bi-pencil>  [ Khóa ]/[ Mở khóa ]  [ Đặt lại mật khẩu ]
[_pagination]
```

Trạng thái: Đang hoạt động / Bị khóa (Admin khóa) / Khóa tạm đến hh:mm. Khóa và Đặt lại mật khẩu đi qua `[_confirm_modal]`. Nút Khóa tắt (disabled) khi là chính mình hoặc Admin cuối cùng đang hoạt động, kèm lý do ở tooltip. Mật khẩu tạm hiện một lần ở trang riêng sau khi tạo / đặt lại (`_form_section` chế độ xem + `_alert`).

**Form `/tai-khoan/them/` và `/<id>/sua/`:** `[_form_section]` với `[_form_field]` Tên tài khoản (khóa khi sửa), Họ tên, Vai trò (khóa khi sửa chính mình); `[ Hủy ] [*Lưu tài khoản*]`.

### 2.12 Cài đặt `/cai-dat/` {A}

```
[_page_header] Cài đặt
[_tabs]  Danh mục | Sinh mã | Ngưỡng và thời hạn | OCR và QR | Chờ hủy | Biên bản hủy
Tab Danh mục: danh sách loại (phòng ban, bộ phận, tổ, chức danh, ca, nguồn ứng tuyển,
              trình độ, nhóm tài liệu, loại tài liệu, công ty khách hàng)  -> mỗi loại 1 [_table]
  Tên | Mã | Trạng thái [_status_badge: Đang dùng / Ngừng] | Thao tác <bi-pencil> [ Ngừng ]/[ Dùng lại ]
  Công ty khách hàng (v1.1): Tên | Địa điểm | Trạng thái | Thao tác (không có cột Mã; mỗi địa điểm một dòng)
     form thêm/sửa: [_form_section] [_form_field] Tên công ty *, Địa điểm (tỉnh/thành) *
  [ Thêm ] ở đầu bảng      (không có nút xóa)
Tab Sinh mã / Ngưỡng / OCR và QR: [_form_section] + [_form_field]   [ Hủy ] [*Lưu cài đặt*]
  (OCR và QR: bật API ngoài -> [_alert] cảnh báo ảnh được gửi ra ngoài)
```

"Đang dùng / Ngừng" của danh mục là nhãn hiển thị từ cờ `is_active` (mục 7, điểm 1), không phải bộ trạng thái.

## 3. Chi tiết hồ sơ `/ho-so/<id>/` (vẽ kỹ)

### 3.1 Khung chung của trang

```
[_page_header]
  breadcrumb:  Hồ sơ công nhân / HS-2026-000123
  tiêu đề:     Nguyễn Văn An    [_status_badge: TT hồ sơ] [_status_badge: TT làm việc]
  nút (căn phải, xem bảng 3.2)
[_alert]  (kết quả thao tác; hoặc ghi chú "Trả lại: <lý do>" khi hồ sơ Cần bổ sung)
[_tabs]  Thông tin cá nhân | Tuyển dụng & CV | Quá trình làm việc | Tài liệu | Lịch sử thay đổi
          (?tab=ca-nhan mặc định | tuyen-dung | lam-viec | tai-lieu | lich-su)
  (nội dung tab - 3.3)
```

Tab đổi bằng liên kết `?tab=` (tải lại trang), riêng các mảnh con (lịch sử chi tiết, kiểm tra trùng) tải bằng HTMX. Hồ sơ đã ẩn danh: các giá trị cá nhân hiện "(đã ẩn danh)", mọi nút ghi bị ẩn.

### 3.2 Nút ở đầu trang (theo trạng thái hồ sơ và vai trò)

Một nút chính duy nhất mỗi trạng thái.

| Nút | Loại | Khi nào hiện | A | Q | H | V |
| --- | --- | --- | --- | --- | --- | --- |
| Gửi duyệt | chính | Nháp hoặc Cần bổ sung | ✓ | ✓ | ✓ | |
| Duyệt hồ sơ | chính | Chờ duyệt và người xem **không** phải người tạo/gửi (câu 8) | ✓ | ✓ | | |
| Mở lại hồ sơ | chính | Lưu trữ và chưa ẩn danh | ✓ | ✓ | ✓ | |
| Sửa hồ sơ | phụ | Theo bảng 4.4 `models.md` | ✓ | ✓ | ✓ | |
| Trả lại | phụ | Chờ duyệt, như Duyệt hồ sơ; modal có ô lý do bắt buộc | ✓ | ✓ | | |
| Từ chối | nguy hiểm (viền) | Chờ duyệt, như Duyệt hồ sơ; modal có ô lý do bắt buộc | ✓ | ✓ | | |
| Lưu trữ | nguy hiểm (viền) | H: chỉ từ Nháp, Cần bổ sung, Bị từ chối. A, Q: thêm Đã xác minh (lý do bắt buộc; ẩn/tắt khi Thử việc hoặc Đang làm việc, tooltip nêu lý do) | ✓ | ✓ | ✓* | |
| Ẩn danh hóa theo yêu cầu | nguy hiểm (viền) | Lưu trữ và chưa ẩn danh (câu 38) | ✓ | | | |

Khi hai nút "chính" cùng đủ điều kiện (không xảy ra, vì trạng thái loại trừ nhau) thì ưu tiên theo thứ tự bảng. Nút ghi lại từng thao tác trong audit log theo `trang.md` mục 5.4.

**Modal Trả lại / Từ chối** (`_confirm_modal`, `{% block body %}`): `_form_field` Lý do * (gợi ý muted "Không ghi họ tên, chỉ dùng mã hồ sơ"); `[ Hủy ] [Trả lại]` hoặc `[ Hủy ] [Từ chối]` (nút xác nhận `btn-danger` chỉ trong modal).

**Modal Ẩn danh hóa theo yêu cầu** (`trang.md` mục 5.4):

```
+--------------------------------------------------------+
| Ẩn danh hóa hồ sơ HS-2026-000123                  [x] |
| Thao tác này không hoàn tác được. Thông tin cá nhân,   |
| giấy tờ và giá trị chi tiết trong nhật ký của hồ sơ    |
| sẽ bị xóa.                                             |
| [_form_field] Lý do *            (gợi ý: chỉ dùng mã)  |
| [_form_field] Số / ngày đơn yêu cầu *                  |
| [_form_field] Gõ lại mã hồ sơ để xác nhận *            |
|                      [ Hủy ]  [ Ẩn danh hóa ]          |
+--------------------------------------------------------+
```

Nút "Ẩn danh hóa" chỉ bật khi ô mã khớp (giao diện); máy chủ kiểm tra lại mọi trường.

### 3.3 Nội dung 5 tab

**Tab 1 – Thông tin cá nhân (`ca-nhan`)**

```
[_form_section] (chế độ xem, 2 cột nhãn–giá trị)
  Thông tin cơ bản : Họ tên, Ngày sinh, Giới tính, SĐT, Email, Nơi ở hiện tại
  Giấy tờ          : Số CCCD ****1234 [ Hiện số đầy đủ ]{A,Q,H}, Ngày cấp, Nơi cấp, Ngày hết hạn
                     CMND cũ{A,Q,H}, Địa chỉ thường trú{A,Q,H}, Quê quán{A,Q,H}
  Liên hệ khẩn cấp : Họ tên, Quan hệ, SĐT
  Đồng ý xử lý dữ liệu: Hình thức, Ngày, Người ghi nhận   [ Ghi nhận đồng ý ]{A,Q,H} [ In mẫu ]{A,Q,H}
[_empty_state] (nếu chưa có đồng ý) "Chưa ghi nhận đồng ý xử lý dữ liệu."
```

"Hiện số đầy đủ" gọi HTMX, ghi log `VIEW_FULL_ID`. Viewer chỉ thấy các trường không nhạy cảm; trường ẩn không hiện nhãn trống mà bỏ hẳn.

**Tab 2 – Tuyển dụng & CV (`tuyen-dung`)**

```
[_table] Lần ứng tuyển:  Vị trí | Nguồn | Ngày | Mức lương mong muốn | TT tuyển dụng [_status_badge] | Thao tác
         [ Thêm lần ứng tuyển ]{A,Q,H}     [ Tiếp nhận ]{A,Q,H, chỉ khi Đạt + Đã xác minh}
[_table] Học vấn      [ Thêm ]{A,Q,H}    cột: Trình độ | Trường | Ngành | Năm | Thao tác <pencil> [ Xóa ]
[_table] Chứng chỉ    [ Thêm ]{A,Q,H}
[_table] Kinh nghiệm  [ Thêm ]{A,Q,H}
Kỹ năng: một đoạn văn bản (câu 25)
(mỗi bảng trống -> [_empty_state] một câu + nút Thêm nếu có quyền)
```

Xóa dòng con qua `[_confirm_modal]` (dòng con là ngoại lệ được xóa, giá trị cũ ghi nhật ký).

**Tab 3 – Quá trình làm việc (`lam-viec`)**

```
[_form_section] Hiện tại (xem): Phòng ban, Bộ phận ("—" nếu chưa có, v1.1), Chức danh, Ca, Ngày vào làm, TT làm việc [_status_badge]
                                  [ Ghi nhận thay đổi ]{A,Q,H}
[_form_section] Đợt làm việc hiện tại (v1.1, xem): Công ty khách | Địa điểm | Vị trí | Từ ngày | Đến ngày (trống = đang mở)
                [_status_badge: Sắp hết hạn] khi sắp đủ 12 tháng              [ Thêm đợt làm việc ]{A,Q,H}
[_table] Lịch sử đợt làm việc (v1.1): Công ty khách | Địa điểm | Vị trí | Từ ngày | Đến ngày | Ghi chú | <bi-pencil>{A,Q,H}
         (đợt mới nhất trước; không có nút xóa; [_empty_state] nếu chưa có đợt nào)
[_form_section] Lương hiện tại của đợt hiện tại (v1.1, xem, mọi vai trò): Lương tháng | Đơn giá tháng (tính cho công ty khách) | Áp dụng từ
                                                       [ Ghi nhận thay đổi lương ]{A,Q}  (thêm dòng cho một đợt)
[_table] Lịch sử lương (v1.1, câu 48: mỗi đợt một chuỗi): Công ty khách (đợt) | Ngày áp dụng | Lương tháng | Đơn giá tháng | Lý do | Người sửa | Ngày ghi
         (nhóm/sắp theo đợt, mới nhất trước; mọi vai trò xem; chỉ thêm dòng, không có nút sửa/xóa; cột số căn phải, ô trống "—")
[_table] Lịch sử điều chuyển: Ngày hiệu lực | Thay đổi (từ → đến) | Số quyết định | Lý do
[_table] Hợp đồng: Loại | Số HĐ | Từ ngày | Đến ngày [_status_badge: Sắp hết hạn nếu có] | Tệp (bản hiện hành) <bi-download>{A,Q,H} | <pencil>
         [ Thêm hợp đồng ]{A,Q,H}
```

**Form v1.1 ở tab này** (cùng khuôn `[_form_section]` + `[_form_field]`, `[ Hủy ] [*Lưu*]`): *Thêm/sửa đợt làm việc* gồm Công ty khách * (chọn, hiện "tên – địa điểm"), Vị trí * (chọn từ Chức danh), Ngày bắt đầu *, Ngày kết thúc, Ghi chú; *Ghi nhận thay đổi lương* gồm Đợt làm việc * (chọn trong các đợt của công nhân, mặc định đợt hiện tại), Lương tháng *, Đơn giá tháng (được trống), Ngày áp dụng * (trong khoảng ngày của đợt), Lý do * (gợi ý "Không ghi họ tên, chỉ dùng mã hồ sơ"). Lỗi chồng lấn ngày hoặc đang có đợt mở hiện bằng `_alert`/lỗi dưới ô. Chỉ dùng component đã duyệt ở `/ui-kit/`: `_form_section`, `_form_field`, `_table`, `_status_badge` (nhãn "Sắp hết hạn" sẵn có), `_alert`, `_empty_state`; không thêm component hay nhãn mới.

**Tab 4 – Tài liệu (`tai-lieu`)**

```
[ Tải tài liệu lên ]{A,Q,H}      (trạng thái hồ sơ cho phép theo bảng 4.4)
[_table] Nhóm / Loại tài liệu | Tên tệp | Ngày tải | Phiên bản | Xác minh [_status_badge: bộ riêng] | Thao tác
         Thao tác: <bi-eye> xem, <bi-download> tải, [ Thay thế ]{A,Q; H khi Nháp/Cần bổ sung},
                   [ Xác minh ]{A,Q}, [ Phiên bản cũ ]
Danh sách "Còn thiếu": loại tài liệu bắt buộc chưa có (chữ muted)
```

Viewer thấy loại, ngày, trạng thái nhưng **không** có liên kết/nút xem, tải (kịch bản 2).

**Tab 5 – Lịch sử thay đổi (`lich-su`)**

```
Dòng thời gian trạng thái (mọi vai trò): ngày giờ · người · chuyển trạng thái [_status_badge] → [_status_badge] · lý do (chỉ mã hồ sơ)
Chi tiết thay đổi từng trường {A,Q}: [_table] Thời điểm | Người | Trường | Trước | Sau
   (trường cá nhân: "(xem giá trị chi tiết)" -> HTMX giải mã từ AuditPersonalValue; CCCD/CMND vẫn che)
```

H và V chỉ thấy dòng thời gian trạng thái.

## 4. Màn hình đối chiếu `/nhap-cccd/<uuid>/` (vẽ kỹ)

### 4.1 Bước tải ảnh `/nhap-cccd/` {A,Q,H}

```
[_page_header] Nhập từ CCCD và CV
[_form_section] Tải tệp (ít nhất một)
  [_form_field] Ảnh mặt trước CCCD   [_form_field] Ảnh mặt sau CCCD
  [_form_field] CV (PDF, DOC, DOCX)  gợi ý muted: tối đa 10 MB, JPG/PNG/PDF
  [_alert] "Ảnh và kết quả nhận diện bị xóa sau 24 giờ nếu chưa lưu hồ sơ."
                                           [ Hủy ]   [*Nhận diện*]
```

### 4.2 Đối chiếu (2 cột 50/50)

```
[_page_header] breadcrumb: Thêm hồ sơ / Nhập từ CCCD · tiêu đề: Đối chiếu thông tin
[_alert]  "Kết quả nhận diện chưa được lưu. Kiểm tra từng trường trước khi lưu hồ sơ."
[_alert]  (nếu có) CCCD trùng: "Số CCCD đã có hồ sơ HS-...." + [ Mở hồ sơ cũ ]
+-----------------------------------+-----------------------------------------+
| CỘT TRÁI (ảnh)                    | CỘT PHẢI (form đối chiếu)               |
|                                   |                                         |
| Ảnh mặt trước       [ Phóng to ]  | [_form_section] Thông tin cá nhân       |
| +-------------------------------+ |  Họ và tên *        [_source_tag: QR]   |
| |        (ảnh CCCD mặt trước)   | |  (ô)                                    |
| +-------------------------------+ |  Ngày sinh *        [_source_tag: QR]   |
| Ảnh mặt sau         [ Phóng to ]  |  (ô)                                    |
| +-------------------------------+ |  Số CCCD *          [_source_tag: QR]   |
| |        (ảnh CCCD mặt sau)     | |  (ô)    <- kiểm tra trùng khi rời ô     |
| +-------------------------------+ |  Địa chỉ thường trú [_source_tag: OCR]  |
| CV: tên tệp   [ Xem CV ]          |  +-- nền vàng nhạt, viền warning -----+  |
| (trích từ CV hiện ở cột phải,     |  | (ô, độ tin cậy thấp)               |  |
|  gắn nhãn Nhập tay/OCR)           |  | [ ] Đã kiểm tra                    |  |
|                                   |  +------------------------------------+  |
|                                   |  Ngày cấp / Nơi cấp  [_source_tag: Nhập tay] |
|                                   | [_form_section] Từ CV (Học vấn, Kinh     |
|                                   |  nghiệm, Kỹ năng: gợi ý, HR sửa tay)     |
|                                   | [_form_section] Liên hệ, SĐT *           |
|                                   |                                         |
|                                   | [ Hủy phiên ]  [*Lưu hồ sơ*] (khóa nếu  |
|                                   |  còn trường vàng chưa tích "Đã kiểm tra")|
+-----------------------------------+-----------------------------------------+
```

**Quy tắc hiển thị:**
- Mỗi trường nhận diện có `[_source_tag]` cạnh nhãn: QR, OCR hoặc Nhập tay (trường HR tự gõ/sửa đổi sang Nhập tay).
- Trường độ tin cậy thấp (OCR dưới ngưỡng, hoặc không đọc được): nền vàng nhạt + viền warning + ô tích "Đã kiểm tra". **Không điền chữ đoán**: trường đọc không được để trống, vẫn tô vàng.
- Nút "Lưu hồ sơ" (nút chính duy nhất) ở trạng thái khóa (disabled, tooltip "Cần tích Đã kiểm tra cho các trường tô vàng") đến khi mọi ô tô vàng được tích. Máy chủ kiểm tra lại.
- "Hủy phiên" mở `[_confirm_modal]`: "Ảnh và kết quả nhận diện sẽ bị xóa ngay và không khôi phục được." `[ Quay lại ] [ Hủy phiên ]` (POST `/nhap-cccd/<uuid>/huy/`).
- Kiểm tra trùng chạy bằng HTMX khi rời ô số CCCD / SĐT / ngày sinh: trùng CCCD → khung lỗi + `[ Mở hồ sơ cũ ]` (và chặn Lưu); trùng SĐT hoặc họ tên + ngày sinh → cảnh báo (`_alert`), cho lưu.
- Lưu thành công → chuyển tới `/ho-so/<id>/` với `_alert` "Đã lưu hồ sơ ở trạng thái Nháp."
- Chỉ người tạo phiên và A mở được; người khác thấy 404.

**Màn hình hẹp (390px):** hai cột xếp thành một: ảnh xếp trên (thu gọn, bấm Phóng to), form dưới, nút Lưu cố định cuối form.

## 5. Bốn trang phụ

**Giới thiệu `/gioi-thieu/`** (mọi người đã đăng nhập)
```
[_page_header] Giới thiệu
[_form_section] (chế độ xem)  Tên phần mềm | Đơn vị phát triển | Phiên bản | Năm phát hành
```

**Đổi mật khẩu `/doi-mat-khau/`** (mọi người đã đăng nhập; khi `must_change_password` thì là trang duy nhất vào được)
```
[_page_header] Đổi mật khẩu
[_alert] (nếu buộc đổi) "Bạn cần đổi mật khẩu tạm trước khi tiếp tục."
[_form_section] [_form_field] Mật khẩu hiện tại *  Mật khẩu mới * (gợi ý: tối thiểu 8 ký tự, có chữ và số)  Nhập lại *
                                    [ Hủy ]  [*Đổi mật khẩu*]
```

**Lịch sử đăng nhập `/tai-khoan/lich-su-dang-nhap/`** {A}
```
[_page_header] Quản lý tài khoản
[_tabs] Danh sách | *Lịch sử đăng nhập*
[_filter_bar] (Tài khoản)(Kết quả)(Từ ngày)(đến)   [ Lọc ] [ Xóa lọc ]
[_table] Thời điểm | Tài khoản | Kết quả [_status_badge] | Lý do | Địa chỉ IP
[_pagination]
```

**Danh sách chờ hủy `/cai-dat/cho-huy/`** {A}
```
[_page_header] Cài đặt
[_tabs] ... | *Chờ hủy* | Biên bản hủy
[_table] [ ] chọn | Mã hồ sơ | Lưu trữ từ | Căn cứ lưu trữ | Hết hạn lưu trữ (dd/mm/yyyy) | TT [_status_badge: Lưu trữ]
         [ Hủy hồ sơ đã chọn ]  -> [_confirm_modal] (ẩn danh hóa không hoàn tác được)
[_empty_state] "Không có hồ sơ nào quá hạn lưu trữ."
```

**Trang 403** (khung chung `base.html`)
```
[_page_header] Không có quyền truy cập
Bạn không có quyền thực hiện thao tác này.     [ Về trang tổng quan ]
```

## 6. Trang `/ui-kit/` (chỉ Admin)

```
[_page_header] Bộ giao diện mẫu              (mục lục neo ở đầu trang)
1. Đầu trang        : tiêu đề + breadcrumb + 3 kiểu nút (chính / phụ / nguy hiểm), trạng thái disabled
2. Thẻ số liệu      : 4 thẻ có số; 1 thẻ không số (nhãn + dòng phụ)
3. Thanh lọc        : bình thường
4. Bảng             : 10 dòng, nhãn trạng thái đủ màu; cột số căn phải; ô trống "—"; trạng thái rỗng
5. Phân trang       : giữa trang; trang đầu (nút Trước tắt); trang cuối (nút Sau tắt)
6. Form 2 cột       : trường bình thường, bắt buộc, có gợi ý, có lỗi, bị khóa (disabled)
7. Nhãn trạng thái  : 4 bộ (hồ sơ, làm việc, tuyển dụng, tài liệu) + chỉ số tự tính, mỗi giá trị 1 nhãn
   Nhãn hiển thị    : tài khoản, danh mục, kết quả đăng nhập (bảng riêng, ghi rõ không phải bộ trạng thái)
8. Hộp xác nhận     : kiểu đơn giản + kiểu có trường form
9. Trạng thái rỗng  : có nút / không nút
10. Thông báo       : thành công, lỗi, (tự ẩn 5 giây)
11. Tab             : 3 tab, tab đang chọn
12. Nhãn nguồn      : QR / OCR / Nhập tay; trường tô vàng + "Đã kiểm tra"
13. Biểu đồ cột     : 1 biểu đồ Chart.js, một chuỗi màu navy, tiêu đề nói kết quả + đơn vị
14. Bảng màu và chữ : token, cỡ chữ, khoảng cách (chỉ để so sánh)
```

## 7. Điểm cần chốt khi làm component (chưa chặn giai đoạn A)

1. **Nhãn hiển thị (đã duyệt 22/11/2026):** Đang hoạt động / Bị khóa / Khóa tạm (tài khoản), Đang dùng / Ngừng (danh mục), Thành công / Thất bại (đăng nhập) dùng `_status_badge` theo bảng "Nhãn hiển thị" ở pa-ui mục 5. Đây chỉ là hiển thị từ trường có sẵn (`is_active`, `locked_until`, `success`), không phải bộ trạng thái nghiệp vụ, không tạo `TextChoices`.
2. **Cột bảng của Tuyển dụng, Duyệt hồ sơ, Nhật ký, Quản lý tài khoản** là phỏng đoán, đã đánh dấu "[Phỏng đoán – chốt ở Phase N]" ở từng trang; `yeu-cau.md` chỉ quy định cột cho Danh sách công nhân.
3. **Nút "Thêm ▾"** (pa-ui mục 4) giữ trong `/ui-kit` (đã duyệt).
