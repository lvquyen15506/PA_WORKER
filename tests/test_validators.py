from datetime import date

import pytest
from django.core.exceptions import ValidationError

from apps.core import validators as v


def test_so_dinh_danh():
    v.validate_id_number("999000000001")
    for bad in ("99900000000", "9990000000011", "99900000000a", ""):
        with pytest.raises(ValidationError, match="12 chữ số"):
            v.validate_id_number(bad)


def test_so_dien_thoai():
    v.validate_phone("0912345678")
    for bad in ("912345678", "09123456789", "1912345678", "09123abc78"):
        with pytest.raises(ValidationError, match="10 chữ số"):
            v.validate_phone(bad)


def test_tuoi_theo_cau_16():
    today = date(2026, 11, 22)
    assert v.check_age(None, today) is None
    assert v.check_age(date(2012, 1, 1), today) == "block"
    assert v.check_age(date(2011, 11, 23), today) == "block"  # 14 tuổi, chưa đến sinh nhật
    assert v.check_age(date(2011, 11, 22), today) == "warn"  # đúng 15 tuổi
    assert v.check_age(date(2008, 11, 23), today) == "warn"  # 17 tuổi
    assert v.check_age(date(2008, 11, 22), today) is None  # đúng 18 tuổi
