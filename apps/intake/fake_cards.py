"""Sinh bộ ảnh CCCD giả và CV giả để test, demo và đo độ chính xác (docs/yeu-cau.md mục V).

Mọi dữ liệu là hư cấu: số CCCD bắt đầu `999`, tên ghép từ họ/tên đệm/tên giả, địa chỉ là địa danh
hư cấu. Bố cục là bản vẽ giản lược (chỉ có chữ), KHÔNG có quốc huy hay họa tiết của thẻ thật; mọi
mặt thẻ đều có dòng "MẪU – KHÔNG CÓ GIÁ TRỊ". QR sinh đúng theo `QrFormat` được truyền vào
(thường là cấu hình đang dùng trong CSDL, câu 20), nên bộ ảnh chỉ chứng minh bộ tách khớp cấu
hình, chưa chứng minh khớp thẻ thật.
"""

import datetime
import io
import json
import os
import random

import segno
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from apps.core.choices import Gender, IdDocType

from .fields import DATE_FIELDS, DATE_FORMATS, FIELD_NAMES, SKIP

WATERMARK = "MẪU – KHÔNG CÓ GIÁ TRỊ"
FONT_DIRS = ("/usr/share/fonts/truetype/dejavu", "C:/Windows/Fonts")
FONT_REGULAR = ("DejaVuSans.ttf", "arial.ttf")
FONT_BOLD = ("DejaVuSans-Bold.ttf", "arialbd.ttf")

CARD_W, CARD_H = 1400, 880
LOW_RES_W = 800
QR_SCALE = 7

FAMILY = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Vũ", "Đặng", "Bùi", "Đỗ", "Ngô"]
MIDDLE = ["Văn", "Thị", "Minh", "Quốc", "Hữu", "Ngọc", "Thanh", "Đức", "Anh", "Gia"]
GIVEN = ["Mẫu", "Thử", "Giả", "Kiểm", "Demo", "Nghiệm", "Lập", "Tạo", "Dựng", "Mô"]
PLACES = ["Thôn Mẫu", "Xã Thử Nghiệm", "Huyện Giả Lập", "Phường Demo", "Quận Kiểm Tra"]

# Thứ tự và chất lượng 15 thẻ: (mẫu thẻ, chất lượng ảnh). Ảnh kém chỉ ở thẻ không có QR hoặc chỉ
# giảm độ phân giải, để QR vẫn đọc được và kịch bản 3 (đúng 100% trường QR) đo được.
PLAN = (
    [(IdDocType.CCCD_2021.value, "good")] * 5
    + [(IdDocType.CCCD_2021.value, "low_res")]
    + [(IdDocType.CAN_CUOC_2024.value, "good")] * 5
    + [
        (IdDocType.CCCD_2016.value, "good"),
        (IdDocType.CCCD_2016.value, "good"),
        (IdDocType.CCCD_2016.value, "dark"),
        (IdDocType.CCCD_2016.value, "blur"),
    ]
)

_TITLES = {
    IdDocType.CCCD_2021.value: "CĂN CƯỚC CÔNG DÂN",
    IdDocType.CCCD_2016.value: "CĂN CƯỚC CÔNG DÂN",
    IdDocType.CAN_CUOC_2024.value: "CĂN CƯỚC",
}

# Dòng in trên mỗi mặt: (nhãn in trên thẻ, tên trường). Tên trường khớp apps.intake.fields.
_SIDES = {
    IdDocType.CCCD_2021.value: {
        "front": [
            ("Số", "id_number"),
            ("Họ và tên", "full_name"),
            ("Ngày sinh", "date_of_birth"),
            ("Giới tính", "gender"),
            ("Quốc tịch", "nationality"),
            ("Quê quán", "hometown"),
            ("Nơi thường trú", "permanent_address"),
            ("Có giá trị đến", "expiry_date"),
        ],
        "back": [("Ngày cấp", "issue_date"), ("Nơi cấp", "issue_place")],
        "qr_side": "front",
    },
    IdDocType.CAN_CUOC_2024.value: {
        "front": [
            ("Số định danh", "id_number"),
            ("Họ và tên", "full_name"),
            ("Ngày sinh", "date_of_birth"),
            ("Giới tính", "gender"),
            ("Quốc tịch", "nationality"),
        ],
        "back": [
            ("Nơi cư trú", "permanent_address"),
            ("Nơi đăng ký khai sinh", "birth_registration_place"),
            ("Ngày cấp", "issue_date"),
            ("Ngày hết hạn", "expiry_date"),
        ],
        "qr_side": "back",
    },
    IdDocType.CCCD_2016.value: {
        "front": [
            ("Số", "id_number"),
            ("Họ và tên", "full_name"),
            ("Ngày sinh", "date_of_birth"),
            ("Giới tính", "gender"),
            ("Quốc tịch", "nationality"),
            ("Quê quán", "hometown"),
            ("Nơi thường trú", "permanent_address"),
            ("Có giá trị đến", "expiry_date"),
        ],
        "back": [("Ngày cấp", "issue_date"), ("Nơi cấp", "issue_place")],
        "qr_side": None,
    },
}

