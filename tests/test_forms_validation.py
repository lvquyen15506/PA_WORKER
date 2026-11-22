"""Kiểm tra dữ liệu hồ sơ (models.md 4.5, câu 5, 16), form hồ sơ và che số CCCD (câu 1)."""

import datetime

import pytest

from apps.core.text import mask_id_number
from apps.workers.forms import ContactFormSet, WorkerForm, contact_rows
from apps.workers.models import IdentityDocument, Worker
from apps.workers.validation import (
    DRAFT,
    MSG_UNDER_15,
    MSG_WARN_UNDER_18,
    SUBMISSION,
    validate_contacts,
    validate_worker_data,
)
from tests.factories import fake_id, make_worker_full

pytestmark = pytest.mark.django_db
D = datetime.date
TODAY = D(2026, 11, 22)
OK = {"full_name": "Nguyễn Văn Giả", "phone": "0912345678"}


def check(**data):
    return validate_worker_data({**OK, **data}, today=TODAY)


# ----- Che số CCCD ------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("079123452345", "0791••••2345"),
        ("0791 2345 2345", "0791••••2345"),
        ("123456789", "123•••789"),  # CMND 9 số
        ("12", "••"),
        ("", ""),
        (None, ""),
    ],
)
def test_che_so_dinh_danh(value, expected):
    assert mask_id_number(value) == expected


def test_so_12_chu_so_che_dung_mau_cua_cau_1():
    masked = mask_id_number("999123456789")
    assert masked == "9991••••6789" and len(masked) == 12
    assert "2345" not in masked


# ----- Tuổi (câu 16) ----------------------------------------------------------------------
def birth_years_ago(years, days_offset=0):
    return D(TODAY.year - years, TODAY.month, TODAY.day) + datetime.timedelta(days=days_offset)


@pytest.mark.parametrize(
    ("birth", "blocked", "warned"),
    [
        (birth_years_ago(14, 0), True, False),  # đúng 14 tuổi
        (birth_years_ago(15, 1), True, False),  # còn 1 ngày nữa tròn 15
        (birth_years_ago(15, 0), False, True),  # đúng 15 tuổi hôm nay
        (birth_years_ago(17, 0), False, True),
        (birth_years_ago(18, 1), False, True),  # còn 1 ngày nữa tròn 18
        (birth_years_ago(18, 0), False, False),  # đúng 18 tuổi hôm nay
        (birth_years_ago(40, 0), False, False),
    ],
)
def test_ranh_gioi_tuoi_14_15_17_18(birth, blocked, warned):
    result = check(date_of_birth=birth)
    assert ("date_of_birth" in result.errors) is blocked
    if blocked:
        assert result.errors["date_of_birth"] == MSG_UNDER_15
    assert (MSG_WARN_UNDER_18 in result.warnings) is warned


def test_chua_nhap_ngay_sinh_thi_khong_kiem_tuoi():
    result = check(date_of_birth=None)
    assert "date_of_birth" not in result.errors and MSG_WARN_UNDER_18 not in result.warnings


def test_ngay_sinh_o_tuong_lai_la_loi():
    assert (
        "tương lai"
        in check(date_of_birth=TODAY + datetime.timedelta(days=1)).errors["date_of_birth"]
    )


# ----- Các quy tắc khác -------------------------------------------------------------------
@pytest.mark.parametrize("phone", ["0912345", "912345678", "09123456789", "abcdefghij", ""])
def test_sdt_phai_10_chu_so_bat_dau_bang_0(phone):
    assert "phone" in check(phone=phone).errors


@pytest.mark.parametrize("number", ["12345678901", "1234567890123", "99912345678a", "abc"])
def test_so_cccd_phai_12_chu_so(number):
    assert "id_number" in check(id_number=number).errors


def test_so_cccd_hop_le_va_chua_trung_la_dat():
    result = check(id_number=fake_id())
    assert "id_number" not in result.errors and result.duplicate is None


def test_so_cccd_trung_la_loi_kem_ho_so_cu():
    old = make_worker_full()
    number = fake_id()
    IdentityDocument.objects.filter(worker=old).update(id_number_enc=number)
    identity = IdentityDocument.objects.get(worker=old)
    identity.id_number_enc = number
    identity.save()
    result = check(id_number=number)
    assert old.worker_code in result.errors["id_number"] and result.duplicate == old
    assert "id_number" not in check(id_number=number).warnings  # là lỗi, không phải cảnh báo
    # Sửa chính hồ sơ đó với số của nó thì không báo trùng.
    assert validate_worker_data({"id_number": number}, instance=old, today=TODAY).errors == {}


