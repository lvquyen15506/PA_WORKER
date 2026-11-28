# Danh sách URL và trang – PA Worker

Phase 1 · Ngày 21/11/2026 · Cập nhật v1.1 ngày 23/11/2026 · Dựa trên `docs/thiet-ke/erd.md` và `docs/thiet-ke/models.md`. Quyền theo `docs/yeu-cau.md` mục III, sửa bởi `docs/lam-ro-yeu-cau.md` câu 1–47.

## 1. Quy ước

- **Vai trò:** A = Admin · Q = Quản lý nhân sự · H = Nhân viên HR · V = Viewer.
- **URL:** chữ tiếng Việt không dấu, gạch nối (`/ho-so/`), tham số là `id` số (riêng phiên nhận diện dùng UUID).
- **Kiểm tra quyền ở máy chủ** cho mọi URL bằng decorator `role_required(...)` (đặt trong `apps/accounts/permissions.py`) và kiểm tra theo trạng thái trong service (`models.md` mục 4). Chưa đăng nhập → chuyển tới `/dang-nhap/`. Đăng nhập nhưng không có quyền → trang 403 "Bạn không có quyền thực hiện thao tác này." Ẩn nút chỉ là phần phụ.
- **Thao tác thay đổi dữ liệu** chỉ nhận `POST` có CSRF. `GET` không bao giờ thay đổi dữ liệu.
- **Nhật ký:** cột "Nhật ký" ghi mã `AuditAction` được ghi khi gọi URL đó.
- **Component** là tên file trong `templates/components/` (skill `pa-ui` mục 3). Mọi trang kế thừa `base.html` và có `_page_header`, nên không ghi lại hai thứ này ở từng dòng. Riêng trang Đăng nhập dùng khung tối giản không có sidebar.
- Người dùng có `must_change_password = True` bị chuyển tới `/doi-mat-khau/` ở mọi URL khác (trừ đăng xuất).
- **Trường ẩn với Viewer** (câu 13 `lam-ro-yeu-cau.md`): số CCCD (chỉ dạng che), số CMND cũ, địa chỉ thường trú/cư trú, quê quán / nơi đăng ký khai sinh, ảnh CCCD. Ẩn ở mọi trang, mảnh HTMX và file xuất; Viewer vẫn thấy SĐT và nơi ở hiện tại. **Thay đổi v1.1 (câu 42, 48):** mọi dữ liệu lương đều xem được với mọi vai trò, gồm lương tháng và đơn giá tháng (tab Quá trình làm việc) và **mức lương mong muốn** (trước đây ẩn với Viewer); chỉ A, Q thêm lương.

## 2. Menu sidebar

| Mục menu | Icon | URL | A | Q | H | V |
| --- | --- | --- | --- | --- | --- | --- |
| Tổng quan | `bi-speedometer2` | `/` | ✓ | ✓ | ✓ | ✓ |
| Hồ sơ công nhân | `bi-people` | `/ho-so/` | ✓ | ✓ | ✓ | ✓ |
| Thêm hồ sơ | `bi-person-plus` | `/ho-so/them/` | ✓ | ✓ | ✓ | |
| Tuyển dụng | `bi-briefcase` | `/tuyen-dung/` | ✓ | ✓ | ✓ | ✓ |
| Duyệt hồ sơ | `bi-check2-square` | `/duyet-ho-so/` | ✓ | ✓ | | |
| Báo cáo | `bi-bar-chart` | `/bao-cao/` | ✓ | ✓ | ✓ | ✓ |
| Nhật ký thao tác | `bi-clock-history` | `/nhat-ky/` | ✓ | ✓ | | |
| Tài khoản | `bi-person-gear` | `/tai-khoan/` | ✓ | | | |
| Cài đặt | `bi-gear` | `/cai-dat/` | ✓ | | | |

Thanh trên: ô tìm nhanh (gửi tới `/ho-so/?q=`), tên người dùng + vai trò, menu người dùng (Đổi mật khẩu, Đăng xuất). Chân trang: "PA Worker v1.0 · Phát triển bởi QQIT" + liên kết Giới thiệu.

## 3. 12 trang chính (mục VII)

