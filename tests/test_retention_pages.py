"""Cài đặt: tab Chờ hủy và Biên bản hủy; ẩn danh lý do trạng thái (Phase 7, bước 8).

Danh sách chờ hủy dùng expired_entries/anonymize của Phase 4; kiểm tra lại ở máy chủ mọi hồ sơ được
gửi lên; biên bản đúng; lý do do người dùng gõ ở dòng thời gian trạng thái được thay bằng
"(đã ẩn danh)" (ngoại lệ có kiểm soát của bảng chỉ thêm), lý do hệ thống tự điền giữ nguyên.
"""

import datetime
import importlib
import re
import types
from pathlib import Path

import pytest
from django.db import models

from apps.audit.models import AuditLog, AuditPersonalValue
from apps.core.choices import AnonymizationKind as Kind
from apps.core.choices import VerificationStatus as VS
from apps.workers import retention
from apps.workers.models import AnonymizationItem, AnonymizationRecord, StatusChange
from apps.workers.workflow import Trigger, transition
from tests.factories import (
    at,
    freeze_time,
    login_client,
    make_user,
    make_worker_full,
    make_worker_in_status,
)
from tests.test_retention import archive_by_system, archive_manual, archived_with_expiry

pytestmark = pytest.mark.django_db
D = datetime.date
ROOT = Path(__file__).resolve().parent.parent
URLS = ["/cai-dat/cho-huy/", "/cai-dat/bien-ban-huy/"]


def admin_client():
    return login_client(make_user("ADMIN"))


def get(client, path, expect=200):
    response = client.get(path)
    assert response.status_code == expect, (path, response.status_code)
    return response.content.decode()


def total(content):
    match = re.search(r"Hiển thị[^/]*/\s*(\d+)", content)
    return int(match.group(1)) if match else 0


def post_destroy(client, ids):
    return client.post("/cai-dat/cho-huy/huy/", {"workers": [str(i) for i in ids]})


# --- Quyền -------------------------------------------------------------------------------------
def test_chua_dang_nhap_chuyen_ve_dang_nhap():
    from django.test import Client

    for path in [*URLS, "/cai-dat/bien-ban-huy/1/", "/cai-dat/bien-ban-huy/1/in/"]:
        response = Client().get(path)
        assert response.status_code == 302 and response.url.startswith("/dang-nhap/")
    assert Client().post("/cai-dat/cho-huy/huy/", {}).status_code == 302


@pytest.mark.parametrize("role", ["HR_MANAGER", "HR_STAFF", "VIEWER"])
def test_chi_admin_vao_duoc_ca_nam_url(role):
    worker = archived_with_expiry(D(2026, 1, 5))
    record = retention.anonymize([worker], Kind.EXPIRED, make_user("ADMIN"))
    client = login_client(make_user(role))
    for path in [
        *URLS,
        f"/cai-dat/bien-ban-huy/{record.pk}/",
        f"/cai-dat/bien-ban-huy/{record.pk}/in/",
    ]:
        assert client.get(path).status_code == 403, path
    assert post_destroy(client, [worker.pk]).status_code == 403
    assert not AuditLog.objects.filter(action="PRINT").exists()


def test_admin_vao_duoc_va_post_nguoi_khac_khong_an_danh_gi():
    worker = archived_with_expiry(D(2026, 1, 5))
    for role in ("HR_MANAGER", "HR_STAFF", "VIEWER"):
        assert post_destroy(login_client(make_user(role)), [worker.pk]).status_code == 403
    worker.refresh_from_db()
    assert worker.anonymized_at is None and not AnonymizationRecord.objects.exists()


def test_get_khong_duoc_phep_o_url_huy_va_in_la_get():
    client = admin_client()
    assert client.get("/cai-dat/cho-huy/huy/").status_code == 405
    worker = archived_with_expiry(D(2026, 1, 5))
    record = retention.anonymize([worker], Kind.EXPIRED, make_user("ADMIN"))
    assert client.post(f"/cai-dat/bien-ban-huy/{record.pk}/in/").status_code == 405


