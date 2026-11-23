"""Nhập hồ sơ từ file Excel (Phase 7, bước 6; kịch bản nghiệm thu 16; excel-mau.md).

Lỗi từng dòng (dòng đúng vẫn nhập), phần B chỉ Admin/Quản lý, mã NV cũ đẩy CodeSequence đúng quy
tắc câu 27, đợt làm việc từ B12/B13 qua add_assignment, không nhập lương, chống zip bomb.
"""

import datetime
import io
import itertools
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from openpyxl import Workbook, load_workbook

from apps.audit.models import AuditLog, AuditPersonalValue
from apps.core import excel
from apps.core.models import (
    ClientCompany,
    CodeSequence,
    Department,
    Position,
    Section,
    Shift,
    Team,
)
from apps.employment.models import Employment, EmploymentHistory, SalaryHistory, WorkAssignment
from apps.reports import excel_template, importer
from apps.reports.excel_columns import COLUMNS, EXAMPLES, HEADERS, SHEET_CATALOG, SHEET_DATA
from apps.workers.models import IdentityDocument, StatusChange, Worker
from tests.factories import login_client, make_user, make_worker_full
from tests.samples import DOCX, XLSX

pytestmark = pytest.mark.django_db
TODAY = timezone.localdate()
_n = itertools.count(1)
DEFAULT_TYPE = "CCCD gắn chip (mẫu 2021)"


def build(rows, *, headers=None, sheet=SHEET_DATA):
    """Bytes một file .xlsx: dòng 1 là tiêu đề, mỗi phần tử `rows` là dict {khóa cột: giá trị}."""
    book = Workbook()
    ws = book.active
    ws.title = sheet
    ws.append(headers if headers is not None else list(HEADERS))
    for row in rows:
        ws.append([row.get(c.key) for c in COLUMNS])
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def good(**over):
    """Một dòng phần A hợp lệ, số điện thoại/CCCD duy nhất."""
    n = next(_n)
    row = {
        "full_name": f"Nguyễn Văn Nhập {n}",
        "phone": f"09{n:08d}",
        "date_of_birth": "15/03/1995",
        "gender": "Nam",
        "id_doc_type": DEFAULT_TYPE,
        "id_number": f"999{n:09d}",
        "issue_date": "20/06/2023",
        "contact_name": "Người Thân Giả",
        "contact_relationship": "Anh",
        "contact_phone": "0912345678",
    }
    row.update(over)
    return row


def work(**over):
    """Phần B hợp lệ (cần catalog())."""
    n = next(_n)
    row = {
        "employee_code": f"CN-{n + 100:05d}",
        "department": "Xưởng May",
        "section": "Chuyền May 1",
        "team": "Tổ 1",
        "position": "Công nhân may",
        "shift": "Ca 1",
        "received_date": "01/02/2023",
        "start_date": "01/02/2023",
        "work_status": "Đang làm việc",
    }
    row.update(over)
    return row


@pytest.fixture
def catalog():
    dep = Department.objects.create(name="Xưởng May")
    section = Section.objects.create(department=dep, name="Chuyền May 1")
    other_dep = Department.objects.create(name="Kho Vận")
    other_section = Section.objects.create(department=other_dep, name="Kho 1")
    Section.objects.create(department=dep, name="Chuyền Trùng")
    Section.objects.create(department=other_dep, name="Chuyền Trùng")
    team = Team.objects.create(section=section, name="Tổ 1")
    Team.objects.create(section=other_section, name="Tổ Kho")
    return {
        "dep": dep,
        "section": section,
        "team": team,
        "position": Position.objects.create(name="Công nhân may"),
        "shift": Shift.objects.create(name="Ca 1"),
        "company": ClientCompany.objects.create(name="Công ty Mẫu A", location="Tỉnh Mẫu"),
    }


@pytest.fixture
def manager():
    return make_user("HR_MANAGER")


@pytest.fixture
def hr():
    return make_user("HR_STAFF")


def run(user, rows, **kw):
    return importer.import_workbook(user, build(rows, **kw))


def messages(result):
    return [i.text for i in result.errors]


# --- Kịch bản 16 -----------------------------------------------------------------------------
def test_kich_ban_16_dong_dung_duoc_nhap_ba_dong_loi_duoc_bao(manager):
    rows = [good() for _ in range(10)]
    rows[2] = good(phone="12345")  # dòng 4 trong Excel
    rows[5] = good(id_number="12345678")  # dòng 7
    rows[8] = good(date_of_birth="01/01/2020")  # dòng 10: dưới 15 tuổi
    result = run(manager, rows)
    assert result.read == 10 and result.imported == 7 and result.error_rows == 3
    assert result.summary == "Đã đọc 10 dòng. Nhập thành công 7 hồ sơ. 3 dòng lỗi. 0 cảnh báo."
    assert messages(result) == [
        "Dòng 4 – Số điện thoại: Số điện thoại phải gồm 10 chữ số, bắt đầu bằng 0.",
        "Dòng 7 – Số định danh: Số CCCD phải gồm 12 chữ số.",
        "Dòng 10 – Ngày sinh: Người dưới 15 tuổi không được nhập vào hệ thống.",
    ]
    assert Worker.objects.count() == 7


