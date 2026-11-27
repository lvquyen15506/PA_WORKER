"""Tạo 3 tài liệu bàn giao dạng Word (.docx) từ tài liệu markdown có sẵn.

Chạy bằng python-docx + Pillow (cả hai đã có trong requirements.txt):
    - Trên máy (host):   py -3.12 scripts/tao_tai_lieu_word.py
    - Trong container web: docker compose exec -T web python scripts/tao_tai_lieu_word.py

Đầu ra (cả .docx) nằm trong docs/ban-giao/:
    - Pa-Worker-Huong-dan-cai-dat.docx
    - Pa-Worker-Huong-dan-su-dung.docx
    - Pa-Worker-Xu-ly-su-co.docx

Mỗi ảnh minh họa được nhúng ngay dưới thao tác; ảnh chưa chụp được (bước cài
Docker Desktop/WSL…) để khung "[ẢNH CẦN CHỤP: …]" để người nhận thay trong Word.
Ảnh đã có thì có thể khoanh vùng cần bấm bằng khung đỏ (Pillow).
Tài liệu dùng dữ liệu giả lập (CCCD 999…), không có dữ liệu thật.

Quy ước: khổ A4, font hệ thống có dấu (Segoe UI), cỡ 12, trang bìa, mục lục,
đầu/chân trang có số trang, ảnh rộng vừa lề (16 cm), chú thích "Hình x: …".
"""

from __future__ import annotations

import datetime
import io
import re
import unicodedata
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "docs" / "screenshots"
OUT = ROOT / "docs" / "ban-giao"
OUT.mkdir(parents=True, exist_ok=True)

FONT = "Segoe UI"
NGAY = datetime.date.today().strftime("%d/%m/%Y")
PHIEN_BAN = "1.1.1"
MUC_RONG = 16.0  # cm, rộng ảnh vừa lề A4 (21 - 2*2 = 17, chừa lề an toàn)

# Vị trí khung đỏ (tỉ lệ 0–1 so với chiều ngang/dọc của ảnh) để khoanh vùng
# cần bấm. Giá trị xấp xỉ theo bố cục 1366x768; ảnh không có trong bảng thì
# chèn nguyên (không khoanh). Có thể điều chỉnh lại khi xem thử PDF.
KHUNG_DAU: dict[str, list[tuple[float, float, float, float]]] = {
    "phase-8/01-dang-nhap-1366x768.png": [(0.30, 0.30, 0.70, 0.60)],  # ô tên + mật khẩu + nút
    "phase-3/doi-mat-khau-1366x768.png": [(0.30, 0.28, 0.70, 0.60)],
    "phase-3/tai-khoan-1366x768.png": [(0.03, 0.12, 0.40, 0.30)],
    "phase-4/02-danh-sach-loc-tim-1366x768.png": [(0.03, 0.10, 0.60, 0.30)],
    "phase-4/08-chi-tiet-ca-nhan-1366x768.png": [(0.02, 0.04, 0.35, 0.16)],
    "phase-4/17-duyet-ho-so-1366x768.png": [(0.60, 0.30, 0.97, 0.55)],
    "phase-4/19-hop-tra-lai-1366x768.png": [(0.25, 0.35, 0.80, 0.70)],
    "phase-4/23-viewer-chi-tiet-1366x768.png": [(0.02, 0.04, 0.35, 0.16)],
    "phase-5/07-doi-chieu-qr-1366x768.png": [(0.50, 0.10, 0.95, 0.90)],
    "phase-5/09-doi-chieu-to-vang-1366x768.png": [(0.50, 0.10, 0.95, 0.90)],
    "phase-6/01-danh-muc-phong-ban-1366x768.png": [(0.03, 0.10, 0.40, 0.45)],
    "phase-6/26-lam-viec-day-du-1366x768.png": [(0.02, 0.04, 0.35, 0.16)],
    "phase-6/34-lich-su-luong-1366x768.png": [(0.50, 0.35, 0.95, 0.80)],
    "phase-7/kt-dashboard-1366x768.png": [(0.02, 0.10, 0.97, 0.40)],
    "phase-7/kt-nhap-excel-1366x768.png": [(0.03, 0.15, 0.90, 0.55)],
    "phase-7/kt-nhat-ky-1366x768.png": [(0.03, 0.10, 0.50, 0.35)],
}


