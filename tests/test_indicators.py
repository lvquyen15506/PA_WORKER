"""Chỉ số tự tính: thiếu giấy tờ, hoàn thiện, sắp hết hạn (yeu-cau.md mục II; models.md 4.6)."""

import datetime

import pytest

from apps.core.choices import VerificationStatus as VS
from apps.core.models import RequiredDocumentGroup, SystemSetting
from apps.documents.models import WorkerDocument
from apps.documents.services import missing_groups
from apps.employment.models import Contract
from apps.workers import indicators
from apps.workers.models import IdentityDocument, Worker
from tests.factories import make_document, make_worker_full, make_worker_in_status

pytestmark = pytest.mark.django_db
D = datetime.date
TODAY = D(2026, 11, 22)

ALL_TYPES = ["CCCD_FRONT", "CCCD_BACK", "PORTRAIT", "CV"]


def annotated(worker):
    return indicators.annotate_documents(Worker.objects.filter(pk=worker.pk)).get()


def give(worker, *codes, **kw):
    return [make_document(worker, code, **kw) for code in codes]


def names(groups):
    return [g.name for g in groups]


# ----- Thiếu giấy tờ ----------------------------------------------------------------------
def test_ho_so_chua_co_tai_lieu_nao_thieu_ca_4_nhom():
    worker = make_worker_full()
    assert names(missing_groups(worker)) == [
        "CCCD mặt trước",
        "CCCD mặt sau",
        "Ảnh chân dung",
        "CV hoặc Đơn xin việc",
    ]
    assert annotated(worker).missing_documents is True


def test_du_4_nhom_thi_khong_thieu():
    worker = make_worker_full()
    give(worker, *ALL_TYPES)
    assert missing_groups(worker) == []
    assert annotated(worker).missing_documents is False


@pytest.mark.parametrize("code", ["CV", "APPLICATION_LETTER"])
def test_cv_hoac_don_xin_viec_chung_mot_nhom_mot_loai_la_du(code):
    worker = make_worker_full()
    give(worker, "CCCD_FRONT", "CCCD_BACK", "PORTRAIT", code)
    assert missing_groups(worker) == []


def test_tai_lieu_khong_hop_le_khong_duoc_tinh():
    worker = make_worker_full()
    docs = give(worker, *ALL_TYPES)
    WorkerDocument.objects.filter(pk=docs[2].pk).update(verification_status="INVALID")
    assert names(missing_groups(worker)) == ["Ảnh chân dung"]
    assert annotated(worker).missing_documents is True


def test_tai_lieu_da_bi_thay_the_khong_duoc_tinh_nhung_ban_moi_thi_co():
    worker = make_worker_full()
    docs = give(worker, *ALL_TYPES)
    WorkerDocument.objects.filter(pk=docs[0].pk).update(is_current=False)
    assert names(missing_groups(worker)) == ["CCCD mặt trước"]
    make_document(worker, "CCCD_FRONT", replaces=docs[0], version=2)
    assert missing_groups(worker) == []


def test_loai_tai_lieu_khong_thuoc_nhom_bat_buoc_khong_giup_du():
    worker = make_worker_full()
    give(worker, "CONTRACT", "CONSENT")
    assert len(missing_groups(worker)) == 4


def test_nhom_ngung_su_dung_khong_con_bat_buoc():
    worker = make_worker_full()
    give(worker, "CCCD_FRONT", "CCCD_BACK", "CV")
    assert names(missing_groups(worker)) == ["Ảnh chân dung"]
    RequiredDocumentGroup.objects.filter(name="Ảnh chân dung").update(is_active=False)
    assert missing_groups(worker) == []
    assert annotated(worker).missing_documents is False


def test_tai_lieu_cua_ho_so_khac_khong_tinh():
    a, b = make_worker_full(), make_worker_full()
    give(a, *ALL_TYPES)
    assert missing_groups(a) == [] and len(missing_groups(b)) == 4
    flags = {
        w.pk: w.missing_documents
        for w in indicators.annotate_documents(Worker.objects.filter(pk__in=[a.pk, b.pk]))
    }
    assert flags == {a.pk: False, b.pk: True}