def test_ho_so_nhap_la_nhap_nguoi_tao_la_nguoi_nhap_va_co_dong_thoi_gian(manager):
    result = run(manager, [good(full_name="Trần Thị Mẫu")])
    worker = Worker.objects.get()
    assert result.imported == 1
    assert worker.verification_status == "DRAFT" and worker.created_by == manager
    assert worker.worker_code and worker.employee_code is None
    assert worker.gender == "MALE" and worker.nationality == "Việt Nam"
    change = StatusChange.objects.get(worker=worker)
    assert (change.from_status, change.to_status) == ("", "DRAFT")
    identity = IdentityDocument.objects.get(worker=worker)
    assert identity.id_doc_type == "CCCD_2021" and identity.id_number_enc.startswith("999")
    assert worker.emergency_contacts.count() == 1
    assert not Employment.objects.filter(worker=worker).exists()  # ứng viên: không có phần B


def test_nguoi_nhap_khong_tu_duyet_duoc_ho_so_vua_nhap(manager):
    from apps.core.choices import ConsentMethod
    from apps.workers.models import DataConsent
    from apps.workers.workflow import TransitionForbidden, transition

    run(manager, [good()])
    worker = Worker.objects.get()
    # Hồ sơ nhập còn thiếu nơi ở và đồng ý xử lý dữ liệu: bổ sung rồi mới gửi duyệt được.
    Worker.objects.filter(pk=worker.pk).update(current_address="Địa chỉ giả")
    DataConsent.objects.create(
        worker=worker,
        consented=True,
        consent_date=TODAY,
        method=ConsentMethod.ELECTRONIC,
        recorded_by=manager,
    )
    worker.refresh_from_db()
    transition(worker, "PENDING", manager)
    with pytest.raises(TransitionForbidden):
        transition(worker, "VERIFIED", manager)  # người tạo/gửi duyệt không tự duyệt (câu 8)


def test_dong_trong_bi_bo_qua_khong_tinh_la_loi(manager):
    result = run(manager, [good(), {}, {"full_name": "   "}, good()])
    assert result.read == 2 and result.imported == 2 and not result.errors


def test_tep_chi_co_tieu_de_khong_nhap_gi(manager):
    result = run(manager, [])
    assert result.read == 0 and result.imported == 0 and not result.file_error


# --- Nhật ký --------------------------------------------------------------------------------
def test_nhat_ky_import_mot_dong_cho_ca_lan_va_create_tung_ho_so(manager):
    run(manager, [good(), good(phone="1"), good()])
    entry = AuditLog.objects.get(action="IMPORT")
    assert entry.user == manager and entry.object_type == "excel_import"
    assert entry.note == "Đọc 3 dòng; nhập 2; lỗi 1; cảnh báo 0"
    assert AuditLog.objects.filter(action="CREATE", object_type="workers.Worker").count() == 2
    # Giá trị cá nhân của người liên hệ nằm ở AuditPersonalValue, không ở nhật ký.
    assert AuditPersonalValue.objects.exists()
    assert "Nguyễn Văn" not in entry.note


# --- Từng lỗi trong bảng excel-mau.md mục 4 ---------------------------------------------------
@pytest.mark.parametrize(
    ("over", "column", "message"),
    [
        ({"full_name": ""}, "Họ và tên", "Họ và tên không được để trống."),
        ({"full_name": "A" * 101}, "Họ và tên", "Họ và tên tối đa 100 ký tự."),
        ({"phone": "0912"}, "Số điện thoại", "Số điện thoại phải gồm 10 chữ số, bắt đầu bằng 0."),
        (
            {"phone": "1912345678"},
            "Số điện thoại",
            "Số điện thoại phải gồm 10 chữ số, bắt đầu bằng 0.",
        ),
        ({"date_of_birth": "31/02/2000"}, "Ngày sinh", "Ngày phải theo dạng dd/mm/yyyy."),
        ({"date_of_birth": "2000-01-01"}, "Ngày sinh", "Ngày phải theo dạng dd/mm/yyyy."),
        (
            {"date_of_birth": "01/01/2999", "issue_date": ""},
            "Ngày sinh",
            "Ngày sinh không được ở tương lai.",
        ),
        ({"gender": "Khác"}, "Giới tính", "Giới tính chỉ nhận Nam hoặc Nữ."),
        ({"id_doc_type": ""}, "Loại giấy tờ", "Cần chọn loại giấy tờ khi đã nhập số định danh."),
        (
            {"id_doc_type": "Hộ chiếu"},
            "Loại giấy tờ",
            "Loại giấy tờ không hợp lệ. Hãy chọn từ danh sách.",
        ),
        ({"id_number": "99900000000"}, "Số định danh", "Số CCCD phải gồm 12 chữ số."),
        ({"issue_date": "01/01/1990"}, "Ngày cấp", "Ngày cấp phải sau ngày sinh."),
        ({"expiry_date": "01/01/2020"}, "Ngày hết hạn", "Ngày hết hạn phải sau ngày cấp."),
        ({"old_id_number": "12345"}, "Số CMND cũ", "Số CMND cũ phải gồm 9 hoặc 12 chữ số."),
        ({"email": "khong-phai-email"}, "Email", "Email không đúng định dạng."),
        (
            {"contact_phone": ""},
            "Người liên hệ khẩn cấp – Họ tên",
            "Thông tin người liên hệ khẩn cấp phải điền đủ họ tên, quan hệ và SĐT.",
        ),
        (
            {"contact_phone": "123"},
            "Người liên hệ khẩn cấp – SĐT",
            "Số điện thoại phải gồm 10 chữ số, bắt đầu bằng 0.",
        ),
    ],
)
def test_loi_phan_a(manager, over, column, message):
    result = run(manager, [good(**over)])
    assert result.imported == 0
    assert [(i.row, i.column, i.message) for i in result.errors] == [(2, column, message)]
    assert not Worker.objects.exists()


