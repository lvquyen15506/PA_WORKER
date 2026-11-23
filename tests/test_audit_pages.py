"""Trang nhật ký /nhat-ky/ và /nhat-ky/<id>/ (Phase 7, bước 7; trang.md 5.9; câu 11, 30)."""

import datetime
import re

import pytest
from django.utils import timezone

from apps.audit.models import AuditLog, AuditPersonalValue
from apps.audit.services import log
from apps.core.choices import AuditAction
from apps.workers import retention
from apps.workers.models import IdentityDocument
from tests.factories import (
    login_client,
    make_user,
    make_worker_full,
    make_worker_in_status,
)

pytestmark = pytest.mark.django_db
TODAY = timezone.localdate()


def get(role, path, expect=200):
    response = login_client(make_user(role)).get(path)
    assert response.status_code == expect, (role, path, response.status_code)
    return response.content.decode()


def total(content):
    match = re.search(r"Hiển thị[^/]*/\s*(\d+)", content)
    return int(match.group(1)) if match else 0


def activity(n=1, *, worker=None, user=None):
    """Tạo n dòng nhật ký thật qua log() (make_worker_full không tự ghi nhật ký)."""
    worker = worker or make_worker_full()
    user = user or make_user("HR_STAFF")
    return [
        log(
            AuditAction.UPDATE,
            user=user,
            obj=worker,
            changes={"note": ("", f"ghi chú {i}")},
            note=f"lần {i}",
        )
        for i in range(n)
    ]


# --- Quyền ------------------------------------------------------------------------------------
def test_chua_dang_nhap_chuyen_ve_dang_nhap():
    from django.test import Client

    for path in ("/nhat-ky/", "/nhat-ky/1/"):
        response = Client().get(path)
        assert response.status_code == 302 and response.url.startswith("/dang-nhap/")


@pytest.mark.parametrize(
    ("role", "status"),
    [("ADMIN", 200), ("HR_MANAGER", 200), ("HR_STAFF", 403), ("VIEWER", 403)],
)
def test_chi_admin_va_quan_ly_xem_nhat_ky(role, status):
    entry = activity()[0]
    get(role, "/nhat-ky/", status)
    get(role, f"/nhat-ky/{entry.pk}/", status)


def test_khong_co_thao_tac_sua_xoa_va_dong_khong_ton_tai_la_404():
    activity()
    content = get("ADMIN", "/nhat-ky/")
    table = content[content.index("<table") : content.index("</table>")]
    assert "<form" not in table and "<button" not in table  # bảng chỉ có liên kết xem
    assert "bi-pencil" not in table and "bi-trash" not in table and "bi-archive" not in table
    assert table.count("bi-eye") == 1  # duy nhất nút xem chi tiết
    get("ADMIN", "/nhat-ky/999999/", 404)
    client = login_client(make_user("ADMIN"))
    assert client.post("/nhat-ky/", {}).status_code == 405
    assert client.post("/nhat-ky/1/", {}).status_code == 405


def test_xem_nhat_ky_khong_ghi_nhat_ky():
    make_worker_full()
    before = AuditLog.objects.count()
    login_client(make_user("ADMIN")).get("/nhat-ky/")
    assert AuditLog.objects.count() == before


# --- Danh sách --------------------------------------------------------------------------------
def test_danh_sach_co_cot_dung_moi_nhat_truoc_va_phan_trang_20():
    activity(25)
    content = get("ADMIN", "/nhat-ky/")
    for column in ("Thời điểm", "Người thực hiện", "Hành động", "Đối tượng", "Trường thay đổi"):
        assert column in content
    assert total(content) == AuditLog.objects.count() > 20
    page2 = get("ADMIN", "/nhat-ky/?trang=2")
    assert "Hiển thị 21–" in page2
    newest = AuditLog.objects.order_by("-created_at", "-id").first()
    assert f"/nhat-ky/{newest.pk}/" in content.split("<tbody>")[1].split("</tr>")[0]


def test_loc_theo_nguoi_thuc_hien_ke_ca_he_thong():
    worker = make_worker_full()
    manager = make_user("HR_MANAGER")
    log(AuditAction.UPDATE, user=manager, obj=worker, changes={"note": ("", "x")}, note="Manager")
    log(AuditAction.UPDATE, user=None, obj=worker, note="Do he thong")
    mine = get("ADMIN", f"/nhat-ky/?nguoi={manager.pk}")
    assert total(mine) == AuditLog.objects.filter(user=manager).count() == 1
    system = get("ADMIN", "/nhat-ky/?nguoi=he-thong")
    assert total(system) == AuditLog.objects.filter(user__isnull=True).count() == 1
    assert "Hệ thống" in system