| # | Trang | URL chính | A | Q | H | V | Component pa-ui |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Đăng nhập | `/dang-nhap/` | mọi người chưa đăng nhập | | | | `_form_field`, `_alert` |
| 2 | Dashboard | `/` | ✓ | ✓ | ✓ | ✓ | `_stat_card` ×9, biểu đồ Chart.js ×4, `_table` (việc cần làm), `_status_badge`, `_empty_state` |
| 3 | Danh sách công nhân | `/ho-so/` | ✓ | ✓ | ✓ | ✓ (không tìm theo CCCD) | `_filter_bar`, `_table`, `_status_badge`, `_pagination`, `_empty_state` |
| 4 | Thêm hồ sơ | `/ho-so/them/` | ✓ | ✓ | ✓ | | 3 lựa chọn dạng thẻ liên kết (Nhập tay / Từ CCCD và CV / Từ file Excel) dựng bằng `_stat_card` không số liệu; form nhập tay: `_form_section`, `_form_field` |
| 5 | Nhập từ CCCD và CV | `/nhap-cccd/` → `/nhap-cccd/<uuid>/` | ✓ | ✓ | ✓ | | `_form_field` (tải ảnh), màn hình đối chiếu 2 cột: `_form_section`, `_form_field`, `_source_tag`, `_alert`, `_confirm_modal` |
| 6 | Chi tiết hồ sơ | `/ho-so/<id>/` | ✓ | ✓ | ✓ | ✓ (ẩn trường nhạy cảm: CCCD đầy đủ, CMND cũ, địa chỉ thường trú, quê quán, ảnh CCCD; thấy lương và mức lương mong muốn) | `_tabs`, `_form_section` (chế độ xem), `_table`, `_status_badge`, `_confirm_modal`, `_empty_state`, `_alert` |
| 7 | Tuyển dụng | `/tuyen-dung/` | ✓ | ✓ | ✓ | ✓ (có cột mức lương mong muốn từ v1.1) | `_filter_bar`, `_table`, `_status_badge`, `_pagination`, `_empty_state` |
| 8 | Duyệt hồ sơ | `/duyet-ho-so/` | ✓ | ✓ | | | `_filter_bar`, `_table`, `_status_badge`, `_pagination`, `_empty_state` |
| 9 | Thống kê báo cáo | `/bao-cao/` | ✓ | ✓ | ✓ | ✓ (không xuất, không in) | `_filter_bar`, `_table`, biểu đồ Chart.js, `_empty_state` |
| 10 | Nhật ký thao tác | `/nhat-ky/` | ✓ | ✓ | | | `_filter_bar`, `_table`, `_pagination`, `_empty_state` |
| 11 | Quản lý tài khoản | `/tai-khoan/` | ✓ | | | | `_tabs`, `_table`, `_status_badge`, `_form_field`, `_confirm_modal`, `_pagination` |
| 12 | Cài đặt | `/cai-dat/` | ✓ | | | | `_tabs`, `_table`, `_form_section`, `_form_field`, `_confirm_modal`, `_status_badge` |

## 4. Bốn trang phụ (câu 19)

| Trang | URL | Vị trí | Ai | Component |
| --- | --- | --- | --- | --- |
| Giới thiệu | `/gioi-thieu/` | Liên kết ở chân trang | Mọi người đã đăng nhập | `_form_section` (chế độ xem) |
| Đổi mật khẩu | `/doi-mat-khau/` | Menu người dùng | Mọi người đã đăng nhập | `_form_field`, `_alert` |
| Lịch sử đăng nhập | `/tai-khoan/lich-su-dang-nhap/` | Tab trong Tài khoản | A | `_tabs`, `_filter_bar`, `_table`, `_pagination` |
| Danh sách chờ hủy | `/cai-dat/cho-huy/` | Tab trong Cài đặt | A | `_tabs`, `_table`, `_status_badge` (Lưu trữ), `_confirm_modal`, `_empty_state` |

## 5. Toàn bộ URL

Ký hiệu cột phương thức: G = GET, P = POST, H = trả mảnh HTML cho HTMX.

### 5.1 Tài khoản và chung (`apps/accounts`, `apps/core`)

| URL | PT | A | Q | H | V | Nhật ký | Ghi chú |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `/dang-nhap/` | G, P | công khai | | | | `LoginHistory` | Sai 5 lần liên tiếp → khóa tạm 15 phút; thông báo chung "Tên tài khoản hoặc mật khẩu không đúng." |
| `/dang-xuat/` | P | ✓ | ✓ | ✓ | ✓ | | Tự đăng xuất sau 30 phút không thao tác |
| `/doi-mat-khau/` | G, P | ✓ | ✓ | ✓ | ✓ | `UPDATE` | Tối thiểu 8 ký tự, có chữ và số |
| `/gioi-thieu/` | G | ✓ | ✓ | ✓ | ✓ | | Tên, đơn vị, phiên bản, năm phát hành |
| `/ui-kit/` | G | ✓ | | | | | Phase 3 |
| `/tai-khoan/` | G | ✓ | | | | | Tab Danh sách; cột Trạng thái: Đang hoạt động / Bị khóa (Admin khóa) / Khóa tạm đến hh:mm (sai mật khẩu) |
| `/tai-khoan/them/` | G, P | ✓ | | | | `CREATE` | Mật khẩu tạm, `must_change_password = True` |
| `/tai-khoan/<id>/sua/` | G, P | ✓ | | | | `UPDATE` | Họ tên, vai trò. Ô vai trò bị khóa khi sửa chính mình; máy chủ chặn hạ vai trò Admin cuối cùng đang hoạt động |
| `/tai-khoan/<id>/khoa/` | P | ✓ | | | | `ACCOUNT_LOCK` | Đặt `is_active = False`: khóa **vô thời hạn** đến khi Admin mở; hủy luôn các phiên đăng nhập đang có của người đó. Chặn tự khóa chính mình và chặn khóa Admin cuối cùng đang hoạt động |
| `/tai-khoan/<id>/mo-khoa/` | P | ✓ | | | | `ACCOUNT_UNLOCK` | Đặt `is_active = True`, xóa `locked_until`, `failed_login_count = 0`. Dùng được cho cả tài khoản bị Admin khóa lẫn tài khoản đang khóa tạm |
| `/tai-khoan/<id>/dat-lai-mat-khau/` | P | ✓ | | | | `PASSWORD_RESET` | Hiện mật khẩu tạm một lần |
| `/tai-khoan/lich-su-dang-nhap/` | G | ✓ | | | | | Trang phụ, lọc theo tài khoản, kết quả, khoảng ngày |

