# Kết quả nghiệm thu tổng – PA Worker v1.1.0

Đơn vị phát triển: QQIT · Phiên bản: **1.1.0** · Ngày nghiệm thu: **24/11/2026**.

Tài liệu này trình bày kết quả chạy đủ 17 kịch bản nghiệm thu (mục X của `docs/yeu-cau.md`) và các bước bổ sung, trên **bản cài sạch** dùng tệp `PA Worker.bat` (chỉ có Docker Desktop, không có Python hay cơ sở dữ liệu sẵn). Mọi số liệu lấy từ kết quả chạy thật, lưu tại `docs/screenshots/phase-8/nghiem-thu/ket-qua.json` và nhật ký từng bước trong `docs/screenshots/phase-8/nghiem-thu/logs/`.

## 1. Môi trường và thời gian

| Hạng mục | Giá trị |
| --- | --- |
| Hệ điều hành | Windows (máy chủ) |
| Cách cài | Chạy `PA Worker.bat` bản Demo trên máy chỉ có Docker Desktop |
| Cài đặt lần đầu (bước 1) | ~2,0 phút, tạo 4 tài khoản mẫu, có bộ hồ sơ giả lập |
| Chạy nghiệm thu tổng (lượt chính thức) | **955 giây** (gồm tất cả bước dưới) |
| Kiểm thử tự động (bộ test) | **2503 test đạt** (PostgreSQL, không skip) |

Chú ý: thời gian cài đặt ở mục 1 của `docs/yeu-cau.md` yêu cầu "chạy được trong 30 phút" — lượt này cài đặt lần đầu trong ~2 phút (mạng nhanh của máy phát triển), đạt yêu cầu.

## 2. Kịch bản nghiệm thu (17 kịch bản + v1.1)

Tất cả các kịch bản **đạt** (Đạt/Không đạt: "Đạt"). Cột "Số bước" là số bước kiểm tra đã chạy và đạt trong nhóm đó; cột "Ảnh minh họa" trỏ tới thư mục nhật ký/ảnh lưu kết quả.

| # | Kịch bản (theo `docs/yeu-cau.md` mục X) | Kết quả | Số bước | Ảnh minh họa |
| --- | --- | --- | --- | --- |
| 1 | Máy mới chỉ có Docker Desktop, chạy theo hướng dẫn (cài đặt, 4 tài khoản mẫu) | Đạt | (bước 1) | `logs/01-cai-dat-pa-worker-bat.txt` |
| 15 | Nhập 5 lần sai mật khẩu → khóa 15 phút | Đạt | 52 (chạy chung K1) | `docs/screenshots/phase-3/nghiem-thu/` |
| 2 | Viewer mở hồ sơ → che CCCD, từ chối sửa/tải | Đạt | 40 (nhóm K2–14) | `docs/screenshots/phase-4/nghiem-thu/` |
| 5 | Nhập CCCD trùng → báo trùng, mở hồ sơ cũ | Đạt | (nhóm trên) | `docs/screenshots/phase-4/nghiem-thu/` |
| 6 | Gửi duyệt → trả lại → bổ sung → duyệt | Đạt | (nhóm trên) | `docs/screenshots/phase-4/nghiem-thu/` |
| 7 | HR tự duyệt hồ sơ mình nhập → bị chặn | Đạt | (nhóm trên) | `docs/screenshots/phase-4/nghiem-thu/` |
| 14 | Sửa hồ sơ đã xác minh → quay về Chờ duyệt, có nhật ký | Đạt | (nhóm trên) | `docs/screenshots/phase-4/nghiem-thu/` |
| 3 | HR tải ảnh CCCD giả có QR → điền đúng 100% trường QR | Đạt | 41 (nhóm K3–5) | `docs/screenshots/phase-5/nghiem-thu/` |
| 4 | Ảnh CCCD không QR → OCR, tô vàng, chưa xác nhận không lưu | Đạt | (nhóm trên) | `docs/screenshots/phase-5/nghiem-thu/` |
| 8 | Ứng viên "Đạt" → tiếp nhận sinh mã nhân viên | Đạt | 39 (nhóm K8–10 + v1.1) | `docs/screenshots/phase-6/nghiem-thu/` |
| 9 | Điều chuyển bộ phận, lịch sử giữ dòng cũ | Đạt | (nhóm trên) | `docs/screenshots/phase-6/nghiem-thu/` |
| 10 | Hợp đồng sắp hết hạn hiện trong thẻ Dashboard | Đạt | (cả nhóm K8–10 và K10–16) | `docs/screenshots/phase-7/nghiem-thu/` |
| 11 | Bấm thẻ "Thiếu giấy tờ" → danh sách khớp số | Đạt | 105 (nhóm K10–16) | `docs/screenshots/phase-7/nghiem-thu/` |
| 12 | Tìm không dấu "nguyen van an" → ra "Nguyễn Văn An" | Đạt | (nhóm trên) | `docs/screenshots/phase-7/nghiem-thu/` |
| 13 | Xuất Excel danh sách đang lọc, che CCCD theo quyền | Đạt | (nhóm trên) | `docs/screenshots/phase-7/nghiem-thu/` |
| 16 | Nhập Excel có 3 dòng lỗi → dòng đúng nhập, báo rõ 3 lỗi | Đạt | (nhóm trên) | `docs/screenshots/phase-7/nghiem-thu/` |
| 17 | Sao lưu, xóa volume, dựng lại, phục hồi | Đạt | 25 | `docs/screenshots/phase-8/sao-luu/` + `logs/kb-17.txt` |
| v1.1 | Đợt làm việc, lịch sử lương, cảnh báo 12 tháng, báo cáo công ty khách | Đạt | (trong nhóm K8–10, 39 bước) | `docs/screenshots/phase-6/nghiem-thu/` |

