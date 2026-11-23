"""Nạp dữ liệu mẫu: 4 tài khoản, danh mục, ~500 hồ sơ giả (Faker vi_VN).

Chạy TAY (không chạy lúc khởi động container, để mật khẩu tạm không nằm trong logs):
    docker compose exec web python manage.py seed_demo

- Mật khẩu tạm sinh ngẫu nhiên, in ra console MỘT lần, không ghi vào file hay nhật ký.
- Idempotent: chạy lại không nhân đôi hồ sơ (nhận biết bằng số CCCD giả 999000000001...), không
  đổi mật khẩu tài khoản đã có (trừ khi --reset-passwords).
- Số CCCD giả luôn bắt đầu bằng 999; tên người là tên hư cấu do Faker sinh.
- Ghi bằng bulk_create nên name_search và id_number_hash được tính trước bằng đúng các hàm
  mà save() dùng (compute_name_search, compute_id_hash). Ngày tháng trải đều ~18 tháng, đúng
  thứ tự logic; các trường auto_now/auto_now_add được tạm tắt khi ghi (keep_dates).
"""

import datetime
import io
import random
from contextlib import contextmanager
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from faker import Faker
from PIL import Image, ImageDraw

from apps.accounts import services as account_services
from apps.accounts.models import Role, User
from apps.audit.services import log
from apps.core.choices import (
    AuditAction,
    ConsentMethod,
    ContractType,
    DocumentVerificationStatus,
    EmploymentChangeType,
    Gender,
    IdDocType,
    RecruitmentStatus,
    ResignReason,
    VerificationStatus,
    WorkStatus,
)
from apps.core.codes import next_code
from apps.core.crypto import compute_id_hash
from apps.core.models import (
    ApplicationSource,
    ClientCompany,
    Department,
    DocumentType,
    EducationLevel,
    Position,
    Section,
    Shift,
    Team,
)
from apps.core.text import compute_name_search
from apps.documents.models import WorkerDocument
from apps.employment.models import (
    Contract,
    Employment,
    EmploymentHistory,
    SalaryHistory,
    WorkAssignment,
)
from apps.recruitment.models import Application, Certificate, Education, WorkExperience
from apps.workers.models import (
    DataConsent,
    EmergencyContact,
    IdentityDocument,
    StatusChange,
    Worker,
)

# Tên ngắn cho các bộ trạng thái (khai báo gốc ở apps.core.choices).
V, W, R, EC = VerificationStatus, WorkStatus, RecruitmentStatus, EmploymentChangeType

SEED = 20261122
MAX_DAYS = 540  # ~18 tháng
ID_PREFIX = "999"  # số CCCD giả luôn bắt đầu bằng 999

USERS = [
    ("admin", "Quản Trị Viên Mẫu", "ADMIN"),
    ("quanly", "Quản Lý Nhân Sự Mẫu", "HR_MANAGER"),
    ("hr", "Nhân Viên Nhân Sự Mẫu", "HR_STAFF"),
    ("viewer", "Người Xem Mẫu", "VIEWER"),
]

# Số hồ sơ theo kịch bản khi tổng là 500 (tự co giãn theo --count).
WEIGHTS = {
    "DRAFT": 50,
    "PENDING": 40,
    "NEEDS_INFO": 35,
    "VER_CANDIDATE": 40,
    "VER_AWAITING": 25,
    "VER_PROBATION": 60,
    "VER_ACTIVE": 140,
    "VER_SUSPENDED": 15,
    "VER_RESIGNED": 15,
    "REJECTED": 20,
    "VER_FAILED": 10,
    "ARCH_RESIGNED": 15,
    "ARCH_EMPLOYEE_OTHER": 8,
    "ARCH_FAILED": 12,
    "ARCH_REJECTED": 5,
    "ARCH_ABANDONED": 5,
    "ARCH_OTHER": 5,
}

DEPARTMENTS = {
    # phòng ban -> bộ phận -> các tổ
    "Khối văn phòng": {"Văn phòng": []},
    "Sản xuất": {
        "Lắp ráp": ["Tổ 1", "Tổ 2", "Tổ 3"],
        "Đóng gói": ["Tổ 1", "Tổ 2"],
        "Gia công": ["Tổ 1", "Tổ 2"],
    },
    "Kho vận": {"Kho": ["Tổ 1"]},
}
POSITIONS = {
    "Văn phòng": ["Nhân viên văn phòng", "Nhân viên nhân sự", "Kế toán"],
    "Lắp ráp": ["Công nhân", "Công nhân", "Công nhân", "Tổ trưởng"],
    "Đóng gói": ["Công nhân", "Công nhân", "Tổ trưởng"],
    "Gia công": ["Công nhân", "Công nhân", "Tổ trưởng"],
    "Kho": ["Thủ kho", "Nhân viên kho", "Nhân viên kho"],
}
SHIFTS = [
    ("Ca sáng", "06:00-14:00"),
    ("Ca chiều", "14:00-22:00"),
    ("Ca đêm", "22:00-06:00"),
    ("Hành chính", "08:00-17:00"),
]
SOURCES = ["Giới thiệu", "Website", "Mạng xã hội", "Tuyển trực tiếp", "Trung tâm việc làm"]

