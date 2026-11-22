import re

import pytest
from django.conf import settings
from django.core.files.base import ContentFile

from apps.core.storage import PrivateStorage


def test_ten_ngau_nhien_giu_duoi_va_thu_muc():
    st = PrivateStorage()
    name = st.save("intake/abc/cccd-that-cua-toi.JPG", ContentFile(b"x"))
    assert re.fullmatch(r"intake/abc/[0-9a-f]{32}\.jpg", name.replace("\\", "/"))
    assert "cccd" not in name
    assert st.exists(name)


def test_hai_lan_luu_hai_ten_khac_nhau():
    st = PrivateStorage()
    a = st.save("a.pdf", ContentFile(b"1"))
    b = st.save("a.pdf", ContentFile(b"1"))
    assert a != b


def test_duoi_khong_hop_le_bi_bo():
    st = PrivateStorage()
    name = st.save("tep.exe-rat-dai-khong-hop-le", ContentFile(b"1"))
    assert re.fullmatch(r"[0-9a-f]{32}", name)


def test_khong_co_url_cong_khai():
    st = PrivateStorage()
    assert st.base_url is None
    with pytest.raises(ValueError, match="không có URL công khai"):
        st.url("a.pdf")


def test_nam_ngoai_static_root():
    st = PrivateStorage()
    assert st.location == str(settings.PRIVATE_MEDIA_ROOT)
    assert not str(settings.PRIVATE_MEDIA_ROOT).startswith(str(settings.STATIC_ROOT))