**Tổng kết: 17/17 kịch bản + kịch bản v1.1 đều đạt.** Nhóm chạy được gộp theo phase để tránh trùng lặp (ví dụ K1+15 chạy trong một script 52 bước; K2, 5, 6, 7, 14 chạy trong một script 40 bước); mỗi kịch bản vẫn có bước riêng được kiểm và đạt.

## 3. Kiểm thử giao diện (hồi quy Phase 3–8)

| Phase | Số bước | Kết quả |
| --- | --- | --- |
| Phase 3 | 81 | Đạt |
| Phase 4 | 111 | Đạt |
| Phase 5 | 88 | Đạt |
| Phase 6 | 149 | Đạt |
| Phase 7 | 173 | Đạt |
| Phase 8 | 21 | Đạt |

Ảnh 1366×768 và 390×844 của từng phase ở `docs/screenshots/phase-3/` … `docs/screenshots/phase-8/`.

## 4. Bản Thật (thư mục riêng, tên dự án `pa_ban_that`, cổng 8002)

8/8 bước đạt:

- `PA Worker.bat` bản Thật chạy xong, tạo **1 tài khoản Admin** duy nhất
- **seed_demo bị chặn** ở bản Thật (không nạp dữ liệu giả lập)
- `DEMO_MODE=0`, `DEBUG=0`
- Đăng nhập lần đầu bị chuyển tới trang **Đổi mật khẩu** (bắt buộc)
- Sau đổi mật khẩu vào Tổng quan, menu Admin đủ mục
- Trang 404 hiển thị **tiếng Việt** (DEBUG=0)
- Máy khác trong mạng truy cập được bằng **IP LAN** (192.168.10.27)

Ảnh: `docs/screenshots/phase-8/nghiem-thu/ban-that-tong-quan.png`, `logs/05-ban-that-pa-worker-bat.txt`.

## 5. Hiệu năng

Chi tiết ở `docs/hieu-nang.md`. Tóm tắt (trên bản có 500 hồ sơ, qua HTTP):

- Các trang danh sách, lọc, tìm: **35 trang đều dưới 0,4 giây** (yêu cầu < 2 giây)
- Nhập Excel: 1.000 dòng ~13–22 giây (dưới ngưỡng 90 giây), giữ giới hạn 1.000 dòng

## 6. Giới hạn đã biết (không phải lỗi)

Đã liệt kê trong `docs/ban-giao.md` (mục 3, 4) và `docs/tien-do.md` phần "Việc còn tồn". Điểm chính người nhận bàn giao cần biết:

- Cấu trúc QR của thẻ CCCD/Căn cước là **giả định**, cần kiểm chứng bằng thẻ thật tại nơi triển khai (đã thử 1 thẻ CCCD 2021 thật, QR đọc đúng; còn cần thử thẻ 2024 và CCCD 2016).
- API OCR ngoài chỉ có **cài đặt và nhật ký**, chưa gắn nhà cung cấp (tắt mặc định).
- Chạy thử bằng SQLite (`docs/chay-sqlite.md`) **chỉ dành cho người phát triển**, không phải cho khách; bản chạy thật dùng Docker + PostgreSQL.
- Thời gian cài đặt trong mục 1 đo trên máy phát triển (mạng nhanh); nên **đo lại trên máy khách** khi cài thật.

Mọi điểm **cần khách hàng/hội đồng xác nhận** (các mục E, F, câu 49 và các quyết định [Nội bộ] của Phase 4, 7) đã gom tại `docs/ban-giao.md` mục 3, 4.