def test_cccd_trung_ho_so_da_co_chi_dan_ma_ho_so_khong_in_ho_ten(manager):
    existing = make_worker_full(full_name="Người Cũ Tên Riêng")
    number = IdentityDocument.objects.get(worker=existing).id_number_enc
    result = run(manager, [good(id_number=number)])
    assert messages(result) == [
        f"Dòng 2 – Số định danh: Số CCCD đã có trong hồ sơ {existing.worker_code}."
    ]
    assert "Người Cũ" not in messages(result)[0]


def test_cccd_trung_dong_khac_trong_cung_tep_dong_dau_thang(manager):
    result = run(manager, [good(id_number="999000000777"), good(id_number="999000000777")])
    assert result.imported == 1
    assert messages(result) == ["Dòng 3 – Số định danh: Số CCCD trùng với dòng 2 trong cùng tệp."]


def test_cccd_trung_voi_dong_bi_loi_thi_dong_sau_van_nhap_duoc(manager):
    rows = [good(id_number="999000000888", phone="1"), good(id_number="999000000888")]
    result = run(manager, rows)
    assert result.imported == 1 and [i.row for i in result.errors] == [2]


def test_cong_thuc_excel_that_bi_loi_chu_gach_dau_dong_van_nhan(manager):
    rows = [good(note="=SUM(1,1)"), good(skills="- Vận hành máy may", note="+ghi chú, @abc")]
    result = run(manager, rows)
    assert messages(result) == ["Dòng 2 – Ghi chú: Ô không được chứa công thức Excel."]
    worker = Worker.objects.get()
    assert worker.skills == "- Vận hành máy may" and worker.note == "+ghi chú, @abc"


def test_cong_thuc_o_cot_so_dien_thoai_cung_bi_chan(manager):
    result = run(manager, [good(phone="=0912345678")])
    assert messages(result) == ["Dòng 2 – Số điện thoại: Ô không được chứa công thức Excel."]


def test_o_kieu_so_cua_excel_duoc_doc_thanh_chu(manager):
    result = run(manager, [good(phone=912345678, id_number=999000000321)])
    assert [i.column for i in result.errors] == ["Số điện thoại"]  # mất số 0 đầu → báo lỗi rõ
    result2 = run(manager, [good(id_number=999000000322.0)])
    assert result2.imported == 1
    # Trường mã hóa không lọc trực tiếp được: đọc lại giá trị đã giải mã.
    assert [i.id_number_enc for i in IdentityDocument.objects.all()] == ["999000000322"]


def test_o_ngay_kieu_excel_duoc_doc_kem_canh_bao(manager):
    result = run(manager, [good(date_of_birth=datetime.date(1995, 3, 15))])
    assert result.imported == 1 and not result.errors
    assert [(w.column, w.message) for w in result.warnings] == [
        ("Ngày sinh", "Ô ngày của Excel có thể bị đảo ngày/tháng; kiểm tra lại.")
    ]
    assert Worker.objects.get().date_of_birth == datetime.date(1995, 3, 15)


# --- Cảnh báo -------------------------------------------------------------------------------
def test_canh_bao_duoi_18_tuoi_van_nhap(manager):
    year = TODAY.year - 17
    result = run(manager, [good(date_of_birth=f"01/01/{year}", issue_date="")])
    assert result.imported == 1 and not result.errors
    assert [w.message for w in result.warnings] == [
        "Người dưới 18 tuổi. Kiểm tra quy định sử dụng lao động chưa thành niên."
    ]


def test_canh_bao_trung_sdt_va_trung_ho_ten_ngay_sinh_chi_dan_ma_ho_so(manager):
    existing = make_worker_full(full_name="Lê Văn Trùng", date_of_birth=datetime.date(1990, 5, 5))
    row = good(full_name="Le Van Trung", phone=existing.phone, date_of_birth="05/05/1990")
    result = run(manager, [row])
    assert result.imported == 1 and not result.errors
    texts = sorted(w.message for w in result.warnings)
    assert texts == [
        f"Họ tên và ngày sinh trùng hồ sơ {existing.worker_code}. Kiểm tra có phải cùng một người.",
        f"Số điện thoại trùng hồ sơ {existing.worker_code}. Kiểm tra có phải cùng một người.",
    ]
    assert all("Lê Văn" not in t for t in texts)


def test_canh_bao_cua_dong_loi_khong_duoc_liet_ke(manager):
    existing = make_worker_full()
    result = run(manager, [good(phone=existing.phone, id_number="1")])
    assert result.errors and not result.warnings  # dòng bị bỏ qua nên không có cảnh báo