@pytest.mark.parametrize("have", [[], ["CCCD_FRONT"], ["CCCD_FRONT", "CCCD_BACK"], ALL_TYPES])
@pytest.mark.parametrize("invalid", [None, 0])
@pytest.mark.parametrize("replaced", [None, 0])
def test_ban_python_va_ban_queryset_cho_cung_ket_qua(have, invalid, replaced):
    worker = make_worker_full()
    docs = give(worker, *have)
    if have and invalid is not None:
        WorkerDocument.objects.filter(pk=docs[invalid].pk).update(verification_status="INVALID")
    if have and replaced is not None:
        WorkerDocument.objects.filter(pk=docs[replaced].pk).update(is_current=False)
    assert bool(missing_groups(worker)) == annotated(worker).missing_documents


def test_loc_thieu_giay_to_va_hoan_thien():
    full = make_worker_in_status(VS.VERIFIED)
    give(full, *ALL_TYPES)
    verified_missing = make_worker_in_status(VS.VERIFIED)
    give(verified_missing, "CCCD_FRONT")
    draft_full = make_worker_full()
    give(draft_full, *ALL_TYPES)
    everyone = Worker.objects.all()
    assert set(indicators.missing_documents(everyone)) == {verified_missing}
    # Hoàn thiện = Đã xác minh VÀ không thiếu giấy tờ.
    assert set(indicators.complete(everyone)) == {full}


# ----- Sắp hết hạn ------------------------------------------------------------------------
def with_identity_expiry(worker, expiry):
    IdentityDocument.objects.filter(worker=worker).update(expiry_date=expiry)
    return worker


def contract(worker, expiry, no):
    return Contract.objects.create(
        worker=worker,
        contract_no=no,
        contract_type="FIXED_TERM",
        signed_date=D(2025, 1, 1),
        effective_date=D(2025, 1, 1),
        expiry_date=expiry,
        created_by=worker.created_by,
    )


@pytest.mark.parametrize(
    ("offset", "expected"),
    [(-1, False), (0, True), (1, True), (30, True), (31, False)],
)
def test_cccd_sap_het_han_ranh_gioi_30_ngay(offset, expected):
    worker = with_identity_expiry(make_worker_full(), TODAY + datetime.timedelta(days=offset))
    found = indicators.id_expiring(Worker.objects.all(), today=TODAY)
    assert (worker in found) is expected


@pytest.mark.parametrize(
    ("offset", "expected"),
    [(-1, False), (0, True), (20, True), (30, True), (31, False)],
)
def test_hop_dong_sap_het_han_ranh_gioi_30_ngay(offset, expected):
    worker = make_worker_full()
    contract(worker, TODAY + datetime.timedelta(days=offset), "HD-A")
    found = indicators.contract_expiring(Worker.objects.all(), today=TODAY)
    assert (worker in found) is expected


def test_doi_so_ngay_canh_bao_trong_cai_dat():
    worker = make_worker_full()
    contract(worker, TODAY + datetime.timedelta(days=45), "HD-B")
    assert worker not in indicators.contract_expiring(Worker.objects.all(), today=TODAY)
    setting = SystemSetting.load()
    setting.expiry_warning_days = 60
    setting.save()
    assert worker in indicators.contract_expiring(Worker.objects.all(), today=TODAY)


def test_hop_dong_khong_xac_dinh_thoi_han_khong_bao_gio_sap_het_han():
    worker = make_worker_full()
    contract(worker, None, "HD-C")
    assert worker not in indicators.contract_expiring(Worker.objects.all(), today=TODAY)


def test_sap_het_han_gop_cccd_hoac_hop_dong_va_moi_ho_so_chi_dem_mot_lan():
    only_id = with_identity_expiry(make_worker_full(), TODAY + datetime.timedelta(days=5))
    only_contract = make_worker_full()
    contract(only_contract, TODAY + datetime.timedelta(days=10), "HD-D")
    both = with_identity_expiry(make_worker_full(), TODAY + datetime.timedelta(days=3))
    contract(both, TODAY + datetime.timedelta(days=4), "HD-E1")
    contract(both, TODAY + datetime.timedelta(days=6), "HD-E2")
    far = with_identity_expiry(make_worker_full(), TODAY + datetime.timedelta(days=200))
    found = list(indicators.expiring(Worker.objects.all(), today=TODAY))
    assert sorted(w.pk for w in found) == sorted(w.pk for w in (only_id, only_contract, both))
    assert far not in found
