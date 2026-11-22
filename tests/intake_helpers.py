"""Hàm dùng chung cho test nhập từ CCCD/CV. Chỉ dùng ảnh và dữ liệu giả của tests/fixtures."""

import json
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile

from apps.intake import services

FIXTURES = Path(__file__).parent / "fixtures"
CARDS = FIXTURES / "cccd"
CV_DIR = FIXTURES / "cv"
TRUTH = json.loads((CARDS / "truth.json").read_text(encoding="utf-8"))["cards"]
PHONE = "0900000001"


def card(card_id):
    return next(c for c in TRUTH if c["id"] == card_id)


def card_bytes(card_id, side="front"):
    return (CARDS / card(card_id)["files"][side]).read_bytes()


def card_upload(card_id, side="front"):
    name = card(card_id)["files"][side]
    return SimpleUploadedFile(name, (CARDS / name).read_bytes(), content_type="image/png")


def cv_upload(name="cv-mau.docx"):
    return SimpleUploadedFile(name, (CV_DIR / name).read_bytes())


def make_session(user, card_id=None, sides=("front", "back"), cv=None, doc_type="", request=None):
    files = {}
    if card_id:
        if "front" in sides:
            files["front"] = card_upload(card_id, "front")
        if "back" in sides:
            files["back"] = card_upload(card_id, "back")
    return services.create_session(user, cv=cv, doc_type=doc_type, request=request, **files)


def low_fields(session):
    initial, meta, low = services.review_initial(session)
    return low


def _display(value):
    return value.strftime("%d/%m/%Y") if hasattr(value, "strftime") else value


def review_data(session, tick=True, **overrides):
    """Dữ liệu POST của màn hình đối chiếu, dựng từ kết quả nhận diện. `tick`: tích Đã kiểm tra
    cho mọi trường tô vàng. Giá trị None trong `overrides` nghĩa là bỏ khóa đó."""
    initial, _meta, low = services.review_initial(session)
    data = {name: _display(value) for name, value in initial.items()}
    data.setdefault("full_name", "")
    data.update({"phone": PHONE})
    for prefix in ("contacts", "edu", "exp", "cert"):
        data[f"{prefix}-TOTAL_FORMS"] = "1"
        data[f"{prefix}-INITIAL_FORMS"] = "0"
    if tick:
        data.update({f"{name}__checked": "on" for name in low})
    data.update(overrides)
    return {k: v for k, v in data.items() if v is not None}
