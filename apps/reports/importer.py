"""Nhập hồ sơ hàng loạt từ file Excel mẫu (docs/thiet-ke/excel-mau.md; câu 5, 16, 27, 48;
kịch bản 16).

- Mở bằng `load_workbook(read_only=True, data_only=False)`: ô công thức Excel THẬT (data_type "f")
  bị báo lỗi dòng; chữ thường bắt đầu bằng = + - @ (ví dụ gạch đầu dòng "- " ở Kỹ năng) vẫn nhận.
- TRƯỚC khi openpyxl mở: kiểm tra chữ ký .xlsx, kích thước và chống zip bomb (`check_zip_safe`).
- Mỗi dòng một giao dịch: dòng đúng được nhập, dòng sai bị bỏ qua và được báo (dòng, cột, lý do);
  cảnh báo không chặn. Dòng trống hoàn toàn bị bỏ qua.
- Hồ sơ tạo ra ở trạng thái Nháp (`create_worker`), người nhập là người tạo nên không tự duyệt được.
  Phần B (thông tin làm việc, đợt làm việc) chỉ Admin, Quản lý nhân sự; không nhập lương.
- Thông báo chỉ dẫn mã hồ sơ, không in họ tên của hồ sơ khác (câu 30).
"""

import datetime
import io
import re
import unicodedata
from dataclasses import dataclass, field

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.utils import timezone
from openpyxl import load_workbook

from apps.audit.services import log
from apps.core import excel
from apps.core.choices import AuditAction, Gender, IdDocType, ResignReason, WorkStatus
from apps.core.models import ClientCompany, Department, Position, Section, Shift, Team
from apps.core.text import collapse_spaces, normalize_key
from apps.core.validators import check_age
from apps.employment.assignments import AssignmentError
from apps.employment.services import EmploymentError, import_employment
from apps.workers.duplicates import find_by_id_number, find_similar
from apps.workers.models import Worker
from apps.workers.rules import MANAGERS
from apps.workers.services import WorkerDataError, create_worker
from apps.workers.validation import clean_id_number

from .excel_columns import BY_KEY, COLUMNS, HEADERS, SHEET_DATA, WORK_KEYS, letter

MAX_ROWS = 1000  # số dòng dữ liệu tối đa mỗi lần nhập (đo ở Phase 7, xem docs/hieu-nang.md)
MAX_BYTES = 10 * 1024 * 1024
MAX_SCANNED_BLANK = (
    20_000  # dừng đọc khi gặp quá nhiều dòng trống liên tiếp (tệp khai man kích thước)
)

MSG_NOT_XLSX = "Tệp phải là file Excel .xlsx. Hãy tải file mẫu và nhập lại."
MSG_TOO_BIG = (
    f"Tệp vượt giới hạn {MAX_BYTES // (1024 * 1024)} MB hoặc {MAX_ROWS} dòng. "
    "Hãy chia thành nhiều tệp nhỏ hơn."
)
MSG_FORMULA = "Ô không được chứa công thức Excel."
MSG_DATE_FORMAT = "Ngày phải theo dạng dd/mm/yyyy."
MSG_DATE_SWAP = "Ô ngày của Excel có thể bị đảo ngày/tháng; kiểm tra lại."
MSG_PHONE = "Số điện thoại phải gồm 10 chữ số, bắt đầu bằng 0."
MSG_WORK_ROLE = "Chỉ Admin hoặc Quản lý nhân sự được nhập thông tin làm việc."
EMPLOYEE_CODE = re.compile(r"[A-Za-z0-9-]{1,20}")
DASHES = str.maketrans({"-": "–", "—": "–", "‑": "–"})  # gạch nối các loại -> gạch ngang en

GENDERS = {normalize_key(label): value for value, label in Gender.choices}
ID_TYPES = {normalize_key(label): value for value, label in IdDocType.choices}
WORK_STATUSES = {normalize_key(label): value for value, label in WorkStatus.choices}
RESIGN_REASONS = {normalize_key(label): value for value, label in ResignReason.choices}


@dataclass
class Issue:
    row: int  # số dòng trong Excel (dòng tiêu đề là 1)
    column: str
    message: str

    @property
    def text(self):
        return f"Dòng {self.row} – {self.column}: {self.message}"


