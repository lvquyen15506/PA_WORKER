"""Nút quy trình trên web: gửi duyệt, duyệt, trả lại, từ chối, lưu trữ, mở lại, ẩn danh hóa.

Gồm kịch bản nghiệm thu 6 (gửi duyệt → trả lại → bổ sung → duyệt) và 7 (không tự duyệt)."""

import re

import pytest
from django.test import Client

from apps.audit.models import AuditLog
from apps.core.choices import VerificationStatus as VS
from apps.core.models import ApplicationSource, Position
from apps.documents.models import WorkerDocument
from apps.recruitment.models import Application
from apps.workers.models import AnonymizationRecord, StatusChange, Worker
from tests.factories import (
    login_client,
    make_document,
    make_employment,
    make_user,
    make_worker_full,
    make_worker_in_status,
)

pytestmark = pytest.mark.django_db
STAFF = ["ADMIN", "HR_MANAGER", "HR_STAFF"]
MANAGERS = ["ADMIN", "HR_MANAGER"]


def status_of(worker):
    return Worker.objects.get(pk=worker.pk).verification_status


def post(client, worker, action, data=None, **kw):
    return client.post(f"/ho-so/{worker.pk}/{action}/", data or {}, **kw)


def text(response):
    return response.content.decode()


def flashed(response):
    return [str(m) for m in response.wsgi_request._messages]


# ===== Kịch bản 6: gửi duyệt → trả lại → bổ sung → duyệt ======================================
def test_kich_ban_6_gui_duyet_tra_lai_bo_sung_duyet_co_ly_do_va_nhat_ky():
    hr = make_user("HR_STAFF")
    manager = make_user("HR_MANAGER")
    worker = make_worker_full(created_by=hr)
    c_hr, c_mgr = login_client(hr), login_client(manager)

    # 1. HR gửi duyệt
    response = post(c_hr, worker, "gui-duyet")
    assert response.status_code == 302 and status_of(worker) == VS.PENDING
    assert flashed(response) == ["Đã gửi duyệt hồ sơ."]

    # 2. Quản lý trả lại, có lý do
    response = post(c_mgr, worker, "tra-lai", {"return-reason": "Bổ sung ảnh CCCD mặt sau"})
    assert response.status_code == 302 and status_of(worker) == VS.NEEDS_INFO
    page = text(c_hr.get(f"/ho-so/{worker.pk}/"))
    assert "Trả lại: Bổ sung ảnh CCCD mặt sau" in page  # HR thấy nội dung cần bổ sung

    # 3. HR bổ sung rồi gửi duyệt lại
    make_document(worker, "CCCD_BACK")
    assert post(c_hr, worker, "gui-duyet").status_code == 302
    assert status_of(worker) == VS.PENDING

    # 4. Quản lý duyệt
    response = post(c_mgr, worker, "duyet")
    assert response.status_code == 302 and status_of(worker) == VS.VERIFIED

    changes = list(
        StatusChange.objects.filter(worker=worker).values_list("from_status", "to_status", "reason")
    )
    assert [(a, b) for a, b, _ in changes] == [
        ("", "DRAFT"),
        ("DRAFT", "PENDING"),
        ("PENDING", "NEEDS_INFO"),
        ("NEEDS_INFO", "PENDING"),
        ("PENDING", "VERIFIED"),
    ]
    assert changes[2][2] == "Bổ sung ảnh CCCD mặt sau"
    logs = AuditLog.objects.filter(worker=worker, action="STATUS_CHANGE").order_by("id")
    assert [e.changes["verification_status"] for e in logs] == [
        ["DRAFT", "PENDING"],
        ["PENDING", "NEEDS_INFO"],
        ["NEEDS_INFO", "PENDING"],
        ["PENDING", "VERIFIED"],
    ]
    # Tab lịch sử hiển thị dòng thời gian cho cả HR.
    timeline = text(c_hr.get(f"/ho-so/{worker.pk}/?tab=lich-su"))
    for label in ("Chờ duyệt", "Cần bổ sung", "Đã xác minh"):
        assert label in timeline


# ===== Kịch bản 7: không tự duyệt =============================================================
def test_kich_ban_7_hr_tu_duyet_ho_so_minh_nhap_bi_chan():
    hr = make_user("HR_STAFF")
    worker = make_worker_full(created_by=hr)
    client = login_client(hr)
    post(client, worker, "gui-duyet")
    for action, data in [
        ("duyet", {}),
        ("tra-lai", {"return-reason": "x"}),
        ("tu-choi", {"reject-reason": "x"}),
    ]:
        assert post(client, worker, action, data).status_code == 403
    assert status_of(worker) == VS.PENDING


