# Biên bản danh sách bàn giao – PA Worker v1.1.0

Đơn vị phát triển: QQIT · Ngày lập: 24/11/2026 · Phiên bản: **1.1.0** (tag Git `v1.1.0`).

Dành cho đại diện doanh nghiệp nhận bàn giao và người phụ trách dự án. Kết quả kiểm thử chi tiết: [docs/nghiem-thu.md](nghiem-thu.md).

## 1. Danh sách bàn giao

| # | Hạng mục | Nội dung | Ghi chú |
| --- | --- | --- | --- |
| 1 | Mã nguồn | Kho Git, tag `v1.1.0` | Bản quyền thuộc QQIT; có README, chú thích tiếng Việt ở phần nghiệp vụ |
| 2 | Bản cài đặt | Tệp `pa-worker-v1.1.0.zip` (tạo bằng `git archive` từ tag `v1.1.0`) | Không chứa `.env`, khóa, dữ liệu, bản sao lưu |
| 3 | Tệp bấm chạy (Windows) | `PA Worker.bat`, `Sao luu.bat`, `Phuc hoi.bat`, `Cap nhat.bat`, `Kiem tra.bat`; `scripts\windows\mo-cong-8000.ps1`, `dang-ky-chep-sao-luu.ps1` | Đã thử trên Windows 11 |
| 4 | Hướng dẫn cài đặt | [docs/huong-dan-cai-dat.md](huong-dan-cai-dat.md) | Có các khung "[ẢNH CẦN CHỤP]" cho bước cài Docker Desktop: chụp trên máy thật khi cài |
| 5 | Hướng dẫn sử dụng | [docs/huong-dan-su-dung.md](huong-dan-su-dung.md) | Theo 4 vai trò |
| 6 | Xử lý sự cố | [docs/xu-ly-su-co.md](xu-ly-su-co.md) | |
| 7 | Kết quả nghiệm thu | [docs/nghiem-thu.md](nghiem-thu.md), ảnh trong `docs/screenshots/` | 17 kịch bản mục X và kịch bản v1.1 |
| 8 | Rà soát bảo mật | [docs/ra-soat-bao-mat.md](ra-soat-bao-mat.md) | Gồm quét lỗ hổng image (Trivy) |
| 9 | Tài liệu yêu cầu, thiết kế | `docs/yeu-cau.md`, `docs/lam-ro-yeu-cau.md`, `docs/thiet-ke/` | |
| 10 | Đo hiệu năng, độ chính xác nhận diện | `docs/hieu-nang.md`, `docs/do-chinh-xac-nhan-dien.md` | Đo trên dữ liệu và ảnh giả lập |
| 11 | Tài liệu khóa luận | `docs/khoa-luan/` (quy trình trước/sau, so sánh thời gian, đối chiếu pháp luật), [kịch bản trình diễn 10 phút](kich-ban-demo.md) | Bảng thời gian thủ công và số điều luật cần người viết khóa luận và pháp chế bổ sung |
| 12 | Bộ kiểm thử tự động | `tests/` (pytest, chạy trên PostgreSQL), `scripts/kiem_thu_giao_dien_*.py`, `scripts/nghiem_thu_*.py` (Playwright) | |

## 2. Tài khoản và khóa

