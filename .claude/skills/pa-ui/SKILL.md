---
name: pa-ui
description: Hệ thống giao diện của PA Worker. Dùng mỗi khi tạo hoặc sửa template Django, CSS, trang, form, bảng, nút, nhãn trạng thái, biểu đồ, hoặc khi review giao diện để giữ mọi trang đồng bộ, đơn giản, không màu mè.
---

# PA Worker – Hệ thống giao diện

Mục tiêu: một phần mềm văn phòng **nghiêm túc, gọn, đồng bộ**. Người dùng là nhân viên nhân sự làm việc cả ngày với bảng và biểu mẫu. Ưu tiên dễ đọc, dễ quét mắt, ít màu, ít icon. Không cố làm giao diện "ấn tượng".

Trang `/ui-kit` (tạo ở phase 3) là bản chuẩn. Khi đã duyệt, **mọi trang chỉ được lắp ráp từ component có trong `/ui-kit`**. Cần component mới thì thêm vào `/ui-kit` trước, rồi mới dùng.

## 1. Token (khai báo một lần trong `static/css/pa.css`)

```css
:root {
  --pa-navy: #1F3A5F;        /* sidebar, tiêu đề, nút chính */
  --pa-blue: #2F6FB2;        /* liên kết, trạng thái đang chọn, focus */
  --pa-bg: #F5F7FA;          /* nền vùng nội dung */
  --pa-surface: #FFFFFF;     /* thẻ, bảng, form */
  --pa-border: #DDE3EA;
  --pa-text: #1F2933;
  --pa-muted: #6B7785;
  --pa-success: #2E7D32;
  --pa-warning: #B7791F;
  --pa-danger: #C62828;
  --pa-radius: 6px;
}
```

- Ghi đè biến Bootstrap (`--bs-primary` = navy, `--bs-link-color` = blue, `--bs-border-radius` = 6px) trong `pa.css`. Không viết màu hex ở bất kỳ file nào khác.
- Khoảng cách chỉ dùng thang 4, 8, 12, 16, 24, 32 px (utility Bootstrap `1`–`5`).
- Font: một bộ font hệ thống `system-ui, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif` (hiển thị tốt tiếng Việt, không tải font ngoài vì hệ thống chạy offline). Cỡ chữ: thân 14px, tiêu đề trang 20px/600, tiêu đề thẻ 16px/600, chữ phụ 13px màu muted.
- Không đổ bóng; tách lớp bằng viền `1px solid var(--pa-border)`.

## 2. Bố cục khung (`templates/base.html`)

- `base.html` có `{% block shell %}` bao sidebar + thanh trên; trang Đăng nhập làm rỗng block này (khung tối giản: tên "PA Worker" + chân trang "Phát triển bởi QQIT"), các trang khác giữ nguyên.
- **Sidebar trái** rộng 240px, nền navy, chữ trắng 85%; mục đang chọn có nền trắng 10% và vạch trái 3px màu blue. Đầu sidebar: logo chữ "PA Worker".
- **Thanh trên** nền trắng, viền dưới: ô tìm nhanh bên trái, tên người dùng + vai trò + nút Đăng xuất bên phải.
- **Vùng nội dung** nền `--pa-bg`, padding 24px.
- **Đầu trang** (component `_page_header.html`): tiêu đề trang, breadcrumb nhỏ phía trên, các nút thao tác căn phải. Mọi trang đều có đầu trang này.
- **Chân trang:** "PA Worker v1.0 · Phát triển bởi QQIT", chữ 12px muted.
- Màn hình hẹp (< 992px): sidebar thu thành menu mở bằng nút.

## 3. Component dùng chung (`templates/components/`)

