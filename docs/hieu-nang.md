# Hiệu năng – Phase 7

Đo ngày 23/11/2026 bằng `scripts/do_hieu_nang_phase7.py` qua HTTP (như người dùng thật) trên bản cài sạch Docker Compose (`docker compose -f docker-compose.yml`, Gunicorn 3 worker, PostgreSQL 16) với `seed_demo` 500 hồ sơ, tài khoản Admin. Mỗi trang đo 5 lần sau 1 lần làm nóng; bảng ghi trung vị và lớn nhất. Yêu cầu (`docs/yeu-cau.md` mục VII): mở danh sách, lọc, tìm kiếm **dưới 2 giây**.

| Trang | Trung vị (giây) | Lớn nhất (giây) | Kết quả |
| --- | --- | --- | --- |
| Dashboard (`/`) | 0.35 | 0.39 | Đạt |
| Danh sách hồ sơ (không lọc) (`/ho-so/`) | 0.05 | 0.07 | Đạt |
| Danh sách trang 5 (`/ho-so/?trang=5`) | 0.05 | 0.07 | Đạt |
| Tìm không dấu “nguyen van an” (kịch bản 12) (`/ho-so/?q=nguyen+van+an`) | 0.05 | 0.05 | Đạt |
| Tìm theo số CCCD 12 chữ số (`/ho-so/?q=999000000123`) | 0.04 | 0.04 | Đạt |
| Tìm theo SĐT (`/ho-so/?q=0912`) | 0.05 | 0.06 | Đạt |
| Lọc chưa Lưu trữ (`/ho-so/?trang_thai_ho_so=chua-luu-tru`) | 0.05 | 0.05 | Đạt |
| Lọc Thiếu giấy tờ (kịch bản 11) (`/ho-so/?thieu_giay_to=1&trang_thai_ho_so=chua-luu-tru`) | 0.31 | 0.33 | Đạt |
| Lọc Hoàn thiện (`/ho-so/?hoan_thien=1`) | 0.09 | 0.09 | Đạt |
| Lọc đang làm việc (`/ho-so/?trang_thai_lam_viec=PROBATION%2CACTIVE`) | 0.05 | 0.06 | Đạt |
| Lọc hợp đồng sắp hết hạn (kịch bản 10) (`/ho-so/?hop_dong_sap_het_han=1`) | 0.05 | 0.05 | Đạt |
| Lọc đợt sắp đủ 12 tháng (`/ho-so/?dot_sap_du_han=1`) | 0.07 | 0.09 | Đạt |
| Lọc CCCD sắp hết hạn (`/ho-so/?cccd_sap_het_han=1`) | 0.05 | 0.07 | Đạt |
| Lọc công ty khách (`/ho-so/?cong_ty_khach=5`) | 0.06 | 0.07 | Đạt |
| Lọc chưa có bộ phận (`/ho-so/?bo_phan=chua-co`) | 0.07 | 0.10 | Đạt |
| Lọc trình độ (`/ho-so/?trinh_do=1`) | 0.05 | 0.05 | Đạt |
| Lọc trạng thái tuyển dụng (`/ho-so/?trang_thai_tuyen_dung=NEW`) | 0.06 | 0.06 | Đạt |
| Xuất Excel danh sách (kịch bản 13) (`/ho-so/xuat-excel/`) | 0.15 | 0.19 | Đạt |
| Xuất Excel danh sách đang lọc (`/ho-so/xuat-excel/?trang_thai_lam_viec=PROBATION%2CACTIVE`) | 0.08 | 0.10 | Đạt |
| Tuyển dụng (`/tuyen-dung/`) | 0.03 | 0.04 | Đạt |
| Duyệt hồ sơ (`/duyet-ho-so/`) | 0.05 | 0.06 | Đạt |
| Nhật ký (`/nhat-ky/`) | 0.03 | 0.05 | Đạt |
| Nhật ký lọc hành động (`/nhat-ky/?hanh_dong=CREATE`) | 0.04 | 0.05 | Đạt |
| Chờ hủy (`/cai-dat/cho-huy/`) | 0.10 | 0.11 | Đạt |
| Biên bản hủy (`/cai-dat/bien-ban-huy/`) | 0.02 | 0.04 | Đạt |
| Báo cáo phong-ban (`/bao-cao/?loai=phong-ban`) | 0.02 | 0.05 | Đạt |
| Báo cáo gioi-tinh (`/bao-cao/?loai=gioi-tinh`) | 0.02 | 0.04 | Đạt |
| Báo cáo nhom-tuoi (`/bao-cao/?loai=nhom-tuoi`) | 0.02 | 0.04 | Đạt |
| Báo cáo trinh-do (`/bao-cao/?loai=trinh-do`) | 0.03 | 0.05 | Đạt |
| Báo cáo chuc-danh (`/bao-cao/?loai=chuc-danh`) | 0.02 | 0.05 | Đạt |
| Báo cáo hoan-thien (`/bao-cao/?loai=hoan-thien`) | 0.06 | 0.06 | Đạt |
| Báo cáo ho-so-moi (`/bao-cao/?loai=ho-so-moi`) | 0.03 | 0.04 | Đạt |
| Báo cáo vao-lam-nghi-viec (`/bao-cao/?loai=vao-lam-nghi-viec`) | 0.02 | 0.04 | Đạt |
| Báo cáo cong-ty-khach (`/bao-cao/?loai=cong-ty-khach`) | 0.02 | 0.02 | Đạt |
| Xuất Excel báo cáo phong-ban (`/bao-cao/xuat-excel/?loai=phong-ban`) | 0.03 | 0.03 | Đạt |

## Nhập Excel

Giới hạn dòng mỗi lần nhập được chốt theo kết quả đo; quá 90 giây thì phải hạ giới hạn (không tăng timeout Gunicorn, hiện 120 giây).

| Số dòng | Có phần B (mã NV, đợt làm việc) | Thời gian (giây) | Kết quả đọc |
| --- | --- | --- | --- |
| 1000 | không | 13.3 | HTTP 200; ["1000", "1000", "0"] |
| 1000 | có | 21.6 | HTTP 200; ["1000", "1000", "0"] |


**Kết luận:** lần chậm nhất 21.6 giây (≤ 90 giây) nên giữ giới hạn 1.000 dòng.