# --- Phần B ---------------------------------------------------------------------------------
def test_nhan_vien_hr_nhap_dong_co_phan_b_bi_loi_dong_do_con_dong_a_van_nhap(hr, catalog):
    rows = [good(), good(**work())]
    result = importer.import_workbook(hr, build(rows))
    assert result.imported == 1
    assert [(i.row, i.message) for i in result.errors] == [
        (3, "Chỉ Admin hoặc Quản lý nhân sự được nhập thông tin làm việc.")
    ]
    assert not Employment.objects.exists()


@pytest.mark.parametrize("role", ["ADMIN", "HR_MANAGER"])
def test_admin_va_quan_ly_nhap_duoc_phan_b(role, catalog):
    user = make_user(role)
    result = run(user, [good(**work(employee_code="CN-00012"))])
    assert result.imported == 1 and not result.errors
    worker = Worker.objects.get()
    assert worker.employee_code == "CN-00012" and worker.verification_status == "DRAFT"
    employment = Employment.objects.get(worker=worker)
    assert employment.section == catalog["section"] and employment.team == catalog["team"]
    assert employment.position == catalog["position"] and employment.shift == catalog["shift"]
    assert employment.work_status == "ACTIVE"
    assert employment.received_date == employment.start_date == datetime.date(2023, 2, 1)
    history = EmploymentHistory.objects.get(worker=worker)
    assert history.change_type == "IMPORT" and history.to_work_status == "ACTIVE"
    assert history.to_section == catalog["section"] and history.created_by == user
    assert not WorkAssignment.objects.exists() and not SalaryHistory.objects.exists()


def test_ma_nv_dung_dinh_dang_day_bo_dem_ma_khac_dinh_dang_khong_day(manager, catalog):
    run(manager, [good(**work(employee_code="CN-00012"))])
    assert CodeSequence.objects.get(code_type="EMPLOYEE").last_number == 12
    run(manager, [good(**work(employee_code="NV2019-A12"))])
    assert CodeSequence.objects.get(code_type="EMPLOYEE").last_number == 12  # không đổi
    run(manager, [good(**work(employee_code="CN-00005"))])
    assert CodeSequence.objects.get(code_type="EMPLOYEE").last_number == 12  # chỉ tăng
    from apps.core.codes import next_code

    assert next_code("EMPLOYEE") == "CN-00013"  # không bao giờ cấp trùng mã cũ


@pytest.mark.parametrize(
    ("over", "column", "message"),
    [
        ({"employee_code": ""}, "Mã nhân viên", "Cần nhập mã nhân viên khi có thông tin làm việc."),
        (
            {"employee_code": "CN 123"},
            "Mã nhân viên",
            "Mã nhân viên tối đa 20 ký tự, chỉ gồm chữ, số và dấu gạch ngang.",
        ),
        (
            {"employee_code": "A" * 21},
            "Mã nhân viên",
            "Mã nhân viên tối đa 20 ký tự, chỉ gồm chữ, số và dấu gạch ngang.",
        ),
        ({"position": ""}, "Chức danh", "Cần nhập chức danh khi có thông tin làm việc."),
        (
            {"position": "Chức danh lạ"},
            "Chức danh",
            "Không tìm thấy “Chức danh lạ” trong danh mục. Hãy chọn từ sheet Danh mục.",
        ),
        (
            {"shift": "Ca lạ"},
            "Ca làm việc",
            "Không tìm thấy “Ca lạ” trong danh mục. Hãy chọn từ sheet Danh mục.",
        ),
        ({"start_date": ""}, "Ngày vào làm", "Cần nhập ngày vào làm khi có thông tin làm việc."),
        (
            {"start_date": "01/01/1990", "received_date": "01/01/1990"},
            "Ngày vào làm",
            "Ngày vào làm phải sau ngày sinh.",
        ),
        (
            {"received_date": "02/02/2023"},
            "Ngày tiếp nhận",
            "Ngày tiếp nhận không được sau ngày vào làm.",
        ),
        (
            {"work_status": ""},
            "Trạng thái làm việc",
            "Cần nhập trạng thái làm việc khi có thông tin làm việc.",
        ),
        (
            {"work_status": "Lạ"},
            "Trạng thái làm việc",
            "Trạng thái làm việc không hợp lệ. Hãy chọn từ danh sách.",
        ),
        (
            {"work_status": "Đã nghỉ việc"},
            "Ngày nghỉ việc",
            "Trạng thái Đã nghỉ việc cần ngày nghỉ và lý do nghỉ.",
        ),
        (
            {
                "work_status": "Đã nghỉ việc",
                "resign_date": "01/02/2023",
                "resign_reason": "Tự nghỉ",
            },
            "Ngày nghỉ việc",
            "Ngày nghỉ việc phải sau ngày vào làm.",
        ),
        (
            {"resign_date": "01/06/2023"},
            "Ngày nghỉ việc",
            "Chỉ nhập ngày nghỉ việc và lý do nghỉ khi trạng thái là Đã nghỉ việc.",
        ),
        (
            {
                "work_status": "Đã nghỉ việc",
                "resign_date": "01/06/2023",
                "resign_reason": "Vì lý do",
            },
            "Lý do nghỉ",
            "Lý do nghỉ không hợp lệ. Hãy chọn từ danh sách.",
        ),
    ],
)
def test_loi_phan_b(manager, catalog, over, column, message):
    result = run(manager, [good(**work(**over))])
    assert result.imported == 0
    assert [(i.column, i.message) for i in result.errors] == [(column, message)]
    assert not Worker.objects.exists()  # dòng lỗi không để lại hồ sơ nào