**Hai cơ chế khóa tách riêng** (câu 28 `lam-ro-yeu-cau.md`):

| | Admin khóa | Khóa tạm do sai mật khẩu |
| --- | --- | --- |
| Trường | `User.is_active = False` | `User.locked_until`, `User.failed_login_count` |
| Khi nào | Admin bấm "Khóa tài khoản" | Lần sai thứ 5 liên tiếp |
| Hết khóa | Chỉ khi Admin bấm "Mở khóa" | Tự hết sau 15 phút, hoặc Admin bấm "Mở khóa" |
| Nhật ký | `ACCOUNT_LOCK` / `ACCOUNT_UNLOCK` | `LoginHistory` (lý do "Tài khoản đang khóa tạm") |
| Thông báo khi đăng nhập | "Tài khoản đã bị khóa. Liên hệ Admin." | "Tài khoản tạm khóa do nhập sai nhiều lần. Thử lại sau hh:mm." |

**Bảo vệ quyền quản trị** (kiểm tra ở máy chủ trong `apps/accounts/services.py`, có test cho từng trường hợp): Admin không tự khóa và không tự đổi vai trò của mình; không ai khóa hoặc hạ vai trò Admin cuối cùng đang hoạt động (`role = ADMIN` và `is_active = True`). Vi phạm → không lưu, báo "Hệ thống phải còn ít nhất một Admin đang hoạt động." hoặc "Bạn không thể khóa hoặc đổi vai trò của chính mình."

Trang admin của Django không được bật.

### 5.2 Cài đặt (`apps/core`, `apps/workers`)

| URL | PT | A | Nhật ký | Ghi chú |
| --- | --- | --- | --- | --- |
| `/cai-dat/` | G | ✓ | | Chuyển tới tab đầu tiên đang có (Phase 5: OCR và QR; Phase 6 đổi về Danh mục). Danh sách tab khai báo một chỗ: `SETTINGS_TABS` ở `apps/core/settings_views.py` |
| `/cai-dat/danh-muc/<loai>/` | G | ✓ | | `<loai>`: `phong-ban`, `bo-phan`, `to`, `chuc-danh`, `ca`, `nguon-ung-tuyen`, `trinh-do`, `nhom-tai-lieu`, `loai-tai-lieu`, `cong-ty-khach` (v1.1, câu 39: 10 loại; bảng có cột Tên và Địa điểm; hai dòng không trùng cả tên lẫn địa điểm; ngừng sử dụng thay cho xóa). Thêm công ty khách: Cài đặt → Danh mục → Công ty khách (chỉ A; v1.1.1 sửa lại 28/11/2026: không có mục sidebar riêng, Q không xem) |
| `/cai-dat/danh-muc/<loai>/them/`, `/<id>/sua/` | G, P | ✓ | `CREATE`, `UPDATE` | |
| `/cai-dat/danh-muc/<loai>/<id>/ngung/`, `/<id>/dung-lai/` | P | ✓ | `UPDATE` | Không có nút xóa |
| `/cai-dat/sinh-ma/` | G, P | ✓ | `UPDATE` | Tiền tố, có năm, số chữ số cho mã hồ sơ và mã NV; xem trước mã kế tiếp |
| `/cai-dat/nguong/` | G, P | ✓ | `UPDATE` | Ngưỡng sắp hết hạn (dùng chung cho CCCD, hợp đồng, đợt làm việc), số tháng của đợt làm việc để cảnh báo (12), thời hạn lưu trữ (12 tháng / 10 năm), số ngày tự Lưu trữ (30 / 30), số tháng hồ sơ bỏ dở (6), thời hạn phiên nhận diện (24 giờ) |
| `/cai-dat/ocr-qr/` | G, P | ✓ | `UPDATE` | Ngưỡng tin cậy OCR, `QrFormat` theo mẫu thẻ, API OCR ngoài (tắt mặc định, bật thì hiện cảnh báo gửi ảnh ra ngoài) |
| `/cai-dat/cho-huy/` | G | ✓ | | Trang phụ: hồ sơ Lưu trữ quá hạn lưu trữ; cột "Căn cứ lưu trữ" (6 căn cứ, câu 2) và "Hết hạn lưu trữ" |
| `/cai-dat/cho-huy/huy/` | P | ✓ | `ANONYMIZE` (mỗi hồ sơ) | Chọn nhiều hồ sơ, hộp xác nhận; sinh `AnonymizationRecord` |
| `/cai-dat/bien-ban-huy/` | G | ✓ | | Danh sách biên bản, cột Loại (Hết hạn lưu trữ / Theo yêu cầu của chủ thể) và Số đơn |
| `/cai-dat/bien-ban-huy/<id>/` | G | ✓ | | Xem biên bản: loại, người duyệt, thời điểm, danh sách mã hồ sơ / mã NV, căn cứ lưu trữ. Biên bản loại "Theo yêu cầu của chủ thể" hiện thêm số đơn và dòng "Xóa sớm theo yêu cầu – lẽ ra lưu đến dd/mm/yyyy" |
| `/cai-dat/bien-ban-huy/<id>/in/` | G | ✓ | `PRINT` | **Phase 7.** Bản in biên bản (ghi `PRINT` khi mở trang, cùng cách với `/ho-so/<id>/dong-y/mau-in/`). Không xuất Excel biên bản |

