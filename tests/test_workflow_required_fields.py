"""Trường bắt buộc khi gửi duyệt (models.md mục 4.3): thiếu từng trường thì bị chặn."""

import datetime

import pytest

from apps.core.choices import ConsentMethod
from apps.core.choices import VerificationStatus as VS
from apps.workers.models import DataConsent, EmergencyContact, IdentityDocument, Worker
from apps.workers.workflow import TransitionError, submission_errors, transition
from tests.factories import make_user, make_worker_full, make_worker_in_status

pytestmark = pytest.mark.django_db


def fresh(worker):
    return Worker.objects.get(pk=worker.pk)  # bỏ bộ nhớ đệm quan hệ


def fields_missing(worker):
    return [issue.field for issue in submission_errors(fresh(worker))]


def test_ho_so_du_truong_khong_thieu_gi():
    assert fields_missing(make_worker_full()) == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("full_name", ""),
        ("full_name", "   "),
        ("phone", ""),
        ("date_of_birth", None),
        ("gender", ""),
        ("nationality", ""),
        ("current_address", ""),
        ("current_address", "  "),
    ],
)
def test_thieu_truong_cua_ho_so(field, value):
    worker = make_worker_full()
    Worker.objects.filter(pk=worker.pk).update(**{field: value})
    assert fields_missing(worker) == [field]


def test_thieu_giay_to_nhan_dien_hoan_toan():
    worker = make_worker_full()
    IdentityDocument.objects.filter(worker=worker).delete()
    assert fields_missing(worker) == ["id_doc_type", "id_number"]


def test_thieu_loai_giay_to():
    worker = make_worker_full()
    IdentityDocument.objects.filter(worker=worker).update(id_doc_type="")
    assert fields_missing(worker) == ["id_doc_type"]


def test_thieu_so_dinh_danh():
    worker = make_worker_full()
    identity = IdentityDocument.objects.get(worker=worker)
    identity.id_number_enc = None
    identity.save()
    assert fields_missing(worker) == ["id_number"]


def test_khong_co_nguoi_lien_he():
    worker = make_worker_full()
    EmergencyContact.objects.filter(worker=worker).delete()
    assert fields_missing(worker) == ["emergency_contact"]


@pytest.mark.parametrize("blank", ["full_name", "relationship", "phone"])
def test_nguoi_lien_he_thieu_mot_trong_ba_truong_khong_duoc_tinh(blank):
    worker = make_worker_full()
    EmergencyContact.objects.filter(worker=worker).update(**{blank: ""})
    assert fields_missing(worker) == ["emergency_contact"]


def test_du_mot_nguoi_lien_he_day_du_la_dat_du_con_dong_khac_thieu():
    worker = make_worker_full()
    EmergencyContact.objects.create(worker=worker, full_name="", relationship="", phone="")
    assert fields_missing(worker) == []


def test_chua_co_dong_y():
    worker = make_worker_full()
    DataConsent.objects.filter(worker=worker).delete()
    assert fields_missing(worker) == ["consent"]


def test_dong_y_moi_nhat_la_khong_thi_bi_chan_du_truoc_do_tung_dong_y():
    worker = make_worker_full()  # đã có một bản đồng ý
    DataConsent.objects.create(
        worker=worker,
        consented=False,
        consent_date=datetime.date.today(),
        method=ConsentMethod.ELECTRONIC,
        recorded_by=make_user(),
    )
    assert fields_missing(worker) == ["consent"]


def test_dong_y_lai_sau_khi_rut_thi_du_dieu_kien():
    worker = make_worker_full()
    user = make_user()
    for consented in (False, True):
        DataConsent.objects.create(
            worker=worker,
            consented=consented,
            consent_date=datetime.date.today(),
            method=ConsentMethod.ELECTRONIC,
            recorded_by=user,
        )
    assert fields_missing(worker) == []


def test_thieu_nhieu_truong_bao_het_mot_lan():
    worker = make_worker_full()
    Worker.objects.filter(pk=worker.pk).update(date_of_birth=None, gender="")
    DataConsent.objects.filter(worker=worker).delete()
    assert fields_missing(worker) == ["date_of_birth", "gender", "consent"]


@pytest.mark.parametrize("src", [VS.DRAFT, VS.NEEDS_INFO])
def test_gui_duyet_thieu_truong_bi_chan_va_nen_ten_truong(src):
    worker = make_worker_in_status(src)
    Worker.objects.filter(pk=worker.pk).update(date_of_birth=None)
    with pytest.raises(TransitionError) as exc:
        transition(worker, VS.PENDING, worker.created_by)
    assert [i.field for i in exc.value.issues] == ["date_of_birth"]
    assert exc.value.issues[0].message == "Thiếu ngày sinh."
    assert fresh(worker).verification_status == src


def test_nhap_chi_can_ho_ten_va_sdt_nhung_gui_duyet_thi_thieu_nhieu_truong():
    from tests.factories import make_worker

    worker = make_worker()  # chỉ họ tên + SĐT
    with pytest.raises(TransitionError) as exc:
        transition(worker, VS.PENDING, worker.created_by)
    assert {i.field for i in exc.value.issues} == {
        "date_of_birth",
        "gender",
        "current_address",
        "id_doc_type",
        "id_number",
        "emergency_contact",
        "consent",
    }


def test_thieu_tai_lieu_khong_chan_gui_duyet():
    worker = make_worker_full()  # chưa có tài liệu nào
    assert not worker.documents.exists()
    transition(worker, VS.PENDING, worker.created_by)
    assert fresh(worker).verification_status == VS.PENDING


def test_chua_dat_du_truong_thi_cac_chuyen_khong_phai_gui_duyet_van_chay():
    # Kiểm tra trường chỉ áp cho Nháp/Cần bổ sung -> Chờ duyệt.
    worker = make_worker_in_status(VS.PENDING)
    Worker.objects.filter(pk=worker.pk).update(date_of_birth=None)
    transition(worker, VS.NEEDS_INFO, make_user("HR_MANAGER"), "Thiếu ngày sinh")
    assert fresh(worker).verification_status == VS.NEEDS_INFO