def test_hai_tab_moi_nam_trong_khung_cai_dat():
    content = get(admin_client(), "/cai-dat/cho-huy/")
    assert "Chờ hủy" in content and "Biên bản hủy" in content
    assert 'href="/cai-dat/bien-ban-huy/"' in content and 'href="/cai-dat/cho-huy/"' in content
    assert login_client(make_user("ADMIN")).get("/cai-dat/").url == "/cai-dat/danh-muc/"  # tab đầu


# --- Danh sách chờ hủy --------------------------------------------------------------------------
def test_danh_sach_chi_co_ho_so_qua_han_voi_cot_can_cu_va_ngay_het_han():
    old = archived_with_expiry(D(2026, 1, 5))
    future = make_worker_full(full_name="Chưa Hết Hạn")
    archive_manual(future, at(2026, 11, 1))
    verified = make_worker_in_status(VS.VERIFIED)
    content = get(admin_client(), "/cai-dat/cho-huy/")
    for column in ("Mã hồ sơ", "Lưu trữ từ", "Căn cứ lưu trữ", "Hết hạn lưu trữ", "Trạng thái"):
        assert column in content
    assert old.worker_code in content
    assert future.worker_code not in content and verified.worker_code not in content
    assert "Ứng viên lưu trữ khác" in content and "05/01/2026" in content
    assert "Lưu trữ" in content  # nhãn trạng thái Lưu trữ, không có nhãn "Chờ hủy" nào khác
    assert f'name="workers" value="{old.pk}" form="form-huy"' in content


def test_danh_sach_rong_hien_empty_state_va_khong_co_nut_huy():
    make_worker_full()
    content = get(admin_client(), "/cai-dat/cho-huy/")
    assert "Không có hồ sơ nào quá hạn lưu trữ." in content
    assert "Hủy hồ sơ đã chọn" not in content


def test_hop_xac_nhan_co_canh_bao_va_form_nhan_o_chon_ngoai_bang():
    archived_with_expiry(D(2026, 1, 5))
    content = get(admin_client(), "/cai-dat/cho-huy/")
    assert 'id="form-huy"' in content and 'action="/cai-dat/cho-huy/huy/"' in content
    assert "Thao tác này không hoàn tác được." in content
    assert "csrfmiddlewaretoken" in content


def test_phan_trang_20_dong_va_het_han_som_nhat_truoc():
    late = archived_with_expiry(D(2026, 6, 5))
    early = [archived_with_expiry(D(2026, 1, 5)) for _ in range(22)]
    content = get(admin_client(), "/cai-dat/cho-huy/")
    assert total(content) == 23 and "Hiển thị 1–20" in content
    page2 = get(admin_client(), "/cai-dat/cho-huy/?trang=2")
    assert "Hiển thị 21–23" in page2
    assert late.worker_code in page2 and late.worker_code not in content  # hết hạn muộn ở cuối
    assert all(w.worker_code in content or w.worker_code in page2 for w in early)


