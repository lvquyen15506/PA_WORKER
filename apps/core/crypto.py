"""Mã hóa trường nhạy cảm (Fernet) và băm kiểm tra trùng (HMAC-SHA256).

- EncryptedTextField: lưu dạng mã hóa, đọc ra tự giải mã. Khóa: FIELD_ENCRYPTION_KEY.
- hmac_hash / compute_id_hash: băm có khóa HASH_KEY (khác khóa mã hóa) để tìm trùng.
"""

import hashlib
import hmac
import re
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models

from .keys import MSG_MISMATCH_FIELD, KeyConfigError, decode_key


@lru_cache(maxsize=4)
def _fernet_for(key):
    return Fernet(key.encode("ascii"))


def get_fernet():
    return _fernet_for(settings.FIELD_ENCRYPTION_KEY.strip())


def encrypt_value(text):
    """Mã hóa chuỗi; None giữ None."""
    if text is None:
        return None
    return get_fernet().encrypt(str(text).encode("utf-8")).decode("ascii")


def decrypt_value(token):
    """Giải mã; sai khóa hoặc dữ liệu hỏng thì báo KeyConfigError (tiếng Việt)."""
    if token is None:
        return None
    try:
        return get_fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError) as exc:
        raise KeyConfigError(MSG_MISMATCH_FIELD) from exc


class EncryptedTextField(models.TextField):
    """TextField tự mã hóa khi ghi, tự giải mã khi đọc. NULL giữ NULL.

    Không tìm kiếm theo trường này (Fernet không xác định); dùng cột *_hash để tìm trùng.
    """

    description = "Chuỗi mã hóa Fernet"

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        return encrypt_value(value)

    def from_db_value(self, value, expression, connection):
        return decrypt_value(value)


def hmac_hash(text):
    """HMAC-SHA256 (hex) của chuỗi bằng HASH_KEY."""
    key = decode_key(settings.HASH_KEY)
    return hmac.new(key, text.encode("utf-8"), hashlib.sha256).hexdigest()


def normalize_id_number(value):
    """Chuẩn hóa số định danh: bỏ khoảng trắng, dấu chấm, gạch ngang, chỉ giữ chữ số."""
    return re.sub(r"\D", "", value or "")


def compute_id_hash(value):
    """Băm số định danh đã chuẩn hóa; rỗng thì None. Dùng chung cho save() và seed."""
    normalized = normalize_id_number(value)
    return hmac_hash(normalized) if normalized else None