# Công ty khách hàng hư cấu (v1.1, câu 39): mỗi địa điểm một dòng. Hai dòng đầu cùng tên, khác địa
# điểm, để thử chuỗi đợt liền nhau cộng dồn 12 tháng theo TÊN (câu 43, 48).
CLIENT_COMPANIES = [
    ("Công ty TNHH Điện tử Mẫu A", "Bình Dương"),
    ("Công ty TNHH Điện tử Mẫu A", "Đồng Nai"),
    ("Công ty CP May mặc Mẫu B", "Long An"),
    ("Công ty TNHH Cơ khí Mẫu C", "Bắc Ninh"),
    ("Công ty CP Bao bì Mẫu D", "Hải Phòng"),
]
RELATIONSHIPS = ["Cha", "Mẹ", "Vợ", "Chồng", "Anh", "Chị", "Em", "Bạn"]
JOBS = ["Công nhân may", "Nhân viên bán hàng", "Thợ hàn", "Nhân viên kho", "Phục vụ", "Lái xe"]
SKILLS = [
    "Vận hành máy",
    "Đọc bản vẽ kỹ thuật",
    "Làm việc nhóm",
    "Kiểm tra chất lượng",
    "Tin học văn phòng",
]
EDU_WEIGHTS = {
    "Chưa qua đào tạo": 3,
    "Tiểu học": 5,
    "THCS": 20,
    "THPT": 45,
    "Trung cấp": 10,
    "Cao đẳng": 8,
    "Đại học": 8,
    "Sau đại học": 1,
}


@contextmanager
def keep_dates(*models):
    """Tạm tắt auto_now / auto_now_add để bulk_create ghi đúng ngày đã đặt (thay vì update()
    sau đó: các bảng chỉ-thêm không cho sửa)."""
    saved = []
    for model in models:
        for field in model._meta.concrete_fields:
            if getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False):
                saved.append((field, field.auto_now, field.auto_now_add))
                field.auto_now = field.auto_now_add = False
    try:
        yield
    finally:
        for field, auto_now, auto_now_add in saved:
            field.auto_now, field.auto_now_add = auto_now, auto_now_add


# Loại tài liệu hệ thống (mỗi loại một nhóm bắt buộc) -> phần tên tệp giả.
SEED_DOCUMENTS = {
    "CCCD_FRONT": "mat-truoc",
    "CCCD_BACK": "mat-sau",
    "PORTRAIT": "chan-dung",
    "CV": "cv",
}


def placeholder_png():
    """Ảnh PNG nhỏ ghi "MAU - KHONG CO GIA TRI" (ASCII để không cần phông tiếng Việt)."""
    image = Image.new("RGB", (240, 150), "white")
    ImageDraw.Draw(image).text((20, 65), "MAU - KHONG CO GIA TRI", fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def at(day, hour, minute=0):
    """Ngày + giờ theo giờ Việt Nam."""
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time(hour, minute)))


def scenario_list(n):
    counts = {k: max(1, round(w * n / 500)) for k, w in WEIGHTS.items()}
    counts["VER_ACTIVE"] = max(1, counts["VER_ACTIVE"] + n - sum(counts.values()))
    items = [k for k, c in counts.items() for _ in range(c)]
    random.Random(SEED).shuffle(items)
    return items[:n]