@pytest.mark.parametrize("role", MANAGERS)
def test_ql_admin_khong_tu_duyet_ho_so_do_minh_tao_hoac_gui(role):
    user = make_user(role)
    worker = make_worker_full(created_by=user)
    client = login_client(user)
    post(client, worker, "gui-duyet")
    assert post(client, worker, "duyet").status_code == 403
    assert post(client, worker, "tra-lai", {"return-reason": "x"}).status_code == 403
    assert post(client, worker, "tu-choi", {"reject-reason": "x"}).status_code == 403
    assert status_of(worker) == VS.PENDING
    page = text(client.get(f"/ho-so/{worker.pk}/"))
    assert "không duyệt được" in page
    assert header_labels(page) == []  # không có nút Duyệt, Trả lại, Từ chối


def test_nguoi_khac_duyet_duoc():
    worker = make_worker_full()
    post(login_client(worker.created_by), worker, "gui-duyet")
    assert post(login_client(make_user("ADMIN")), worker, "duyet").status_code == 302
    assert status_of(worker) == VS.VERIFIED


# ===== Ma trận quyền =============================================================================
@pytest.mark.parametrize("role", ["HR_STAFF", "VIEWER"])
@pytest.mark.parametrize("action", ["duyet", "tra-lai", "tu-choi"])
def test_hr_va_viewer_khong_duyet_tra_lai_tu_choi(role, action):
    worker = make_worker_in_status(VS.PENDING)
    response = post(login_client(make_user(role)), worker, action, {"x": "y"})
    assert response.status_code == 403 and status_of(worker) == VS.PENDING


def test_viewer_khong_gui_duyet_luu_tru_mo_lai_an_danh():
    worker = make_worker_in_status(VS.DRAFT)
    archived = make_worker_in_status(VS.ARCHIVED)
    client = login_client(make_user("VIEWER"))
    assert post(client, worker, "gui-duyet").status_code == 403
    assert post(client, worker, "luu-tru").status_code == 403
    assert client.get(f"/ho-so/{archived.pk}/mo-lai/").status_code == 403
    assert post(client, archived, "an-danh-theo-yeu-cau").status_code == 403


@pytest.mark.parametrize("status", [VS.PENDING, VS.REJECTED, VS.ARCHIVED])
def test_gui_duyet_sai_trang_thai_khong_doi_gi_va_bao_loi(status):
    worker = make_worker_in_status(status)
    response = post(login_client(make_user("HR_STAFF")), worker, "gui-duyet")
    assert response.status_code == 302 and status_of(worker) == status
    assert any("Không thể chuyển" in m for m in flashed(response))


def test_gui_duyet_ho_so_da_xac_minh_la_403_vi_chi_tu_ve_cho_duyet_khi_sua_dinh_danh():
    worker = make_worker_in_status(VS.VERIFIED)
    response = post(login_client(make_user("ADMIN")), worker, "gui-duyet")
    assert response.status_code == 403 and status_of(worker) == VS.VERIFIED


def test_gui_duyet_thieu_truong_bao_ro_tung_truong():
    from apps.workers.models import DataConsent

    worker = make_worker_full()
    Worker.objects.filter(pk=worker.pk).update(date_of_birth=None)
    DataConsent.objects.filter(worker=worker).delete()
    response = post(login_client(worker.created_by), worker, "gui-duyet")
    message = flashed(response)[0]
    assert "chưa đủ thông tin" in message and "Thiếu ngày sinh." in message
    assert "Chưa ghi nhận đồng ý xử lý dữ liệu cá nhân." in message
    assert status_of(worker) == VS.DRAFT


@pytest.mark.parametrize(
    "action", ["gui-duyet", "duyet", "tra-lai", "tu-choi", "luu-tru", "an-danh-theo-yeu-cau"]
)
def test_nut_quy_trinh_chi_nhan_post(action):
    worker = make_worker_in_status(VS.DRAFT)
    assert login_client(make_user("ADMIN")).get(f"/ho-so/{worker.pk}/{action}/").status_code == 405


def test_nut_quy_trinh_yeu_cau_csrf():
    worker = make_worker_in_status(VS.PENDING)
    logged = login_client(make_user("ADMIN"))
    client = Client(enforce_csrf_checks=True)
    client.cookies = logged.cookies
    for action in ("duyet", "tra-lai", "tu-choi", "luu-tru", "gui-duyet", "an-danh-theo-yeu-cau"):
        assert post(client, worker, action).status_code == 403
    assert status_of(worker) == VS.PENDING


def test_ho_so_khong_ton_tai_la_404():
    assert login_client(make_user("ADMIN")).post("/ho-so/99999/duyet/").status_code == 404