| File | Dùng cho |
| --- | --- |
| `_page_header.html` | Tiêu đề, breadcrumb, nút thao tác của trang |
| `_stat_card.html` | Thẻ số liệu Dashboard: nhãn, con số lớn, dòng phụ; cả thẻ là liên kết tới danh sách đã lọc. Con số là **tùy chọn**: không truyền số thì thẻ chỉ có nhãn + dòng phụ (dùng cho 3 lựa chọn ở trang Thêm hồ sơ); không tạo component riêng cho dạng này |
| `_filter_bar.html` | Thanh lọc phía trên bảng: các ô chọn cùng hàng, nút "Lọc" và "Xóa lọc" |
| `_table.html` | Bảng danh sách: đầu bảng nền xám nhạt, hover dòng, cột số căn phải, cột Thao tác căn phải |
| `_pagination.html` | Phân trang 20 dòng, hiển thị "Hiển thị 1–20 / 512" |
| `_form_field.html` | Một trường form: nhãn trên, dấu * đỏ nếu bắt buộc, chữ gợi ý muted, lỗi đỏ ngay dưới ô |
| `_form_section.html` | Nhóm trường có tiêu đề nhóm, lưới 2 cột trên desktop |
| `_status_badge.html` | Nhãn trạng thái (bảng ở mục 5) |
| `_confirm_modal.html` | Hộp xác nhận thao tác không hoàn tác được. Có `{% block body %}` để đặt trường form (dùng `_form_field`: lý do, số đơn, gõ lại mã hồ sơ…). Nút xác nhận submit form POST có CSRF; modal chỉ là giao diện, máy chủ kiểm tra lại mọi trường |
| `_empty_state.html` | Khi danh sách trống: một câu giải thích + một nút hành động |
| `_alert.html` | Thông báo sau thao tác (thành công / lỗi), tự ẩn sau 5 giây |
| `_tabs.html` | Tab trong trang chi tiết hồ sơ |
| `_source_tag.html` | Nhãn nguồn dữ liệu trên màn hình đối chiếu: QR / OCR / Nhập tay |

Không viết lại HTML của các khối này trong từng trang; luôn `{% include %}`.

## 4. Nút

- **Nút chính** (`btn-primary`, navy): tối đa **một** nút chính mỗi màn hình (ví dụ "Lưu hồ sơ").
- **Nút phụ** (`btn-outline-secondary`): Hủy, Quay lại, Xuất Excel.
- **Nút nguy hiểm** (`btn-outline-danger`, và `btn-danger` chỉ trong hộp xác nhận): Từ chối, Lưu trữ.
- Chữ trên nút là động từ cụ thể: "Lưu hồ sơ", "Gửi duyệt", "Duyệt hồ sơ", "Trả lại", "Xuất Excel". Không dùng "OK", "Submit", "Xử lý".
- Thao tác trong bảng: nút nhỏ chỉ có icon + tooltip, tối đa 3 nút mỗi dòng (Xem, Sửa, Thêm ▾).

## 5. Màu trạng thái (cố định toàn hệ thống)

Nhãn trạng thái: nền màu nhạt (màu chính ở độ đậm 12%), chữ màu chính, bo 4px, cỡ 12px. Không dùng nhãn nền đặc.

| Màu | Trạng thái |
| --- | --- |
| Xanh lá (success) | Đã xác minh · Hoàn thiện · Đạt · Đang làm việc |
| Xanh dương (blue) | Chờ duyệt · Đang sàng lọc · Hẹn phỏng vấn · Thử việc · Chờ nhận việc · Mới nộp |
| Vàng (warning) | Cần bổ sung · Thiếu giấy tờ · Sắp hết hạn · Tạm hoãn |
| Đỏ (danger) | Bị từ chối · Không đạt |
| Xám (muted) | Nháp · Lưu trữ · Đã nghỉ việc · Ứng viên từ chối |

**Trạng thái xác minh tài liệu** (bộ riêng, chỉ dùng trong tab Tài liệu, xem `docs/lam-ro-yeu-cau.md` câu 3), cùng kiểu nhãn:

| Màu | Trạng thái tài liệu |
| --- | --- |
| Xám (muted) | Chưa xác minh |
| Xanh lá (success) | Đã đối chiếu bản gốc |
| Đỏ (danger) | Không hợp lệ |

**Nhãn hiển thị (không phải bộ trạng thái):** suy ra từ trường có sẵn, dùng cùng `_status_badge` và bảng màu trên, **không** có `TextChoices` riêng.

| Màu | Nhãn | Lấy từ |
| --- | --- | --- |
| Xanh lá | Đang hoạt động | `User.is_active = True` và không bị khóa tạm |
| Đỏ | Bị khóa | `User.is_active = False` (Admin khóa) |
| Vàng | Khóa tạm | `User.locked_until` còn hiệu lực |
| Xanh lá | Đang dùng | Danh mục `is_active = True` |
| Xám | Ngừng | Danh mục `is_active = False` |
| Xanh lá | Thành công | `LoginHistory.success = True` |
| Đỏ | Thất bại | `LoginHistory.success = False` |