@dataclass
class ImportResult:
    read: int = 0
    imported: int = 0
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    file_error: str = ""

    @property
    def error_rows(self):
        return len({issue.row for issue in self.errors})

    @property
    def summary(self):
        return (
            f"Đã đọc {self.read} dòng. Nhập thành công {self.imported} hồ sơ. "
            f"{self.error_rows} dòng lỗi. {len(self.warnings)} cảnh báo."
        )


class Cell:
    """Giá trị đã chuẩn hóa của một ô: chữ, ngày (nếu ô kiểu ngày của Excel), có phải công thức."""

    __slots__ = ("text", "date", "formula")

    def __init__(self, text="", date=None, formula=False):
        self.text, self.date, self.formula = text, date, formula

    @property
    def empty(self):
        return not self.text and self.date is None and not self.formula


def read_cell(raw, *, multiline=False):
    if getattr(raw, "data_type", None) == "f":
        return Cell(formula=True)
    value = getattr(raw, "value", None)
    if value is None:
        return Cell()
    if isinstance(value, datetime.datetime):
        return Cell(date=value.date())
    if isinstance(value, datetime.date):
        return Cell(date=value)
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = unicodedata.normalize("NFC", str(value)).strip()
    return Cell(text if multiline else collapse_spaces(text))


# --- Mở tệp ------------------------------------------------------------------------------------
class FileProblem(Exception):
    """Lỗi cả tệp: không nhập dòng nào."""


def _open_sheet(data):
    if len(data) > MAX_BYTES:
        raise FileProblem(MSG_TOO_BIG)
    if not excel.is_xlsx(data):
        raise FileProblem(MSG_NOT_XLSX)
    try:
        excel.check_zip_safe(data)
    except excel.ExcelFileError as exc:
        raise FileProblem(exc.message) from exc
    try:
        book = load_workbook(io.BytesIO(data), read_only=True, data_only=False)
    except Exception as exc:  # noqa: BLE001 - tệp do người dùng tải lên, lỗi đọc đủ loại
        raise FileProblem(excel.MSG_INVALID) from exc
    if SHEET_DATA not in book.sheetnames:
        raise FileProblem(f"Không thấy sheet “{SHEET_DATA}”. Hãy dùng file mẫu mới nhất.")
    return book[SHEET_DATA]


def _read_rows(sheet):
    """[(số dòng Excel, [Cell...])] của các dòng có dữ liệu; kiểm tra tiêu đề và giới hạn dòng."""
    width = len(COLUMNS)
    rows, blank_run = [], 0
    for number, raw in enumerate(sheet.iter_rows(min_row=1, max_col=width), start=1):
        if number == 1:
            titles = [collapse_spaces(str(getattr(c, "value", "") or "")) for c in raw]
            titles += [""] * (width - len(titles))
            for index, (title, expected) in enumerate(zip(titles, HEADERS, strict=True), start=1):
                if title != expected:
                    col = letter(COLUMNS[index - 1].code)
                    raise FileProblem(
                        f"Tiêu đề cột không khớp file mẫu (cột {col}). Hãy dùng file mẫu mới nhất."
                    )
            continue
        multiline = [c.kind == "multiline" for c in COLUMNS]
        cells = [read_cell(c, multiline=m) for c, m in zip(raw, multiline, strict=False)]
        cells += [Cell()] * (width - len(cells))
        if all(c.empty for c in cells):
            blank_run += 1
            if blank_run > MAX_SCANNED_BLANK:
                break
            continue
        blank_run = 0
        rows.append((number, cells))
        if len(rows) > MAX_ROWS:
            raise FileProblem(MSG_TOO_BIG)
    return rows