# --- Hủy (ẩn danh hóa) từ danh sách --------------------------------------------------------------
def test_huy_ba_ho_so_sinh_mot_bien_ban_dung_va_ba_dong_nhat_ky():
    a = archived_with_expiry(D(2026, 1, 5))
    b = archived_with_expiry(D(2026, 2, 5))
    c = archived_with_expiry(D(2026, 3, 5))
    keep = archived_with_expiry(D(2026, 4, 5))  # quá hạn nhưng không chọn
    client = admin_client()
    response = post_destroy(client, [a.pk, b.pk, c.pk])
    record = AnonymizationRecord.objects.get()
    assert response.status_code == 302 and response.url == f"/cai-dat/bien-ban-huy/{record.pk}/"
    assert record.kind == Kind.EXPIRED and record.worker_count == 3
    assert record.performed_by.role.code == "ADMIN" and record.record_no.startswith("BBH-")
    items = {i.worker_id: i for i in record.items.all()}
    assert set(items) == {a.pk, b.pk, c.pk}
    assert items[a.pk].retention_expired_on == D(2026, 1, 5)
    assert (
        items[a.pk].retention_basis == "CANDIDATE_OTHER"
        and items[a.pk].worker_code == a.worker_code
    )
    for worker in (a, b, c):
        worker.refresh_from_db()
        assert worker.anonymized_at is not None and worker.full_name == "(Đã ẩn danh)"
        assert worker.verification_status == VS.ARCHIVED  # hồ sơ vẫn ở trạng thái Lưu trữ
    keep.refresh_from_db()
    assert keep.anonymized_at is None
    entries = AuditLog.objects.filter(action="ANONYMIZE")
    assert entries.count() == 3 and all(record.record_no in e.note for e in entries)
    assert {e.object_repr for e in entries} == {a.worker_code, b.worker_code, c.worker_code}
    page = get(client, response.url)
    assert record.record_no in page and a.worker_code in page and "Hết hạn lưu trữ" in page


def test_sau_khi_huy_ho_so_roi_khoi_danh_sach_cho_huy():
    worker = archived_with_expiry(D(2026, 1, 5))
    other = archived_with_expiry(D(2026, 1, 6))
    client = admin_client()
    post_destroy(client, [worker.pk])
    content = get(client, "/cai-dat/cho-huy/")
    assert worker.worker_code not in content and other.worker_code in content


@pytest.mark.parametrize("bad", ["not-expired", "anonymized", "missing", "not-archived"])
def test_hồ_so_khong_hop_le_gui_len_bi_tu_choi_khong_an_danh_hoa_gi(bad):
    good = archived_with_expiry(D(2026, 1, 5))
    if bad == "not-expired":
        invalid = make_worker_full()
        archive_manual(invalid, at(2026, 11, 1))
    elif bad == "anonymized":
        invalid = archived_with_expiry(D(2026, 1, 6))
        retention.anonymize([invalid], Kind.EXPIRED, make_user("ADMIN"))
    elif bad == "not-archived":
        invalid = make_worker_in_status(VS.VERIFIED)
    else:
        invalid = types.SimpleNamespace(pk=999999)
    before = AnonymizationRecord.objects.count()
    client = admin_client()
    response = post_destroy(client, [good.pk, invalid.pk])
    assert response.status_code == 302 and response.url == "/cai-dat/cho-huy/"
    good.refresh_from_db()
    assert good.anonymized_at is None  # một hồ sơ sai thì không hủy hồ sơ nào
    assert AnonymizationRecord.objects.count() == before
    assert "Không ẩn danh hóa hồ sơ nào." in get(client, response.url)


@pytest.mark.parametrize("payload", [{}, {"workers": ["abc"]}, {"workers": [""]}])
def test_khong_chon_hoac_gui_gia_tri_la_bao_loi(payload):
    archived_with_expiry(D(2026, 1, 5))
    client = admin_client()
    response = client.post("/cai-dat/cho-huy/huy/", payload)
    assert response.status_code == 302 and response.url == "/cai-dat/cho-huy/"
    assert not AnonymizationRecord.objects.exists()
    assert "Chưa chọn hồ sơ nào để hủy." in get(client, "/cai-dat/cho-huy/")


def test_chon_trung_id_hai_lan_chi_an_danh_mot_lan():
    worker = archived_with_expiry(D(2026, 1, 5))
    post_destroy(admin_client(), [worker.pk, worker.pk])
    assert AnonymizationRecord.objects.get().worker_count == 1


