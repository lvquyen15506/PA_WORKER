# Dữ liệu giả để kiểm thử

Mọi ảnh và tệp trong thư mục này là **dữ liệu hư cấu**, không có thông tin của người thật.

- Số CCCD giả luôn bắt đầu bằng `999`; họ tên, địa chỉ là tên hư cấu.
- Mọi mặt thẻ có dòng "MẪU – KHÔNG CÓ GIÁ TRỊ". Bố cục chỉ là chữ, không có quốc huy hay
  họa tiết thẻ thật.
- QR được sinh theo cấu hình QrFormat tại thời điểm chạy lệnh (`python manage.py make_fake_cccd`),
  nên bộ ảnh chỉ chứng minh bộ tách trường khớp cấu hình, **chưa chứng minh khớp thẻ thật**
  (câu 20).
- `truth.json`: giá trị đúng của từng thẻ (`values`), trường in trên thẻ (`printed`), trường có
  trong QR (`qr_fields`), chất lượng ảnh (`good`, `low_res`, `dark`, `blur`).
- Sinh lại: `docker compose exec web python manage.py make_fake_cccd --out tests/fixtures/cccd`
