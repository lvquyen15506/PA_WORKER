"""Xử lý chữ tiếng Việt dùng chung."""

import re
import unicodedata

MASK_CHAR = "•"


def mask_id_number(value):
    """Che số định danh (lam-ro-yeu-cau.md câu 1): giữ n//3 chữ số đầu và cuối, còn lại là "•".
    Số 12 chữ số: 4 đầu + 4 dấu + 4 cuối (0791••••2345). Số CMND 9 chữ số: 3 + 3 + 3.
    Rỗng thì trả chuỗi rỗng. Dùng chung cho màn hình, file Excel và bản in."""
    digits = re.sub(r"\D", "", value or "")
    if not digits:
        return ""
    keep = len(digits) // 3
    if keep == 0:
        return MASK_CHAR * len(digits)
    return digits[:keep] + MASK_CHAR * (len(digits) - 2 * keep) + digits[-keep:]


def compute_name_search(text):
    """Họ tên không dấu, chữ thường, gộp khoảng trắng (đ -> d). Dùng cho Worker.name_search.

    Hàm duy nhất tính giá trị này: Worker.save() và seed_demo đều gọi nó.
    """
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D").lower()
    return re.sub(r"\s+", " ", text).strip()
