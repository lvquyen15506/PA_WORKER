"""Trích văn bản CV và gợi ý trường (docs/yeu-cau.md mục V, phần CV).

PDF: pdfplumber (lớp chữ; PDF scan thì vẽ tối đa 3 trang ≤ 300 dpi rồi OCR). DOCX: python-docx.
DOC: antiword. JPG/PNG: Tesseract. Kết quả chỉ là GỢI Ý: không tự điền hồ sơ, không tạo thông tin
không có trong CV (HR bôi đen đoạn chữ rồi chọn "Đưa vào trường…").
"""

import io
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field

from django.conf import settings

from apps.core.text import compute_name_search

from . import imaging
from .budget import Budget
from .ocr import ocr_lines

MAX_TEXT_CHARS = 50_000
MSG_NO_TEXT = "Không đọc được chữ trong CV. Hãy nhập tay các mục cần thiết."
MSG_DOC_FAILED = "Không đọc được tệp .doc này. Hãy lưu lại thành .docx hoặc PDF rồi tải lên."
MSG_PDF_FAILED = "Không mở được tệp PDF. Tệp có thể bị hỏng hoặc có mật khẩu."
MSG_DOCX_FAILED = "Không mở được tệp .docx. Tệp có thể bị hỏng."
WARN_PARTIAL = "CV dài hoặc quét ảnh: chỉ đọc các trang đầu."
WARN_TIMEOUT = "Hết thời gian xử lý, vui lòng kiểm tra tay."


class CvError(Exception):
    """CV không đọc được; `args[0]` là thông báo tiếng Việt."""


@dataclass
class CvText:
    text: str = ""
    warnings: list = field(default_factory=list)
    ocr_used: bool = False

    def as_dict(self):
        return {"text": self.text, "warnings": list(self.warnings), "ocr_used": self.ocr_used}


def _clean(text):
    text = (text or "").replace("\r", "").replace("\x00", "")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return "\n".join(line.strip() for line in text.split("\n")).strip()[:MAX_TEXT_CHARS]


def _lines_to_text(lines):
    return "\n".join(" ".join(word.text for word in line) for line in lines)


def _ocr_image(image, budget, engine, result):
    lines = ocr_lines(image, budget, engine)
    if lines is None:
        result.warnings.append(WARN_TIMEOUT)
        return ""
    result.ocr_used = True
    return _lines_to_text(lines)


def _render_dpi(width_pt, height_pt):
    """Độ phân giải vẽ trang PDF: tối đa CV_MAX_DPI, hạ xuống nếu ảnh vượt giới hạn điểm ảnh."""
    area_inch = max(width_pt * height_pt / (72 * 72), 1e-6)
    by_pixels = (settings.MAX_IMAGE_PIXELS * 0.9 / area_inch) ** 0.5
    return max(10, min(settings.CV_MAX_DPI, int(by_pixels)))


def _from_pdf(data, budget, engine, result):
    import pdfplumber

    try:
        pdf = pdfplumber.open(io.BytesIO(data))
    except Exception as exc:
        raise CvError(MSG_PDF_FAILED) from exc
    with pdf:
        pages = pdf.pages
        parts = [page.extract_text() or "" for page in pages[: settings.CV_MAX_TEXT_PAGES]]
        text = "\n".join(parts)
        if len(pages) > settings.CV_MAX_TEXT_PAGES:
            result.warnings.append(WARN_PARTIAL)
        if text.strip():
            return text
        # PDF scan: vẽ vài trang đầu ra ảnh rồi OCR
        if len(pages) > settings.CV_MAX_OCR_PAGES and WARN_PARTIAL not in result.warnings:
            result.warnings.append(WARN_PARTIAL)
        chunks = []
        for page in pages[: settings.CV_MAX_OCR_PAGES]:
            if budget.expired:
                budget.mark_exhausted()
                result.warnings.append(WARN_TIMEOUT)
                break
            dpi = _render_dpi(float(page.width), float(page.height))
            image = page.to_image(resolution=dpi).original.convert("RGB")
            chunks.append(_ocr_image(image, budget, engine, result))
        return "\n".join(chunks)


def _from_docx(data):
    import docx

    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise CvError(MSG_DOCX_FAILED) from exc
    parts = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text.strip() for cell in row.cells))
    return "\n".join(parts)