# --- Danh mục ----------------------------------------------------------------------------------
class Catalogs:
    """Danh mục đang dùng, tra theo tên (không phân biệt hoa thường, giữ dấu)."""

    def __init__(self):
        self.departments = {
            normalize_key(d.name): d for d in Department.objects.filter(is_active=True)
        }
        self.sections = {}
        for s in Section.objects.filter(is_active=True).select_related("department"):
            self.sections.setdefault(normalize_key(s.name), []).append(s)
        self.teams = {}
        for t in Team.objects.filter(is_active=True).select_related("section"):
            self.teams.setdefault(normalize_key(t.name), []).append(t)
        self.positions = {normalize_key(p.name): p for p in Position.objects.filter(is_active=True)}
        self.shifts = {normalize_key(s.name): s for s in Shift.objects.filter(is_active=True)}
        self.companies = {
            normalize_key(str(c).translate(DASHES)): c
            for c in ClientCompany.objects.filter(is_active=True)
        }


@dataclass
class Row:
    """Kết quả kiểm tra một dòng: dữ liệu đã chuẩn hóa để ghi + lỗi + cảnh báo."""

    number: int
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    worker: dict = field(default_factory=dict)
    contacts: list = field(default_factory=list)
    work: dict = None  # None = dòng không có phần B

    def error(self, key, message):
        self.errors.append(Issue(self.number, label(key), message))

    def warn(self, key, message):
        self.warnings.append(Issue(self.number, label(key), message))


def label(key):
    return BY_KEY[key].header if key in BY_KEY else key