### 5.3 Dashboard (`apps/reports`)

| URL | PT | A | Q | H | V | Ghi chú |
| --- | --- | --- | --- | --- | --- | --- |
| `/` | G | ✓ | ✓ | ✓ | ✓ | 9 thẻ, mỗi thẻ là liên kết tới `/ho-so/?...` (hoặc `/tuyen-dung/?...`) với bộ lọc tương ứng, số dòng bằng số trên thẻ. 4 biểu đồ: vào làm/nghỉ việc 12 tháng; theo phòng ban/bộ phận (có nhóm "Chưa có bộ phận", câu 48); giới tính, 5 nhóm tuổi + "Chưa có ngày sinh" (câu 26), trình độ cao nhất; theo trạng thái xác minh. Việc cần làm: Chờ duyệt, Cần bổ sung, CCCD sắp hết hạn, **Đợt làm việc sắp đủ 12 tháng** (v1.1, câu 43; không thêm thẻ, vẫn 9 thẻ) |

Khối việc cần làm "Đợt làm việc sắp đủ 12 tháng" liên kết tới `/ho-so/?dot_sap_du_han=1` (số dòng bằng số trong khối).

**Chốt ở Phase 7 (23/11/2026):**
- Số trên mỗi thẻ được đếm bằng đúng bộ lọc của trang đích với đúng tham số của liên kết (một bảng khai báo `CARDS` ở `apps/reports/stats.py` dùng chung cho số và liên kết), nên số dòng danh sách đích luôn bằng số trên thẻ.
- Mỗi khối việc cần làm hiện 10 dòng đầu và liên kết "Xem tất cả (n)": Chờ duyệt (chỉ A, Q) → `/duyet-ho-so/`; Cần bổ sung → `/ho-so/?trang_thai_ho_so=NEEDS_INFO`; CCCD sắp hết hạn → `/ho-so/?cccd_sap_het_han=1`; Đợt sắp đủ 12 tháng → `/ho-so/?dot_sap_du_han=1`.
- Biểu đồ cơ cấu (phòng ban/bộ phận, giới tính, nhóm tuổi, trình độ) tính **công nhân đang làm** (Thử việc + Đang làm việc); biểu đồ vào làm/nghỉ việc 12 tháng theo `start_date`/`resign_date`; biểu đồ trạng thái xác minh tính mọi hồ sơ. Không dùng biểu đồ tròn.
- Thẻ "Thiếu giấy tờ" không tính hồ sơ Lưu trữ: liên kết `/ho-so/?thieu_giay_to=1&trang_thai_ho_so=chua-luu-tru`. Thẻ "Hồ sơ mới trong tháng" và "Nghỉ việc trong tháng" tính mọi trạng thái hồ sơ.

Bộ lọc của 9 thẻ:

| Thẻ | Liên kết |
| --- | --- |
| Tổng số hồ sơ (không tính Lưu trữ) | `/ho-so/?trang_thai_ho_so=chua-luu-tru` |
| Đang làm việc | `/ho-so/?trang_thai_lam_viec=PROBATION,ACTIVE` |
| Hồ sơ mới trong tháng | `/ho-so/?tao_tu=<ngày 1>&tao_den=<cuối tháng>` |
| Chờ duyệt | `/ho-so/?trang_thai_ho_so=PENDING` |
| Thiếu giấy tờ | `/ho-so/?thieu_giay_to=1&trang_thai_ho_so=chua-luu-tru` (Phase 7: không tính Lưu trữ) |
| Hoàn thiện | `/ho-so/?hoan_thien=1` |
| Đang tuyển dụng | `/tuyen-dung/?trang_thai=NEW,SCREENING,INTERVIEW` |
| Nghỉ việc trong tháng | `/ho-so/?trang_thai_lam_viec=RESIGNED&nghi_tu=<ngày 1>&nghi_den=<cuối tháng>` |
| Hợp đồng sắp hết hạn | `/ho-so/?hop_dong_sap_het_han=1` |

### 5.4 Hồ sơ (`apps/workers`)

