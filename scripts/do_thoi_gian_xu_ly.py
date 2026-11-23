"""Đo thời gian máy xử lý một hồ sơ bằng phần mềm trên dữ liệu giả lập (tài liệu khóa luận,
docs/khoa-luan/so-sanh-thoi-gian.md). Chỉ đo phần máy làm (từ lúc bấm nút tới khi trang kết quả
hiện xong), không đo thời gian người gõ/kiểm tra.
    py -3.12 scripts/do_thoi_gian_xu_ly.py
Cần web ở http://localhost:8000 (bản Demo), tài khoản hr, quanly dùng mật khẩu PA_TEST_PASSWORD.
Mỗi bước đo trên N_RUNS hồ sơ, in trung vị và lớn nhất (giây).
"""

import statistics
import sys
import time

import pw_phase5 as pw
from playwright.sync_api import sync_playwright
from pw_phase5 import CARD_DIR, db, goto, login, new_page

N_RUNS = 5
SIZE = pw.SIZES["1366x768"]

# Hồ sơ Nháp có đủ trường gửi duyệt (seed_demo), chưa có đồng ý, không do quanly tạo.
READY = (
    "from apps.workers.models import Worker;"
    "qs=Worker.objects.filter(verification_status='DRAFT',date_of_birth__isnull=False,"
    "emergency_contacts__isnull=False,identity__id_number_hash__isnull=False)"
    ".exclude(created_by__username='quanly').exclude(consents__consented=True).distinct();"
    f"print(','.join(str(w.pk) for w in qs[:{N_RUNS}]))"
)


def timed(action):
    started = time.perf_counter()
    action()
    return time.perf_counter() - started


def main():
    cards = [c for c in pw.gen_cards() if c["has_qr"]][:N_RUNS]
    steps = {name: [] for name in ("nhan_dien", "luu_nhap", "dong_y", "gui_duyet", "duyet")}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx, hr = new_page(browser, SIZE)
        login(hr, "hr")
        for card in cards:
            goto(hr, "/nhap-cccd/")
            hr.set_input_files("input[name=front_image]", str(CARD_DIR / card["files"]["front"]))
            hr.set_input_files("input[name=back_image]", str(CARD_DIR / card["files"]["back"]))

            def recognize():
                hr.click("button:has-text('Nhận diện')")
                hr.wait_for_load_state("networkidle")

            steps["nhan_dien"].append(timed(recognize))
            hr.fill("input[name=phone]", "0900000001")
            for box in hr.locator("[data-pa-checked]").all():
                box.check()

            def save():
                hr.click("button[data-pa-gate]")
                hr.wait_for_load_state("networkidle")

            steps["luu_nhap"].append(timed(save))

        ready = [pk for pk in db(READY).split(",") if pk]
        ctx_q, ql = new_page(browser, SIZE)
        login(ql, "quanly")
        for pk in ready:
            path = f"/ho-so/{pk}/"
            goto(hr, path + "dong-y/")
            hr.select_option("select[name=method]", "ELECTRONIC")

            def consent():
                hr.click("button:has-text('Lưu ghi nhận')")
                hr.wait_for_load_state("networkidle")

            steps["dong_y"].append(timed(consent))
            goto(hr, path)

            def submit():
                hr.click(".pa-page-header__actions button:has-text('Gửi duyệt')")
                hr.wait_for_load_state("networkidle")

            steps["gui_duyet"].append(timed(submit))
            goto(ql, path)

            def approve():
                ql.click(".pa-page-header__actions button:has-text('Duyệt hồ sơ')")
                ql.wait_for_load_state("networkidle")

            steps["duyet"].append(timed(approve))
        ctx.close()
        ctx_q.close()
        browser.close()

    print("Bước | số lần | trung vị (giây) | lớn nhất (giây)")
    for name, values in steps.items():
        if values:
            print(f"{name} | {len(values)} | {statistics.median(values):.2f} | {max(values):.2f}")
        else:
            print(f"{name} | 0 | - | -")
    return 0 if all(steps.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