# ===== Hộp lý do: lỗi ngay dưới ô, hộp mở sẵn ===============================================
@pytest.mark.parametrize(
    ("action", "prefix", "modal"),
    [("tra-lai", "return", "return-modal"), ("tu-choi", "reject", "reject-modal")],
)
@pytest.mark.parametrize("reason", ["", "   "])
def test_thieu_ly_do_hien_lai_hop_thoai_voi_loi_duoi_o(action, prefix, modal, reason):
    worker = make_worker_in_status(VS.PENDING)
    response = post(
        login_client(make_user("HR_MANAGER")), worker, action, {f"{prefix}-reason": reason}
    )
    page = text(response)
    assert response.status_code == 200 and status_of(worker) == VS.PENDING
    assert "Nhập lý do." in page
    assert f'getElementById("{modal}")' in page  # hộp mở sẵn để thấy lỗi
    assert "Không ghi họ tên, chỉ dùng mã hồ sơ." in page  # gợi ý câu 30


def test_o_ly_do_trong_hop_thoai_khong_co_thuoc_tinh_required_de_loi_hien_bang_tieng_viet():
    # Có `required` thì trình duyệt chặn bằng bong bóng mặc định, không tới được lỗi dưới ô.
    pending = make_worker_in_status(VS.PENDING)
    page = text(login_client(make_user("HR_MANAGER")).get(f"/ho-so/{pending.pk}/"))
    modal = page.split('id="return-modal"')[1].split("</form>")[0]
    assert "<textarea" in modal and not re.search(r"<(textarea|input)[^>]*\brequired\b", modal)
    archived = make_worker_in_status(VS.ARCHIVED)
    page = text(login_client(make_user("ADMIN")).get(f"/ho-so/{archived.pk}/"))
    modal = page.split('id="anonymize-modal"')[1].split("</form>")[0]
    assert "<textarea" in modal and not re.search(r"<(textarea|input)[^>]*\brequired\b", modal)


def test_ly_do_tra_lai_va_tu_choi_ghi_dung_vao_status_change_va_nhat_ky():
    worker = make_worker_in_status(VS.PENDING)
    post(login_client(make_user("HR_MANAGER")), worker, "tu-choi", {"reject-reason": "Giấy tờ sai"})
    assert status_of(worker) == VS.REJECTED
    assert StatusChange.objects.filter(worker=worker).last().reason == "Giấy tờ sai"
    assert (
        AuditLog.objects.filter(worker=worker, action="STATUS_CHANGE").first().note == "Giấy tờ sai"
    )
    page = text(login_client(make_user("HR_STAFF")).get(f"/ho-so/{worker.pk}/"))
    assert "Từ chối: Giấy tờ sai" in page


# ===== Lưu trữ ============================================================================
@pytest.mark.parametrize("status", [VS.DRAFT, VS.NEEDS_INFO, VS.REJECTED])
@pytest.mark.parametrize("role", STAFF)
def test_luu_tru_tu_nhap_can_bo_sung_bi_tu_choi_khong_can_ly_do(status, role):
    worker = make_worker_in_status(status)
    response = post(login_client(make_user(role)), worker, "luu-tru")
    assert response.status_code == 302 and status_of(worker) == VS.ARCHIVED
    assert AuditLog.objects.filter(worker=worker, action="STATUS_CHANGE").first().changes == {
        "verification_status": [status.value, "ARCHIVED"]
    }


def test_hr_khong_luu_tru_ho_so_da_xac_minh():
    worker = make_worker_in_status(VS.VERIFIED)
    response = post(login_client(make_user("HR_STAFF")), worker, "luu-tru", {"archive-reason": "x"})
    assert response.status_code == 403 and status_of(worker) == VS.VERIFIED


@pytest.mark.parametrize("role", MANAGERS)
def test_ql_admin_luu_tru_ho_so_da_xac_minh_bat_buoc_ly_do(role):
    worker = make_worker_in_status(VS.VERIFIED)
    client = login_client(make_user(role))
    response = post(client, worker, "luu-tru", {"archive-reason": ""})
    assert response.status_code == 200 and "Nhập lý do." in text(response)
    assert status_of(worker) == VS.VERIFIED
    response = post(client, worker, "luu-tru", {"archive-reason": "Đã nghỉ, đóng hồ sơ"})
    assert response.status_code == 302 and status_of(worker) == VS.ARCHIVED