"Chờ hủy" **không** phải trạng thái, nên không có nhãn riêng. Tab "Chờ hủy" trong Cài đặt hiển thị nhãn Lưu trữ (xám) cùng cột "Hết hạn lưu trữ" (ngày dd/mm/yyyy).

Ánh xạ này viết **một lần** trong một template tag/filter (ví dụ `{{ status|status_badge }}`), không lặp lại ở từng trang.

## 6. Icon

- Chỉ dùng **Bootstrap Icons** (font cục bộ trong `static/vendor/`), cỡ 16px, cùng màu chữ.
- Chỉ đặt icon ở: mục menu sidebar, nút thao tác trong bảng, ô tìm kiếm, nút đóng hộp thoại.
- **Không** đặt icon trước tiêu đề trang, tiêu đề thẻ, nhãn form, nút có chữ, thẻ số liệu.
- Icon menu cố định:

| Mục menu | Icon |
| --- | --- |
| Tổng quan | `bi-speedometer2` |
| Hồ sơ công nhân | `bi-people` |
| Thêm hồ sơ | `bi-person-plus` |
| Tuyển dụng | `bi-briefcase` |
| Duyệt hồ sơ | `bi-check2-square` |
| Báo cáo | `bi-bar-chart` |
| Nhật ký thao tác | `bi-clock-history` |
| Tài khoản | `bi-person-gear` |
| Cài đặt | `bi-gear` |

- Thao tác trong bảng: Xem `bi-eye`, Sửa `bi-pencil`, Lưu trữ `bi-archive`, Tải xuống `bi-download`.

## 7. Bảng, form, biểu đồ

- **Bảng:** chữ 14px, dòng cao 44px, không kẻ sọc ngang xen màu; ngày dd/mm/yyyy; ô trống hiển thị "—". Cột Mã và Trạng thái không xuống dòng.
- **Form:** nhãn luôn ở trên ô; trường bắt buộc có `*`; nút Lưu/Hủy ở cuối form, căn phải. Lỗi kiểm tra hiện ngay dưới ô và tóm tắt ở đầu form.
- **Màn hình đối chiếu CCCD:** 2 cột 50/50 (ảnh trái, form phải). Trường độ tin cậy thấp: nền vàng nhạt + viền warning + ô tích "Đã kiểm tra".
- **Biểu đồ (Chart.js):** dùng màu navy cho một chuỗi số liệu; nhiều chuỗi thì navy, blue, muted theo thứ tự. Không 3D, không gradient, không hiệu ứng. Trục và lưới màu `--pa-border`. Luôn có tiêu đề nói kết quả và đơn vị.

## 8. Chữ trên giao diện

- Tiếng Việt có dấu, viết hoa chữ đầu câu (không VIẾT HOA TOÀN BỘ).
- Câu ngắn, giọng hành chính trung tính. Không dấu chấm than, không emoji.
- Thông báo lỗi nói rõ sai gì và sửa thế nào: "Số CCCD phải gồm 12 chữ số." thay vì "Dữ liệu không hợp lệ."

## 9. Cấm

Gradient · đổ bóng đậm · animation/hiệu ứng chuyển động (trừ mở/đóng menu, modal mặc định của Bootstrap) · màu ngoài bảng token · font thứ hai · icon trang trí · emoji · ảnh minh họa/hình nền · thẻ bo tròn lớn hơn 6px · nhiều hơn một nút chính trên màn hình · CSS inline (`style="..."`) · thư viện UI khác ngoài Bootstrap.

## 10. Kiểm tra trước khi báo xong một trang

1. Trang kế thừa `base.html` và có `_page_header`.
2. Chỉ dùng component trong mục 3; không có HTML khung tự chế.
3. Không có mã màu hex hoặc `style=` trong template.
4. Icon chỉ nằm ở các vị trí cho phép trong mục 6.
5. Chụp màn hình bằng skill `webapp-testing` ở 1366×768 và 390×844, đặt cạnh `/ui-kit` để so: cùng cỡ chữ, khoảng cách, màu nút, kiểu bảng.