@pytest.mark.parametrize("number", ["123456789", "123456789012"])
def test_cmnd_cu_9_hoac_12_so(number):
    assert "old_id_number" not in check(old_id_number=number).errors


@pytest.mark.parametrize("number", ["12345678", "1234567890", "12345678901"])
def test_cmnd_cu_sai_do_dai(number):
    assert "old_id_number" in check(old_id_number=number).errors


def test_ngay_cap_phai_sau_ngay_sinh():
    birth = D(2000, 1, 1)
    assert "issue_date" in check(date_of_birth=birth, issue_date=birth).errors
    assert "issue_date" in check(date_of_birth=birth, issue_date=D(1999, 12, 31)).errors
    assert "issue_date" not in check(date_of_birth=birth, issue_date=D(2000, 1, 2)).errors
    assert "issue_date" not in check(issue_date=D(1999, 1, 1)).errors  # chưa có ngày sinh


@pytest.mark.parametrize("email", ["a@", "abc", "a b@c.com"])
def test_email_sai_dinh_dang(email):
    assert "email" in check(email=email).errors


def test_email_dung_hoac_trong_la_dat():
    assert "email" not in check(email="giagia@example.com").errors
    assert "email" not in check(email="").errors


def test_gioi_tinh_chi_nam_nu():
    assert "gender" not in check(gender="MALE").errors
    assert "gender" not in check(gender="FEMALE").errors
    assert "gender" in check(gender="OTHER").errors


def test_nhap_chi_can_ho_ten_va_sdt():
    result = validate_worker_data(OK, today=TODAY)
    assert result.errors == {}
    assert validate_worker_data({"full_name": "A"}, today=TODAY).errors == {
        "phone": "Nhập số điện thoại."
    }


def test_muc_gui_duyet_bat_buoc_them_truong():
    result = validate_worker_data(OK, level=SUBMISSION, today=TODAY)
    assert set(result.errors) == {
        "date_of_birth",
        "gender",
        "nationality",
        "current_address",
        "id_doc_type",
        "id_number",
    }
    assert validate_worker_data(OK, level=DRAFT, today=TODAY).errors == {}


def test_cap_nhat_mot_phan_dung_gia_tri_cu_cua_ho_so():
    worker = make_worker_full(phone="0911112222")
    result = validate_worker_data(
        {"email": "x@y.com"}, instance=worker, level=SUBMISSION, today=TODAY
    )
    assert "phone" not in result.errors and "date_of_birth" not in result.errors
    # Muốn sửa địa chỉ thành rỗng ở mức gửi duyệt thì bị chặn.
    result = validate_worker_data({"current_address": ""}, instance=worker, level=SUBMISSION)
    assert set(result.errors) == {"current_address"}  # số CCCD còn nguyên từ hồ sơ


# ----- Cảnh báo trùng khi chưa có số định danh (câu 5) -----------------------------------
def test_chua_co_cccd_canh_bao_trung_sdt_khong_chan():
    old = make_worker_full(phone="0911999888")
    result = check(phone="0911999888")
    assert result.errors == {}
    assert any(old.worker_code in w and "số điện thoại" in w for w in result.warnings)


def test_chua_co_cccd_canh_bao_trung_ten_va_ngay_sinh():
    old = make_worker_full(full_name="Lê Thị Giả", date_of_birth=D(1991, 2, 3))
    result = check(full_name="le thi gia", date_of_birth=D(1991, 2, 3), phone="0900000001")
    assert any(old.worker_code in w and "họ tên và ngày sinh" in w for w in result.warnings)


def test_da_co_cccd_thi_khong_canh_bao_theo_sdt():
    make_worker_full(phone="0911999777")
    result = check(phone="0911999777", id_number=fake_id())
    assert result.warnings == [] and result.similar == []


# ----- Form --------------------------------------------------------------------------------
def form(**data):
    return WorkerForm(data={**OK, **data})


def test_form_hop_le_toi_thieu():
    f = form()
    assert f.is_valid(), f.errors
    assert f.service_data()["full_name"] == "Nguyễn Văn Giả"


