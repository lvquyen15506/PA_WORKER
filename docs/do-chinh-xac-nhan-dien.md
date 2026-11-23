# Độ chính xác nhận diện CCCD và thời gian xử lý

Đo ngày 23/11/2026 bằng `python manage.py measure_intake_accuracy` trên bộ 15 thẻ giả (`tests/fixtures/cccd/`, 2 mặt mỗi thẻ).

## Phạm vi và giới hạn

- **Dữ liệu hoàn toàn giả**: số CCCD bắt đầu `999`, tên hư cấu, mọi ảnh có dòng "MẪU – KHÔNG CÓ GIÁ TRỊ". Bố cục là chữ in rõ trên nền trắng, không có họa tiết, ánh sáng hay nghiêng như ảnh chụp thật.
- QR sinh theo đúng cấu hình `QrFormat` đang dùng, nên kết quả QR chỉ chứng minh bộ tách trường **khớp cấu hình**, **chưa chứng minh khớp thẻ thật** (câu 20 của `docs/lam-ro-yeu-cau.md`). Cấu trúc QR của thẻ thật vẫn là giả định cần kiểm chứng khi triển khai.
- Bộ thẻ có tên nhiều dấu (ví dụ `NGUYỄN THỊ HƯƠNG QUỲNH`, `ĐẶNG VĂN ƯỚC`), QR mã hóa UTF-8 có và không có chỉ thị ECI, ngày cấp đúng mẫu thẻ (CCCD 2021 cấp trước 01/7/2024, Căn cước 2024 từ 01/7/2024) và hạn thẻ đúng mốc tuổi 25/40/60, nên gợi ý "Có giá trị đến" không xuất hiện khi OCR đọc được. Trường nguồn "Gợi ý" (nơi cấp, quốc tịch, hạn tính theo quy định) chỉ xuất hiện khi OCR không đọc được và luôn tô vàng.
- Độ chính xác OCR trên ảnh sạch này **cao hơn nhiều so với ảnh chụp thật**; đừng dùng con số này để cam kết với khách hàng. Cần đo lại trên ảnh chụp thực tế khi có thể.
- Ngưỡng tin cậy OCR khi đo: 80%. Cấu hình QR khi đo:
  - `CAN_CUOC_2024`: phân cách `|`, ngày `ddmmyyyy`, thứ tự `id_number, old_id_number, full_name, date_of_birth, gender, permanent_address, issue_date`
  - `CCCD_2021`: phân cách `|`, ngày `ddmmyyyy`, thứ tự `id_number, old_id_number, full_name, date_of_birth, gender, permanent_address, issue_date`

## Kết quả tổng hợp

| Chỉ số | Kết quả |
| --- | --- |
| Trường đọc từ QR đúng (kịch bản 3) | 66/66 (100%) |
| Trường đọc từ OCR đúng (kịch bản 4) | 76/84 (90%) |
| Nhận đúng mẫu thẻ | 15/15 (100%) |
| Trường để trống (không đọc được) | 7/150 |
| Trường bị tô vàng (phải tích Đã kiểm tra) | 9/150 |
| **Trường sai mà KHÔNG tô vàng** | **0** |

Chỉ số quan trọng nhất là dòng đậm: một trường đọc sai mà không bị tô vàng sẽ lọt qua bước kiểm tra của người dùng.

## Theo mẫu thẻ và trường

| Mẫu thẻ | Trường | QR đúng | OCR đúng |
| --- | --- | --- | --- |
| CAN_CUOC_2024 | Nơi đăng ký khai sinh | — | 5/5 (100%) |
| CAN_CUOC_2024 | Ngày sinh | 5/5 (100%) | — |
| CAN_CUOC_2024 | Có giá trị đến | — | 5/5 (100%) |
| CAN_CUOC_2024 | Họ và tên | 5/5 (100%) | — |
| CAN_CUOC_2024 | Giới tính | 5/5 (100%) | — |
| CAN_CUOC_2024 | Số CCCD | 5/5 (100%) | — |
| CAN_CUOC_2024 | Ngày cấp | 5/5 (100%) | — |
| CAN_CUOC_2024 | Nơi cấp | — | 5/5 (100%) |
| CAN_CUOC_2024 | Quốc tịch | — | 5/5 (100%) |
| CAN_CUOC_2024 | Nơi thường trú | 5/5 (100%) | — |
| CCCD_2016 | Ngày sinh | — | 3/4 (75%) |
| CCCD_2016 | Có giá trị đến | — | 4/4 (100%) |
| CCCD_2016 | Họ và tên | — | 3/4 (75%) |
| CCCD_2016 | Giới tính | — | 3/4 (75%) |
| CCCD_2016 | Quê quán | — | 3/4 (75%) |
| CCCD_2016 | Số CCCD | — | 3/4 (75%) |
| CCCD_2016 | Ngày cấp | — | 3/4 (75%) |
| CCCD_2016 | Nơi cấp | — | 3/4 (75%) |
| CCCD_2016 | Quốc tịch | — | 4/4 (100%) |
| CCCD_2016 | Nơi thường trú | — | 3/4 (75%) |
| CCCD_2021 | Ngày sinh | 6/6 (100%) | — |
| CCCD_2021 | Có giá trị đến | — | 6/6 (100%) |
| CCCD_2021 | Họ và tên | 6/6 (100%) | — |
| CCCD_2021 | Giới tính | 6/6 (100%) | — |
| CCCD_2021 | Quê quán | — | 6/6 (100%) |
| CCCD_2021 | Số CCCD | 6/6 (100%) | — |
| CCCD_2021 | Ngày cấp | 6/6 (100%) | — |
| CCCD_2021 | Nơi cấp | — | 6/6 (100%) |
| CCCD_2021 | Quốc tịch | — | 6/6 (100%) |
| CCCD_2021 | Nơi thường trú | 6/6 (100%) | — |

## Theo chất lượng ảnh

| Chất lượng | Số thẻ |
| --- | --- |
| blur | 1 |
| dark | 1 |
| good | 12 |
| low_res | 1 |

`good` ảnh rõ; `low_res` rộng 800 px (dưới 1000); `dark` rất tối; `blur` mờ vừa.

## Thời gian xử lý một lượt ảnh trên CPU

Một lượt = kiểm tra ảnh + đọc QR + OCR cả hai mặt. Mỗi thẻ đo 3 lần, tính trên toàn bộ các lần đo (giây).

| Giai đoạn | Trung vị | Lớn nhất |
| --- | --- | --- |
| Kiểm tra ảnh | 0.02 | 0.03 |
| Đọc QR | 0.08 | 0.18 |
| OCR (Tesseract vie) | 0.39 | 0.43 |
| **Cả lượt** | 0.48 | 0.64 |

Ngân sách cho cả lượt là 90 giây (Gunicorn timeout 120 giây); hết ngân sách thì trường chưa đọc để trống, tô vàng và có cảnh báo.

## Máy đo

- Bộ xử lý: x86_64, 12 luồng
- Hệ điều hành trong container: Linux-6.18.58.1-microsoft-standard-WSL2-x86_64-with-glibc2.41
- Tesseract: 5.5.0, gói ngôn ngữ `vie`
- Python: 3.12.16
- Chạy trong container `web`, không dùng GPU.
