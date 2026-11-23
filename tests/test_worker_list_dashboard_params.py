"""Tham số lọc của /ho-so/ dành cho liên kết thẻ Dashboard (trang.md 5.3, Phase 7)."""

import datetime
import re

import pytest
from django.utils import timezone

from apps.core.choices import IdDocType
from apps.core.choices import VerificationStatus as VS
from apps.core.models import Department, Position, Section
from apps.employment.models import Employment
from apps.workers.listing import WorkerFilterForm, build_queryset
from apps.workers.models import IdentityDocument, Worker
from tests.factories import login_client, make_user, make_worker_full, make_worker_in_status

pytestmark = pytest.mark.django_db
D = datetime.date


def page(query="", role="HR_STAFF"):
    client = login_client(make_user(role))
    response = client.get("/ho-so/" + query)
    assert response.status_code == 200
    return response.content.decode()


def total(content):
    """Số hồ sơ theo dòng phân trang "Hiển thị a–b / n"."""
    match = re.search(r"Hiển thị[^/]*/\s*(\d+)", content)
    return int(match.group(1)) if match else 0


def employ(worker, work_status="ACTIVE", **kw):
    dep = Department.objects.get_or_create(name="PB")[0]
    section = Section.objects.get_or_create(department=dep, name="BP")[0]
    position = Position.objects.get_or_create(name="CD")[0]
    return Employment.objects.create(
        worker=worker,
        received_date=D(2026, 1, 1),
        start_date=D(2026, 1, 2),
        section=section,
        position=position,
        work_status=work_status,
        **kw,
    )


def ids(**params):
    form = WorkerFilterForm(params)
    form.is_valid()
    qs = build_queryset(make_user("HR_STAFF"), dict(form.cleaned_data))
    return set(qs.values_list("pk", flat=True))


def test_chua_luu_tru_loai_ho_so_luu_tru_va_giu_cac_trang_thai_khac():
    draft = make_worker_full(full_name="Một")
    verified = make_worker_in_status(VS.VERIFIED)
    archived = make_worker_in_status(VS.ARCHIVED)
    assert ids(trang_thai_ho_so="chua-luu-tru") == {draft.pk, verified.pk}
    assert ids(trang_thai_ho_so="ARCHIVED") == {archived.pk}
    assert total(page("?trang_thai_ho_so=chua-luu-tru")) == 2


def test_trang_thai_lam_viec_nhan_danh_sach_cach_nhau_dau_phay():
    probation = make_worker_full(full_name="Thử")
    employ(probation, "PROBATION")
    active = make_worker_full(full_name="Làm")
    employ(active, "ACTIVE")
    resigned = make_worker_full(full_name="Nghỉ")
    employ(resigned, "RESIGNED", resign_date=D(2026, 3, 1))
    assert ids(trang_thai_lam_viec="PROBATION,ACTIVE") == {probation.pk, active.pk}
    assert ids(trang_thai_lam_viec="RESIGNED") == {resigned.pk}
    assert ids(trang_thai_lam_viec=" ACTIVE , RESIGNED ") == {active.pk, resigned.pk}
    # Mã sai bị bỏ; toàn mã sai = không lọc (không văng lỗi).
    assert ids(trang_thai_lam_viec="ACTIVE,XYZ") == {active.pk}
    assert ids(trang_thai_lam_viec="XYZ") == {probation.pk, active.pk, resigned.pk}


def test_o_chon_trang_thai_lam_viec_hien_dung_lua_chon_gop():
    employ(make_worker_full(full_name="Làm"), "ACTIVE")
    content = page("?trang_thai_lam_viec=PROBATION,ACTIVE")
    assert 'value="PROBATION,ACTIVE" selected' in content
    assert "Thử việc + Đang làm việc" in content


def test_loc_ngay_tao_ho_so_theo_gio_viet_nam_ca_hai_dau_mut():
    inside = make_worker_full(full_name="Trong")
    before = make_worker_full(full_name="Trước")
    after = make_worker_full(full_name="Sau")
    zone = timezone.get_current_timezone()
    # 23:30 ngày 31/10 và 00:00 ngày 01/12 giờ VN nằm NGOÀI tháng 11; 23:59 ngày 30/11 nằm TRONG.
    Worker.objects.filter(pk=before.pk).update(
        created_at=datetime.datetime(2026, 10, 31, 23, 30, tzinfo=zone)
    )
    Worker.objects.filter(pk=after.pk).update(
        created_at=datetime.datetime(2026, 12, 1, 0, 0, tzinfo=zone)
    )
    Worker.objects.filter(pk=inside.pk).update(
        created_at=datetime.datetime(2026, 11, 30, 23, 59, tzinfo=zone)
    )
    assert ids(tao_tu="01/11/2026", tao_den="30/11/2026") == {inside.pk}
    assert ids(tao_tu="30/11/2026") == {inside.pk, after.pk}
    assert ids(tao_den="31/10/2026") == {before.pk}


def test_loc_ngay_nghi_viec():
    early = make_worker_full(full_name="Sớm")
    employ(early, "RESIGNED", resign_date=D(2026, 10, 20))
    inside = make_worker_full(full_name="Trong")
    employ(inside, "RESIGNED", resign_date=D(2026, 11, 30))
    working = make_worker_full(full_name="Làm")
    employ(working, "ACTIVE")
    assert ids(nghi_tu="01/11/2026", nghi_den="30/11/2026") == {inside.pk}
    assert ids(trang_thai_lam_viec="RESIGNED", nghi_tu="01/11/2026", nghi_den="30/11/2026") == {
        inside.pk
    }
    assert ids(nghi_den="31/10/2026") == {early.pk}


def test_cccd_sap_het_han_dung_nguong_cai_dat():
    today = timezone.localdate()
    soon = make_worker_full(full_name="Sắp")
    far = make_worker_full(full_name="Xa")
    for worker, delta in ((soon, 10), (far, 400)):
        IdentityDocument.objects.filter(worker=worker).update(
            id_doc_type=IdDocType.CCCD_2021, expiry_date=today + datetime.timedelta(days=delta)
        )
    assert ids(cccd_sap_het_han="1") == {soon.pk}


def test_o_loc_rieng_cua_dashboard_chi_hien_khi_co_gia_tri():
    plain = page()
    for name in ("tao_tu", "tao_den", "nghi_tu", "nghi_den", "cccd_sap_het_han"):
        assert f'name="{name}"' not in plain
    shown = page("?tao_tu=01%2F11%2F2026&cccd_sap_het_han=1")
    assert 'name="tao_tu"' in shown and 'value="01/11/2026"' in shown
    assert 'name="cccd_sap_het_han"' in shown and 'name="nghi_tu"' not in shown


def test_ngay_sai_o_loc_dashboard_bao_loi_khong_sap_trang():
    make_worker_full(full_name="Vẫn Hiện")
    content = page("?tao_tu=2026-11-01")
    assert "Nhập ngày đúng định dạng dd/mm/yyyy." in content and "Vẫn Hiện" in content