# --- Kế hoạch thời gian cho từng hồ sơ ---------------------------------------------------------
def build_plan(sc, rng, today):
    """Trả kế hoạch: ngày của mọi sự kiện, đúng thứ tự logic, trải trong 18 tháng gần nhất.

    Mọi mốc tính bằng số ngày kể từ ngày tạo hồ sơ (offset). 'anchor' là mốc cuối nằm trong quá
    khứ, cách hôm nay 'tail' ngày; ngày tạo = hôm nay - (anchor + tail)."""
    sg, rg = rng.randint(0, 3), rng.randint(1, 5)
    sub, rev = sg, sg + rg
    chain = [(V.DRAFT, 0, "creator", "")]  # (trạng thái, offset, ai, loại lý do)
    app = {"status": R.NEW, "result": None, "interview": None}
    emp = None
    submit = (V.PENDING, sub, "creator", "")
    verified = (V.VERIFIED, rev, "reviewer", "")
    needs_info = (V.NEEDS_INFO, rev, "reviewer", "needs_info")
    rejected = (V.REJECTED, rev, "reviewer", "rejected")

    def tail_in(anchor, lo, hi):
        hi = min(hi, MAX_DAYS - anchor)
        return rng.randint(min(lo, hi), hi)

    if sc == "DRAFT":
        anchor, tail = 0, tail_in(0, 1, 170)
    elif sc == "PENDING":
        chain.append(submit)
        app["status"] = R.SCREENING
        anchor, tail = sub, tail_in(sub, 0, 120)
    elif sc == "NEEDS_INFO":
        chain += [submit, needs_info]
        app["status"] = rng.choice([R.NEW, R.SCREENING])
        anchor, tail = rev, tail_in(rev, 0, 170)
    elif sc == "REJECTED":
        chain += [submit, rejected]
        anchor, tail = rev, rng.randint(1, 28)  # quá 30 ngày sẽ tự Lưu trữ
    elif sc == "VER_CANDIDATE":
        chain += [submit, verified]
        app["status"] = rng.choice([R.NEW, R.SCREENING, R.INTERVIEW])
        if app["status"] == R.INTERVIEW:
            app["interview"] = rev + rng.randint(1, 5)
        anchor, tail = rev, tail_in(rev, 0, 500)
    elif sc in ("VER_FAILED", "ARCH_FAILED"):
        res = rng.randint(5, 20)
        app.update(status=rng.choice([R.FAILED, R.DECLINED]), result=res)
        chain += [submit, verified]
        anchor = max(res, rev)
        if sc == "VER_FAILED":
            tail = rng.randint(1, 28)
        else:
            tail = tail_in(anchor, 31, 300)
            archived = anchor + rng.randint(31, min(60, tail))
            chain.append((V.ARCHIVED, archived, "system", "auto_failed"))
    elif sc == "ARCH_REJECTED":
        chain += [submit, rejected]
        anchor = rev
        tail = tail_in(anchor, 31, 300)
        archived = rev + rng.randint(31, min(60, tail))
        chain.append((V.ARCHIVED, archived, "system", "auto_rejected"))
    elif sc == "ARCH_ABANDONED":
        chain.append((V.ARCHIVED, rng.randint(185, 199), "system", "abandoned"))
        anchor, tail = 0, rng.randint(200, MAX_DAYS)
    elif sc == "ARCH_OTHER":
        archived = rev + rng.randint(2, 20)
        chain += [submit, needs_info, (V.ARCHIVED, archived, "creator", "manual_candidate")]
        anchor, tail = archived, tail_in(archived, 0, 150)
    else:  # các kịch bản có tiếp nhận vào làm
        res = rng.randint(5, 20)
        app.update(status=R.PASSED, result=res)
        chain += [submit, verified]
        received = max(res, rev) + rng.randint(1, 3)
        start = received + rng.randint(3, 10)
        hist = [(EC.ONBOARD, "", W.AWAITING, received)]
        emp = {"received": received, "start": start, "resign": None, "reason": "", "hist": hist}

        def change(frm, to, off):
            hist.append((EC.STATUS_CHANGE, frm, to, off))

        if sc == "VER_AWAITING":
            anchor, tail = received, rng.randint(0, 10)
            emp["start"] = received + rng.randint(3, 14)  # có thể ở tương lai
            emp["status"] = W.AWAITING
        elif sc == "VER_PROBATION":
            anchor, tail = start, rng.randint(1, 55)
            change(W.AWAITING, W.PROBATION, start)
            emp["status"] = W.PROBATION
        else:
            change(W.AWAITING, W.PROBATION, start)
            if sc == "VER_ACTIVE":
                anchor, tail = start, tail_in(start, 61, 500)
                change(W.PROBATION, W.ACTIVE, start + 60)
                emp["status"] = W.ACTIVE
            elif sc == "VER_SUSPENDED":
                anchor, tail = start, tail_in(start, 61, 300)
                change(W.PROBATION, W.ACTIVE, start + 30)
                change(W.ACTIVE, W.SUSPENDED, start + tail - rng.randint(1, 30))
                emp["status"] = W.SUSPENDED
            elif sc in ("VER_RESIGNED", "ARCH_RESIGNED"):
                resign = start + rng.randint(40, 300)
                anchor = resign
                prev = W.PROBATION
                if resign - start >= 45:
                    change(W.PROBATION, W.ACTIVE, start + 30)
                    prev = W.ACTIVE
                change(prev, W.RESIGNED, resign)
                emp.update(
                    status=W.RESIGNED, resign=resign, reason=rng.choice(list(ResignReason.values))
                )
                if sc == "VER_RESIGNED":
                    tail = rng.randint(1, 28)
                else:
                    tail = tail_in(anchor, 31, 200)
                    archived = resign + rng.randint(31, min(60, tail))
                    chain.append((V.ARCHIVED, archived, "system", "auto_resigned"))
            else:  # ARCH_EMPLOYEE_OTHER: tạm hoãn rồi Lưu trữ thủ công bởi Quản lý
                susp = start + rng.randint(30, 60)
                archived = susp + rng.randint(1, 10)
                change(W.PROBATION, W.ACTIVE, start + 20)
                change(W.ACTIVE, W.SUSPENDED, susp)
                emp["status"] = W.SUSPENDED
                chain.append((V.ARCHIVED, archived, "manager", "manual_employee"))
                anchor, tail = archived, tail_in(archived, 1, 30)

    created = today - datetime.timedelta(days=anchor + tail)
    return {
        "sc": sc,
        "created": created,
        "chain": chain,
        "app": app,
        "emp": emp,
        "stale": sc == "ARCH_ABANDONED",
    }


# --- Sinh nội dung -------------------------------------------------------------------------
def weighted_age(rng):
    r = rng.random()
    if r < 0.03:
        return rng.randint(16, 17)
    if r < 0.33:
        return rng.randint(18, 25)
    if r < 0.68:
        return rng.randint(26, 35)
    if r < 0.88:
        return rng.randint(36, 45)
    return rng.randint(46, 58)


def one_line(text):
    return ", ".join(part.strip() for part in text.splitlines() if part.strip())


def years_before(day, years):
    try:
        return day.replace(year=day.year - years)
    except ValueError:  # 29/02
        return day.replace(year=day.year - years, day=28)