def slug(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


class TaiLieu:
    def __init__(self, ten: str, ghi_so: str):
        self.ten = ten
        self.ghi_so = ghi_so
        self.document = Document()
        self._count_hinh = 0
        self._count_phai_chup = 0
        self._set_page()

    # ---- thiết lập ----

    def _set_page(self):
        style = self.document.styles["Normal"]
        style.font.name = FONT
        style.font.size = Pt(12)
        style.element.rPr.rFonts.set(qn("w:cs"), FONT)
        sec = self.document.sections[0]
        sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
        sec.left_margin = sec.right_margin = Cm(2.0)
        sec.top_margin = sec.bottom_margin = Cm(2.0)

    def _shading(self, p, fill: str):
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:fill"), fill)
        p._p.get_or_add_pPr().append(shd)

    # ---- khối nội dung ----

    def _para(
        self, text="", bold=False, size=12, align=None, space_after=8, color=None, italic=False
    ):
        p = self.document.add_paragraph()
        r = p.add_run(text)
        r.font.name = FONT
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.italic = italic
        if color:
            r.font.color.rgb = RGBColor(*color)
        p.paragraph_format.space_after = Pt(space_after)
        if align is not None:
            p.alignment = align
        return p

    def _rich(self, text: str, size=12, indent=None, space_after=8):
        """Đoạn có mix chữ thường và phần @@in đậm@@ (từ markdown **)."""
        # Bỏ link markdown [chữ](đường-dẫn) -> giữ "chữ"; link URL đứng một
        # mình giữ nguyên (để người dùng biết chỗ tải).
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda m: m.group(1), text)
        p = self.document.add_paragraph()
        p.paragraph_format.space_after = Pt(space_after)
        if indent is not None:
            p.paragraph_format.left_indent = Cm(indent)
        for part in re.split(r"(@@.*?@@)", text):
            if not part:
                continue
            if part.startswith("@@") and part.endswith("@@"):
                r = p.add_run(part[2:-2])
                r.font.bold = True
            else:
                r = p.add_run(part)
            r.font.name = FONT
            r.font.size = Pt(size)
        return p

    def heading(self, text: str, level: int):
        size, name = {1: (18, "Heading 1"), 2: (15, "Heading 2"), 3: (13, "Heading 3")}[
            min(level, 3)
        ]
        p = self.document.add_paragraph(style=name)
        r = p.add_run(text)
        r.font.name = FONT
        r.font.size = Pt(size)
        r.font.bold = True
        r.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(6)

    def bullet(self, text: str):
        p = self._rich(text.replace("**", "@@"), indent=0.6, space_after=3)
        p.style = self.document.styles["List Bullet"]

    def number_item(self, text: str):
        self._rich(text.replace("**", "@@"), indent=0.6, space_after=4)

    def code_block(self, lines):
        p = self.document.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.5)
        p.paragraph_format.space_after = Pt(8)
        r = p.add_run("\n".join(lines))
        r.font.name = "Consolas"
        r.font.size = Pt(11)
        self._shading(p, "F2F2F2")

    def blockquote(self, text: str):
        p = self._rich(text.replace("**", "@@"), indent=0.5, space_after=8)
        self._shading(p, "F5F7FA")

    def bang(self, rows):
        if not rows:
            return
        ncols = max(len(r) for r in rows)
        table = self.document.add_table(rows=len(rows), cols=ncols)
        table.style = "Table Grid"
        for ri, row in enumerate(rows):
            for ci in range(ncols):
                cell = table.cell(ri, ci)
                text = row[ci] if ci < len(row) else ""
                text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
                text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
                cell.text = ""
                p = cell.paragraphs[0]
                r = p.add_run(text)
                r.font.name = FONT
                r.font.size = Pt(10)
                if ri == 0:
                    r.font.bold = True
                    self._shading(p, "E8EEF7")
        self.document.add_paragraph().paragraph_format.space_after = Pt(2)

    # ---- ảnh ----

    def hinh(self, image_ref: str, chu_thich: str):
        """image_ref dạng "screenshots/phase-x/y.png" (tương đối với docs/).

        Có ảnh -> nhúng (vẽ khung đỏ nếu trong KHUNG_DAU). Không có -> khung
        "[ẢNH CẦN CHỤP: ...]" để người nhận thay trong Word.
        """
        abs_path = (ROOT / "docs" / image_ref).resolve() if image_ref else None
        if abs_path and abs_path.exists():
            key = image_ref.replace("screenshots/", "")
            if key in KHUNG_DAU:
                img = Image.open(abs_path).convert("RGB")
                draw = ImageDraw.Draw(img)
                w, h = img.size
                for x0f, y0f, x1f, y1f in KHUNG_DAU[key]:
                    x0, y0, x1, y1 = int(w * x0f), int(h * y0f), int(w * x1f), int(h * y1f)
                    for t in range(4):  # khung đỏ dày
                        draw.rectangle([x0 - t, y0 - t, x1 + t, y1 + t], outline="red")
                buf = io.BytesIO()
                img.save(buf, "PNG")
                buf.seek(0)
                self.document.add_picture(buf, width=Cm(MUC_RONG))
            else:
                self.document.add_picture(str(abs_path), width=Cm(MUC_RONG))
            self.document.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            self._count_hinh += 1  # đánh số từ Hình 1
            self._para(
                f"Hình {self._count_hinh}: {chu_thich}",
                size=10,
                align=WD_ALIGN_PARAGRAPH.CENTER,
                space_after=12,
                color=(0x55, 0x55, 0x55),
                italic=True,
            )
        else:
            self._count_phai_chup += 1
            p = self._para(
                f"[ẢNH CẦN CHỤP: {chu_thich}]",
                bold=True,
                size=12,
                space_after=12,
                color=(0xC0, 0x00, 0x00),
            )
            self._shading(p, "FFF3F3")

    # ---- khung trang ----

    def trang_bia(self):
        for _ in range(7):
            self.document.add_paragraph()
        self._para(
            "PA WORKER",
            bold=True,
            size=30,
            align=WD_ALIGN_PARAGRAPH.CENTER,
            color=(0x1F, 0x38, 0x64),
            space_after=10,
        )
        self._para(self.ten, size=18, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=24)
        self._para(
            f"Phiên bản {PHIEN_BAN}", size=14, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6
        )
        self._para("Phát triển bởi QQIT", size=14, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6)
        self._para(NGAY, size=12, align=WD_ALIGN_PARAGRAPH.CENTER)
        self.document.add_page_break()

    def _field(self, p, instr: str, size=10):
        r = p.add_run()
        el = r._r
        fc1 = OxmlElement("w:fldChar")
        fc1.set(qn("w:fldCharType"), "begin")
        el.append(fc1)
        it = OxmlElement("w:instrText")
        it.set(qn("xml:space"), "preserve")
        it.text = instr
        el.append(it)
        fc2 = OxmlElement("w:fldChar")
        fc2.set(qn("w:fldCharType"), "end")
        el.append(fc2)
        r.font.name = FONT
        r.font.size = Pt(size)
        return r

    def muc_luc(self):
        self.heading("Mục lục", 1)
        p = self.document.add_paragraph()
        self._field(p, r'TOC \o "1-3" \h \z \u')
        self.document.add_page_break()

    def dau_chan_trang(self):
        sec = self.document.sections[0]
        fp = sec.footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r1 = fp.add_run("Trang ")
        r1.font.name = FONT
        r1.font.size = Pt(10)
        self._field(fp, "PAGE", size=10)
        r2 = fp.add_run(f"  ·  {self.ghi_so}")
        r2.font.name = FONT
        r2.font.size = Pt(9)
        hp = sec.header.paragraphs[0]
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        hr = hp.add_run(self.ten)
        hr.font.name = FONT
        hr.font.size = Pt(9)
        hr.font.color.rgb = RGBColor(0x66, 0x66, 0x66)