def test_ma_nv_trung_csdl_va_trung_dong_khac_trong_tep(manager, catalog):
    other = make_worker_full()
    Worker.objects.filter(pk=other.pk).update(employee_code="CN-00099")
    rows = [
        good(**work(employee_code="CN-00099")),
        good(**work(employee_code="CN-00500")),
        good(**work(employee_code="CN-00500")),
    ]
    result = run(manager, rows)
    assert result.imported == 1
    assert messages(result) == [
        "Dòng 2 – Mã nhân viên: Mã nhân viên CN-00099 đã được dùng.",
        "Dòng 4 – Mã nhân viên: Mã nhân viên CN-00500 trùng với dòng 3 trong cùng tệp.",
    ]


@pytest.mark.parametrize(
    ("over", "message"),
    [
        (
            {"department": "Kho Vận", "section": "Chuyền May 1"},
            "Bộ phận “Chuyền May 1” không thuộc phòng ban “Kho Vận”.",
        ),
        (
            {"section": "Chuyền Trùng", "department": ""},
            "Có nhiều bộ phận tên “Chuyền Trùng”; hãy ghi thêm phòng ban.",
        ),
        (
            {"section": "Bộ phận lạ"},
            "Không tìm thấy “Bộ phận lạ” trong danh mục. Hãy chọn từ sheet Danh mục.",
        ),
        ({"team": "Tổ Kho"}, "Tổ “Tổ Kho” không thuộc bộ phận “Chuyền May 1”."),
        ({"team": "Tổ lạ"}, "Không tìm thấy “Tổ lạ” trong danh mục. Hãy chọn từ sheet Danh mục."),
        (
            {"department": "Phòng lạ"},
            "Không tìm thấy “Phòng lạ” trong danh mục. Hãy chọn từ sheet Danh mục.",
        ),
        ({"section": "", "team": ""}, "Cần nhập bộ phận (B3) khi có phòng ban hoặc tổ."),
    ],
)
def test_loi_phong_ban_bo_phan_to(manager, catalog, over, message):
    result = run(manager, [good(**work(**over))])
    assert result.imported == 0 and message in [i.message for i in result.errors]


def test_bo_phan_khong_bat_buoc_tu_v11_ho_so_vao_nhom_chua_co_bo_phan(manager, catalog):
    result = run(
        manager,
        [good(**work(department="", section="", team=""))],
    )
    assert result.imported == 1 and not result.errors
    assert Employment.objects.get().section is None


def test_ten_bo_phan_trung_hai_phong_ban_ghi_ro_phong_ban_thi_nhan(manager, catalog):
    result = run(manager, [good(**work(section="Chuyền Trùng", department="Kho Vận", team=""))])
    assert result.imported == 1
    assert Employment.objects.get().section.department.name == "Kho Vận"


def test_khop_ten_khong_phan_biet_hoa_thuong_va_khoang_trang(manager, catalog):
    result = run(manager, [good(**work(position="  công nhân   MAY ", shift="ca 1"))])
    assert result.imported == 1


def test_danh_muc_da_ngung_su_dung_khong_duoc_nhan(manager, catalog):
    Position.objects.filter(pk=catalog["position"].pk).update(is_active=False)
    result = run(manager, [good(**work())])
    assert result.imported == 0 and "Không tìm thấy" in result.errors[0].message


# --- Đợt làm việc B12, B13 (v1.1) ------------------------------------------------------------
def test_b12_b13_tao_dot_lam_viec_qua_add_assignment_khong_tao_luong(manager, catalog):
    row = good(**work(client_company="Công ty Mẫu A – Tỉnh Mẫu", assignment_start="01/03/2023"))
    result = run(manager, [row])
    assert result.imported == 1 and not result.errors
    assignment = WorkAssignment.objects.get()
    assert assignment.client_company == catalog["company"]
    assert assignment.position == catalog["position"]  # vị trí = chức danh B5
    assert assignment.start_date == datetime.date(2023, 3, 1) and assignment.end_date is None
    assert assignment.created_by == manager
    assert not SalaryHistory.objects.exists()
    log = AuditLog.objects.get(action="CREATE", object_type="employment.WorkAssignment")
    assert log.user == manager


def test_b12_chap_nhan_gach_noi_thuong_thay_gach_ngang(manager, catalog):
    row = good(**work(client_company="công ty mẫu a - tỉnh mẫu", assignment_start="01/03/2023"))
    assert run(manager, [row]).imported == 1


def test_da_nghi_viec_co_cong_ty_khach_dot_dong_vao_ngay_nghi(manager, catalog):
    row = good(
        **work(
            work_status="Đã nghỉ việc",
            resign_date="30/06/2023",
            resign_reason="Hết hợp đồng",
            client_company="Công ty Mẫu A – Tỉnh Mẫu",
            assignment_start="01/03/2023",
        )
    )
    result = run(manager, [row])
    assert result.imported == 1 and not result.errors
    employment = Employment.objects.get()
    assert employment.work_status == "RESIGNED"
    assert employment.resign_date == datetime.date(2023, 6, 30)
    assert employment.resign_reason == "CONTRACT_END"
    assignment = WorkAssignment.objects.get()
    assert assignment.end_date == datetime.date(2023, 6, 30)
    history = EmploymentHistory.objects.get()
    assert history.to_work_status == "RESIGNED"


