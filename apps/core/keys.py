"""Kiểm tra khóa mã hóa và khóa băm (docs/thiet-ke/kien-truc.md mục 7, lam-ro-yeu-cau.md câu 31).

Thiếu khóa, sai định dạng, hoặc không khớp dữ liệu hiện có thì ứng dụng từ chối khởi động
với thông báo tiếng Việt. Module này chỉ chứa logic thuần; việc đọc/ghi giá trị kiểm tra
trong bảng Settings nằm ở lệnh check_keys (bước 3a).
"""

import base64
import binascii

from django.conf import settings

# Chuỗi cố định để kiểm tra khóa; lưu mã hóa (key_check_enc) và băm (key_check_hash).
KEY_CHECK_TEXT = "PA-WORKER-KEY-CHECK"


class KeyConfigError(Exception):
    """Cấu hình khóa sai; thông báo là tiếng Việt, hiển thị thẳng cho người cài đặt."""


MSG_MISSING_FIELD = (
    "Thiếu khóa mã hóa FIELD_ENCRYPTION_KEY trong tệp .env. "
    "Hãy chép lại khóa từ bản sao đã cất khi cài đặt. "
    "Ứng dụng không khởi động để tránh làm hỏng dữ liệu."
)
MSG_MISSING_HASH = (
    "Thiếu khóa băm HASH_KEY trong tệp .env. "
    "Hãy chép lại khóa từ bản sao đã cất khi cài đặt. "
    "Ứng dụng không khởi động để tránh làm hỏng dữ liệu."
)
MSG_BAD_FIELD = (
    "Khóa mã hóa FIELD_ENCRYPTION_KEY trong tệp .env sai định dạng "
    "(phải là 32 byte mã hóa base64). Hãy chép lại đúng khóa đã cất khi cài đặt. "
    "Ứng dụng không khởi động để tránh làm hỏng dữ liệu."
)
MSG_BAD_HASH = (
    "Khóa băm HASH_KEY trong tệp .env sai định dạng (tối thiểu 32 byte mã hóa base64). "
    "Hãy chép lại đúng khóa đã cất khi cài đặt. "
    "Ứng dụng không khởi động để tránh làm hỏng dữ liệu."
)
MSG_MISMATCH_FIELD = (
    "Khóa FIELD_ENCRYPTION_KEY không khớp với dữ liệu hiện có. "
    "Nếu chạy tiếp, số định danh và địa chỉ đã mã hóa sẽ không đọc được. "
    "Hãy dùng đúng khóa đã cất khi cài đặt. Ứng dụng không khởi động."
)
MSG_MISMATCH_HASH = (
    "Khóa HASH_KEY không khớp với dữ liệu hiện có. "
    "Nếu chạy tiếp, kiểm tra trùng số CCCD sẽ sai. "
    "Hãy dùng đúng khóa đã cất khi cài đặt. Ứng dụng không khởi động."
)


def decode_key(value):
    """Giải mã base64 url-safe (có hoặc thiếu dấu '='); trả bytes, hoặc None nếu sai."""
    try:
        return base64.urlsafe_b64decode(value.strip() + "=" * (-len(value.strip()) % 4))
    except (binascii.Error, ValueError, AttributeError):
        return None


def check_format():
    """Kiểm tra hai khóa có đủ và đúng định dạng; không cần CSDL."""
    field_key = getattr(settings, "FIELD_ENCRYPTION_KEY", "") or ""
    hash_key = getattr(settings, "HASH_KEY", "") or ""
    if not field_key.strip():
        raise KeyConfigError(MSG_MISSING_FIELD)
    if not hash_key.strip():
        raise KeyConfigError(MSG_MISSING_HASH)
    raw = decode_key(field_key)
    if raw is None or len(raw) != 32:
        raise KeyConfigError(MSG_BAD_FIELD)
    raw = decode_key(hash_key)
    if raw is None or len(raw) < 32:
        raise KeyConfigError(MSG_BAD_HASH)


def key_check_hash():
    """HMAC của chuỗi kiểm tra bằng HASH_KEY (ghi vào key_check_hash lần đầu)."""
    from .crypto import hmac_hash

    return hmac_hash(KEY_CHECK_TEXT)


def verify_key_check(decrypted_text, stored_hash):
    """So khớp giá trị đã lưu với hai khóa hiện tại. Hai khóa được kiểm tra độc lập.

    decrypted_text: nội dung key_check_enc sau giải mã (hoặc None nếu giải mã thất bại).
    stored_hash: key_check_hash đã lưu.
    """
    import hmac

    if decrypted_text != KEY_CHECK_TEXT:
        raise KeyConfigError(MSG_MISMATCH_FIELD)
    if not hmac.compare_digest(str(stored_hash or ""), key_check_hash()):
        raise KeyConfigError(MSG_MISMATCH_HASH)