- **Bản Thật:** khi chạy `PA Worker.bat` lần đầu, máy của doanh nghiệp tự sinh khóa và tạo **một** tài khoản Admin; mật khẩu tạm chỉ hiện trên màn hình cài đặt. Đơn vị phát triển **không** giữ khóa hay mật khẩu nào của bản Thật.
- **Bản Demo:** 4 tài khoản mẫu `admin`, `quanly`, `hr`, `viewer`, mật khẩu tạm sinh ngẫu nhiên khi cài. Chỉ dùng để tập và trình diễn, **không nhập dữ liệu thật**.
- **Quy trình giao khóa:** người cài đặt chép tệp `.env` vào USB riêng (hoặc in, niêm phong) **ngay khi cài**, giao cho người được doanh nghiệp chỉ định giữ, ký nhận. Không gửi `.env`, mật khẩu hay file sao lưu qua email, Zalo, tin nhắn. Mất khóa thì không đọc được dữ liệu đã mã hóa và không phục hồi được bản sao lưu.
- Admin quên mật khẩu: [Xử lý sự cố](xu-ly-su-co.md#quên-mật-khẩu-admin).

## 3. Giới hạn đã biết

| # | Giới hạn | Ảnh hưởng, cách xử lý |
| --- | --- | --- |
| 1 | **Chỉ hỗ trợ Windows; macOS cần khách đồng ý bổ sung.** Không có tệp `.command`, hướng dẫn macOS, phương án chạy không Docker cho người dùng cuối | Yêu cầu mục I và `docs/phases.md` có nhắc macOS. Bản chạy thử SQLite chỉ dành cho người phát triển (`docs/chay-sqlite.md`) |
| 2 | Chạy HTTP trong mạng nội bộ; HTTPS cần reverse proxy do người có chuyên môn cài thêm | `docs/huong-dan-cai-dat.md` mục 12 |
| 3 | Không hỗ trợ đổi khóa mã hóa sau khi cài | Câu 31 |
| 4 | File sao lưu mã hóa bằng khóa của bản cài: mất khóa thì không phục hồi được bản sao lưu | Câu 49; quy trình cất khóa |
| 5 | Khóa đăng nhập theo từng tài khoản, không giới hạn theo địa chỉ IP | `docs/ra-soat-bao-mat.md` mục 3, số 13 |
| 6 | Image chạy thật có cả gói chỉ dùng để kiểm thử (`pytest`, `ruff`) | `docs/ra-soat-bao-mat.md` mục 3, số 14 |
| 7 | Còn lỗ hổng HIGH/CRITICAL chưa có bản sửa trong gói Debian 13 (`libxml2`, `tesseract`, `openssl`…), đã đánh giá mức liên quan | `docs/ra-soat-bao-mat.md` mục 5; quét lại khi cập nhật |
| 8 | Cấu trúc QR của CCCD là giả định: mới thử 1 thẻ CCCD 2021 thật; chưa thử Căn cước 2024 và CCCD 2016 thật; độ chính xác đo trên ảnh giả sạch | Thử thẻ thật tại chỗ, chỉnh ở Cài đặt → OCR và QR (không sửa mã) |
| 9 | API OCR trả phí mới có phần cài đặt, chưa kết nối nhà cung cấp nào | Tắt mặc định |
| 10 | Nhập Excel chạy trong một lượt (1.000 dòng mất 13–22 giây), chưa có thanh tiến độ | `docs/hieu-nang.md` |
| 11 | Mở lại trang Xuất/In ghi thêm dòng nhật ký; hộp "Xuất kèm số CCCD" vẫn mở sau khi tải tệp | Giới hạn Phase 7 |
| 12 | Dòng nhật ký Đổi trạng thái tạo trước Phase 7 có lý do người gõ ở phần ghi chú; chỉ được che khi hiển thị | Bản cài mới không có dòng kiểu cũ |
| 13 | Chưa có nút "rút lại sự đồng ý" riêng; xử lý bằng quy trình Lưu trữ + ẩn danh hóa theo yêu cầu | `docs/khoa-luan/doi-chieu-phap-luat.md` mục 1, số 6 |
| 14 | Tab Chi tiết hồ sơ chưa hiện nhãn nguồn QR/OCR của từng trường (dữ liệu đã lưu) | Phase 5 |
| 15 | Ảnh chụp nghiêng/lóa chưa thử; nút Xoay ảnh chỉ xoay 90°; tệp `.doc` thật chưa thử ngoài tệp tạo bằng LibreOffice | Phase 5 |
| 16 | Không có chức năng nhập lương hàng loạt từ Excel, lương không có trong file xuất | Câu 42, 48 |

## 4. Các điểm cần khách hàng xác nhận

Các quyết định dưới đây do đơn vị phát triển hoặc người phụ trách dự án chốt để làm phần mềm (đánh dấu [Nội bộ]/[Giả định] trong `docs/lam-ro-yeu-cau.md`), **chưa có xác nhận của khách hàng**.

**Ưu tiên cao**

1. **File sao lưu được mã hóa; mất khóa thì không đọc được bản sao lưu – bắt buộc cất khóa theo quy trình (câu 31, 49).**
2. **Chỉ hỗ trợ Windows; macOS cần khách đồng ý bổ sung (câu 49).**
3. Hủy hồ sơ hết hạn = ẩn danh hóa: không xóa cứng; giữ mã và nhật ký, xóa dữ liệu cá nhân, tệp và giá trị cá nhân trong nhật ký; bảng 6 căn cứ hạn lưu trữ (câu 2, 30).
4. Tự Lưu trữ: 30 ngày sau nghỉ việc; 30 ngày sau kết quả Không đạt/Ứng viên từ chối; 30 ngày sau Bị từ chối; hồ sơ Nháp/Cần bổ sung bỏ dở 6 tháng (câu 9).
5. Chặn nhập người dưới 15 tuổi; 15 đến dưới 18 tuổi chỉ cảnh báo (câu 16).
6. Hồ sơ nhập từ Excel phải do người khác người nhập duyệt từng hồ sơ, không duyệt hàng loạt (câu 8, 27).
7. Ẩn danh hóa theo yêu cầu: Admin xóa sớm dữ liệu cá nhân khi người lao động yêu cầu, chỉ với hồ sơ Lưu trữ, không hoàn tác được (câu 38).
8. Hai chế độ cài Demo/Thật; bản Thật không có dữ liệu mẫu, Admin đầu tiên tạo khi cài (câu 49).

**Các điểm khác**

9. Nháp chỉ cần họ tên + SĐT; điều kiện gửi duyệt; cảnh báo trùng theo SĐT, họ tên + ngày sinh (câu 5).
10. HR không chuyển Lưu trữ hồ sơ Đã xác minh; QL/Admin chuyển phải ghi lý do. Chặn Lưu trữ khi Thử việc/Đang làm việc áp dụng cho **mọi** đường chuyển sang Lưu trữ (câu 9, Phase 4).
11. Sửa hồ sơ Đã xác minh phải giữ đủ các trường bắt buộc khi gửi duyệt (Phase 4).
12. Dữ liệu mẫu có bộ phận "Văn phòng" và ít nhất 1 tài khoản Quản lý (câu 15); kỹ năng là một trường văn bản (câu 25); 5 nhóm tuổi và nhóm "Chưa có ngày sinh" (câu 26).
13. File Excel mẫu 2 phần; nhận mã NV cũ tối đa 20 ký tự, chữ/số/gạch ngang (câu 27).
14. Hai cơ chế khóa tài khoản (câu 28); bảo vệ Admin cuối cùng (câu 29).
15. Hợp đồng hiển thị bản tài liệu hiện hành (câu 32); "Ứng viên từ chối" lưu 12 tháng (câu 33); chỉ QL/Admin xác minh tài liệu (câu 34); Bị từ chối chỉ xem (câu 35); Chờ duyệt chỉ khóa phần được duyệt (câu 36); giới tính Nam/Nữ (câu 37).
16. **v1.1** (câu 48): Bộ phận không bắt buộc; cột "Công ty khách" thay cột "Bộ phận" ở danh sách hồ sơ; mức lương mong muốn mở cho Viewer; cảnh báo 12 tháng cộng dồn các đợt liền nhau cùng **tên** công ty khách.
17. **v1.1:** bản gốc hợp đồng lao động, bản cam kết, bảng lương lưu ngoài phần mềm theo quy định (câu 47); có cần nhập lương hàng loạt từ Excel không (câu 48).
18. **Phase 7:** file xuất Excel luôn che CCCD, chỉ Admin và Quản lý được xuất kèm số đầy đủ (ghi nhật ký), HR luôn nhận bản che; báo cáo cơ cấu tính công nhân đang làm (Thử việc + Đang làm việc), khoảng ngày chỉ áp cho báo cáo theo tháng; lý do người gõ khi đổi trạng thái là dữ liệu cá nhân (che khi ẩn danh hóa); thẻ Thiếu giấy tờ không tính hồ sơ Lưu trữ.
19. Pháp chế doanh nghiệp duyệt mẫu văn bản đồng ý (`docs/thiet-ke/mau-dong-y.md`, 5 câu hỏi cuối tệp) và điền số điều luật trong `docs/khoa-luan/doi-chieu-phap-luat.md`.
20. Cấu trúc QR của CCCD (câu 20) được kiểm chứng bằng thẻ thật tại chỗ khách.

## 5. Việc người nhận bàn giao cần làm

- [ ] Chép `docs/yeu-cau-thay-doi-v1.1.pdf` (phiếu thay đổi đã ký) vào kho mã nguồn; các tài liệu đang tham chiếu tới tệp này.
- [ ] Chụp và chèn các ảnh "[ẢNH CẦN CHỤP]" trong hướng dẫn cài đặt khi cài trên máy thật.
- [ ] Thử thẻ Căn cước 2024 và CCCD 2016 thật; chỉnh cấu hình QR nếu cần; không lưu ảnh hay dữ liệu thẻ thật vào kho mã nguồn.
- [ ] Đo thời gian thao tác thủ công cho bảng so sánh (`docs/khoa-luan/so-sanh-thoi-gian.md` mục 2).
- [ ] Xác nhận các điểm ở mục 4.

## 6. Xác nhận bàn giao

| | Bên giao (QQIT) | Bên nhận |
| --- | --- | --- |
| Họ tên | | |
| Chức vụ | | |
| Ngày | | |
| Ký tên | | |