@pytest.mark.parametrize(
    ("over", "column", "message"),
    [
        (
            {"client_company": "Công ty Mẫu A – Tỉnh Mẫu", "assignment_start": ""},
            "Ngày bắt đầu đợt",
            "Cần nhập ngày bắt đầu đợt khi có công ty khách.",
        ),
        (
            {"assignment_start": "01/03/2023"},
            "Ngày bắt đầu đợt",
            "Chỉ nhập ngày bắt đầu đợt khi có công ty khách.",
        ),
        (
            {"client_company": "Công ty Mẫu A – Tỉnh Khác", "assignment_start": "01/03/2023"},
            "Công ty khách",
            "Công ty khách “Công ty Mẫu A – Tỉnh Khác” đã ngừng sử dụng "
            "(hoặc không khớp cả tên và địa điểm).",
        ),
        (
            {"client_company": "Công ty Mẫu A", "assignment_start": "01/03/2023"},
            "Công ty khách",
            "Công ty khách “Công ty Mẫu A” đã ngừng sử dụng (hoặc không khớp cả tên và địa điểm).",
        ),
        (
            {"client_company": "Công ty Mẫu A – Tỉnh Mẫu", "assignment_start": "01/01/1990"},
            "Ngày bắt đầu đợt",
            "Ngày bắt đầu đợt phải sau ngày sinh.",
        ),
    ],
)
def test_loi_b12_b13(manager, catalog, over, column, message):
    result = run(manager, [good(**work(**over))])
    assert result.imported == 0
    assert [(i.column, i.message) for i in result.errors] == [(column, message)]


def test_cong_ty_khach_ngung_su_dung_bi_tu_choi(manager, catalog):
    ClientCompany.objects.filter(pk=catalog["company"].pk).update(is_active=False)
    row = good(**work(client_company="Công ty Mẫu A – Tỉnh Mẫu", assignment_start="01/03/2023"))
    assert run(manager, [row]).imported == 0


def test_ngay_bat_dau_dot_sau_ngay_nghi_viec_bi_loi(manager, catalog):
    row = good(
        **work(
            work_status="Đã nghỉ việc",
            resign_date="30/06/2023",
            resign_reason="Tự nghỉ",
            client_company="Công ty Mẫu A – Tỉnh Mẫu",
            assignment_start="01/09/2023",
        )
    )
    result = run(manager, [row])
    assert messages(result) == [
        "Dòng 2 – Ngày bắt đầu đợt: Ngày bắt đầu đợt không được sau ngày nghỉ việc."
    ]


def test_loi_o_buoc_sau_hoan_tac_ca_dong_khong_de_lai_ho_so_nua_chung(
    manager, catalog, monkeypatch
):
    from apps.employment.services import EmploymentError

    def boom(*args, **kwargs):
        raise EmploymentError({"position": "Chọn chức danh đang sử dụng."})

    monkeypatch.setattr(importer, "import_employment", boom)
    result = run(manager, [good(**work()), good()])
    assert result.imported == 1  # dòng chỉ có phần A vẫn nhập
    assert messages(result) == ["Dòng 2 – Chức danh: Chọn chức danh đang sử dụng."]
    assert Worker.objects.count() == 1 and not Employment.objects.exists()


# --- Lỗi cả tệp (không nhập dòng nào) -------------------------------------------------------
def test_khong_phai_xlsx_that(manager):
    for data in (b"khong phai excel", DOCX, b"", b"PK\x03\x04" + b"x" * 40):
        result = importer.import_workbook(manager, data)
        assert result.file_error == "Tệp phải là file Excel .xlsx. Hãy tải file mẫu và nhập lại."
        assert result.read == 0 and not Worker.objects.exists()


def test_tep_xlsx_hong_noi_dung_bao_khong_hop_le(manager):
    result = importer.import_workbook(manager, XLSX)
    assert result.file_error == "Tệp Excel không hợp lệ."


def test_tep_qua_10_mb(manager):
    result = importer.import_workbook(manager, b"x" * (importer.MAX_BYTES + 1))
    assert result.file_error.startswith("Tệp vượt giới hạn 10 MB hoặc ")


def test_qua_gioi_han_so_dong_khong_nhap_dong_nao(manager, monkeypatch):
    monkeypatch.setattr(importer, "MAX_ROWS", 3)
    result = run(manager, [good() for _ in range(4)])
    assert (
        "vượt giới hạn" in result.file_error
        and "Hãy chia thành nhiều tệp nhỏ hơn." in result.file_error
    )
    assert not Worker.objects.exists() and result.imported == 0
    assert run(manager, [good() for _ in range(3)]).imported == 3  # đúng giới hạn thì nhập


def test_dong_trong_khong_tinh_vao_gioi_han(manager, monkeypatch):
    monkeypatch.setattr(importer, "MAX_ROWS", 2)
    result = run(manager, [good(), {}, {}, {}, good()])
    assert result.imported == 2 and not result.file_error