def test_loc_theo_ma_ho_so_ma_nhan_vien_khong_phan_biet_hoa_thuong():
    a = make_worker_full()
    b = make_worker_full()
    from apps.workers.models import Worker

    Worker.objects.filter(pk=b.pk).update(employee_code="CN-00077")
    expected_a = AuditLog.objects.filter(worker=a).count()
    assert total(get("ADMIN", f"/nhat-ky/?ho_so={a.worker_code.lower()}")) == expected_a
    assert (
        total(get("ADMIN", "/nhat-ky/?ho_so=cn-00077")) == AuditLog.objects.filter(worker=b).count()
    )
    assert total(get("ADMIN", "/nhat-ky/?ho_so=khong-co")) == 0
    assert "Không có dòng nhật ký phù hợp." in get("ADMIN", "/nhat-ky/?ho_so=khong-co")


def test_loc_theo_hanh_dong_va_khoang_ngay():
    worker = make_worker_full()
    log(AuditAction.PRINT, user=make_user("HR_STAFF"), obj=worker, note="In")
    assert total(get("ADMIN", "/nhat-ky/?hanh_dong=PRINT")) == 1
    assert total(get("ADMIN", "/nhat-ky/?hanh_dong=EXPORT")) == 0
    today = TODAY.strftime("%d/%m/%Y")
    yesterday = (TODAY - datetime.timedelta(days=1)).strftime("%d/%m/%Y")
    tomorrow = (TODAY + datetime.timedelta(days=1)).strftime("%d/%m/%Y")
    everything = AuditLog.objects.count()
    assert total(get("ADMIN", f"/nhat-ky/?tu_ngay={today}&den_ngay={today}")) == everything
    assert total(get("ADMIN", f"/nhat-ky/?den_ngay={yesterday}")) == 0
    assert total(get("ADMIN", f"/nhat-ky/?tu_ngay={tomorrow}")) == 0


def test_khoang_ngay_dung_gio_viet_nam_o_hai_dau_mut():
    from tests.factories import at as moment
    from tests.factories import freeze_time

    worker = make_worker_full()
    with freeze_time(moment(2026, 5, 31, 0, 0)):
        first = log(AuditAction.UPDATE, user=None, obj=worker, note="đầu ngày 31")
    with freeze_time(moment(2026, 5, 31, 23, 59)):
        last = log(AuditAction.UPDATE, user=None, obj=worker, note="cuối ngày 31")
    with freeze_time(moment(2026, 6, 1, 0, 0)):
        log(AuditAction.UPDATE, user=None, obj=worker, note="đầu ngày 1")
    with freeze_time(moment(2026, 5, 30, 23, 59)):
        log(AuditAction.UPDATE, user=None, obj=worker, note="cuối ngày 30")
    content = get("ADMIN", "/nhat-ky/?tu_ngay=31/05/2026&den_ngay=31/05/2026")
    assert total(content) == 2  # chỉ hai dòng nằm trong ngày 31 theo giờ Việt Nam
    assert f"/nhat-ky/{first.pk}/" in content and f"/nhat-ky/{last.pk}/" in content


def test_ngay_sai_dinh_dang_bao_loi_khong_sap_trang():
    make_worker_full()
    content = get("ADMIN", "/nhat-ky/?tu_ngay=2026-01-01")
    assert "Nhập ngày đúng định dạng dd/mm/yyyy." in content


def test_cot_truong_thay_doi_chi_hien_ten_truong_khong_hien_gia_tri_ca_nhan():
    worker = make_worker_full(full_name="Họ Tên Rất Riêng")
    from apps.workers.services import update_worker

    update_worker(make_user("HR_STAFF"), worker, {"full_name": "Họ Tên Mới Hoàn Toàn"})
    content = get("ADMIN", "/nhat-ky/")
    assert "Họ và tên" in content or "Họ tên" in content
    assert "Họ Tên Rất Riêng" not in content and "Họ Tên Mới Hoàn Toàn" not in content
    assert "(xem giá trị chi tiết)" not in content  # danh sách chỉ ghi tên trường


# --- Chi tiết ---------------------------------------------------------------------------------
def entry_with(worker, field):
    return (
        AuditLog.objects.filter(worker=worker, personal_values__field_name=field)
        .order_by("-id")
        .first()
    )


