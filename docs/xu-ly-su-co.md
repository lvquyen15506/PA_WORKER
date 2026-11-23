# Xử lý sự cố thường gặp – PA Worker

Phiên bản 1.1.0 · Dành cho Admin và người hỗ trợ kỹ thuật tại doanh nghiệp.

Việc đầu tiên khi có sự cố: bấm đúp **`Kiem tra.bat`** trong thư mục PA Worker. Tệp này báo Docker có chạy không, các thành phần có chạy không, khóa có khớp không, dung lượng đĩa và bản sao lưu mới nhất. Các lệnh `docker compose …` bên dưới chạy trong PowerShell mở tại thư mục PA Worker (Shift + chuột phải vào khoảng trống → *Open PowerShell window here*).

## Mục lục

- [Quên mật khẩu Admin](#quên-mật-khẩu-admin)
- [Người dùng quên mật khẩu hoặc bị khóa](#người-dùng-quên-mật-khẩu-hoặc-bị-khóa)
- [Mất hoặc sai khóa mã hóa](#mất-hoặc-sai-khóa-mã-hóa)
- [Docker Desktop không chạy](#docker-desktop-không-chạy)
- [Trang web không mở được](#trang-web-không-mở-được)
- [Máy khác báo "Yêu cầu không hợp lệ"](#máy-khác-báo-yêu-cầu-không-hợp-lệ)
- [Đầy đĩa](#đầy-đĩa)
- [Sao lưu hoặc phục hồi báo lỗi](#sao-lưu-hoặc-phục-hồi-báo-lỗi)
- [Nhận diện CCCD đọc sai](#nhận-diện-cccd-đọc-sai)
- [Trang báo "Hệ thống gặp lỗi"](#trang-báo-hệ-thống-gặp-lỗi)
- [Khi cần gọi đơn vị phát triển](#khi-cần-gọi-đơn-vị-phát-triển)

## Quên mật khẩu Admin

Nếu còn một Admin khác: Admin đó vào **Tài khoản** → **Đặt lại mật khẩu**.

Nếu không còn Admin nào đăng nhập được:

1. Mở PowerShell tại thư mục PA Worker.
2. Chạy:
   ```
   docker compose exec web python manage.py reset_admin_password
   ```
   Có nhiều Admin thì lệnh liệt kê tên đăng nhập; chạy lại kèm tên, ví dụ `… reset_admin_password admin`.
3. Lệnh mở khóa tài khoản, in **mật khẩu tạm** (chỉ hiện một lần) và đăng xuất mọi phiên cũ của tài khoản đó. Đăng nhập bằng mật khẩu tạm, hệ thống bắt đổi mật khẩu ngay.
4. Việc đặt lại được ghi nhật ký với người thực hiện "Hệ thống".

Lệnh chỉ dùng cho tài khoản Admin. Tài khoản khác do Admin đặt lại trong trang Tài khoản.

## Người dùng quên mật khẩu hoặc bị khóa

| Tình huống | Cách xử lý |
| --- | --- |
| Quên mật khẩu | Admin: **Tài khoản** → chọn người đó → **Đặt lại mật khẩu**, giao mật khẩu tạm trực tiếp |
| "Tài khoản tạm khóa do nhập sai nhiều lần. Thử lại sau hh:mm." | Chờ 15 phút, hoặc Admin bấm **Mở khóa** |
| "Tài khoản đã bị khóa. Liên hệ Admin." | Admin đã khóa tài khoản; chỉ Admin **Mở khóa** được |

## Mất hoặc sai khóa mã hóa

Khi tệp `.env` bị mất hoặc khóa trong đó sai, PA Worker **từ chối khởi động** để không làm hỏng dữ liệu. `PA Worker.bat` báo "Hệ thống chưa sẵn sàng" và in nhật ký có dòng như:

```
Thiếu khóa mã hóa FIELD_ENCRYPTION_KEY trong tệp .env. Hãy chép lại khóa từ bản sao đã cất khi cài đặt…
Khóa FIELD_ENCRYPTION_KEY không khớp với dữ liệu hiện có…
Khóa HASH_KEY không khớp với dữ liệu hiện có. Nếu chạy tiếp, kiểm tra trùng số CCCD sẽ sai…
```

Cách xử lý:
1. Lấy USB (hoặc phong bì niêm phong) đã cất khi cài đặt.
2. Chép tệp `.env` từ USB đè lên tệp `.env` trong thư mục PA Worker. Nếu cất bản giấy: mở `.env` bằng Notepad, gõ lại đúng hai dòng `FIELD_ENCRYPTION_KEY=` và `HASH_KEY=` (phân biệt chữ hoa, chữ thường), lưu lại.
3. Chạy lại `PA Worker.bat`.

**Nếu không còn bản sao khóa nào:** dữ liệu đã mã hóa (số CCCD, CMND cũ, địa chỉ thường trú, lương, giá trị chi tiết trong nhật ký) **không thể đọc lại**, và **mọi file sao lưu cũng không phục hồi được**. Không có cách nào lấy lại khóa, kể cả đơn vị phát triển. Lúc đó chỉ có thể cài mới (bản Thật) và nhập lại dữ liệu từ hồ sơ giấy.

Không bao giờ tự tạo `.env` mới (chạy lại `make_env.py` trên tệp `.env` đã có thì tệp đó không bị thay đổi). Nếu lỡ tạo `.env` mới với khóa mới, hệ thống sẽ báo khóa không khớp; chép lại `.env` cũ từ USB.

## Docker Desktop không chạy

Dấu hiệu: `PA Worker.bat` báo "Docker Desktop không khởi động được", hoặc biểu tượng cá voi ở góc phải thanh tác vụ không có hoặc báo lỗi.

1. Mở **Docker Desktop** từ menu Start, chờ 2–3 phút tới khi hiện **Engine running**.
2. Vẫn không chạy: khởi động lại máy, thử lại.
3. Báo lỗi về **WSL**: mở PowerShell (Admin), chạy `wsl --update`, rồi khởi động lại máy.
4. Báo lỗi về **virtualization** (ảo hóa): ảo hóa trong BIOS bị tắt sau khi cập nhật BIOS, xem [Hướng dẫn cài đặt, mục 2.1](huong-dan-cai-dat.md#21-kiểm-tra-ảo-hóa).
5. Docker Desktop báo cần cập nhật: cho phép cập nhật, xong chạy lại `PA Worker.bat`.

Dữ liệu PA Worker nằm trong vùng lưu trữ của Docker và **không mất** khi Docker Desktop tắt, khởi động lại hay cập nhật. **Không** chọn *Troubleshoot → Clean / Purge data* hoặc *Reset to factory defaults* trong Docker Desktop: thao tác này **xóa toàn bộ dữ liệu** (khi đó chỉ còn cách phục hồi từ bản sao lưu).

## Trang web không mở được

| Dấu hiệu | Nguyên nhân thường gặp | Cách xử lý |
| --- | --- | --- |
| Trên máy chủ không mở được `http://localhost:8000` | Docker hoặc PA Worker chưa chạy | Chạy `PA Worker.bat` |
| `PA Worker.bat` chờ lâu rồi báo "Hệ thống chưa sẵn sàng" | Lỗi khóa (xem mục trên) hoặc thiếu bộ nhớ | Đọc nhật ký in ra; xem `docker compose logs --tail 50 web` |
| Máy khác không mở được, máy chủ mở được | Tường lửa, mạng Public, sai IP | Chạy `scripts\windows\mo-cong-8000.ps1`; đặt mạng Private; kiểm tra IP bằng `ipconfig` |
| Máy khác mở được hôm qua, hôm nay không | IP máy chủ đổi | Chạy `PA Worker.bat`, gõ `C` để thêm IP mới; báo người dùng địa chỉ mới |
| "Thư mục dữ liệu … không ghi được" | Cập nhật từ bản cũ mà chưa chạy `Cap nhat.bat` | Chạy `Cap nhat.bat` |

## Máy khác báo "Yêu cầu không hợp lệ"

Trang này (lỗi 400) nghĩa là địa chỉ IP dùng để truy cập chưa có trong `ALLOWED_HOSTS` của tệp `.env`. Chạy `PA Worker.bat` trên máy chủ và gõ `C` khi được hỏi thêm địa chỉ IP. Nếu máy chủ có nhiều card mạng, có thể thêm tay:

```
docker run --rm -v "${PWD}:/w" python:3.12-slim python /w/scripts/make_env.py --allowed-hosts 192.168.1.20
docker compose up -d
```

## Đầy đĩa

Dấu hiệu: `Kiem tra.bat` hoặc `PA Worker.bat` báo **CẢNH BÁO** ổ đĩa còn ít chỗ; sao lưu tự động báo "Ổ đĩa chứa bản sao lưu còn trống …"; tải tài liệu lên bị lỗi.

Xử lý theo thứ tự, an toàn trước:
1. **Chép các file sao lưu cũ ra ổ ngoài**, rồi xóa bớt trong thư mục `backups` (giữ lại ít nhất 3 bản mới nhất). Có thể giảm số bản tự giữ: thêm dòng `BACKUP_KEEP=7` vào `.env`, chạy lại `PA Worker.bat`.
2. Xóa các file `pa-worker-truoc-phuc-hoi-….pawbk` đã cũ (bản tự tạo trước mỗi lần phục hồi) sau khi chắc chắn không cần.
3. Dọn image và bộ nhớ đệm Docker cũ (sau mỗi lần cập nhật phiên bản sẽ có image cũ):
   ```
   docker image prune -a
   docker builder prune
   ```
   Hai lệnh này **không** đụng tới dữ liệu.
4. Dọn rác Windows: Settings → System → Storage → Temporary files.

**TUYỆT ĐỐI KHÔNG** chạy `docker volume prune`, `docker system prune --volumes`, `docker compose down -v`, hoặc xóa volume `pa_worker_pgdata` / `pa_worker_media` trong Docker Desktop: các lệnh này **xóa toàn bộ dữ liệu hồ sơ và tài liệu**.

Ổ đĩa vẫn không đủ: lắp ổ lớn hơn, hoặc nhờ đơn vị phát triển chuyển dữ liệu (sao lưu → cài lại trên ổ khác → phục hồi).

## Sao lưu hoặc phục hồi báo lỗi

| Thông báo | Cách xử lý |
| --- | --- |
| "Ổ đĩa chứa bản sao lưu còn trống …, cần khoảng …" | Giải phóng dung lượng (mục Đầy đĩa) rồi chạy lại `Sao luu.bat` |
| "Đang có một lượt sao lưu hoặc phục hồi khác chạy" | Sao lưu tự động đang chạy; chờ 1–2 phút rồi thử lại |
| "PA Worker chưa chạy" | Chạy `PA Worker.bat` trước |
| "Khóa FIELD_ENCRYPTION_KEY trong tệp .env không khớp với file sao lưu này" | File sao lưu được tạo bằng khóa khác: chép đúng tệp `.env` của bản cài đã tạo file đó (từ USB). Dữ liệu đang có không bị thay đổi |
| "File sao lưu bị hỏng hoặc đã bị sửa" / "bị thiếu phần cuối" | File bị hỏng khi chép; dùng bản sao lưu khác (bản trên ổ ngoài) |
| "Bản sao lưu được tạo từ phiên bản PA Worker … mới hơn" | Cài phiên bản PA Worker mới hơn trước rồi phục hồi |
| "Số dòng sau phục hồi không khớp bản sao lưu" | Không thay dữ liệu đang có; gửi thông báo này cho đơn vị phát triển |

Kiểm tra một file sao lưu mà không thay đổi gì:

```
docker compose exec web python manage.py verify_backup pa-worker-20261124-173000.pawbk
```

## Nhận diện CCCD đọc sai

- Ảnh mờ, lóa, nghiêng, thiếu sáng: chụp lại trên nền tối, đủ sáng, không đèn flash, ảnh rộng tối thiểu 1000 điểm ảnh; dùng **Xoay ảnh** nếu ảnh bị xoay.
- Mã QR của thẻ thật đọc ra sai thứ tự trường (ví dụ họ tên nằm ở ô ngày sinh): Admin vào **Cài đặt → OCR và QR**, sửa thứ tự trường của mẫu thẻ đó, lưu; thử lại. Không cần sửa phần mềm.
- Máy luôn tô vàng trường không chắc chắn; HR phải đối chiếu với ảnh trước khi tích **Đã kiểm tra**. Không lưu khi chưa kiểm tra.

## Trang báo "Hệ thống gặp lỗi"

Trang này (lỗi 500) nghĩa là có lỗi bất ngờ trong phần mềm. Thao tác đang làm thường chưa được lưu; mở lại hồ sơ để kiểm tra trước khi làm lại.
1. Ghi lại **thời điểm** xảy ra lỗi và thao tác đang làm.
2. Lấy nhật ký hệ thống (không chứa số CCCD, số điện thoại; dãy số dài đã được che):
   ```
   docker compose logs --since 30m web > loi-pa-worker.txt
   ```
3. Gửi tệp `loi-pa-worker.txt` và mô tả cho đơn vị phát triển. **Không** gửi tệp `.env`, file sao lưu hay ảnh CCCD.

## Khi cần gọi đơn vị phát triển

Chuẩn bị: phiên bản (chân trang, ví dụ "PA Worker v1.1.0"), kết quả `Kiem tra.bat`, thời điểm và mô tả lỗi, tệp nhật ký ở mục trên. Không gửi mật khẩu, tệp `.env`, file sao lưu hay dữ liệu cá nhân qua tin nhắn hoặc email.
