"""Hồi quy cho các điểm /code-review Phase 7: ô Excel quá dài, phòng ban giữ khi ngày sai, tên người
thực hiện thiếu họ tên, che lý do người gõ ở dòng nhật ký cũ của hồ sơ đã ẩn danh."""

import pytest
from django.db import DataError

from apps.audit.models import AuditLog
from apps.audit.services import log
from apps.core.choices import AuditAction
from apps.core.models import Department
from apps.reports import importer, reports
from apps.reports.forms import ReportFilterForm
from apps.workers import retention
from apps.workers.models import Worker
from tests.factories import (
    at,
    freeze_time,
    login_client,
    make_user,
    make_worker_full,
)
from tests.test_excel_import import build, good, messages, run
from tests.test_retention import archive_manual

pytestmark = pytest.mark.django_db


# --- Ô Excel quá dài --------------------------------------------------------------------------
@pytest.mark.parametrize("key", sorted(importer.MAX_LENGTHS))
def test_o_qua_dai_bao_loi_dong_khong_lam_hong_ca_tep(key):
    limit = importer.MAX_LENGTHS[key]
    manager = make_user("HR_MANAGER")
    too_long = "A" * (limit + 1)
    if key == "email":
        too_long = "a" * (limit - 10) + "@example.com"  # email dài hơn giới hạn
    result = run(manager, [good(**{key: too_long}), good()])
    assert result.imported == 1 and result.error_rows == 1
    assert [i.row for i in result.errors] == [2]
    assert f"tối đa {limit} ký tự" in messages(result)[0] or key == "email"
    assert Worker.objects.count() == 1


def test_o_dung_gioi_han_do_dai_van_nhap_duoc():
    manager = make_user("HR_MANAGER")
    row = good(hometown="Q" * importer.MAX_LENGTHS["hometown"])
    assert run(manager, [row]).imported == 1


def test_loi_co_so_du_lieu_bat_ngo_o_mot_dong_chi_bo_qua_dong_do(monkeypatch):
    manager = make_user("HR_MANAGER")
    real = importer.create_worker
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise DataError("value too long")
        return real(*args, **kwargs)

    monkeypatch.setattr(importer, "create_worker", flaky)
    result = run(manager, [good(), good(), good()])
    assert result.imported == 2 and [i.row for i in result.errors] == [3]
    assert "ô quá dài hoặc không hợp lệ" in messages(result)[0]
    assert AuditLog.objects.filter(action="IMPORT").count() == 1  # vẫn ghi nhật ký cả lần


def test_loi_khong_luong_truoc_van_ghi_nhat_ky_import_cho_cac_dong_da_nhap(monkeypatch):
    manager = make_user("HR_MANAGER")
    real = importer.create_worker
    calls = {"n": 0}

    def boom(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("lỗi bất ngờ")
        return real(*args, **kwargs)

    monkeypatch.setattr(importer, "create_worker", boom)
    with pytest.raises(RuntimeError):
        importer.import_workbook(manager, build([good(), good()]))
    assert Worker.objects.count() == 1  # dòng đầu đã commit
    entry = AuditLog.objects.get(action="IMPORT")
    assert "nhập 0" in entry.note or "nhập 1" in entry.note  # có dòng nhật ký cho lần nhập dở


# --- Báo cáo: ngày sai không làm mất lọc phòng ban -----------------------------------------------
def test_ngay_sai_van_giu_loc_phong_ban():
    department = Department.objects.create(name="Phòng giữ lọc")
    form = ReportFilterForm(
        {
            "loai": "gioi-tinh",
            "tu_ngay": "01/12/2026",
            "den_ngay": "01/01/2026",
            "phong_ban": str(department.pk),
        }
    )
    assert not form.is_valid() and "den_ngay" in form.errors
    ctx = form.context()
    assert ctx.department == department  # phòng ban hợp lệ vẫn áp dụng
    assert ctx.start <= ctx.end  # ngày sai dùng khoảng mặc định
    assert reports.build_report(ctx).scope.endswith("Không lọc theo khoảng ngày")
    assert "Phòng giữ lọc" in reports.build_report(ctx).scope


def test_trang_bao_cao_ngay_sai_hien_dung_phong_ban_da_chon():
    department = Department.objects.create(name="Phòng hiện đúng")
    page = login_client(make_user("ADMIN")).get(
        f"/bao-cao/?loai=gioi-tinh&tu_ngay=01/12/2026&den_ngay=01/01/2026&phong_ban={department.pk}"
    )
    content = page.content.decode()
    assert "Đến ngày phải sau hoặc bằng từ ngày." in content
    assert "Phòng ban: Phòng hiện đúng" in content


# --- Nhật ký ---------------------------------------------------------------------------------
def test_nguoi_thuc_hien_thieu_ho_ten_hien_ten_tai_khoan():
    user = make_user("HR_STAFF")
    user.full_name = ""
    user.save()
    worker = make_worker_full()
    entry = log(AuditAction.UPDATE, user=user, obj=worker, note="Thử")
    content = login_client(make_user("ADMIN")).get(f"/nhat-ky/{entry.pk}/").content.decode()
    assert user.username in content
    assert user.username in login_client(make_user("ADMIN")).get("/nhat-ky/").content.decode()


def test_dong_cu_truoc_phase_7_cua_ho_so_da_an_danh_che_ly_do_nguoi_go():
    """Dòng đổi trạng thái kiểu cũ (lý do người gõ ở note) không được lộ khi hồ sơ đã ẩn danh."""
    worker = make_worker_full()
    staff = make_user("HR_STAFF")
    old = log(
        AuditAction.STATUS_CHANGE,
        user=staff,
        obj=worker,
        changes={"verification_status": ("DRAFT", "PENDING")},
        note="Trả lại: anh Nguyễn Văn A thiếu giấy khai sinh",
    )
    system = log(
        AuditAction.STATUS_CHANGE,
        user=None,
        obj=worker,
        changes={"verification_status": ("PENDING", "ARCHIVED")},
        note=f"Hệ thống tự chuyển hồ sơ {worker.worker_code} sang Lưu trữ",
    )
    admin = make_user("ADMIN")
    client = login_client(admin)
    assert "anh Nguyễn Văn A" in client.get(f"/nhat-ky/{old.pk}/").content.decode()  # chưa ẩn danh
    with freeze_time(at(2025, 1, 5)):
        archive_manual(worker, at(2025, 1, 5))
    retention.anonymize([worker], "EXPIRED", admin)
    assert "anh Nguyễn Văn A" not in client.get(f"/nhat-ky/{old.pk}/").content.decode()
    assert "(đã ẩn danh)" in client.get(f"/nhat-ky/{old.pk}/").content.decode()
    # Lý do hệ thống chỉ có mã hồ sơ: giữ nguyên.
    assert worker.worker_code in client.get(f"/nhat-ky/{system.pk}/").content.decode()