# ---- phân tích markdown -> khối ----


def parse_markdown(md_text: str) -> list[dict]:
    blocks: list[dict] = []
    lines = md_text.splitlines()
    i = 0
    in_code = False
    code_buf: list[str] = []
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            if in_code:
                blocks.append({"loai": "code", "noi_dung": code_buf})
                code_buf, in_code = [], False
            else:
                in_code = True
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            blocks.append(
                {"loai": "heading", "cap": len(m.group(1)), "noi_dung": m.group(2).strip()}
            )
            i += 1
            continue
        if line.strip().startswith("|"):
            tbl: list[list[str]] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-?:?", c) for c in cells):
                    tbl.append(cells)
                i += 1
            if tbl:
                blocks.append({"loai": "bang", "noi_dung": tbl})
            continue
        mm = re.match(r"^!\[(.*)\]\((.*)\)\s*$", line)
        if mm:
            blocks.append(
                {"loai": "anh", "noi_dung": mm.group(2).strip(), "chu_thich": mm.group(1)}
            )
            i += 1
            continue
        cm = re.match(r"^\[ẢNH CẦN CHỤP:\s*(.*)\]\s*$", line)
        if cm:
            blocks.append({"loai": "phai_chup", "noi_dung": cm.group(1)})
            i += 1
            continue
        if line.startswith(">"):
            blocks.append({"loai": "quote", "noi_dung": line.lstrip("> ").strip()})
            i += 1
            continue
        bm = re.match(r"^\s*[-*]\s+(.*)", line)
        if bm:
            blocks.append({"loai": "bullet", "noi_dung": bm.group(1).strip()})
            i += 1
            continue
        nm = re.match(r"^\s*(\d+)\.\s+(.*)", line)
        if nm:
            blocks.append({"loai": "so", "noi_dung": f"{nm.group(1)}. {nm.group(2).strip()}"})
            i += 1
            continue
        if line.strip() in ("", "---", "***"):
            i += 1
            continue
        blocks.append({"loai": "doan", "noi_dung": line.strip()})
        i += 1
    if in_code and code_buf:
        blocks.append({"loai": "code", "noi_dung": code_buf})
    return blocks