| URL | PT | A | Q | H | V | Nhật ký | Ghi chú |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `/ho-so/` | G | ✓ | ✓ | ✓ | ✓ | | **Tham số thêm ở Phase 7 (liên kết thẻ Dashboard):** `trang_thai_ho_so=chua-luu-tru` (mọi hồ sơ trừ Lưu trữ), `trang_thai_lam_viec` nhận danh sách cách nhau dấu phẩy (`PROBATION,ACTIVE`), `tao_tu`/`tao_den` (ngày tạo hồ sơ, dd/mm/yyyy), `nghi_tu`/`nghi_den` (ngày nghỉ việc), `cccd_sap_het_han=1`. Cột theo mục IV.7; lọc: phòng ban, bộ phận, chức danh, trình độ, 3 bộ trạng thái, thiếu giấy tờ, hoàn thiện, khoảng ngày tiếp nhận, **công ty khách hàng** (`?cong_ty_khach=<id>`, theo đợt đang diễn ra) và **đợt sắp đủ 12 tháng** (`?dot_sap_du_han=1`) (v1.1); bộ lọc bộ phận có thêm lựa chọn "Chưa có bộ phận" (`?bo_phan=chua-co`; v1.1, câu 48); **cột "Công ty khách" thay cột "Bộ phận"** (vẫn 12 cột; công nhân chưa có đợt đang diễn ra hiện "Chưa gán" (v1.1.1)); `q` tìm mã hồ sơ, mã NV, họ tên không dấu, SĐT; `q` 12 chữ số tìm theo băm CCCD **chỉ với A, Q, H**; sắp xếp theo cột; 20 dòng/trang; bộ lọc giữ trong phiên |
| `/ho-so/xuat-excel/` | G | ✓ | ✓ | ✓ | | `EXPORT` | Cùng tham số lọc và thứ tự sắp xếp với `/ho-so/`. **Chốt Phase 7:** CCCD luôn che (`0791••••2345`); số CCCD đầy đủ chỉ qua **POST có CSRF** với `cccd_day_du=1` (bộ lọc vẫn nằm trên URL), chỉ nhận với A, Q (H gửi → 403; GET luôn ra bản che) và nhật ký `EXPORT` ghi "có số CCCD đầy đủ". Cột: 11 cột như màn hình + "Mã hồ sơ" + "Số CCCD"; không có lương. Nhật ký không ghi chữ tìm kiếm `q`. Nút ở `/ho-so/`: H có "Xuất Excel"; A, Q có "Xuất Excel ▾" gồm "Xuất Excel" và "Xuất kèm số CCCD đầy đủ" (qua `_confirm_modal`) |
| `/ho-so/them/` | G | ✓ | ✓ | ✓ | | | Chọn cách thêm |
| `/ho-so/them/nhap-tay/` | G, P | ✓ | ✓ | ✓ | | `CREATE` | Lưu Nháp: chỉ cần họ tên + SĐT; sinh mã hồ sơ |
| `/ho-so/kiem-tra-trung/` | P, H | ✓ | ✓ | ✓ | | | Gọi khi rời ô số CCCD / SĐT / ngày sinh: trùng CCCD → khung lỗi + nút "Mở hồ sơ cũ"; trùng SĐT hoặc họ tên + ngày sinh → cảnh báo |
| `/ho-so/nhap-excel/` | G, P | ✓ | ✓ | ✓ | | `IMPORT` | Báo lỗi từng dòng; phần thông tin làm việc chỉ A, Q; mã NV cũ tối đa 20 ký tự, chữ/số/gạch ngang, không trùng (câu 27) |
| `/ho-so/nhap-excel/file-mau/` | G | ✓ | ✓ | ✓ | | | Tải file mẫu `.xlsx` (`excel-mau.md`) |
| `/ho-so/<id>/` | G | ✓ | ✓ | ✓ | ✓ | | `?tab=ca-nhan` (mặc định), `tuyen-dung`, `lam-viec`, `tai-lieu`, `lich-su` |
| `/ho-so/<id>/sua/` | G, P | ✓ | ✓ | ✓ | | `UPDATE` (+ `STATUS_CHANGE` khi tự về Chờ duyệt) | Theo bảng 4.4 `models.md`; liên hệ khẩn cấp sửa cùng form (thêm, sửa, **xóa dòng**: dòng con không bảng nào trỏ tới, giá trị cũ ghi vào nhật ký; hồ sơ Đã xác minh vẫn phải còn ≥ 1 dòng đủ 3 trường khi gửi duyệt) |
| `/ho-so/<id>/cccd-day-du/` | P, H | ✓ | ✓ | ✓ | | `VIEW_FULL_ID` | Nút "Hiện số đầy đủ" (câu 12) |
| `/ho-so/<id>/dong-y/` | G, P | ✓ | ✓ | ✓ | | `CREATE` | Ghi nhận đồng ý; hình thức Ký giấy thì bắt buộc tải tệp biên bản |
| `/ho-so/<id>/dong-y/mau-in/` | G | ✓ | ✓ | ✓ | | `PRINT` | Văn bản đồng ý điền sẵn họ tên, mã hồ sơ (`mau-dong-y.md`) |
| `/ho-so/<id>/gui-duyet/` | P | ✓ | ✓ | ✓ | | `STATUS_CHANGE` | Nháp/Cần bổ sung → Chờ duyệt |
| `/ho-so/<id>/duyet/` | P | ✓ | ✓ | | | `STATUS_CHANGE` | Không tự duyệt (câu 8) |
| `/ho-so/<id>/tra-lai/` | P | ✓ | ✓ | | | `STATUS_CHANGE` | Bắt buộc lý do; ô lý do có gợi ý "Không ghi họ tên, chỉ dùng mã hồ sơ" (câu 30) |
| `/ho-so/<id>/tu-choi/` | P | ✓ | ✓ | | | `STATUS_CHANGE` | Bắt buộc lý do; gợi ý như trên |
| `/ho-so/<id>/luu-tru/` | P | ✓ | ✓ | ✓* | | `STATUS_CHANGE` | *H chỉ từ Nháp, Cần bổ sung, Bị từ chối. Từ Đã xác minh: chỉ A, Q, bắt buộc lý do, chặn khi Thử việc/Đang làm việc (câu 9) |
| `/ho-so/<id>/mo-lai/` | G, P | ✓ | ✓ | ✓ | | `REOPEN` | Lưu trữ → Nháp + ứng tuyển mới; chặn khi đã ẩn danh |
| `/ho-so/<id>/an-danh-theo-yeu-cau/` | P | ✓ | | | | `ANONYMIZE` | Câu 38. Nút "Ẩn danh hóa theo yêu cầu" (nút nguy hiểm) chỉ hiện với Admin khi hồ sơ **Lưu trữ** và chưa ẩn danh. Mở `_confirm_modal` gồm: lý do (bắt buộc, gợi ý "Không ghi họ tên, chỉ dùng mã hồ sơ"), số/ngày đơn yêu cầu (bắt buộc), ô gõ lại mã hồ sơ để xác nhận (máy chủ kiểm tra lại). Hộp ghi rõ: "Thao tác này không hoàn tác được. Thông tin cá nhân, giấy tờ và giá trị chi tiết trong nhật ký của hồ sơ sẽ bị xóa." Sinh biên bản hủy loại "Theo yêu cầu của chủ thể" |
| `/ho-so/<id>/lich-su/chi-tiet/` | H | ✓ | ✓ | | | | Giá trị trước/sau từng trường trong tab Lịch sử (câu 11), giải mã từ `AuditPersonalValue` (câu 30); số CCCD/CMND hiện dạng che; hồ sơ đã ẩn danh hiện "(đã ẩn danh)". H, V chỉ thấy dòng thời gian trạng thái |