def make_person(fake, rng, index, today, soon_expiry):
    """Họ tên, ngày sinh, giấy tờ giả. soon_expiry: giấy tờ hết hạn trong 25 ngày tới."""
    male = rng.random() < 0.5
    name = fake.name_male() if male else fake.name_female()
    age = rng.randint(30, 50) if soon_expiry else weighted_age(rng)
    dob = today - datetime.timedelta(days=age * 365 + rng.randint(0, 364))
    if soon_expiry:
        expiry = today + datetime.timedelta(days=rng.randint(1, 25))
        issue = years_before(expiry, 10)
        id_type = IdDocType.CCCD_2016.value
    else:
        id_type = rng.choices(
            [IdDocType.CCCD_2021.value, IdDocType.CAN_CUOC_2024.value, IdDocType.CCCD_2016.value],
            [50, 20, 30],
        )[0]
        earliest = dob + datetime.timedelta(days=14 * 365 + 5)
        issue = max(earliest, today - datetime.timedelta(days=rng.randint(60, 365 * 6)))
        issue = min(issue, today - datetime.timedelta(days=30))
        expiry = issue + datetime.timedelta(days=365 * 10 + rng.randint(0, 365 * 5))
        if expiry <= today:  # giấy tờ còn hạn, trừ nhóm hết hạn trong 25 ngày
            expiry = today + datetime.timedelta(days=rng.randint(200, 3000))
    return {
        "name": name,
        "gender": Gender.MALE if male else Gender.FEMALE,
        "dob": dob,
        "issue": issue,
        "expiry": expiry,
        "id_type": id_type,
        "id_number": f"{ID_PREFIX}{index:09d}",
        "phone": f"0{rng.choice([3, 5, 7, 8, 9])}{rng.randint(10_000_000, 99_999_999)}",
    }