@pytest.mark.parametrize("work", ["PROBATION", "ACTIVE"])
def test_chan_luu_tru_khi_thu_viec_hoac_dang_lam_viec_bao_loi_va_khong_doi_gi(work):
    worker = make_worker_in_status(VS.VERIFIED)
    make_employment(worker, work)
    client = login_client(make_user("HR_MANAGER"))
    response = post(client, worker, "luu-tru", {"archive-reason": "Thử"})
    assert response.status_code == 302 and status_of(worker) == VS.VERIFIED
    assert any("Thử việc hoặc Đang làm việc" in m for m in flashed(response))
    page = text(client.get(f"/ho-so/{worker.pk}/"))
    assert "Đang Thử việc hoặc Đang làm việc nên chưa Lưu trữ được." in page  # nút bị tắt kèm lý do


# ===== Mở lại ===============================================================================
def reopen_data():
    return {
        "position": Position.objects.get_or_create(name="Công nhân giả")[0].pk,
        "source": ApplicationSource.objects.get_or_create(name="Nguồn giả")[0].pk,
    }


@pytest.mark.parametrize("role", STAFF)
def test_mo_lai_ho_so_luu_tru(role):
    worker = make_worker_in_status(VS.ARCHIVED)
    Worker.objects.filter(pk=worker.pk).update(employee_code="CN-00099")
    client = login_client(make_user(role))
    assert client.get(f"/ho-so/{worker.pk}/mo-lai/").status_code == 200
    response = post(client, worker, "mo-lai", reopen_data())
    assert response.status_code == 302 and status_of(worker) == VS.DRAFT
    assert Worker.objects.get(pk=worker.pk).employee_code == "CN-00099"
    assert Application.objects.filter(worker=worker, status="NEW").count() == 1
    assert AuditLog.objects.filter(worker=worker, action="REOPEN").exists()


def test_mo_lai_thieu_vi_tri_hien_loi_duoi_o_va_khong_doi_gi():
    worker = make_worker_in_status(VS.ARCHIVED)
    response = post(login_client(make_user("HR_STAFF")), worker, "mo-lai", {})
    page = text(response)
    assert response.status_code == 200 and "Chọn vị trí ứng tuyển." in page
    assert "Chọn nguồn ứng tuyển." in page and status_of(worker) == VS.ARCHIVED


@pytest.mark.parametrize("status", [VS.DRAFT, VS.PENDING, VS.VERIFIED, VS.REJECTED])
def test_mo_lai_ho_so_chua_luu_tru_bi_chan(status):
    worker = make_worker_in_status(status)
    client = login_client(make_user("HR_STAFF"))
    response = client.get(f"/ho-so/{worker.pk}/mo-lai/")
    assert response.status_code == 302
    assert post(client, worker, "mo-lai", reopen_data()).status_code == 302
    assert status_of(worker) == status and not Application.objects.filter(worker=worker).exists()


def test_mo_lai_ho_so_da_an_danh_bi_chan():
    from django.utils import timezone

    worker = make_worker_in_status(VS.ARCHIVED)
    Worker.objects.filter(pk=worker.pk).update(anonymized_at=timezone.now())
    response = post(login_client(make_user("ADMIN")), worker, "mo-lai", reopen_data())
    assert response.status_code == 302 and status_of(worker) == VS.ARCHIVED


# ===== Ẩn danh hóa theo yêu cầu (câu 38) ===================================================
def anon_data(worker, **override):
    data = {
        "anon-reason": f"Chủ thể yêu cầu xóa, hồ sơ {worker.worker_code}",
        "anon-request_ref": "Đơn số 7 ngày 20/11/2026",
        "anon-confirm_code": worker.worker_code,
    }
    data.update(override)
    return data


@pytest.mark.parametrize("role", ["HR_MANAGER", "HR_STAFF", "VIEWER"])
def test_chi_admin_an_danh_theo_yeu_cau(role):
    worker = make_worker_in_status(VS.ARCHIVED)
    response = post(
        login_client(make_user(role)), worker, "an-danh-theo-yeu-cau", anon_data(worker)
    )
    assert response.status_code == 403
    assert Worker.objects.get(pk=worker.pk).anonymized_at is None