def test_chi_tiet_giai_ma_gia_tri_truoc_sau_cua_truong_ca_nhan():
    worker = make_worker_full(full_name="Giá Trị Cũ Riêng")
    from apps.workers.services import update_worker

    update_worker(make_user("HR_STAFF"), worker, {"full_name": "Giá Trị Mới Riêng"})
    entry = entry_with(worker, "full_name")
    content = get("HR_MANAGER", f"/nhat-ky/{entry.pk}/")
    assert "Giá Trị Cũ Riêng" in content and "Giá Trị Mới Riêng" in content
    assert worker.worker_code in content
    assert "Giá trị trước" in content and "Giá trị sau" in content


def test_chi_tiet_so_cccd_va_cmnd_luon_che():
    worker = make_worker_full()
    from apps.workers.services import update_worker

    update_worker(
        make_user("HR_STAFF"),
        worker,
        {"id_number": "999314159265", "old_id_number": "999271828"},
    )
    entry = entry_with(worker, "identity.id_number")
    assert entry is not None
    content = get("ADMIN", f"/nhat-ky/{entry.pk}/")
    assert "999314159265" not in content and "999271828" not in content
    assert "9993••••9265" in content


def test_chi_tiet_truong_khong_ca_nhan_hien_gia_tri_ngay_trong_nhat_ky():
    worker = make_worker_in_status("PENDING")
    entry = AuditLog.objects.filter(worker=worker, action="STATUS_CHANGE").order_by("-id").first()
    content = get("ADMIN", f"/nhat-ky/{entry.pk}/")
    assert "Trạng thái hồ sơ" in content and "Nháp" in content and "Chờ duyệt" in content


def test_chi_tiet_ho_so_da_an_danh_hien_da_an_danh_khong_lo_gia_tri():
    from apps.workers.services import update_worker
    from apps.workers.workflow import transition

    worker = make_worker_full(full_name="Tên Sẽ Bị Xóa")
    staff = make_user("HR_STAFF")
    update_worker(staff, worker, {"full_name": "Tên Mới Sẽ Bị Xóa"})
    entry = entry_with(worker, "full_name")
    assert entry is not None
    transition(worker, "ARCHIVED", staff)
    admin = make_user("ADMIN")
    retention.anonymize_on_request(
        worker, admin, reason="Theo đơn", request_ref="Đơn 1", confirm_code=worker.worker_code
    )
    assert not AuditPersonalValue.objects.filter(worker=worker).exists()
    content = get("ADMIN", f"/nhat-ky/{entry.pk}/")
    assert "(đã ẩn danh)" in content
    assert "Tên Sẽ Bị Xóa" not in content and "Tên Mới Sẽ Bị Xóa" not in content


def test_chi_tiet_dong_khong_co_thay_doi_hien_thong_bao():
    worker = make_worker_full()
    entry = log(AuditAction.PRINT, user=make_user("HR_STAFF"), obj=worker, note="In mẫu đồng ý")
    content = get("ADMIN", f"/nhat-ky/{entry.pk}/")
    assert "Dòng nhật ký này không có thay đổi giá trị." in content
    assert "In mẫu đồng ý" in content and "In báo cáo" in content


def test_chi_tiet_dong_he_thong_hien_he_thong():
    worker = make_worker_full()
    entry = log(AuditAction.UPDATE, user=None, obj=worker, note="Tự động")
    assert "Hệ thống" in get("ADMIN", f"/nhat-ky/{entry.pk}/")


def test_tab_lich_su_cua_ho_so_van_giong_truoc_khi_tach_ham():
    worker = make_worker_full(full_name="Tên Tab Cũ")
    from apps.workers.services import update_worker

    update_worker(make_user("HR_STAFF"), worker, {"full_name": "Tên Tab Mới"})
    detail = get("HR_MANAGER", f"/ho-so/{worker.pk}/lich-su/chi-tiet/")
    assert "Tên Tab Cũ" in detail and "Tên Tab Mới" in detail
    number = IdentityDocument.objects.get(worker=worker).id_number_enc
    assert number not in detail


def test_so_truy_van_danh_sach_khong_tang_theo_so_dong(django_assert_max_num_queries):
    client = login_client(make_user("ADMIN"))
    client.get("/nhat-ky/")
    with django_assert_max_num_queries(12):
        assert client.get("/nhat-ky/").status_code == 200
    for _ in range(25):
        make_worker_full()
    with django_assert_max_num_queries(12):
        assert client.get("/nhat-ky/").status_code == 200
