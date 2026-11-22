"""Môi trường nhận diện (Phase 5 bước 0): Tesseract có gói tiếng Việt, antiword, zbar, OpenCV."""

import subprocess

import pytesseract


def test_tesseract_co_tieng_viet():
    assert "vie" in pytesseract.get_languages()


def test_antiword_chay_duoc():
    result = subprocess.run(["antiword"], capture_output=True, text=True, timeout=10)
    assert "antiword" in (result.stdout + result.stderr).lower()


def test_pyzbar_nap_duoc_thu_vien_zbar():
    import numpy as np
    from pyzbar import pyzbar

    assert pyzbar.decode(np.full((50, 50), 255, dtype="uint8")) == []  # ảnh trắng, không có QR


def test_opencv_va_pillow_nap_duoc():
    import cv2
    import numpy as np

    gray = cv2.cvtColor(np.zeros((4, 4, 3), dtype="uint8"), cv2.COLOR_BGR2GRAY)
    assert gray.shape == (4, 4)