def sap_xep_chuong(blocks: list[dict], thu_tu: list[str], bo_di: list[str]) -> list[dict]:
    """Gom khối theo chương H2 (cap==2) rồi sắp xếp lại theo thu_tu (chương
    không liệt kê thì giữ nguyên thứ tự nguồn và xếp sau). Chương trong bo_di
    bị bỏ hẳn (đã nhập nội dung vào chương vai trò)."""
    chap: list[str] = []
    noi_dung_chap: dict[str, list[dict]] = {}
    dau: list[dict] = []
    for b in blocks:
        if b["loai"] == "heading" and b["cap"] == 2:
            chap.append(b["noi_dung"])
            noi_dung_chap[b["noi_dung"]] = [b]
        else:
            (noi_dung_chap[chap[-1]] if chap else dau).append(b)
    for ten in bo_di:
        noi_dung_chap.pop(ten, None)
    ket_qua = list(dau)
    cho_nen = [t for t in chap if t not in thu_tu and t not in bo_di]
    for ten in thu_tu + cho_nen:
        ket_qua.extend(noi_dung_chap.get(ten, []))
    return ket_qua


def render(blocks: list[dict], tl: TaiLieu, sap_xep: dict | None = None):
    if sap_xep:
        blocks = sap_xep_chuong(blocks, sap_xep["thu_tu"], sap_xep.get("bo_di", []))
    for b in blocks:
        loai = b["loai"]
        if loai == "heading":
            if b["cap"] == 1:
                continue  # tiêu đề chính đã có ở trang bìa
            if b["noi_dung"].strip() == "Mục lục":
                continue  # mục lục tự động đã có ở đầu (F9 trong Word)
            tl.heading(b["noi_dung"], b["cap"] - 1)
        elif loai == "doan":
            tl._rich(b["noi_dung"].replace("**", "@@"), space_after=8)
        elif loai == "bullet":
            tl.bullet(b["noi_dung"])
        elif loai == "so":
            tl.number_item(b["noi_dung"])
        elif loai == "code":
            tl.code_block(b["noi_dung"])
        elif loai == "bang":
            tl.bang(b["noi_dung"])
        elif loai == "quote":
            tl.blockquote(b["noi_dung"])
        elif loai == "anh":
            tl.hinh(b["noi_dung"], b.get("chu_thich", ""))
        elif loai == "phai_chup":
            tl.hinh("", b["noi_dung"])


def main():
    # Tài liệu sử dụng: chương theo vai trò, thứ tự Admin → Quản lý → HR →
    # Viewer (khối "Dùng chung" đứng đầu, "Bảng quyền tóm tắt" cuối).
    sap_xep_su_dung = {
        "thu_tu": [
            "Dùng chung cho mọi vai trò",
            "Admin",
            "Quản lý nhân sự",
            "Nhân viên HR",
            "Viewer",
            "Bảng quyền tóm tắt",
        ],
        "bo_di": [],
    }
    for md_file, ten_file, ten, ghi_so, sap_xep in [
        (
            "docs/huong-dan-cai-dat.md",
            "Pa-Worker-Huong-dan-cai-dat.docx",
            "PA Worker – Hướng dẫn cài đặt",
            f"PA Worker v{PHIEN_BAN}",
            None,
        ),
        (
            "docs/huong-dan-su-dung.md",
            "Pa-Worker-Huong-dan-su-dung.docx",
            "PA Worker – Hướng dẫn sử dụng",
            f"PA Worker v{PHIEN_BAN}",
            sap_xep_su_dung,
        ),
        (
            "docs/xu-ly-su-co.md",
            "Pa-Worker-Xu-ly-su-co.docx",
            "PA Worker – Xử lý sự cố",
            f"PA Worker v{PHIEN_BAN}",
            None,
        ),
    ]:
        tl = TaiLieu(ten, ghi_so)
        md_text = (ROOT / md_file).read_text(encoding="utf-8")
        tl.trang_bia()
        tl.muc_luc()
        tl.dau_chan_trang()
        render(parse_markdown(md_text), tl, sap_xep)
        out = OUT / ten_file
        tl.document.save(str(out))
        print(
            f"{ten_file}: {tl._count_hinh} ảnh, "
            f"{tl._count_phai_chup} chỗ [ẢNH CẦN CHỤP], "
            f"{out.stat().st_size // 1024} KB"
        )


if __name__ == "__main__":
    main()
