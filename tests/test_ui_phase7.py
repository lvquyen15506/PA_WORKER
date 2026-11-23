"""Phase 7: bổ sung /ui-kit/ (cột `check`, `link` của _table; biểu đồ nhiều chuỗi, cột ngang)."""

import json
import re
from pathlib import Path

import pytest
from django.template.loader import render_to_string
from django.test import Client

from tests.factories import PASSWORD, make_user

pytestmark = pytest.mark.django_db
ROOT = Path(__file__).resolve().parent.parent


def table(columns, rows):
    return render_to_string("components/_table.html", {"columns": columns, "rows": rows})


def test_table_cot_check_gan_form_ngoai_va_khoa_dong():
    html = table(
        [{"key": "pick", "label": "Chọn", "kind": "check", "name": "ids", "form": "f-chon"}],
        [{"pick": 7}, {"pick": 8, "disabled": True}],
    )
    assert html.count('type="checkbox"') == 2
    assert 'name="ids" value="7" form="f-chon"' in html
    assert re.search(r'value="8" form="f-chon"[^>]* disabled', html)
    assert not re.search(r'value="7" form="f-chon"[^>]* disabled', html)


def test_table_cot_link_so_lieu_bam_duoc_va_so_0_khong_thanh_gach():
    html = table(
        [{"key": "n", "label": "Số công nhân", "kind": "link", "num": True}],
        [{"n": {"text": 12, "url": "/ho-so/?cong_ty_khach=3"}}, {"n": {"text": 0}}, {"n": {}}],
    )
    assert '<a href="/ho-so/?cong_ty_khach=3">12</a>' in html
    cells = re.findall(r"<td[^>]*>\s*(.*?)\s*</td>", html, flags=re.S)
    assert cells == ['<a href="/ho-so/?cong_ty_khach=3">12</a>', "0", "—"]
    assert html.count("is-num") == 4  # tiêu đề + 3 ô: căn phải


def test_table_so_0_o_cot_thuong_hien_0_chu_khong_gach():
    html = table([{"key": "n", "label": "Số", "kind": "num"}], [{"n": 0}, {"n": None}])
    cells = re.findall(r"<td[^>]*>\s*(.*?)\s*</td>", html, flags=re.S)
    assert cells == ["0", "—"]


def test_ui_kit_co_cac_thanh_phan_moi_va_du_lieu_bieu_do_hop_le():
    client = Client()
    client.post("/dang-nhap/", {"username": make_user("ADMIN").username, "password": PASSWORD})
    body = client.get("/ui-kit/").content.decode()
    assert 'id="form-demo-chon"' in body and 'form="form-demo-chon"' in body
    for chart_id in ("chart-group", "chart-horizontal"):
        assert f'data-pa-chart="{chart_id}"' in body
        data = json.loads(
            re.search(
                rf'<script id="{chart_id}" type="application/json">(.*?)</script>', body
            ).group(1)
        )
        assert data["unit"] and data["labels"]
    group = json.loads(
        re.search(r'<script id="chart-group" type="application/json">(.*?)</script>', body).group(1)
    )
    assert len(group["datasets"]) == 2
    assert all(len(d["values"]) == len(group["labels"]) for d in group["datasets"])


def test_pa_charts_js_ho_tro_nhieu_chuoi_cot_ngang_va_van_dung_token():
    js = (ROOT / "static/js/pa-charts.js").read_text(encoding="utf-8")
    assert "cfg.datasets" in js and "horizontal" in js and "indexAxis" in js
    assert "--pa-navy" in js and "--pa-blue" in js and "--pa-muted" in js
    assert "animation: false" in js
    assert not re.search(r"#[0-9a-fA-F]{3,6}\b", js)  # không viết mã màu cứng
