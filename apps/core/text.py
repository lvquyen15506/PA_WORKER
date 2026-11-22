"""Xử lý chữ tiếng Việt dùng chung."""

import re
import unicodedata


def compute_name_search(text):
    """Họ tên không dấu, chữ thường, gộp khoảng trắng (đ -> d). Dùng cho Worker.name_search.

    Hàm duy nhất tính giá trị này: Worker.save() và seed_demo đều gọi nó.
    """
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.replace("đ", "d").replace("Đ", "D").lower()
    return re.sub(r"\s+", " ", text).strip()