### 5.5 Tài liệu (`apps/documents`)

| URL | PT | A | Q | H | V | Nhật ký | Ghi chú |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `/ho-so/<id>/tai-lieu/them/` | G, P | ✓ | ✓ | ✓ | | `UPLOAD_FILE` | Theo bảng 4.4 `models.md` |
| `/tai-lieu/<id>/xem/` | G | ✓ | ✓ | ✓ | | `VIEW_FILE` | Trả tệp `inline` (ảnh, PDF) qua view kiểm quyền; DOC/DOCX chỉ tải xuống |
| `/tai-lieu/<id>/tai-xuong/` | G | ✓ | ✓ | ✓ | | `DOWNLOAD_FILE` | `attachment` |
| `/tai-lieu/<id>/thay-the/` | G, P | ✓ | ✓ | ✓* | | `REPLACE_FILE` | *H chỉ khi hồ sơ Nháp/Cần bổ sung |
| `/tai-lieu/<id>/xac-minh/` | P | ✓ | ✓ | | | `UPDATE` | Đổi trạng thái xác minh tài liệu |
| `/tai-lieu/<id>/lich-su/` | H | ✓ | ✓ | ✓ | | | Các phiên bản cũ của tài liệu |

V thấy danh sách tài liệu (loại, ngày, trạng thái) nhưng không có liên kết xem/tải; gọi thẳng URL xem/tải → 403 (kịch bản 2).

### 5.6 Nhập từ CCCD và CV (`apps/intake`)

| URL | PT | A | Q | H | Nhật ký | Ghi chú |
| --- | --- | --- | --- | --- | --- | --- |
| `/nhap-cccd/` | G, P | ✓ | ✓ | ✓ | `INTAKE_CREATE` | Tải ảnh mặt trước, mặt sau, CV (mỗi thứ không bắt buộc, cần ít nhất một); tạo `IntakeSession`, chạy kiểm tra ảnh → QR → OCR → trích CV |
| `/nhap-cccd/<uuid>/` | G, P | người tạo phiên, A | | | `INTAKE_SAVE`, `CREATE` | Màn hình đối chiếu; "Lưu hồ sơ" chỉ bật khi mọi trường tô vàng đã tích "Đã kiểm tra" (kiểm tra lại ở máy chủ) |
| `/nhap-cccd/<uuid>/tep/<loai>/` | G | người tạo phiên, A | | | | Ảnh/CV của phiên (`mat-truoc`, `mat-sau`, `cv`) |
| `/nhap-cccd/<uuid>/kiem-tra-trung/` | P, H | người tạo phiên, A | | | | Như `/ho-so/kiem-tra-trung/` |
| `/nhap-cccd/<uuid>/huy/` | P | người tạo phiên, A | | | `INTAKE_CANCEL` | Xóa phiên, ảnh và kết quả ngay |
| `/nhap-cccd/<uuid>/xoay/<loai>/` | P | người tạo phiên, A | | | | `<loai>`: `mat-truoc`, `mat-sau`. Xoay ảnh 90° rồi nhận diện lại, ngân sách thời gian riêng của request (Phase 5) |
| `/nhap-cccd/<uuid>/mo-ho-so-cu/<id>/` | P | người tạo phiên, A | | | `INTAKE_CANCEL` | Nút "Mở hồ sơ cũ" khi trùng CCCD: đóng phiên (ghi hồ sơ cũ), không tạo hồ sơ mới, không lưu ảnh (Phase 5) |