class Command(BaseCommand):
    help = "Nạp dữ liệu mẫu (4 tài khoản, danh mục, ~500 hồ sơ giả). Chạy tay; idempotent."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=500, help="Số hồ sơ mẫu (mặc định 500).")
        parser.add_argument(
            "--reset-passwords",
            action="store_true",
            help="Sinh lại và in mật khẩu tạm cho cả 4 tài khoản mẫu.",
        )

    def handle(self, *args, **options):
        today = timezone.localdate()
        with transaction.atomic():
            passwords = self.seed_users(options["reset_passwords"])
            catalog = self.seed_catalog()
            created = self.seed_workers(options["count"], today, catalog)
            if created:
                log(
                    AuditAction.CREATE,
                    object_type="core.SeedDemo",
                    object_id="seed_demo",
                    object_repr="seed_demo",
                    note=f"Nạp dữ liệu mẫu: {created} hồ sơ",
                )
        self.report(passwords, created)

    # ----- tài khoản ---------------------------------------------------------------------------
    def seed_users(self, reset):
        """Trả {username: mật khẩu tạm} cho tài khoản vừa tạo/đặt lại (in một lần)."""
        out = {}
        for username, full_name, role_code in USERS:
            user = User.objects.filter(username=username).first()
            if user is None:
                _, temp = account_services.create_user(
                    None,
                    username=username,
                    full_name=full_name,
                    role=Role.objects.get(code=role_code),
                )
                out[username] = temp
            elif reset:
                out[username] = account_services.reset_password(None, user)
        return out

    # ----- danh mục ----------------------------------------------------------------------------
    def seed_catalog(self):
        sections = {}
        for dep_order, (dep_name, secs) in enumerate(DEPARTMENTS.items(), start=1):
            dep, _ = Department.objects.get_or_create(
                name=dep_name, defaults={"sort_order": dep_order}
            )
            for sec_order, (sec_name, teams) in enumerate(secs.items(), start=1):
                sec, _ = Section.objects.get_or_create(
                    department=dep, name=sec_name, defaults={"sort_order": sec_order}
                )
                team_objs = [
                    Team.objects.get_or_create(section=sec, name=t, defaults={"sort_order": i})[0]
                    for i, t in enumerate(teams, start=1)
                ]
                sections[sec_name] = (sec, team_objs)
        positions = {
            name: Position.objects.get_or_create(name=name)[0]
            for names in POSITIONS.values()
            for name in names
        }
        shifts = [
            Shift.objects.get_or_create(name=n, defaults={"time_range": t})[0] for n, t in SHIFTS
        ]
        sources = [ApplicationSource.objects.get_or_create(name=n)[0] for n in SOURCES]
        levels = {lv.name: lv for lv in EducationLevel.objects.all()}
        clients = [
            ClientCompany.objects.get_or_create(name=name, location=location)[0]
            for name, location in CLIENT_COMPANIES
        ]
        return {
            "clients": clients,
            "sections": sections,
            "positions": positions,
            "shifts": shifts,
            "sources": sources,
            "levels": levels,
        }

    # ----- hồ sơ -------------------------------------------------------------------------------
    def seed_workers(self, count, today, catalog):
        wanted = {i: f"{ID_PREFIX}{i:09d}" for i in range(1, count + 1)}
        hashes = {i: compute_id_hash(n) for i, n in wanted.items()}
        existing = set(
            IdentityDocument.objects.filter(id_number_hash__in=list(hashes.values())).values_list(
                "id_number_hash", flat=True
            )
        )
        todo = [i for i in range(1, count + 1) if hashes[i] not in existing]
        if not todo:
            return 0
        scenarios = scenario_list(count)
        users = {u.username: u for u in User.objects.filter(username__in=["admin", "quanly", "hr"])}
        staff = [users["hr"], users["quanly"], users["admin"]]
        fake = Faker("vi_VN")

        plans = []
        soon_left = 8  # số công nhân có hợp đồng sắp hết hạn trong 30 ngày
        soon_id_left = max(1, round(count * 0.04))  # số có CCCD sắp hết hạn
        for i in todo:
            rng = random.Random(f"{SEED}-{i}")
            fake.seed_instance(SEED + i)
            plan = build_plan(scenarios[i - 1], rng, today)
            drafts = plan["sc"] in ("DRAFT", "ARCH_ABANDONED")
            soon_id = (not drafts) and soon_id_left > 0 and rng.random() < 0.08
            if soon_id:
                soon_id_left -= 1
            plan["person"] = make_person(fake, rng, i, today, soon_id)
            plan["index"], plan["rng"] = i, rng
            plan["creator"] = rng.choice(staff)
            plan["reviewer"] = rng.choice([u for u in staff[1:] if u != plan["creator"]])
            plan["address"] = one_line(fake.address())
            plan["perm_address"] = one_line(fake.address())
            plan["place"] = fake.city()
            plan["soon_contract"] = False
            emp = plan["emp"]
            if emp and soon_left > 0 and plan["sc"] == "VER_ACTIVE":
                start = plan["created"] + datetime.timedelta(days=emp["start"])
                # Hợp đồng 6 tháng bắt đầu sau thử việc (start + 61 ngày): cần làm đủ lâu.
                if (today - start).days >= 245:
                    plan["soon_contract"] = True
                    soon_left -= 1
            plans.append(plan)

        self.build_and_save(plans, today, catalog, staff, users)
        return len(plans)

    def build_and_save(self, plans, today, catalog, staff, users):
        # 1. Mã và hồ sơ gốc
        for p in plans:
            rng, person = p["rng"], p["person"]
            p["worker_code"] = next_code("WORKER")
            p["employee_code"] = next_code("EMPLOYEE") if p["emp"] else None
            last = max(
                [p["created"]]
                + [
                    p["created"] + datetime.timedelta(days=off)
                    for _, off, _, _ in p["chain"]
                    if p["created"] + datetime.timedelta(days=off) <= today
                ]
            )
            p["updated"] = p["created"] if p["stale"] else last
            worker = Worker(
                worker_code=p["worker_code"],
                employee_code=p["employee_code"],
                full_name=person["name"],
                name_search=compute_name_search(person["name"]),  # cùng hàm với Worker.save()
                date_of_birth=person["dob"],
                gender=person["gender"],
                nationality="Việt Nam",
                phone=person["phone"],
                email=f"nv{p['index']:05d}@example.com" if rng.random() < 0.4 else "",
                current_address=p["address"][:255],
                skills="\n".join(rng.sample(SKILLS, rng.randint(0, 3))),
                note="",
                verification_status=p["chain"][-1][0],
                created_by=p["creator"],
                created_at=at(p["created"], 7, 30),
                updated_at=at(p["updated"], 17, 0),
            )
            p["worker"] = worker
        with keep_dates(Worker):
            Worker.objects.bulk_create([p["worker"] for p in plans], batch_size=200)

        # 2. Bảng con của hồ sơ
        rows = {
            k: []
            for k in (
                "identity",
                "contacts",
                "consents",
                "status",
                "education",
                "experience",
                "certificates",
                "applications",
            )
        }
        for p in plans:
            self.children(p, rows, today, catalog, users)
        with keep_dates(IdentityDocument, DataConsent, StatusChange, Application):
            IdentityDocument.objects.bulk_create(rows["identity"], batch_size=200)
            EmergencyContact.objects.bulk_create(rows["contacts"], batch_size=200)
            DataConsent.objects.bulk_create(rows["consents"], batch_size=200)
            StatusChange.objects.bulk_create(rows["status"], batch_size=200)
            Application.objects.bulk_create(rows["applications"], batch_size=200)
        Education.objects.bulk_create(rows["education"], batch_size=200)
        WorkExperience.objects.bulk_create(rows["experience"], batch_size=200)
        Certificate.objects.bulk_create(rows["certificates"], batch_size=200)
        self.documents(plans, users)

        # 3. Làm việc, lịch sử, hợp đồng
        employments, history, contracts = [], [], []
        for p in plans:
            if p["emp"]:
                self.employment(p, employments, history, contracts, today, catalog, users)
        with keep_dates(Employment, EmploymentHistory, Contract):
            Employment.objects.bulk_create(employments, batch_size=200)
            EmploymentHistory.objects.bulk_create(history, batch_size=200)
            Contract.objects.bulk_create(contracts, batch_size=200)

        # 4. Đợt làm việc tại công ty khách và lịch sử lương (v1.1)
        assignments = []
        for p in plans:
            if p["emp"]:
                self.assignments(p, today, catalog, users, assignments)
        with keep_dates(WorkAssignment):
            WorkAssignment.objects.bulk_create(assignments, batch_size=200)
        salaries = [row for a in assignments for row in a.salary_plan]
        with keep_dates(SalaryHistory):
            SalaryHistory.objects.bulk_create(salaries, batch_size=200)

    def documents(self, plans, users):
        """Tài liệu mẫu (tệp ảnh giả "MẪU", không phải giấy tờ thật) để chỉ số "Hoàn thiện" và
        "Thiếu giấy tờ" có số liệu: ~70% hồ sơ đủ 4 nhóm bắt buộc, còn lại thiếu một phần."""
        types = {
            t.system_code: t
            for t in DocumentType.objects.filter(system_code__in=SEED_DOCUMENTS.keys())
        }
        if len(types) < len(SEED_DOCUMENTS):  # danh mục bị sửa mất loại hệ thống: bỏ qua
            return
        image = placeholder_png()
        rows = []
        for p in plans:
            rng = random.Random(f"{SEED}-doc-{p['index']}")
            drafts = p["sc"] in ("DRAFT", "ARCH_ABANDONED")
            if not drafts and rng.random() < 0.7:
                codes = list(SEED_DOCUMENTS)
            else:
                codes = rng.sample(list(SEED_DOCUMENTS), rng.randint(0, 3))
            checked = p["chain"][-1][0] in (
                VerificationStatus.VERIFIED,
                VerificationStatus.ARCHIVED,
            )
            for code in codes:
                doc = WorkerDocument(
                    worker=p["worker"],
                    document_type=types[code],
                    stored_file=ContentFile(image, name=f"mau-{code.lower()}.png"),
                    original_name=f"mau-{SEED_DOCUMENTS[code]}.png",
                    mime_type="image/png",
                    size_bytes=len(image),
                    uploaded_by=p["creator"],
                    uploaded_at=at(p["created"], 8, 0),
                )
                if checked:
                    doc.verification_status = DocumentVerificationStatus.MATCHED
                    doc.verified_by = users["quanly"]
                    doc.verified_at = at(p["created"], 9, 0)
                rows.append(doc)
        with keep_dates(WorkerDocument):
            WorkerDocument.objects.bulk_create(rows, batch_size=200)

    def children(self, p, rows, today, catalog, users):
        rng, person, worker = p["rng"], p["person"], p["worker"]
        created = p["created"]

        def day(off):
            return created + datetime.timedelta(days=off)

        drafts = p["sc"] in ("DRAFT", "ARCH_ABANDONED")
        # Giấy tờ: mã hóa số định danh, địa chỉ thường trú; băm bằng compute_id_hash.
        old_style = person["id_type"] == IdDocType.CCCD_2016.value
        rows["identity"].append(
            IdentityDocument(
                worker=worker,
                id_doc_type=person["id_type"],
                id_number_enc=person["id_number"],
                id_number_hash=compute_id_hash(person["id_number"]),  # cùng hàm với save()
                old_id_number_enc=None,
                issue_date=person["issue"],
                issue_place="Cục Cảnh sát quản lý hành chính về trật tự xã hội",
                expiry_date=person["expiry"],
                hometown=p["place"] if old_style else "",
                birth_registration_place="" if old_style else p["place"],
                permanent_address_enc=p["perm_address"],
                updated_at=at(p["updated"], 17, 0),
            )
        )
        for k in range(rng.randint(0, 1) if drafts else rng.randint(1, 2)):
            rows["contacts"].append(
                EmergencyContact(
                    worker=worker,
                    full_name=f"Người thân mẫu {p['index']}-{k + 1}",
                    relationship=rng.choice(RELATIONSHIPS),
                    phone=f"0{rng.choice([3, 5, 7, 8, 9])}{rng.randint(10_000_000, 99_999_999)}",
                    sort_order=k,
                )
            )
        if not drafts or rng.random() < 0.4:
            rows["consents"].append(
                DataConsent(
                    worker=worker,
                    consented=True,
                    consent_date=created,
                    method=ConsentMethod.ELECTRONIC,
                    recorded_by=p["creator"],
                    recorded_at=at(created, 7, 45),
                )
            )
        # Lịch sử trạng thái xác minh; giờ tăng dần theo thứ tự để cùng ngày vẫn đúng thứ tự.
        previous = ""
        for k, (to, off, who, reason_kind) in enumerate(p["chain"]):
            actor = {
                "creator": p["creator"],
                "reviewer": p["reviewer"],
                "manager": users["quanly"],
                "system": None,
            }[who]
            rows["status"].append(
                StatusChange(
                    worker=worker,
                    from_status=previous,
                    to_status=to,
                    reason=self.reason(reason_kind, p["worker_code"]),
                    changed_by=actor,
                    changed_at=at(day(off), 8 + 2 * k),
                )
            )
            previous = to
        # Ứng tuyển
        app = p["app"]
        interview = at(day(app["interview"]), 9) if app["interview"] is not None else None
        position = catalog["positions"][rng.choice(sum(POSITIONS.values(), []))]
        p["application"] = Application(
            worker=worker,
            position=position,
            source=rng.choice(catalog["sources"]),
            applied_date=created,
            expected_salary=Decimal(rng.randrange(6_000_000, 16_000_001, 500_000)),
            available_date=day(rng.randint(3, 20)) if rng.random() < 0.5 else None,
            status=app["status"],
            interview_at=interview,
            interview_notes="Ứng viên trao đổi rõ ràng." if interview else "",
            result_date=day(app["result"]) if app["result"] is not None else None,
            reject_reason="Chưa phù hợp vị trí tuyển dụng." if app["status"] == R.FAILED else "",
            created_by=p["creator"],
            created_at=at(created, 8, 30),
            updated_at=at(p["updated"], 17, 0),
        )
        rows["applications"].append(p["application"])
        # Học vấn, kinh nghiệm, chứng chỉ
        names = list(EDU_WEIGHTS)
        picks = {
            rng.choices(names, [EDU_WEIGHTS[n] for n in names])[0] for _ in range(rng.randint(1, 2))
        }
        birth_year = person["dob"].year
        for k, name in enumerate(sorted(picks, key=lambda n: catalog["levels"][n].rank)):
            end = min(today.year, birth_year + 17 + catalog["levels"][name].rank * 2 + k)
            rows["education"].append(
                Education(
                    worker=worker,
                    education_level=catalog["levels"][name],
                    school_name=f"Trường {name} mẫu số {rng.randint(1, 40)}",
                    major="" if catalog["levels"][name].rank <= 4 else "Kỹ thuật",
                    start_year=max(birth_year + 6, end - 3),
                    end_year=end,
                )
            )
        if not drafts:
            for _ in range(rng.randint(0, 2)):
                end_date = created - datetime.timedelta(days=rng.randint(30, 700))
                rows["experience"].append(
                    WorkExperience(
                        worker=worker,
                        company_name=f"Công ty mẫu {rng.randint(1, 99)}",
                        job_title=rng.choice(JOBS),
                        start_date=end_date - datetime.timedelta(days=rng.randint(180, 900)),
                        end_date=end_date,
                        description="Công việc theo ca.",
                    )
                )
            if rng.random() < 0.2:
                rows["certificates"].append(
                    Certificate(
                        worker=worker,
                        name="Chứng chỉ an toàn lao động",
                        issuer="Trung tâm đào tạo mẫu",
                        issue_date=created - datetime.timedelta(days=rng.randint(30, 400)),
                    )
                )

    @staticmethod
    def reason(kind, code):
        """Lý do do hệ thống tự điền: chỉ dùng mã hồ sơ, không họ tên (câu 30)."""
        return {
            "": "",
            "needs_info": f"Cần bổ sung thông tin giấy tờ (hồ sơ {code})",
            "rejected": f"Hồ sơ không đạt yêu cầu xác minh (hồ sơ {code})",
            "auto_resigned": f"Tự động Lưu trữ: đã nghỉ việc quá 30 ngày (hồ sơ {code})",
            "auto_failed": f"Tự động Lưu trữ: kết quả tuyển dụng quá 30 ngày (hồ sơ {code})",
            "auto_rejected": f"Tự động Lưu trữ: bị từ chối quá 30 ngày (hồ sơ {code})",
            "abandoned": f"Hồ sơ bỏ dở (hồ sơ {code})",
            "manual_candidate": "",
            "manual_employee": f"Lưu trữ theo đề nghị của quản lý (hồ sơ {code})",
        }[kind]

    def employment(self, p, employments, history, contracts, today, catalog, users):
        rng, worker, emp = p["rng"], p["worker"], p["emp"]
        created = p["created"]

        def day(off):
            return created + datetime.timedelta(days=off)

        sec_name = rng.choices(list(POSITIONS), [10, 40, 25, 15, 10])[0]
        section, teams = catalog["sections"][sec_name]
        team = rng.choice(teams) if teams else None
        position = catalog["positions"][rng.choice(POSITIONS[sec_name])]
        shift = (
            catalog["shifts"][3] if sec_name == "Văn phòng" else rng.choice(catalog["shifts"][:3])
        )
        # v1.1 (câu 48): bộ phận không bắt buộc; khoảng 5% công nhân chưa có bộ phận (bộ sinh riêng
        # để không đổi các giá trị ngẫu nhiên đã có).
        no_section = random.Random(p["index"] * 104729 + 7).random() < 0.05
        if no_section:
            section = team = None
        start = day(emp["start"])
        hist_rows = [(kind, frm, to, day(off)) for kind, frm, to, off in emp["hist"]]
        # Điều chuyển bộ phận (một số công nhân đang làm lâu)
        final_section, final_team = section, team
        tenure = (today - start).days
        if emp["status"] == W.ACTIVE and tenure >= 120 and rng.random() < 0.25 and section:
            others = [n for n in POSITIONS if n not in ("Văn phòng", sec_name)]
            new_name = rng.choice(others)
            final_section, new_teams = catalog["sections"][new_name]
            final_team = rng.choice(new_teams) if new_teams else None
            transfer = start + datetime.timedelta(days=rng.randint(70, tenure - 5))
            history.append(
                EmploymentHistory(
                    worker=worker,
                    change_type=EmploymentChangeType.TRANSFER,
                    effective_date=transfer,
                    decision_no=f"QD-{p['index']:05d}",
                    reason="Điều chuyển theo nhu cầu sản xuất",
                    from_section=section,
                    to_section=final_section,
                    from_team=team,
                    to_team=final_team,
                    created_by=users["quanly"],
                    created_at=at(transfer, 10),
                )
            )
        last_event = max([d for *_, d in hist_rows if d <= today] or [day(emp["received"])])
        employment = Employment(
            worker=worker,
            application=p["application"],
            received_date=day(emp["received"]),
            start_date=start,
            section=final_section,
            team=final_team,
            position=position,
            shift=shift,
            work_status=emp["status"],
            resign_date=day(emp["resign"]) if emp["resign"] is not None else None,
            resign_reason=emp["reason"],
            created_at=at(day(emp["received"]), 9),
            updated_at=at(last_event, 11),
        )
        employments.append(employment)
        for kind, frm, to, when in hist_rows:
            onboard = kind == EC.ONBOARD
            history.append(
                EmploymentHistory(
                    worker=worker,
                    change_type=kind,
                    effective_date=when,
                    reason="Tiếp nhận vào làm" if onboard else "",
                    to_section=section if onboard else None,
                    to_team=team if onboard else None,
                    to_position=position if onboard else None,
                    to_shift=shift if onboard else None,
                    from_work_status=frm,
                    to_work_status=to,
                    created_by=users["quanly"],
                    created_at=at(when, 9),
                )
            )
        self.contracts(p, worker, start, tenure, contracts, today, users)

    def assignments(self, p, today, catalog, users, out):
        """Đợt làm việc và lương giả của một công nhân. Dùng bộ sinh ngẫu nhiên riêng theo số thứ tự
        để không làm đổi các giá trị ngẫu nhiên đã có. Một phần công nhân chưa có đợt; một phần
        có hai đợt liền nhau cùng tên công ty khác địa điểm; một số đợt sắp đủ 12 tháng."""
        emp, worker = p["emp"], p["worker"]
        if emp["status"] == W.AWAITING:
            return
        rng = random.Random(p["index"] * 7919 + 13)
        if rng.random() < 0.12:
            return
        start = p["created"] + datetime.timedelta(days=emp["start"])
        tenure = (today - start).days
        end_final = (
            p["created"] + datetime.timedelta(days=emp["resign"])
            if emp["status"] == W.RESIGNED and emp["resign"] is not None
            else None
        )
        if tenure < 1 or (end_final is not None and end_final < start):
            return
        if emp["status"] == W.ACTIVE and tenure >= 345 and rng.random() < 0.5:
            start = today - datetime.timedelta(days=rng.randint(330, 350))  # sắp đủ 12 tháng
            tenure = (today - start).days
        clients = catalog["clients"]
        position = rng.choice(list(catalog["positions"].values()))
        span_days = ((end_final or today) - start).days  # công nhân đã nghỉ: tính tới ngày nghỉ
        if span_days >= 200 and rng.random() < 0.3:
            split = start + datetime.timedelta(days=span_days // 2)
            spans = [
                (clients[0], start, split - datetime.timedelta(days=1)),
                (clients[1], split, end_final),
            ]
        else:
            spans = [(rng.choice(clients), start, end_final)]
        for client, span_start, span_end in spans:
            assignment = WorkAssignment(
                worker=worker,
                client_company=client,
                position=position,
                start_date=span_start,
                end_date=span_end,
                created_by=users["quanly"],
                created_at=at(span_start, 9),
                updated_at=at(span_start, 9),
            )
            assignment.salary_plan = self.salary_rows(
                rng, assignment, min(span_end or today, today), users
            )
            out.append(assignment)

    def salary_rows(self, rng, assignment, last_day, users):
        """1–3 dòng lương, ngày áp dụng nằm trong khoảng đợt (lương gắn với đợt, câu 48)."""
        base = rng.randint(55, 120) * 100_000
        rows, day, step = [], assignment.start_date, 0
        while day <= last_day and step < 3:
            salary = base + step * rng.randint(2, 6) * 100_000
            price = round(salary * 1.3, -4) if rng.random() < 0.8 else None
            rows.append(
                SalaryHistory(
                    assignment=assignment,
                    worker=assignment.worker,
                    monthly_salary_enc=str(int(salary)),
                    client_unit_price_enc=str(int(price)) if price else None,
                    effective_date=day,
                    reason="Thiết lập ban đầu" if step == 0 else "Tăng lương theo bậc",
                    created_by=users["quanly"],
                    created_at=at(day, 9),
                )
            )
            day += datetime.timedelta(days=rng.randint(90, 200))
            step += 1
        return rows

    def contracts(self, p, worker, start, tenure, contracts, today, users):
        rng, emp = p["rng"], p["emp"]
        if emp["status"] == W.AWAITING:
            return
        n = f"HD-DEMO-{p['index']:05d}"
        probation_end = start + datetime.timedelta(days=60)
        contracts.append(
            Contract(
                worker=worker,
                contract_no=f"{n}-1",
                contract_type=ContractType.PROBATION,
                signed_date=start - datetime.timedelta(days=2),
                effective_date=start,
                expiry_date=probation_end,
                created_by=users["hr"],
                created_at=at(start, 9),
            )
        )
        if tenure < 62:
            return
        second_start = probation_end + datetime.timedelta(days=1)
        if p["soon_contract"]:  # sắp hết hạn trong 30 ngày (thẻ Dashboard, kịch bản 10)
            expiry = today + datetime.timedelta(days=rng.randint(1, 25))
            kind, eff = ContractType.FIXED_TERM, expiry - datetime.timedelta(days=180)
        elif emp["status"] == W.RESIGNED:
            resign = p["created"] + datetime.timedelta(days=emp["resign"])
            if resign <= second_start + datetime.timedelta(days=1):
                return
            kind, eff, expiry = ContractType.FIXED_TERM, second_start, resign
        elif rng.random() < 0.4:
            kind, eff, expiry = ContractType.INDEFINITE, second_start, None
        else:
            kind, eff = ContractType.FIXED_TERM, second_start
            expiry = second_start + datetime.timedelta(days=1095)
        contracts.append(
            Contract(
                worker=worker,
                contract_no=f"{n}-2",
                contract_type=kind,
                signed_date=eff - datetime.timedelta(days=2),
                effective_date=eff,
                expiry_date=expiry,
                created_by=users["hr"],
                created_at=at(eff, 9),
            )
        )

    # ----- báo cáo -----------------------------------------------------------------------------
    def report(self, passwords, created):
        self.stdout.write(
            f"Đã tạo {created} hồ sơ mẫu mới." if created else "Hồ sơ mẫu đã đủ, không tạo thêm."
        )
        if passwords:
            self.stdout.write("")
            self.stdout.write(
                "MẬT KHẨU TẠM (chỉ hiện một lần, không lưu ở đâu cả; phải đổi ở lần đăng nhập đầu):"
            )
            for username, temp in passwords.items():
                self.stdout.write(f"  {username:<8} {temp}")
        for username, _, _ in USERS:
            if username not in passwords:
                self.stdout.write(f"Tài khoản {username} đã có: giữ nguyên mật khẩu.")