def _from_doc(data, budget):
    timeout = budget.timeout_for(settings.ANTIWORD_TIMEOUT_SECONDS)
    if timeout <= 0:
        budget.mark_exhausted()
        return ""
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "cv.doc")
        with open(path, "wb") as handle:
            handle.write(data)
        try:
            run = subprocess.run(
                ["antiword", "-m", "UTF-8.txt", path],
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            budget.mark_exhausted()
            return ""
        except OSError as exc:
            raise CvError(MSG_DOC_FAILED) from exc
    if run.returncode != 0:
        raise CvError(MSG_DOC_FAILED)
    return run.stdout.decode("utf-8", errors="replace")


def extract_text(data, kind, budget=None, engine=None):
    """Trích văn bản từ CV. `kind`: PDF, DOCX, DOC, JPG hoặc PNG (kết quả của
    apps.documents.validators.detect_kind). Trả CvText; ném CvError (tiếng Việt) hoặc
    imaging.ImageRejected khi tệp không dùng được."""
    budget = budget or Budget()
    result = CvText()
    if kind == "PDF":
        raw = _from_pdf(data, budget, engine, result)
    elif kind == "DOCX":
        raw = _from_docx(data)
    elif kind == "DOC":
        raw = _from_doc(data, budget)
    elif kind in ("JPG", "PNG"):
        raw = _ocr_image(imaging.load_image(data), budget, engine, result)
    else:
        raise CvError("CV chỉ nhận PDF, DOC, DOCX, JPG hoặc PNG.")
    if budget.exhausted and WARN_TIMEOUT not in result.warnings:
        result.warnings.append(WARN_TIMEOUT)
    result.text = _clean(raw)
    if not result.text and WARN_TIMEOUT not in result.warnings:
        result.warnings.append(MSG_NO_TEXT)
    return result


# ----- gợi ý: chỉ nhận mẫu rõ ràng, không tự điền -----

HEADINGS = {
    "education": ("Học vấn", ["hoc van", "trinh do hoc van"]),
    "experience": ("Kinh nghiệm", ["kinh nghiem", "qua trinh lam viec"]),
    "skills": ("Kỹ năng", ["ky nang"]),
    "certificate": ("Chứng chỉ", ["chung chi", "bang cap"]),
}
_PHONE = re.compile(r"(?<![\d])(?:\+84|84|0)(?:[\s.\-]?\d){8,9}(?![\d])")
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_DATE = re.compile(r"(?<![\d/])(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})(?![\d])")
_MONTH_YEAR = re.compile(r"(?<![\d/])(\d{1,2})/(\d{4})(?![\d/])")


def _phone(raw):
    digits = re.sub(r"\D", "", raw)
    if raw.strip().startswith("+84") or (digits.startswith("84") and len(digits) == 11):
        digits = "0" + digits[2:]
    return digits if re.fullmatch(r"0\d{9}", digits) else None


def _unique(items):
    seen, out = set(), []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _heading_key(line):
    norm = compute_name_search(line).strip(" :-–_*#")
    words = norm.split()
    if not words or len(words) > 6:
        return None
    for key, (_, labels) in HEADINGS.items():
        if any(norm == label or norm.startswith(label + " ") for label in labels):
            return key
    return None


def find_hints(text):
    """Nhận các mẫu rõ ràng trong văn bản CV. Trả dict:
    phones (10 số), emails, dates (dd/mm/yyyy), month_years (mm/yyyy), headings, sections
    ({"education"|"experience"|"skills"|"certificate": đoạn chữ dưới đề mục}). Không đoán."""
    text = text or ""
    phones = _unique(p for p in (_phone(m.group()) for m in _PHONE.finditer(text)) if p)
    emails = _unique(m.group().lower() for m in _EMAIL.finditer(text))
    dates = []
    for m in _DATE.finditer(text):
        day, month, year = (int(g) for g in m.groups())
        if 1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2100:
            dates.append(f"{day:02d}/{month:02d}/{year}")
    month_years = _unique(
        f"{int(m.group(1)):02d}/{m.group(2)}"
        for m in _MONTH_YEAR.finditer(text)
        if 1 <= int(m.group(1)) <= 12
    )
    headings, sections, current = [], {}, None
    for line in text.split("\n"):
        key = _heading_key(line)
        if key:
            current = key
            headings.append({"key": key, "label": HEADINGS[key][0], "line": line.strip()})
            sections.setdefault(key, [])
        elif current and line.strip():
            sections[current].append(line.strip())
    return {
        "phones": phones,
        "emails": emails,
        "dates": _unique(dates),
        "month_years": month_years,
        "headings": headings,
        "sections": {k: "\n".join(v) for k, v in sections.items() if v},
    }