def test_thieu_sheet_ho_so(manager):
    result = importer.import_workbook(manager, build([good()], sheet="Sheet khác"))
    assert result.file_error == "Không thấy sheet “Hồ sơ”. Hãy dùng file mẫu mới nhất."
    assert not Worker.objects.exists()


def test_tieu_de_khong_khop_bao_ten_cot(manager):
    headers = list(HEADERS)
    headers[2] = "Ngày sinh nhật"  # cột C
    result = importer.import_workbook(manager, build([good()], headers=headers))
    assert (
        result.file_error == "Tiêu đề cột không khớp file mẫu (cột C). Hãy dùng file mẫu mới nhất."
    )
    assert not Worker.objects.exists()
    swapped = list(HEADERS)
    swapped[0], swapped[1] = swapped[1], swapped[0]
    assert "(cột A)" in importer.import_workbook(manager, build([], headers=swapped)).file_error
    assert (
        "(cột AH)" in importer.import_workbook(manager, build([], headers=HEADERS[:-1])).file_error
    )


def test_zip_bomb_bi_chan_truoc_khi_openpyxl_mo(manager, monkeypatch):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "<x/>")
        archive.writestr("xl/workbook.xml", "<x/>")
        archive.writestr("xl/worksheets/sheet1.xml", b"\x00" * (30 * 1024 * 1024))
    bomb = buffer.getvalue()
    assert len(bomb) < 1024 * 1024  # tệp nhỏ nhưng bung ra 30 MB, tỉ lệ nén > 100 lần

    def never(*args, **kwargs):
        raise AssertionError("openpyxl không được gọi với zip bomb")

    monkeypatch.setattr(importer, "load_workbook", never)
    result = importer.import_workbook(manager, bomb)
    assert result.file_error == "Tệp Excel không hợp lệ." and not Worker.objects.exists()


def test_zip_tong_giai_nen_qua_100_mb_bi_chan(manager, monkeypatch):
    monkeypatch.setattr(excel, "MAX_UNZIPPED_BYTES", 60_000)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        archive.writestr("[Content_Types].xml", "<x/>")
        archive.writestr("xl/workbook.xml", "<x/>")
        archive.writestr("xl/big.bin", b"a" * 70_000)
    monkeypatch.setattr(importer, "load_workbook", lambda *a, **k: pytest.fail("không được mở"))
    assert (
        importer.import_workbook(manager, buffer.getvalue()).file_error == "Tệp Excel không hợp lệ."
    )


# --- File mẫu -------------------------------------------------------------------------------
def template_book(catalog=None):
    return load_workbook(io.BytesIO(_bytes(excel_template.build_template())), data_only=False)


def _bytes(book):
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def test_file_mau_co_3_sheet_dung_thu_tu_va_tieu_de_chi_co_dong_1(catalog):
    book = template_book()
    assert book.sheetnames == ["Hồ sơ", "Hướng dẫn", "Danh mục"]
    ws = book["Hồ sơ"]
    assert [c.value for c in ws[1]] == HEADERS and len(HEADERS) == 34
    assert ws.max_row == 1  # không có dòng dữ liệu ví dụ
    assert ws.freeze_panes == "A2"


def test_file_mau_moi_cot_dinh_dang_text_va_co_o_tha_xuong(catalog):
    ws = template_book()["Hồ sơ"]
    from openpyxl.utils import get_column_letter

    for index in range(1, 35):
        assert ws.column_dimensions[get_column_letter(index)].number_format == "@"
    validations = ws.data_validations.dataValidation
    ranges = " ".join(str(v.sqref) for v in validations)
    assert len(validations) == 10
    assert "D2:D1001" in ranges  # giới tính (A4)
    assert any("Danh mục" in v.formula1 for v in validations)


def test_file_mau_sheet_danh_muc_lay_tu_he_thong(catalog):
    ws = template_book()[SHEET_CATALOG]
    columns = {c[0].value: [x.value for x in c[1:] if x.value] for c in ws.iter_cols()}
    assert columns["Phòng ban"] == ["Kho Vận", "Xưởng May"] or set(columns["Phòng ban"]) == {
        "Xưởng May",
        "Kho Vận",
    }
    assert "Chuyền May 1" in columns["Bộ phận"] and "Tổ 1" in columns["Tổ"]
    assert columns["Công ty khách (tên – địa điểm)"] == ["Công ty Mẫu A – Tỉnh Mẫu"]
    assert columns["Giới tính"] == ["Nam", "Nữ"]
    assert columns["Trạng thái làm việc"][-1] == "Đã nghỉ việc"
    assert len(columns["Loại giấy tờ"]) == 3 and len(columns["Lý do nghỉ"]) == 4


def test_file_mau_danh_muc_bo_muc_ngung_su_dung_va_qua_safe_cell(catalog):
    Position.objects.create(name="=CMD()")
    Position.objects.create(name="Đã ngừng", is_active=False)
    ws = template_book()[SHEET_CATALOG]
    values = [c.value for row in ws.iter_rows() for c in row]
    assert "'=CMD()" in values and "Đã ngừng" not in values
    assert all(c.data_type != "f" for row in ws.iter_rows() for c in row)