# --- Biên bản hủy -------------------------------------------------------------------------------
def test_danh_sach_bien_ban_cot_loai_so_don_so_ho_so():
    admin = make_user("ADMIN")
    expired = archived_with_expiry(D(2026, 1, 5))
    retention.anonymize([expired], Kind.EXPIRED, admin)
    early = make_worker_full()
    archive_manual(early, at(2026, 11, 1))
    retention.anonymize_on_request(
        early, admin, reason="Theo đơn", request_ref="Đơn 12/2026", confirm_code=early.worker_code
    )
    content = get(login_client(admin), "/cai-dat/bien-ban-huy/")
    for column in ("Số biên bản", "Thời điểm", "Loại", "Số đơn", "Số hồ sơ", "Người duyệt"):
        assert column in content
    assert "Hết hạn lưu trữ" in content and "Theo yêu cầu của chủ thể" in content
    assert "Đơn 12/2026" in content
    assert total(content) == 2
    assert content.index("BBH-2026-002") < content.index("BBH-2026-001")  # mới nhất ở đầu


def test_danh_sach_bien_ban_rong():
    assert "Chưa có biên bản hủy nào." in get(admin_client(), "/cai-dat/bien-ban-huy/")


def test_chi_tiet_bien_ban_theo_yeu_cau_co_so_don_ly_do_va_dong_xoa_som():
    admin = make_user("ADMIN")
    worker = make_worker_full()
    archive_manual(worker, at(2026, 11, 1))
    expires = retention.retention_info(worker).expires_on
    record = retention.anonymize_on_request(
        worker,
        admin,
        reason="Người lao động xin xóa",
        request_ref="Đơn 7",
        confirm_code=worker.worker_code,
    )
    content = get(login_client(admin), f"/cai-dat/bien-ban-huy/{record.pk}/")
    assert record.record_no in content and "Theo yêu cầu của chủ thể" in content
    assert "Đơn 7" in content and "Người lao động xin xóa" in content
    assert f"Xóa sớm theo yêu cầu – lẽ ra lưu đến {expires:%d/%m/%Y}" in content
    assert worker.worker_code in content
    assert "In biên bản" in content and f"/cai-dat/bien-ban-huy/{record.pk}/in/" in content


def test_chi_tiet_bien_ban_het_han_khong_co_dong_xoa_som_va_la_404_neu_khong_co():
    worker = archived_with_expiry(D(2026, 1, 5))
    record = retention.anonymize([worker], Kind.EXPIRED, make_user("ADMIN"))
    content = get(admin_client(), f"/cai-dat/bien-ban-huy/{record.pk}/")
    assert "Xóa sớm theo yêu cầu" not in content and "Số đơn yêu cầu" not in content
    get(admin_client(), "/cai-dat/bien-ban-huy/99999/", 404)
    get(admin_client(), "/cai-dat/bien-ban-huy/99999/in/", 404)


def test_in_bien_ban_ghi_print_va_khong_co_ho_ten():
    admin = make_user("ADMIN")
    worker = make_worker_full(full_name="Tên Người Bị Hủy")
    archive_manual(worker, at(2025, 1, 5))
    record = retention.anonymize([worker], Kind.EXPIRED, admin)
    client = login_client(admin)
    assert not AuditLog.objects.filter(action="PRINT").exists()
    content = get(client, f"/cai-dat/bien-ban-huy/{record.pk}/in/")
    assert (
        record.record_no in content and "Người duyệt hủy" in content and "d-print-none" in content
    )
    assert "Tên Người Bị Hủy" not in content
    entry = AuditLog.objects.get(action="PRINT")
    assert entry.user == admin and entry.object_type == "workers.AnonymizationRecord"
    assert entry.object_repr == record.record_no and entry.note == "In biên bản hủy"
    get(client, f"/cai-dat/bien-ban-huy/{record.pk}/in/")
    assert AuditLog.objects.filter(action="PRINT").count() == 2  # mỗi lần mở ghi một dòng
    assert AnonymizationItem.objects.filter(record=record).count() == 1


