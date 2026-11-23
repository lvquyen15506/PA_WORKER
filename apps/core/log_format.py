"""Định dạng log ra stdout của container (docs/ra-soat-bao-mat.md mục 6).

Log không được chứa dữ liệu cá nhân. Thông điệp của ứng dụng chỉ dùng pk và mã hồ sơ, nhưng
thông báo lỗi của thư viện (ví dụ lỗi ràng buộc CSDL) có thể kèm giá trị; bộ định dạng che mọi
dãy từ 9 chữ số liền nhau trở lên (số CCCD 12 số, CMND 9 số, số điện thoại 10 số).
"""

import logging
import re

DIGITS = re.compile(r"\d{9,}")
MASK = "[số đã che]"


def redact(text):
    return DIGITS.sub(MASK, text)


class RedactingFormatter(logging.Formatter):
    """Che dãy số dài trong cả thông điệp và traceback."""

    def format(self, record):
        return redact(super().format(record))