- **Chủ ý thiết kế:** một phiên nhận diện **chỉ người tạo phiên và Admin mở được**, kể cả QL hay HR khác cũng không mở được. Lý do: phiên chứa ảnh CCCD và kết quả nhận diện chưa được xác nhận, chỉ người đang nhập cần thấy; giảm số người tiếp xúc dữ liệu chưa kiểm soát. Người khác gọi URL phiên → 404 (không để lộ phiên tồn tại).
- **Phiên bỏ dở tự xóa sau 24 giờ** (cấu hình ở `/cai-dat/nguong/`, `Settings.intake_ttl_hours`): lệnh `run_daily_jobs` xóa dòng phiên, ảnh, CV và kết quả mã hóa, ghi nhật ký `INTAKE_EXPIRE` với người thực hiện "Hệ thống". Phiên cũng bị xóa ngay khi HR lưu hồ sơ hoặc bấm hủy.
- Viewer không vào được nhóm URL này.

### 5.7 Tuyển dụng (`apps/recruitment`)

| URL | PT | A | Q | H | V | Nhật ký | Ghi chú |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `/tuyen-dung/` | G | ✓ | ✓ | ✓ | ✓ | | Danh sách lần ứng tuyển, lọc theo trạng thái tuyển dụng, vị trí, nguồn, khoảng ngày. Cột "Mức lương mong muốn" hiện với mọi vai trò kể cả V (v1.1, câu 48) |
| `/ho-so/<id>/ung-tuyen/them/` | G, P | ✓ | ✓ | ✓ | | `CREATE` | |
| `/ung-tuyen/<id>/sua/` | G, P | ✓ | ✓ | ✓ | | `UPDATE` | Không đạt bắt buộc lý do |
| `/ung-tuyen/<id>/tiep-nhan/` | G, P | ✓ | ✓ | ✓ | | `CREATE`, `UPDATE` | Nút chỉ hiện và máy chủ chỉ nhận khi Đạt + Đã xác minh (câu 7); form thông tin làm việc ban đầu. **v1.1.1:** phần không bắt buộc "Gán công ty khách ngay" (công ty, vị trí, ngày bắt đầu); có điền thì tạo đợt qua `add_assignment` trong cùng giao dịch |
| `/ho-so/<id>/<loai>/them/`, `/<loai>/<id>/sua/`, `/<loai>/<id>/xoa/` với `<loai>` = `hoc-van`, `chung-chi`, `kinh-nghiem` (xóa chỉ nhận POST; loại khác → 404; chốt ở Phase 6) | G, P, H | ✓ | ✓ | ✓ | | `CREATE`, `UPDATE`, `UPDATE` (xóa dòng) | Thêm nhiều dòng. Cho xóa dòng vì không bảng nào trỏ tới các dòng này; giá trị cũ ghi vào nhật ký |

Từ v1.1 mức lương mong muốn **không còn ẩn** với V ở trang Tuyển dụng và tab Tuyển dụng (câu 48). V vẫn không có nút xuất Excel (câu 18).

### 5.8 Quá trình làm việc (`apps/employment`)

| URL | PT | A | Q | H | V | Nhật ký | Ghi chú |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `/ho-so/<id>/lam-viec/thay-doi/` | G, P | ✓ | ✓ | ✓ | | `UPDATE` | Điều chuyển, đổi chức danh, đổi ca, đổi trạng thái làm việc; ngày hiệu lực, số quyết định, lý do; thêm dòng `EmploymentHistory` |
| `/ho-so/<id>/hop-dong/them/` | G, P | ✓ | ✓ | ✓ | | `CREATE` | Kèm tệp (tạo `WorkerDocument` loại Hợp đồng) |
| `/hop-dong/<id>/sua/` | G, P | ✓ | ✓ | ✓ | | `UPDATE` | |
| `/ho-so/<id>/dot-lam-viec/them/` | G, P | ✓ | ✓ | ✓ | | `CREATE` | v1.1, câu 40. Công ty khách (đang dùng), vị trí, ngày bắt đầu, ngày kết thúc (không bắt buộc), ghi chú. Đang có đợt mở thì phải nhập ngày kết thúc cho đợt cũ; không chồng lấn ngày. Chỉ công nhân có mã NV, chưa Đã nghỉ việc |
| `/dot-lam-viec/<id>/sua/` | G, P | ✓ | ✓ | ✓ | | `UPDATE` | Sửa (kể cả đặt ngày kết thúc); không có nút xóa; giá trị cũ ghi nhật ký |
| `/dot-lam-viec/<id>/luong/them/` | G, P | ✓ | ✓ | | | `CREATE` | v1.1, câu 41, 42, 48. Thêm một dòng lương **của đợt làm việc `<id>`**: lương tháng, đơn giá tháng (được trống), ngày áp dụng (trong khoảng ngày của đợt), lý do (bắt buộc; gợi ý "Không ghi họ tên, chỉ dùng mã hồ sơ"); **thêm dòng mới, không có URL sửa/xóa**. H và V gọi → 403. Mọi vai trò xem lịch sử lương ở tab Quá trình làm việc (không cần URL riêng) |

Tệp đính kèm hợp đồng (ở tab Quá trình làm việc và form sửa) luôn là **bản hiện hành** của chuỗi thay thế (`Contract.current_document`, câu 32).

### 5.9 Duyệt, báo cáo, nhật ký (`apps/workers`, `apps/reports`, `apps/audit`)

