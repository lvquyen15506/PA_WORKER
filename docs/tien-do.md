# Tiến độ dự án PA Worker

## Quyết định đã chốt

| Ngày | Quyết định |
| --- | --- |
| 21/11/2026 | Khách hàng duyệt tài liệu yêu cầu v1.0 |
| 21/11/2026 | Web app chạy cục bộ; Python 3.12 + Django 5.2 LTS + PostgreSQL 16; triển khai bằng Docker Compose |
| 21/11/2026 | Giao diện theo skill `pa-ui`: navy/xanh dương/trắng, Bootstrap 5, một bộ icon, không màu mè |
| 21/11/2026 | Chốt 24 câu làm rõ yêu cầu ở Phase 0 (che CCCD, ẩn danh hóa khi hủy, bộ trạng thái tài liệu, Nháp chỉ cần họ tên + SĐT, tự Lưu trữ sau 30 ngày, tuổi < 15 chặn, cấu hình QR trong Cài đặt…), chi tiết ở `docs/lam-ro-yeu-cau.md`; tài liệu này ưu tiên hơn `docs/yeu-cau.md` khi khác nhau |
| 21/11/2026 | Quyết định nội bộ, chưa xác nhận với khách hàng: câu 9 – HR chỉ chuyển Lưu trữ từ Nháp/Cần bổ sung, hồ sơ Đã xác minh chỉ QL/Admin chuyển Lưu trữ (bắt buộc lý do, chặn khi Thử việc/Đang làm việc); câu 15 – dữ liệu mẫu có bộ phận "Văn phòng" và ít nhất 1 tài khoản QL; câu 25 – kỹ năng là trường văn bản; câu 26 – 5 nhóm tuổi (thêm Dưới 18); câu 27 – file Excel mẫu 2 phần (cá nhân + làm việc, nhận mã NV cũ qua Admin/QL) |
| 21/11/2026 | Rà thiết kế Phase 1 (câu 28–38), quyết định [Nội bộ]: ký hiệu [Sửa]/[Nội bộ]; bảng 6 căn cứ hạn lưu trữ (câu 2); 4 quy tắc tự Lưu trữ (câu 9); ẩn lương mong muốn với Viewer (câu 13); mã NV cũ ≤ 20 ký tự (câu 27); hai cơ chế khóa tài khoản (câu 28); bảo vệ Admin cuối cùng (câu 29); `AuditPersonalValue` (câu 30); khóa mã hóa ngoài file sao lưu, kiểm tra bằng giá trị kiểm tra (câu 31); hợp đồng trỏ bản tài liệu hiện hành (câu 32); câu 33–37; ẩn danh hóa theo yêu cầu của chủ thể (câu 38). Mục E của `docs/lam-ro-yeu-cau.md` liệt kê 5 điểm ưu tiên cần khách xác nhận |

## Nhật ký phase

| Phase | Trạng thái | Ngày xong | Ghi chú |
| --- | --- | --- | --- |
| 0. Khởi động | Xong | 21/11/2026 | Cài skill webapp-testing + Playwright (Python 3.12 64-bit); thêm vòng lặp tự kiểm thử vào CLAUDE.md; tóm tắt yêu cầu, chốt 24 câu hỏi vào `docs/lam-ro-yeu-cau.md` |
| 1. Thiết kế | Xong | 22/11/2026 | 6 file trong `docs/thiet-ke/`: `erd.md` (34 bảng), `models.md` (34 model, TextChoices, quy tắc nghiệp vụ), `trang.md` (URL, quyền, component), `kien-truc.md`, `excel-mau.md`, `mau-dong-y.md`; `docs/lam-ro-yeu-cau.md` câu 1–38; CLAUDE.md cập nhật. Sơ đồ Mermaid đã kiểm tra cú pháp. `phac-thao-trang.md` dời sang đầu Phase 3. Không có code nên chưa chạy pytest/ruff |
| 2. Nền tảng + Docker | Chưa làm | | |
| 3. Bộ giao diện mẫu | Chưa làm | | |
| 4. Hồ sơ + tài liệu | Chưa làm | | |
| 5. CCCD + CV | Chưa làm | | |
| 6. Tuyển dụng + làm việc | Chưa làm | | |
| 7. Tra cứu + báo cáo | Chưa làm | | |
| 8. Nghiệm thu + bàn giao | Chưa làm | | |

## Việc còn tồn

- Khách hàng xác nhận mục E của `docs/lam-ro-yeu-cau.md` (5 điểm ưu tiên cao: hủy = ẩn danh hóa, tự Lưu trữ, chặn dưới 15 tuổi, duyệt hồ sơ nhập Excel, ẩn danh hóa theo yêu cầu).
- Pháp chế doanh nghiệp duyệt `docs/thiet-ke/mau-dong-y.md` (5 câu hỏi ở cuối file).
- Cấu trúc QR CCCD là giả định (câu 20), cần kiểm chứng bằng thẻ thật tại chỗ khách khi triển khai.
- Viết `docs/thiet-ke/phac-thao-trang.md` ở đầu Phase 3.