class Importer:
    def __init__(self, user, *, request=None, today=None):
        self.user = user
        self.request = request
        self.today = today or timezone.localdate()
        self.is_manager = user.role.code in MANAGERS
        self.catalogs = Catalogs()
        self.seen_numbers = {}  # số định danh -> số dòng đã nhập trong tệp này
        self.seen_codes = {}  # mã nhân viên -> số dòng đã nhập trong tệp này

    # ---- kiểm tra một dòng ----
    def check(self, number, cells):
        row = Row(number)
        v = {c.key: cells[i] for i, c in enumerate(COLUMNS)}
        for key, cell in v.items():
            if cell.formula:
                row.error(key, MSG_FORMULA)
        if row.errors:
            return row
        self._check_personal(row, v)
        has_work = any(not v[k].empty for k in WORK_KEYS)
        if has_work:
            if not self.is_manager:
                row.error("employee_code", MSG_WORK_ROLE)
            else:
                self._check_work(row, v)
        return row

    def date(self, row, v, key):
        cell = v[key]
        if cell.date is not None:
            row.warn(key, MSG_DATE_SWAP)
            return cell.date
        if not cell.text:
            return None
        match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", cell.text)
        try:
            if not match:
                raise ValueError
            return datetime.date(int(match[3]), int(match[2]), int(match[1]))
        except ValueError:
            row.error(key, MSG_DATE_FORMAT)
            return None

    def _check_personal(self, row, v):
        text = {k: c.text for k, c in v.items()}
        name = text["full_name"]
        if not name:
            row.error("full_name", "Họ và tên không được để trống.")
        elif len(name) > 100:
            row.error("full_name", "Họ và tên tối đa 100 ký tự.")
        phone = text["phone"]
        if not re.fullmatch(r"0\d{9}", phone):
            row.error("phone", MSG_PHONE)

        birth = self.date(row, v, "date_of_birth")
        today = self.today
        if birth:
            if birth > today:
                row.error("date_of_birth", "Ngày sinh không được ở tương lai.")
            else:
                age = check_age(birth, today)
                if age == "block":
                    row.error("date_of_birth", "Người dưới 15 tuổi không được nhập vào hệ thống.")
                elif age == "warn":
                    row.warn(
                        "date_of_birth",
                        "Người dưới 18 tuổi. Kiểm tra quy định sử dụng lao động chưa thành niên.",
                    )

        gender = ""
        if text["gender"]:
            gender = GENDERS.get(normalize_key(text["gender"]), "")
            if not gender:
                row.error("gender", "Giới tính chỉ nhận Nam hoặc Nữ.")

        id_number = clean_id_number(text["id_number"]) or ""
        id_type = ""
        if text["id_doc_type"]:
            id_type = ID_TYPES.get(normalize_key(text["id_doc_type"]), "")
            if not id_type:
                row.error("id_doc_type", "Loại giấy tờ không hợp lệ. Hãy chọn từ danh sách.")
        elif id_number:
            row.error("id_doc_type", "Cần chọn loại giấy tờ khi đã nhập số định danh.")
        if id_number:
            self._check_id_number(row, id_number)
        issue = self.date(row, v, "issue_date")
        expiry = self.date(row, v, "expiry_date")
        if issue and birth and issue <= birth:
            row.error("issue_date", "Ngày cấp phải sau ngày sinh.")
        if expiry and issue and expiry <= issue:
            row.error("expiry_date", "Ngày hết hạn phải sau ngày cấp.")
        old_id = clean_id_number(text["old_id_number"]) or ""
        if old_id and not re.fullmatch(r"\d{9}|\d{12}", old_id):
            row.error("old_id_number", "Số CMND cũ phải gồm 9 hoặc 12 chữ số.")
        if text["email"]:
            try:
                validate_email(text["email"])
            except ValidationError:
                row.error("email", "Email không đúng định dạng.")

        contact = [text["contact_name"], text["contact_relationship"], text["contact_phone"]]
        if any(contact):
            if not all(contact):
                row.error(
                    "contact_name",
                    "Thông tin người liên hệ khẩn cấp phải điền đủ họ tên, quan hệ và SĐT.",
                )
            elif not re.fullmatch(r"0\d{9}", text["contact_phone"]):
                row.error("contact_phone", MSG_PHONE)
            else:
                row.contacts = [
                    {"full_name": contact[0], "relationship": contact[1], "phone": contact[2]}
                ]

        row.worker = {
            "full_name": name,
            "phone": phone,
            "date_of_birth": birth,
            "gender": gender,
            "nationality": text["nationality"] or "Việt Nam",
            "email": text["email"],
            "current_address": text["current_address"],
            "skills": text["skills"],
            "note": text["note"],
            "id_doc_type": id_type,
            "id_number": id_number or None,
            "old_id_number": old_id or None,
            "issue_date": issue,
            "issue_place": text["issue_place"],
            "expiry_date": expiry,
            "hometown": text["hometown"],
            "birth_registration_place": text["birth_registration_place"],
            "permanent_address": text["permanent_address"] or None,
        }

    def _check_id_number(self, row, id_number):
        if not re.fullmatch(r"\d{12}", id_number):
            row.error("id_number", "Số CCCD phải gồm 12 chữ số.")
            return
        if id_number in self.seen_numbers:
            row.error(
                "id_number",
                f"Số CCCD trùng với dòng {self.seen_numbers[id_number]} trong cùng tệp.",
            )
            return
        existing = find_by_id_number(id_number)
        if existing is not None:
            row.error("id_number", f"Số CCCD đã có trong hồ sơ {existing.worker_code}.")

    # ---- phần B ----
    def _check_work(self, row, v):
        text = {k: c.text for k, c in v.items()}
        work = {}
        code = text["employee_code"]
        if not code:
            row.error("employee_code", "Cần nhập mã nhân viên khi có thông tin làm việc.")
        elif not EMPLOYEE_CODE.fullmatch(code):
            row.error(
                "employee_code",
                "Mã nhân viên tối đa 20 ký tự, chỉ gồm chữ, số và dấu gạch ngang.",
            )
        elif code in self.seen_codes:
            row.error(
                "employee_code",
                f"Mã nhân viên {code} trùng với dòng {self.seen_codes[code]} trong cùng tệp.",
            )
        elif Worker.objects.filter(employee_code=code).exists():
            row.error("employee_code", f"Mã nhân viên {code} đã được dùng.")
        work["employee_code"] = code

        section = self._section(row, text)
        work["section"] = section
        work["team"] = self._team(row, text, section)
        position = None
        if not text["position"]:
            row.error("position", "Cần nhập chức danh khi có thông tin làm việc.")
        else:
            position = self.catalogs.positions.get(normalize_key(text["position"]))
            if position is None:
                row.error("position", self._missing(text["position"]))
        work["position"] = position
        work["shift"] = self._lookup(row, "shift", text["shift"], self.catalogs.shifts)

        received = self.date(row, v, "received_date")
        start = self.date(row, v, "start_date")
        if not v["start_date"].text and v["start_date"].date is None:
            row.error("start_date", "Cần nhập ngày vào làm khi có thông tin làm việc.")
        birth = row.worker.get("date_of_birth")
        if start and birth and start <= birth:
            row.error("start_date", "Ngày vào làm phải sau ngày sinh.")
        if received and start and received > start:
            row.error("received_date", "Ngày tiếp nhận không được sau ngày vào làm.")
        work["start_date"] = start
        work["received_date"] = received or start

        status = ""
        if not text["work_status"]:
            row.error("work_status", "Cần nhập trạng thái làm việc khi có thông tin làm việc.")
        else:
            status = WORK_STATUSES.get(normalize_key(text["work_status"]), "")
            if not status:
                row.error("work_status", "Trạng thái làm việc không hợp lệ. Hãy chọn từ danh sách.")
        work["work_status"] = status
        resign_date = self.date(row, v, "resign_date")
        reason = ""
        if text["resign_reason"]:
            reason = RESIGN_REASONS.get(normalize_key(text["resign_reason"]), "")
            if not reason:
                row.error("resign_reason", "Lý do nghỉ không hợp lệ. Hãy chọn từ danh sách.")
        if status == WorkStatus.RESIGNED:
            if not resign_date or not text["resign_reason"]:
                row.error("resign_date", "Trạng thái Đã nghỉ việc cần ngày nghỉ và lý do nghỉ.")
            elif start and resign_date <= start:
                row.error("resign_date", "Ngày nghỉ việc phải sau ngày vào làm.")
        elif status and (resign_date or text["resign_reason"]):
            row.error(
                "resign_date",
                "Chỉ nhập ngày nghỉ việc và lý do nghỉ khi trạng thái là Đã nghỉ việc.",
            )
        work["resign_date"] = resign_date
        work["resign_reason"] = reason

        company = None
        assignment_start = self.date(row, v, "assignment_start")
        has_start = v["assignment_start"].date is not None or bool(v["assignment_start"].text)
        if text["client_company"]:
            company = self.catalogs.companies.get(
                normalize_key(text["client_company"].translate(DASHES))
            )
            if company is None:
                row.error(
                    "client_company",
                    f"Công ty khách “{text['client_company']}” đã ngừng sử dụng "
                    "(hoặc không khớp cả tên và địa điểm).",
                )
            if not has_start:
                row.error("assignment_start", "Cần nhập ngày bắt đầu đợt khi có công ty khách.")
            elif assignment_start and birth and assignment_start <= birth:
                row.error("assignment_start", "Ngày bắt đầu đợt phải sau ngày sinh.")
            elif (
                assignment_start
                and status == WorkStatus.RESIGNED
                and resign_date
                and assignment_start > resign_date
            ):
                row.error("assignment_start", "Ngày bắt đầu đợt không được sau ngày nghỉ việc.")
        elif has_start:
            row.error("assignment_start", "Chỉ nhập ngày bắt đầu đợt khi có công ty khách.")
        work["client_company"] = company
        work["assignment_start"] = assignment_start
        row.work = work

    def _missing(self, value):
        return f"Không tìm thấy “{value}” trong danh mục. Hãy chọn từ sheet Danh mục."

    def _lookup(self, row, key, value, mapping):
        if not value:
            return None
        found = mapping.get(normalize_key(value))
        if found is None:
            row.error(key, self._missing(value))
        return found

    def _section(self, row, text):
        dep_name, name = text["department"], text["section"]
        department = None
        if dep_name:
            department = self.catalogs.departments.get(normalize_key(dep_name))
            if department is None:
                row.error("department", self._missing(dep_name))
        if not name:
            if dep_name:
                row.error("section", "Cần nhập bộ phận (B3) khi có phòng ban hoặc tổ.")
            elif text["team"]:
                row.error("team", "Cần nhập bộ phận (B3) khi có phòng ban hoặc tổ.")
            return None
        matches = self.catalogs.sections.get(normalize_key(name), [])
        if not matches:
            row.error("section", self._missing(name))
            return None
        if dep_name and department is not None:
            in_department = [s for s in matches if s.department_id == department.pk]
            if not in_department:
                row.error("department", f"Bộ phận “{name}” không thuộc phòng ban “{dep_name}”.")
                return None
            return in_department[0]
        if len(matches) > 1:
            row.error("department", f"Có nhiều bộ phận tên “{name}”; hãy ghi thêm phòng ban.")
            return None
        return matches[0]

    def _team(self, row, text, section):
        name = text["team"]
        if not name or section is None:
            return None
        matches = self.catalogs.teams.get(normalize_key(name), [])
        for team in matches:
            if team.section_id == section.pk:
                return team
        if matches:
            row.error("team", f"Tổ “{name}” không thuộc bộ phận “{section.name}”.")
        else:
            row.error("team", self._missing(name))
        return None

    # ---- ghi một dòng ----
    def similar_warnings(self, row):
        data = row.worker
        found = find_similar(
            phone=data["phone"], full_name=data["full_name"], date_of_birth=data["date_of_birth"]
        )
        for match in found:
            if match.by_phone:
                row.warn(
                    "phone",
                    f"Số điện thoại trùng hồ sơ {match.worker.worker_code}. "
                    "Kiểm tra có phải cùng một người.",
                )
            if match.by_name_dob:
                row.warn(
                    "full_name",
                    f"Họ tên và ngày sinh trùng hồ sơ {match.worker.worker_code}. "
                    "Kiểm tra có phải cùng một người.",
                )

    def write(self, row):
        """Ghi một dòng đã hợp lệ trong một giao dịch riêng; trả True nếu thành công, ngược lại thêm
        lỗi vào `row.errors` (giao dịch đã hoàn tác)."""
        try:
            with transaction.atomic():
                worker = create_worker(self.user, row.worker, row.contacts, request=self.request)
                if row.work is not None:
                    w = row.work
                    import_employment(
                        self.user,
                        worker,
                        employee_code=w["employee_code"],
                        received_date=w["received_date"],
                        start_date=w["start_date"],
                        position=w["position"],
                        work_status=w["work_status"],
                        section=w["section"],
                        team=w["team"],
                        shift=w["shift"],
                        resign_date=w["resign_date"],
                        resign_reason=w["resign_reason"],
                        client_company=w["client_company"],
                        assignment_start=w["assignment_start"],
                        request=self.request,
                    )
        except WorkerDataError as exc:
            for key, message in exc.errors.items():
                row.error(key, message)
            for fields in exc.contact_errors.values():
                for message in fields.values():
                    row.error("contact_name", message)
        except EmploymentError as exc:
            for key, message in exc.errors.items():
                row.error(key, message)
            if not exc.errors:
                row.error("employee_code", exc.message)
        except AssignmentError as exc:
            mapping = {
                "start_date": "assignment_start",
                "end_date": "resign_date",
                "previous_end_date": "assignment_start",
            }
            for key, message in exc.errors.items():
                row.error(mapping.get(key, key), message)
            if not exc.errors:
                row.error("client_company", exc.message)
        except PermissionDenied:
            row.error("employee_code", MSG_WORK_ROLE)
        except IntegrityError:
            row.error("full_name", "Không lưu được dòng này vì dữ liệu trùng với hồ sơ khác.")
        if row.errors:
            return False
        if row.work is not None:
            self.seen_codes[row.work["employee_code"]] = row.number
        if row.worker["id_number"]:
            self.seen_numbers[row.worker["id_number"]] = row.number
        return True


def import_workbook(user, data, *, request=None):
    """Đọc và nhập một file Excel (bytes). Trả ImportResult; ghi một dòng nhật ký IMPORT cả lần."""
    result = ImportResult()
    try:
        rows = _read_rows(_open_sheet(data))
    except FileProblem as exc:
        result.file_error = str(exc)
        return result
    importer = Importer(user, request=request)
    result.read = len(rows)
    for number, cells in rows:
        row = importer.check(number, cells)
        if not row.errors:
            importer.similar_warnings(row)
            importer.write(row)
        result.errors.extend(row.errors)
        if not row.errors:
            result.imported += 1
            result.warnings.extend(row.warnings)
    log(
        AuditAction.IMPORT,
        user=user,
        object_type="excel_import",
        object_id="nhap-excel",
        object_repr="Nhập hồ sơ từ Excel",
        note=(
            f"Đọc {result.read} dòng; nhập {result.imported}; lỗi {result.error_rows}; "
            f"cảnh báo {len(result.warnings)}"
        ),
        request=request,
    )
    return result