| URL | PT | A | Q | H | V | Nhật ký | Ghi chú |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `/duyet-ho-so/` | G | ✓ | ✓ | | | | Hồ sơ Chờ duyệt, cũ nhất trước; dòng mình tạo/gửi có ghi chú "Bạn không duyệt được hồ sơ này" |
| `/bao-cao/` | G | ✓ | ✓ | ✓ | ✓ | | Chọn loại báo cáo, khoảng thời gian, phòng ban. v1.1 (câu 45): thêm loại báo cáo "Công nhân đang làm theo công ty khách hàng" (số người theo từng công ty và địa điểm, tính theo đợt làm việc đang diễn ra; số liệu mỗi công ty liên kết tới `/ho-so/?cong_ty_khach=<id>`). Các báo cáo theo phòng ban/bộ phận có nhóm "Chưa có bộ phận" (câu 48). **Chốt Phase 7 – 9 loại báo cáo:** (1) theo phòng ban/bộ phận, (2) giới tính, (3) nhóm tuổi (5 nhóm + "Chưa có ngày sinh"), (4) trình độ cao nhất (có nhóm "Chưa có"), (5) chức danh, (6) hoàn thiện / chưa hoàn thiện, (7) hồ sơ mới theo tháng, (8) vào làm / nghỉ việc theo tháng, (9) công nhân đang làm theo công ty khách. Báo cáo cơ cấu (1–6, 9) tính **công nhân đang làm hiện tại** (Thử việc + Đang làm việc), lọc được theo phòng ban; khoảng thời gian (mặc định 12 tháng gần nhất) chỉ áp cho báo cáo theo tháng (7, 8). Mỗi bảng có dòng Tổng |
| `/bao-cao/xuat-excel/` | G | ✓ | ✓ | ✓ | | `EXPORT` | Cùng tham số với `/bao-cao/`; mọi ô qua `safe_cell()`; V → 403 (câu 18) |
| `/bao-cao/in/` | G | ✓ | ✓ | ✓ | | `PRINT` | Bản in: tiêu đề, ngày lập, người lập; V → 403 (câu 18). Nhật ký ghi tên báo cáo, số dòng, bộ lọc (không ghi họ tên) |
| `/nhat-ky/` | G | ✓ | ✓ | | | | Lọc theo người (kể cả "Hệ thống"), mã hồ sơ/mã NV, hành động, khoảng thời gian. Không có nút sửa/xóa. Trường cá nhân hiện "(xem giá trị chi tiết)", bấm mở giá trị trước/sau từ `AuditPersonalValue`, giải mã khi hiển thị, chỉ A, Q (câu 30); số CCCD/CMND cũ vẫn hiện dạng che; hồ sơ đã ẩn danh hiện "(đã ẩn danh)" |
| `/nhat-ky/<id>/` | G | ✓ | ✓ | | | | **Phase 7.** Chi tiết một dòng nhật ký: giá trị trước/sau từng trường (dùng chung bộ dựng dòng với tab Lịch sử của hồ sơ). Xem trang này không ghi nhật ký (giống tab Lịch sử). H, V → 403 |

## 6. Kịch bản nghiệm thu → trang

| # | Kịch bản | Trang / URL |
| --- | --- | --- |
| 1 | Cài mới bằng Docker | `/dang-nhap/` với 4 tài khoản mẫu, `/ho-so/` (~500 hồ sơ) |
| 2 | Viewer mở hồ sơ | `/ho-so/<id>/` (CCCD che); `/ho-so/<id>/sua/`, `/tai-lieu/<id>/tai-xuong/` → 403 |
| 3 | CCCD giả có QR | `/nhap-cccd/` → `/nhap-cccd/<uuid>/` |
| 4 | CCCD không QR | `/nhap-cccd/<uuid>/` (trường tô vàng, nút Lưu khóa) |
| 5 | CCCD đã có | `/nhap-cccd/<uuid>/kiem-tra-trung/`, `/ho-so/kiem-tra-trung/` → "Mở hồ sơ cũ" |
| 6 | Gửi duyệt → trả lại → bổ sung → duyệt | `/ho-so/<id>/gui-duyet/`, `/duyet-ho-so/`, `/ho-so/<id>/tra-lai/`, `/ho-so/<id>/duyet/`, tab `lich-su`, `/nhat-ky/` |
| 7 | HR tự duyệt | `/ho-so/<id>/duyet/` → 403 |
| 8 | Đạt → Tiếp nhận | `/ung-tuyen/<id>/tiep-nhan/`, `/ho-so/?trang_thai_lam_viec=AWAITING` |
| 9 | Điều chuyển bộ phận | `/ho-so/<id>/lam-viec/thay-doi/`, tab `lam-viec` |
| 10 | Hợp đồng hết hạn sau 20 ngày | `/` thẻ "Hợp đồng sắp hết hạn" |
| 11 | Thẻ Thiếu giấy tờ | `/` → `/ho-so/?thieu_giay_to=1` |
| 12 | Tìm không dấu | `/ho-so/?q=nguyen van an` |
| 13 | Xuất Excel đang lọc | `/ho-so/xuat-excel/?...` |
| 14 | Sửa họ tên hồ sơ đã xác minh | `/ho-so/<id>/sua/`, tab `lich-su` |
| 15 | Sai mật khẩu 5 lần | `/dang-nhap/` |
| 16 | File Excel 3 dòng lỗi | `/ho-so/nhap-excel/` |
| 17 | Sao lưu, phục hồi | Không có trang (kịch bản trong `scripts/`, Phase 8) |