# --- Lý do do người dùng gõ khi đổi trạng thái -------------------------------------------------
def test_ly_do_nguoi_dung_go_bi_thay_con_ly_do_he_thong_giu_nguyen():
    worker = make_worker_full(full_name="Họ Tên Có Trong Lý Do")
    staff = make_user("HR_STAFF")
    manager = make_user("HR_MANAGER")
    transition(worker, VS.PENDING, staff)
    typed = transition(worker, VS.NEEDS_INFO, manager, "Bổ sung giấy tờ của Họ Tên Có Trong Lý Do")
    transition(worker, VS.PENDING, staff)
    transition(worker, VS.REJECTED, manager, "Sai thông tin của Họ Tên Có Trong Lý Do")
    with freeze_time(at(2025, 1, 5)):
        system = transition(worker, VS.ARCHIVED, None, trigger=Trigger.SYSTEM)
    assert typed.reason_by_user and not system.reason_by_user
    created = StatusChange.objects.get(worker=worker, from_status="")
    system_reason = system.reason
    assert worker.worker_code in system_reason
    record = retention.anonymize([worker], Kind.EXPIRED, make_user("ADMIN"))
    assert record.worker_count == 1
    reasons = {c.to_status: c.reason for c in StatusChange.objects.filter(worker=worker)}
    assert reasons[VS.NEEDS_INFO] == "(đã ẩn danh)" and reasons[VS.REJECTED] == "(đã ẩn danh)"
    assert reasons[VS.ARCHIVED] == system_reason  # lý do hệ thống tự điền giữ nguyên
    assert reasons[VS.PENDING] == "" and created.reason == ""  # lý do rỗng không đổi
    assert all("Họ Tên Có Trong Lý Do" not in c.reason for c in StatusChange.objects.all())


def test_ly_do_khong_con_o_audit_log_note_va_audit_personal_value_bi_xoa():
    worker = make_worker_full()
    staff, manager = make_user("HR_STAFF"), make_user("HR_MANAGER")
    transition(worker, VS.PENDING, staff)
    transition(worker, VS.REJECTED, manager, "Lý do bí mật ZQX")
    entry = AuditLog.objects.filter(worker=worker, action="STATUS_CHANGE").order_by("-id").first()
    assert entry.note == "" and "ZQX" not in f"{entry.note}{entry.changes}{entry.object_repr}"
    assert (
        AuditPersonalValue.objects.get(audit_log=entry, field_name="status_reason").new_value_enc
        == "Lý do bí mật ZQX"
    )
    with freeze_time(at(2025, 1, 5)):
        transition(worker, VS.ARCHIVED, staff)
    retention.anonymize([worker], Kind.EXPIRED, make_user("ADMIN"))
    assert not AuditPersonalValue.objects.filter(worker=worker).exists()
    assert not AuditLog.objects.filter(note__contains="ZQX").exists()
    # Dòng nhật ký vẫn còn (ai, khi nào, hành động, tên trường).
    entry.refresh_from_db()
    assert entry.changes["status_reason"] == "(xem giá trị chi tiết)"


def test_tab_lich_su_hien_da_an_danh_o_cot_ly_do_sau_khi_huy():
    worker = make_worker_full()
    staff, manager = make_user("HR_STAFF"), make_user("HR_MANAGER")
    transition(worker, VS.PENDING, staff)
    transition(worker, VS.REJECTED, manager, "Lý do riêng ZQX")
    with freeze_time(at(2025, 1, 5)):
        transition(worker, VS.ARCHIVED, staff)
    client = login_client(make_user("HR_MANAGER"))
    assert "Lý do riêng ZQX" in client.get(f"/ho-so/{worker.pk}/?tab=lich-su").content.decode()
    retention.anonymize([worker], Kind.EXPIRED, make_user("ADMIN"))
    page = client.get(f"/ho-so/{worker.pk}/?tab=lich-su").content.decode()
    assert "Lý do riêng ZQX" not in page and "(đã ẩn danh)" in page


