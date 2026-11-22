"""Mở ảnh an toàn, kiểm tra chất lượng, xóa EXIF (Phase 5 bước 2, quyết định 6, 7)."""

import io
import json
import struct
import zlib
from pathlib import Path

import pytest
from PIL import Image

from apps.intake import imaging
from apps.intake.imaging import ImageRejected, check_quality, load_image, strip_metadata

CARDS = Path(__file__).parent / "fixtures" / "cccd"
TRUTH = json.loads((CARDS / "truth.json").read_text(encoding="utf-8"))["cards"]


def card_image(card_id, side="front"):
    card = next(c for c in TRUTH if c["id"] == card_id)
    return load_image((CARDS / card["files"][side]).read_bytes())


def png_bytes(width, height):
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def forge_png_size(data, width, height):
    """Sửa kích thước khai báo trong header PNG (IHDR), giữ nguyên phần còn lại và CRC hợp lệ."""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    chunk = b"IHDR" + ihdr
    new = struct.pack(">I", len(ihdr)) + chunk + struct.pack(">I", zlib.crc32(chunk))
    return data[:8] + new + data[8 + 4 + 4 + 13 + 4 :]


# ----- chất lượng -----


def test_anh_tot_khong_canh_bao():
    for card_id in ("01", "07", "12"):
        for side in ("front", "back"):
            assert check_quality(card_image(card_id, side)).warnings == []


def test_anh_hep_bi_canh_bao_do_phan_giai():
    report = check_quality(card_image("06"))
    assert report.width == 800
    assert imaging.WARN_LOW_RES in report.warnings


def test_anh_toi_bi_canh_bao():
    assert imaging.WARN_DARK in check_quality(card_image("14")).warnings


def test_anh_mo_bi_canh_bao():
    assert imaging.WARN_BLUR in check_quality(card_image("15")).warnings


def test_anh_chay_sang_bi_canh_bao():
    assert imaging.WARN_BRIGHT in check_quality(Image.new("RGB", (1200, 800), "white")).warnings


def test_bao_cao_chat_luong_la_json_duoc():
    report = check_quality(card_image("01")).as_dict()
    assert set(report) == {"width", "height", "sharpness", "brightness", "warnings"}
    json.dumps(report)


# ----- giới hạn điểm ảnh, không giải nén ảnh khổng lồ -----


def test_anh_khai_bao_kich_thuoc_khong_lo_bi_tu_choi_truoc_khi_giai_nen():
    data = forge_png_size(png_bytes(10, 10), 50_000, 50_000)
    with pytest.raises(ImageRejected) as exc:
        load_image(data)
    assert str(exc.value) == imaging.MSG_TOO_LARGE
    assert "40 triệu" in str(exc.value)


def test_gioi_han_diem_anh_dung_bien(settings):
    settings.MAX_IMAGE_PIXELS = 100 * 100
    assert load_image(png_bytes(100, 100)).size == (100, 100)
    with pytest.raises(ImageRejected):
        load_image(png_bytes(101, 100))


def test_gioi_han_mac_dinh_la_40_trieu():
    from django.conf import settings

    assert settings.MAX_IMAGE_PIXELS == 40_000_000


def test_khong_phai_anh_hoac_anh_hong():
    for data in (b"khong phai anh", png_bytes(20, 20)[:40]):
        with pytest.raises(ImageRejected) as exc:
            load_image(data)
        assert str(exc.value) == imaging.MSG_CANNOT_OPEN


# ----- xóa EXIF -----


def jpeg_with_exif():
    image = Image.new("RGB", (200, 100), "white")
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation: xoay 90 độ
    exif[0x010F] = "MayAnhGia"
    exif.get_ifd(0x8825)[1] = "N"  # GPS
    exif.get_ifd(0x8825)[2] = (10.0, 0.0, 0.0)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


def test_du_lieu_thu_co_exif_va_gps():
    exif = Image.open(io.BytesIO(jpeg_with_exif())).getexif()
    assert exif.get(0x010F) == "MayAnhGia" and exif.get_ifd(0x8825)


def test_xoa_exif_sau_khi_xoay_theo_exif():
    image = load_image(jpeg_with_exif())
    assert image.size == (100, 200)  # đã xoay theo Orientation
    cleaned = Image.open(io.BytesIO(strip_metadata(image, "JPG")))
    assert cleaned.size == (100, 200)
    assert len(cleaned.getexif()) == 0
    assert "exif" not in cleaned.info and "icc_profile" not in cleaned.info


def test_xoa_metadata_png():
    buffer = io.BytesIO()
    from PIL.PngImagePlugin import PngInfo

    info = PngInfo()
    info.add_text("Author", "NguoiGia")
    Image.new("RGB", (50, 50), "white").save(buffer, format="PNG", pnginfo=info)
    image = load_image(buffer.getvalue())
    cleaned = Image.open(io.BytesIO(strip_metadata(image, "PNG")))
    assert cleaned.format == "PNG" and "Author" not in cleaned.info and not cleaned.text


def test_xoay_anh_90_do():
    image = Image.new("RGB", (200, 100), "white")
    assert imaging.rotate(image).size == (100, 200)