def test_admin_an_danh_thanh_cong_xoa_tep_va_ghi_bien_ban(django_capture_on_commit_callbacks):
    worker = make_worker_in_status(VS.ARCHIVED)
    doc = make_document(worker, "CCCD_FRONT")
    path = doc.stored_file.path
    client = login_client(make_user("ADMIN"))
    with django_capture_on_commit_callbacks(execute=True):  # tệp chỉ bị xóa sau khi commit
        response = post(client, worker, "an-danh-theo-yeu-cau", anon_data(worker))
    assert response.status_code == 302
    fresh = Worker.objects.get(pk=worker.pk)
    assert fresh.anonymized_at is not None and fresh.full_name == "(Đã ẩn danh)"
    import os

    assert not os.path.exists(path) and not WorkerDocument.objects.get(pk=doc.pk).stored_file
    record = AnonymizationRecord.objects.get()
    assert record.kind == "SUBJECT_REQUEST" and record.request_ref == "Đơn số 7 ngày 20/11/2026"
    assert any(record.record_no in m for m in flashed(response))
    page = text(client.get(f"/ho-so/{worker.pk}/"))
    assert "đã được ẩn danh hóa" in page and "Mở lại hồ sơ" not in page
    assert "Ẩn danh hóa theo yêu cầu" not in page and "Sửa hồ sơ" not in page


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"anon-confirm_code": "HS-SAI"}, "Mã hồ sơ gõ lại không khớp."),
        ({"anon-confirm_code": ""}, "Gõ lại mã hồ sơ để xác nhận."),
        ({"anon-reason": ""}, "Nhập lý do."),
        ({"anon-request_ref": ""}, "Nhập số hoặc ngày đơn yêu cầu."),
    ],
)
def test_an_danh_thieu_hoac_sai_thong_tin_hien_loi_duoi_o_va_khong_an_danh(override, message):
    worker = make_worker_in_status(VS.ARCHIVED)
    response = post(
        login_client(make_user("ADMIN")),
        worker,
        "an-danh-theo-yeu-cau",
        anon_data(worker, **override),
    )
    page = text(response)
    assert response.status_code == 200 and message in page
    assert 'getElementById("anonymize-modal")' in page
    assert Worker.objects.get(pk=worker.pk).anonymized_at is None
    assert not AnonymizationRecord.objects.exists()


@pytest.mark.parametrize("status", [VS.DRAFT, VS.PENDING, VS.VERIFIED, VS.REJECTED])
def test_an_danh_ho_so_chua_luu_tru_bi_chan(status):
    worker = make_worker_in_status(status)
    response = post(
        login_client(make_user("ADMIN")), worker, "an-danh-theo-yeu-cau", anon_data(worker)
    )
    assert response.status_code == 302
    assert any("Lưu trữ" in m for m in flashed(response))
    assert Worker.objects.get(pk=worker.pk).anonymized_at is None


# ===== Nút ở đầu trang theo trạng thái và vai trò ===============================================
def header_labels(content):
    block = re.search(r'pa-page-header__actions">(.*?)</div>\s*</div>', content, re.S)
    return (
        re.findall(r"<(?:button|a)[^>]*class=\"btn btn-[^\"]*\"[^>]*>([^<]+)</", block.group(1))
        if block
        else []
    )


def primary_count(content):
    block = re.search(r'pa-page-header__actions">(.*?)</div>\s*</div>', content, re.S)
    return block.group(1).count('class="btn btn-primary"') if block else 0


@pytest.mark.parametrize(
    ("status", "role", "labels"),
    [
        (VS.DRAFT, "HR_STAFF", ["Gửi duyệt", "Sửa hồ sơ", "Lưu trữ"]),
        (VS.NEEDS_INFO, "HR_STAFF", ["Gửi duyệt", "Sửa hồ sơ", "Lưu trữ"]),
        (VS.PENDING, "HR_MANAGER", ["Duyệt hồ sơ", "Trả lại", "Từ chối"]),
        (VS.PENDING, "HR_STAFF", []),
        (VS.VERIFIED, "HR_MANAGER", ["Sửa hồ sơ", "Lưu trữ"]),
        (VS.VERIFIED, "HR_STAFF", ["Sửa hồ sơ"]),
        (VS.REJECTED, "HR_STAFF", ["Lưu trữ"]),
        (VS.ARCHIVED, "HR_STAFF", ["Mở lại hồ sơ"]),
        (VS.ARCHIVED, "ADMIN", ["Mở lại hồ sơ", "Ẩn danh hóa theo yêu cầu"]),
        (VS.ARCHIVED, "HR_MANAGER", ["Mở lại hồ sơ"]),
    ],
)
def test_nut_dau_trang_theo_trang_thai_va_vai_tro(status, role, labels):
    worker = make_worker_in_status(status)
    content = text(login_client(make_user(role)).get(f"/ho-so/{worker.pk}/"))
    assert sorted(header_labels(content)) == sorted(labels)
    assert primary_count(content) <= 1  # tối đa một nút chính mỗi màn hình


def test_viewer_khong_co_nut_nao():
    for status in VS:
        worker = make_worker_in_status(status)
        content = text(login_client(make_user("VIEWER")).get(f"/ho-so/{worker.pk}/"))
        assert header_labels(content) == []