def test_form_loi_hien_duoi_tung_o_bang_tieng_viet():
    f = WorkerForm(data={"full_name": "", "phone": "123", "id_number": "12", "email": "x"})
    assert not f.is_valid()
    assert f.errors["full_name"] == ["Nhập họ và tên."]
    assert "10 chữ số" in f.errors["phone"][0]
    assert f.errors["id_number"] == ["Số CCCD phải gồm 12 chữ số."]
    assert f.errors["email"] == ["Email không đúng định dạng."]


def test_form_ngay_nhap_dang_dd_mm_yyyy():
    f = form(date_of_birth="05/03/1995")
    assert f.is_valid() and f.cleaned_data["date_of_birth"] == D(1995, 3, 5)
    assert not form(date_of_birth="1995-03-05").is_valid()
    assert form(date_of_birth="31/02/1995").errors["date_of_birth"] == [
        "Nhập ngày đúng định dạng dd/mm/yyyy."
    ]


def test_form_chan_duoi_15_tuoi_canh_bao_duoi_18():
    today = datetime.date.today()
    teen_birth = (
        D(today.year - 16, 1, 1) if today > D(today.year, 1, 1) else D(today.year - 17, 1, 1)
    )
    child = form(date_of_birth=D(today.year - 10, 6, 1).strftime("%d/%m/%Y"))
    assert not child.is_valid() and child.errors["date_of_birth"] == [MSG_UNDER_15]
    teen = form(date_of_birth=teen_birth.strftime("%d/%m/%Y"))
    assert teen.is_valid() and MSG_WARN_UNDER_18 in teen.warnings


def test_form_bao_trung_cccd_kem_ho_so_cu():
    old = make_worker_full()
    identity = IdentityDocument.objects.get(worker=old)
    identity.id_number_enc = "999111222333"
    identity.save()
    f = form(id_number="999111222333")
    assert not f.is_valid()
    assert old.worker_code in f.errors["id_number"][0]
    assert f.duplicate == old


def test_form_sua_ho_so_da_xac_minh_bat_buoc_du_truong_gui_duyet():
    worker = make_worker_full()
    f = WorkerForm(data={**OK}, instance=worker, level=SUBMISSION)
    assert not f.is_valid()
    assert {"date_of_birth", "gender", "current_address", "id_number", "id_doc_type"} <= set(
        f.errors
    )
    assert f.errors["date_of_birth"] == ["Nhập ngày sinh."]


def test_form_sua_hien_gia_tri_cu_ke_ca_truong_ma_hoa():
    worker = make_worker_full()
    identity = IdentityDocument.objects.get(worker=worker)
    identity.permanent_address_enc = "Địa chỉ thường trú giả"
    identity.save()
    worker = Worker.objects.get(pk=worker.pk)  # tải lại: bỏ bộ nhớ đệm quan hệ cũ
    f = WorkerForm(instance=worker)
    assert f.initial["full_name"] == worker.full_name
    assert f.initial["permanent_address"] == "Địa chỉ thường trú giả"
    assert f.initial["id_number"] == identity.id_number_enc


# ----- Người liên hệ khẩn cấp ---------------------------------------------------------------
def formset(rows):
    data = {"form-TOTAL_FORMS": str(len(rows)), "form-INITIAL_FORMS": "0"}
    for i, row in enumerate(rows):
        for key, value in row.items():
            data[f"form-{i}-{key}"] = value
    return ContactFormSet(data)


def test_dong_lien_he_trong_duoc_bo_qua_dong_co_du_lieu_phai_du_3_truong():
    assert validate_contacts([{"full_name": "", "relationship": "", "phone": ""}]) == {}
    assert validate_contacts([{"full_name": "A", "relationship": "", "phone": ""}]) == {
        0: {"relationship": "Nhập mối quan hệ.", "phone": "Nhập số điện thoại."}
    }
    assert set(validate_contacts([{"full_name": "A", "relationship": "B", "phone": "123"}])[0]) == {
        "phone"
    }
    assert (
        validate_contacts([{"full_name": "", "relationship": "", "phone": "", "delete": True}])
        == {}
    )


def test_formset_lien_he():
    ok = formset(
        [
            {"full_name": "Người Thân", "relationship": "Anh", "phone": "0911111111"},
            {"full_name": "", "relationship": "", "phone": ""},
        ]
    )
    assert ok.is_valid()
    rows = contact_rows(ok)
    assert rows[0]["full_name"] == "Người Thân" and rows[0]["delete"] is False
    bad = formset([{"full_name": "Người Thân", "relationship": "", "phone": "0911111111"}])
    assert not bad.is_valid()
    assert bad.forms[0].errors["relationship"] == ["Nhập mối quan hệ."]