GENDER_TEXT = {Gender.MALE.value: "Nam", Gender.FEMALE.value: "Nữ"}


def _font(names, size):
    for folder in FONT_DIRS:
        for name in names:
            path = os.path.join(folder, name)
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
    raise RuntimeError("Không tìm thấy phông DejaVu/Arial có dấu tiếng Việt để vẽ ảnh giả.")


def font_path(names=FONT_REGULAR):
    for folder in FONT_DIRS:
        for name in names:
            path = os.path.join(folder, name)
            if os.path.exists(path):
                return path
    raise RuntimeError("Không tìm thấy phông DejaVu/Arial có dấu tiếng Việt.")


def _make_values(rng, number, doc_type):
    """Dữ liệu hư cấu đã chuẩn hóa (ngày ISO, giới tính MALE/FEMALE)."""
    gender = rng.choice([Gender.MALE.value, Gender.FEMALE.value])
    middle = "Văn" if gender == Gender.MALE.value else "Thị"
    name = f"{rng.choice(FAMILY)} {middle} {rng.choice(GIVEN)}"
    birth = datetime.date(rng.randint(1985, 2004), rng.randint(1, 12), rng.randint(1, 28))
    issue = datetime.date(rng.randint(2021, 2025), rng.randint(1, 12), rng.randint(1, 28))
    expiry = datetime.date(issue.year + rng.choice([10, 15]), issue.month, issue.day)
    place = f"{rng.choice(PLACES)} {number}"
    return {
        "id_number": f"999{number:09d}",
        "old_id_number": f"999{rng.randint(0, 999999):06d}" if rng.random() < 0.5 else None,
        "full_name": name.upper(),
        "date_of_birth": birth.isoformat(),
        "gender": gender,
        "nationality": "Việt Nam",
        "hometown": f"{rng.choice(PLACES)} {number}, Tỉnh Demo",
        "permanent_address": f"Số {number} Đường Mẫu, {place}",
        "birth_registration_place": f"{rng.choice(PLACES)} {number}, Tỉnh Demo",
        "issue_date": issue.isoformat(),
        "issue_place": "Cục Mẫu Thử Nghiệm",
        "expiry_date": expiry.isoformat(),
    }


def _display(name, value):
    """Giá trị hiển thị trên thẻ: ngày dd/mm/yyyy, giới tính Nam/Nữ."""
    if name in DATE_FIELDS:
        return datetime.date.fromisoformat(value).strftime("%d/%m/%Y")
    if name == "gender":
        return GENDER_TEXT[value]
    return value


def build_qr_payload(values, qr_format):
    """Chuỗi QR theo cấu hình: mỗi phần tử của field_order là giá trị tương ứng (rỗng nếu không
    có). Trả (chuỗi, danh sách trường thực sự có trong QR)."""
    pattern = DATE_FORMATS[qr_format.date_format]
    parts, present = [], []
    for name in qr_format.field_order:
        value = values.get(name) if name != SKIP and name in FIELD_NAMES else None
        if not value:
            parts.append("")
            continue
        if name in DATE_FIELDS:
            parts.append(datetime.date.fromisoformat(value).strftime(pattern))
        elif name == "gender":
            parts.append(GENDER_TEXT[value])
        else:
            parts.append(value)
        present.append(name)
    return qr_format.separator.join(parts), present


def _qr_image(payload):
    buffer = io.BytesIO()
    segno.make(payload, error="m", encoding="utf-8").save(
        buffer, kind="png", scale=QR_SCALE, border=3
    )
    buffer.seek(0)
    return Image.open(buffer).convert("L")


def _draw_side(doc_type, side, values, qr_payload):
    image = Image.new("RGB", (CARD_W, CARD_H), "white")
    draw = ImageDraw.Draw(image)
    bold, regular, small = _font(FONT_BOLD, 38), _font(FONT_REGULAR, 31), _font(FONT_REGULAR, 26)
    draw.text((60, 36), "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", font=bold, fill="black")
    title = _TITLES[doc_type] if side == "front" else f"{_TITLES[doc_type]} (mặt sau)"
    draw.text((60, 92), title, font=bold, fill="black")
    layout = _SIDES[doc_type]
    y = 190
    for label, name in layout[side]:
        draw.text((60, y), f"{label}: {_display(name, values[name])}", font=regular, fill="black")
        y += 58
    if qr_payload and layout["qr_side"] == side:
        qr = _qr_image(qr_payload)
        image.paste(qr, (CARD_W - qr.width - 50, 170))
    draw.text((60, CARD_H - 70), WATERMARK, font=small, fill=(150, 150, 150))
    return image