def test_ly_do_tu_dong_dien_va_sua_dinh_danh_khong_bi_danh_dau_nguoi_dung():
    worker = make_worker_in_status(VS.VERIFIED)
    from apps.workers.services import update_worker

    update_worker(make_user("HR_STAFF"), worker, {"full_name": "Tên Mới Hoàn Toàn"})
    change = (
        StatusChange.objects.filter(worker=worker, to_status=VS.PENDING).order_by("-id").first()
    )
    assert change.reason.startswith("Sửa trường định danh:") and not change.reason_by_user
    entry = AuditLog.objects.filter(worker=worker, action="STATUS_CHANGE").order_by("-id").first()
    assert entry.note.startswith("Sửa trường định danh:")  # lý do hệ thống vẫn ở note
    assert "status_reason" not in entry.changes


def test_migration_dien_lai_du_lieu_cu_theo_quy_tac():
    module = importlib.import_module("apps.workers.migrations.0003_statuschange_reason_by_user")
    worker = make_worker_full()
    user = make_user("HR_STAFF")
    base = {"worker": worker, "from_status": "DRAFT", "to_status": "PENDING"}
    rows = {
        "typed": StatusChange.objects.create(**base, reason="Người gõ", changed_by=user),
        "system": StatusChange.objects.create(**base, reason="Hệ thống tự chuyển", changed_by=None),
        "identity": StatusChange.objects.create(
            **base, reason="Sửa trường định danh: họ tên", changed_by=user
        ),
        "empty": StatusChange.objects.create(**base, reason="", changed_by=user),
    }
    # Lược đồ lịch sử của migration không có QuerySet chặn update: giả lập bằng QuerySet gốc.
    shim = types.SimpleNamespace(
        get_model=lambda app, name: types.SimpleNamespace(
            objects=models.QuerySet(model=StatusChange)
        )
    )
    module.mark_user_reasons(shim, None)
    flags = {key: StatusChange.objects.get(pk=row.pk).reason_by_user for key, row in rows.items()}
    assert flags == {"typed": True, "system": False, "identity": False, "empty": False}


def test_quet_ma_nguon_ngoai_le_sua_status_change_chi_o_mot_cho():
    """Ngoại lệ có kiểm soát: chỉ retention._redact_status_reasons (gọi từ _wipe) được dùng
    QuerySet gốc để ghi vào bảng chỉ thêm StatusChange."""
    hits = []
    for path in (ROOT / "apps").rglob("*.py"):
        if "migrations" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), start=1):
            if re.search(r"models\.QuerySet\(\s*model=StatusChange", line):
                hits.append((path.relative_to(ROOT).as_posix(), number))
            if re.search(r"\b_redact_status_reasons\(", line) and "def " not in line:
                hits.append((path.relative_to(ROOT).as_posix(), "call"))
    files = sorted({h[0] for h in hits})
    assert files == ["apps/workers/retention.py"], hits
    assert [h for h in hits if h[1] == "call"] == [("apps/workers/retention.py", "call")]
    source = (ROOT / "apps/workers/retention.py").read_text(encoding="utf-8")
    wipe = source[source.index("def _wipe(") : source.index("def anonymize(")]
    assert "_redact_status_reasons(worker)" in wipe


def test_cau_hinh_mac_dinh_cua_abandoned_van_tinh_duoc_can_cu_sau_khi_doi_logic_ly_do():
    """Căn cứ "Hồ sơ bỏ dở" nhận bằng lý do HỆ THỐNG: không bị ảnh hưởng bởi cờ reason_by_user."""
    worker = make_worker_full()
    archive_by_system(worker, at(2025, 3, 1), "Hồ sơ bỏ dở (hồ sơ X)")
    info = retention.retention_info(worker)
    assert info.basis == "ABANDONED"
    change = StatusChange.objects.get(worker=worker, to_status=VS.ARCHIVED)
    assert not change.reason_by_user