def test_file_mau_huong_dan_co_gioi_han_va_hai_dong_vi_du_gia(catalog):
    ws = template_book()["Hướng dẫn"]
    text = "\n".join(str(c.value) for row in ws.iter_rows() for c in row if c.value)
    assert f"tối đa {importer.MAX_ROWS} dòng" in text and "10 MB" in text
    for number in ("999000000001", "999000000002"):
        assert number in text
    assert "Lương không nhập" in text


@pytest.mark.parametrize("role", ["ADMIN", "HR_MANAGER", "HR_STAFF"])
def test_tai_file_mau_va_trang_nhap_theo_vai_tro(role, catalog):
    client = login_client(make_user(role))
    response = client.get("/ho-so/nhap-excel/file-mau/")
    assert response.status_code == 200 and ".xlsx" in response["Content-Disposition"]
    assert is_book(response.content)
    assert client.get("/ho-so/nhap-excel/").status_code == 200


def is_book(data):
    return excel.is_xlsx(data)


def test_viewer_va_nguoi_chua_dang_nhap_khong_vao_duoc():
    from django.test import Client

    viewer = login_client(make_user("VIEWER"))
    for path in ("/ho-so/nhap-excel/", "/ho-so/nhap-excel/file-mau/"):
        assert viewer.get(path).status_code == 403
    assert viewer.post("/ho-so/nhap-excel/", {}).status_code == 403
    assert Client().get("/ho-so/nhap-excel/").status_code == 302


def test_khu_hoi_file_mau_dien_hai_dong_vi_du_roi_nhap_thanh_cong(manager, catalog):
    """Hai dòng ví dụ ở sheet Hướng dẫn nhập được nếu danh mục khớp (sau khi tạo danh mục mẫu)."""
    ClientCompany.objects.filter(pk=catalog["company"].pk).delete()
    ClientCompany.objects.create(name="Công ty Mẫu A", location="Tỉnh Mẫu")
    Position.objects.filter(pk=catalog["position"].pk).update(name="Công nhân may")
    dep = Department.objects.get(name="Xưởng May")
    Section.objects.filter(department=dep, name="Chuyền May 1").update(name="Chuyền May 1")
    rows = [
        {c.key: EXAMPLES[c.key][0] for c in COLUMNS},
        {c.key: EXAMPLES[c.key][1] for c in COLUMNS},
    ]
    result = run(manager, rows)
    assert result.imported == 2 and not result.errors, messages(result)
    worker = Worker.objects.get(employee_code="CN-00012")
    assert worker.full_name == "Lê Văn Thử"
    assert WorkAssignment.objects.get(worker=worker).start_date == datetime.date(2023, 3, 1)
    assert Worker.objects.get(full_name="Trần Thị Mẫu").employee_code is None


# --- Trang nhập -----------------------------------------------------------------------------
def post_file(client, data, name="du-lieu.xlsx"):
    upload = SimpleUploadedFile(name, data)
    return client.post("/ho-so/nhap-excel/", {"file": upload})


def test_trang_ket_qua_tom_tat_bang_loi_canh_bao_va_nhac_nguoi_duyet(manager, catalog):
    client = login_client(manager)
    rows = [good(), good(phone="1"), good(date_of_birth=datetime.date(1995, 3, 15))]
    response = post_file(client, build(rows))
    content = response.content.decode()
    assert response.status_code == 200
    assert "Đã đọc 3 dòng. Nhập thành công 2 hồ sơ. 1 dòng lỗi. 1 cảnh báo." in content
    assert "Số điện thoại phải gồm 10 chữ số, bắt đầu bằng 0." in content
    assert "Ô ngày của Excel có thể bị đảo ngày/tháng; kiểm tra lại." in content
    assert "cần một tài khoản khác duyệt" in content
    assert (
        "/ho-so/?trang_thai_ho_so=DRAFT&amp;tao_tu="
        + TODAY.strftime("%d/%m/%Y").replace("/", "%2F")
        in content
    )


def test_trang_loi_ca_tep_hien_thong_bao_khong_nhap_gi(manager):
    client = login_client(manager)
    content = post_file(client, b"khong phai excel").content.decode()
    assert "Tệp phải là file Excel .xlsx. Hãy tải file mẫu và nhập lại." in content
    assert not Worker.objects.exists()


def test_post_khong_chon_tep_bao_loi_o_form(manager):
    content = login_client(manager).post("/ho-so/nhap-excel/", {}).content.decode()
    assert "Chọn tệp Excel để nhập." in content


def test_ten_tep_goc_khong_vao_nhat_ky(manager):
    post_file(login_client(manager), build([good()]), name="Danh-sach-Nguyen-Van-A.xlsx")
    entry = AuditLog.objects.get(action="IMPORT")
    assert "Nguyen" not in f"{entry.note}{entry.object_repr}{entry.changes}"


def test_hr_nhap_qua_giao_dien_dong_co_phan_b_bao_loi(hr, catalog):
    content = post_file(login_client(hr), build([good(), good(**work())])).content.decode()
    assert "Nhập thành công 1 hồ sơ. 1 dòng lỗi." in content
    assert "Chỉ Admin hoặc Quản lý nhân sự được nhập thông tin làm việc." in content