def _degrade(image, quality):
    if quality == "low_res":
        height = round(image.height * LOW_RES_W / image.width)
        return image.resize((LOW_RES_W, height), Image.LANCZOS)
    if quality == "blur":
        return image.filter(ImageFilter.GaussianBlur(radius=3.5))
    if quality == "dark":
        return ImageEnhance.Brightness(image).enhance(0.12)
    return image


def generate_cards(out_dir, qr_formats, seed=2026):
    """Sinh 15 thẻ × 2 mặt vào `out_dir`, kèm truth.json. `qr_formats`: {mã mẫu thẻ: QrFormat}.
    Trả danh sách mô tả thẻ."""
    rng = random.Random(seed)
    os.makedirs(out_dir, exist_ok=True)
    cards = []
    for index, (doc_type, quality) in enumerate(PLAN, start=1):
        values = _make_values(rng, index, doc_type)
        layout = _SIDES[doc_type]
        qr_payload, qr_fields = None, []
        if layout["qr_side"]:
            qr_payload, qr_fields = build_qr_payload(values, qr_formats[doc_type])
        printed = [name for side in ("front", "back") for _, name in layout[side]]
        files = {}
        for side, suffix in (("front", "truoc"), ("back", "sau")):
            name = f"{index:02d}-{doc_type.lower()}-{suffix}.png"
            image = _degrade(_draw_side(doc_type, side, values, qr_payload), quality)
            image.save(os.path.join(out_dir, name))
            files[side] = name
        cards.append(
            {
                "id": f"{index:02d}",
                "doc_type": doc_type,
                "quality": quality,
                "files": files,
                "values": values,
                "printed": printed,
                "qr_fields": qr_fields,
                "has_qr": bool(layout["qr_side"]),
                "qr_side": layout["qr_side"],
            }
        )
    with open(os.path.join(out_dir, "truth.json"), "w", encoding="utf-8") as handle:
        json.dump({"watermark": WATERMARK, "cards": cards}, handle, ensure_ascii=False, indent=1)
    return cards


# ----- CV giả -----

CV_TEXT = {
    "name": "NGUYỄN VĂN MẪU",
    "phone": "0999000111",
    "email": "mau.thu@example.com",
    "education": "Trung học phổ thông Thử Nghiệm, 2010 - 2013",
    "experience": "Công ty Giả Lập, Công nhân may, 03/2016 - 06/2020",
    "skills": "Vận hành máy may công nghiệp, kiểm tra chất lượng",
    "certificate": "Chứng chỉ an toàn lao động, Trung tâm Mẫu, 2019",
}


def cv_lines():
    c = CV_TEXT
    return [
        ("title", c["name"]),
        ("text", f"Điện thoại: {c['phone']}"),
        ("text", f"Email: {c['email']}"),
        ("heading", "Học vấn"),
        ("text", c["education"]),
        ("heading", "Kinh nghiệm làm việc"),
        ("text", c["experience"]),
        ("heading", "Kỹ năng"),
        ("text", c["skills"]),
        ("heading", "Chứng chỉ"),
        ("text", c["certificate"]),
    ]


def write_cv_docx(path):
    import docx

    document = docx.Document()
    for kind, text in cv_lines():
        if kind == "title":
            document.add_heading(text, level=0)
        elif kind == "heading":
            document.add_heading(text, level=1)
        else:
            document.add_paragraph(text)
    document.save(path)


def write_cv_pdf(path):
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("Dejavu", "", font_path(FONT_REGULAR))
    pdf.add_font("Dejavu", "B", font_path(FONT_BOLD))
    for kind, text in cv_lines():
        pdf.set_font("Dejavu", "B" if kind != "text" else "", 16 if kind == "title" else 12)
        pdf.cell(0, 9, text, new_x="LMARGIN", new_y="NEXT")
    pdf.output(path)


def write_cv_image(path):
    """CV dạng ảnh (chụp/scan) để thử OCR."""
    image = Image.new("RGB", (1240, 1000), "white")
    draw = ImageDraw.Draw(image)
    y = 40
    for kind, text in cv_lines():
        size = 40 if kind == "title" else 32
        draw.text(
            (60, y),
            text,
            font=_font(FONT_BOLD if kind != "text" else FONT_REGULAR, size),
            fill="black",
        )
        y += 70 if kind != "text" else 56
    image.save(path)
