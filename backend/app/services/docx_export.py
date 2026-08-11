"""
สร้างไฟล์ .docx ตามระเบียบสารบรรณ (FR-M5-04, 05, 06)

ฟอนต์ TH Sarabun New ขนาด 16 pt · กระดาษ A4 · ขอบตามหนังสือราชการ
ตั้งค่า w:cs (complex script) ด้วย ไม่งั้น Word จะใช้ฟอนต์อื่นเรนเดอร์ตัวอักษรไทย

หมายเหตุจาก §M5: ของจริงควรใช้ไฟล์ .docx ต้นแบบขององค์กรแล้วแทนที่ placeholder
ฟังก์ชัน build_* ทั้งหมดจึงรับ template_path ไว้ ถ้าองค์กรวางไฟล์ต้นแบบไว้ ระบบจะเปิดจากไฟล์นั้น
แล้วเติมเนื้อหาต่อท้าย แทนการสร้างเอกสารเปล่าเอง
"""

from __future__ import annotations

import io
import os
from datetime import date

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

from app.services.thai_format import thai_date, thai_numeral

FONT_NAME = "TH Sarabun New"
BODY_SIZE = Pt(16)
TITLE_SIZE = Pt(20)
HEADING_SIZE = Pt(18)


def _new_document(template_path: str | None) -> Document:
    if template_path and os.path.exists(template_path):
        return Document(template_path)

    doc = Document()
    section = doc.sections[0]
    section.orientation = WD_ORIENT.PORTRAIT
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(3.0)
    section.right_margin = Cm(2.0)

    style = doc.styles["Normal"]
    style.font.name = FONT_NAME
    style.font.size = BODY_SIZE
    style.element.rPr.rFonts.set(qn("w:eastAsia"), FONT_NAME)
    style.element.rPr.rFonts.set(qn("w:cs"), FONT_NAME)
    return doc


def _para(doc: Document, text: str = "", *, size=BODY_SIZE, bold=False, align=None, indent_cm=0.0):
    paragraph = doc.add_paragraph()
    if align is not None:
        paragraph.alignment = align
    if indent_cm:
        paragraph.paragraph_format.left_indent = Cm(indent_cm)
    paragraph.paragraph_format.space_after = Pt(2)

    for i, line in enumerate((text or "").split("\n")):
        run = paragraph.add_run(line)
        run.bold = bold
        run.font.size = size
        run.font.name = FONT_NAME
        run._element.rPr.rFonts.set(qn("w:cs"), FONT_NAME)
        run._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_NAME)
        if i < len(text.split("\n")) - 1:
            run.add_break()
    return paragraph


def _signature_block(doc: Document) -> None:
    doc.add_paragraph()
    table = doc.add_table(rows=1, cols=2)
    table.autofit = True
    left, right = table.rows[0].cells
    for cell, role in ((left, "ผู้จดรายงานการประชุม"), (right, "ผู้ตรวจรายงานการประชุม")):
        cell.text = ""
        for line in ("(ลงชื่อ) ..............................................", "", "(..............................................)", role):
            para = cell.add_paragraph()
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = para.add_run(line)
            run.font.size = BODY_SIZE
            run.font.name = FONT_NAME
            run._element.rPr.rFonts.set(qn("w:cs"), FONT_NAME)


def _to_bytes(doc: Document) -> bytes:
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


# ── ร่างระเบียบวาระ ─────────────────────────────────────────────────────

def build_agenda_docx(
    series_name: str,
    fiscal_year: int,
    sequence_no: int,
    meeting_date: date | None,
    sections: list[tuple[int, str, list[tuple[str, str]]]],
    template_path: str | None = None,
) -> bytes:
    """sections = [(section_no, section_title, [(item_title, item_body), ...])]"""
    doc = _new_document(template_path)

    _para(doc, f"ระเบียบวาระการประชุม{series_name}", size=TITLE_SIZE, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    _para(
        doc,
        f"ครั้งที่ {thai_numeral(sequence_no)}/{thai_numeral(fiscal_year)}",
        size=HEADING_SIZE,
        align=WD_ALIGN_PARAGRAPH.CENTER,
    )
    if meeting_date:
        _para(
            doc,
            f"วันที่ {thai_numeral(thai_date(meeting_date))}",
            size=HEADING_SIZE,
            align=WD_ALIGN_PARAGRAPH.CENTER,
        )
    doc.add_paragraph()

    for section_no, section_title, items in sections:
        _para(
            doc,
            f"ระเบียบวาระที่ {thai_numeral(section_no)} {section_title}",
            size=HEADING_SIZE,
            bold=True,
        )
        if not items:
            _para(doc, "(ไม่มี)", indent_cm=1.27)
            continue
        for idx, (title, body) in enumerate(items, start=1):
            _para(
                doc,
                f"{thai_numeral(section_no)}.{thai_numeral(idx)} {title}",
                bold=True,
                indent_cm=1.27,
            )
            if body:
                _para(doc, body, indent_cm=1.27)

    _signature_block(doc)
    return _to_bytes(doc)


def build_agenda_attachment(doc: Document, rows: list[dict]) -> None:
    """ตารางสรุปสถานะมติค้าง แนบท้ายวาระ ให้ประธานอ่านหน้าเดียวจบ"""
    if not rows:
        return
    _para(doc, "เอกสารแนบ ๑ สรุปสถานะมติค้างดำเนินการ", size=HEADING_SIZE, bold=True)
    table = doc.add_table(rows=1, cols=6)
    table.style = "Table Grid"
    headers = ["ลำดับ", "มติ", "ที่มา", "ผู้รับผิดชอบ", "กำหนด", "สถานะ"]
    for cell, header in zip(table.rows[0].cells, headers):
        cell.text = header
    for i, row in enumerate(rows, start=1):
        cells = table.add_row().cells
        cells[0].text = thai_numeral(i)
        cells[1].text = row["text"]
        cells[2].text = row["ref_no"]
        cells[3].text = row["assignees"]
        cells[4].text = thai_numeral(thai_date(row["due_date"])) if row["due_date"] else "-"
        cells[5].text = row["status"] + (f"\nเกิน {thai_numeral(row['overdue'])} วัน" if row["overdue"] else "")


# ── รายงานการประชุมฉบับเต็ม ─────────────────────────────────────────────

def build_minutes_docx(
    series_name: str,
    fiscal_year: int,
    sequence_no: int,
    meeting_date: date,
    attendees: list[str],
    resolutions: list[dict],
    segments: list[dict],
    template_path: str | None = None,
) -> bytes:
    doc = _new_document(template_path)

    _para(doc, f"รายงานการประชุม{series_name}", size=TITLE_SIZE, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    _para(
        doc,
        f"ครั้งที่ {thai_numeral(sequence_no)}/{thai_numeral(fiscal_year)}",
        size=HEADING_SIZE,
        align=WD_ALIGN_PARAGRAPH.CENTER,
    )
    _para(
        doc,
        f"เมื่อวันที่ {thai_numeral(thai_date(meeting_date))}",
        size=HEADING_SIZE,
        align=WD_ALIGN_PARAGRAPH.CENTER,
    )
    doc.add_paragraph()

    _para(doc, "ผู้มาประชุม", bold=True)
    for i, name in enumerate(attendees, start=1):
        _para(doc, f"{thai_numeral(i)}. {name}", indent_cm=1.27)
    if not attendees:
        _para(doc, "(ไม่ได้ระบุ)", indent_cm=1.27)

    _para(doc, "เริ่มประชุมเวลา ๐๙.๐๐ น.", bold=True)

    _para(doc, "ระเบียบวาระที่ ๑ เรื่องที่ประธานแจ้งให้ที่ประชุมทราบ", size=HEADING_SIZE, bold=True)
    _para(doc, "ประธานกล่าวเปิดการประชุมและแจ้งให้ที่ประชุมทราบตามระเบียบวาระ", indent_cm=1.27)

    _para(doc, "ระเบียบวาระที่ ๒ เรื่องรับรองรายงานการประชุม", size=HEADING_SIZE, bold=True)
    _para(
        doc,
        f"ที่ประชุมพิจารณารายงานการประชุมครั้งที่ {thai_numeral(max(sequence_no - 1, 0))}/"
        f"{thai_numeral(fiscal_year)} แล้ว มีมติรับรองรายงานการประชุม",
        indent_cm=1.27,
    )

    _para(doc, "ระเบียบวาระที่ ๔ เรื่องเสนอเพื่อพิจารณา", size=HEADING_SIZE, bold=True)
    if not resolutions:
        _para(doc, "(ไม่มีมติจากการประชุมครั้งนี้)", indent_cm=1.27)
    for i, r in enumerate(resolutions, start=1):
        _para(doc, f"๔.{thai_numeral(i)} {r['title']}", bold=True, indent_cm=1.27)
        _para(doc, f"มติที่ประชุม {r['text']}", indent_cm=1.27)
        if r.get("assignees"):
            due = f" กำหนดแล้วเสร็จภายในวันที่ {thai_numeral(thai_date(r['due_date']))}" if r.get("due_date") else ""
            _para(doc, f"ผู้รับผิดชอบ {r['assignees']}{due}", indent_cm=1.27)

    _para(doc, "ระเบียบวาระที่ ๕ เรื่องอื่น ๆ", size=HEADING_SIZE, bold=True)
    _para(doc, "ไม่มี", indent_cm=1.27)
    _para(doc, "เลิกประชุมเวลา ๑๒.๐๐ น.", bold=True)

    #  บันทึกคำต่อคำแนบท้าย — เป็นหลักฐานให้ตรวจย้อนกลับได้
    if segments:
        doc.add_page_break()
        _para(doc, "เอกสารแนบ ๑ บันทึกถ้อยคำการประชุม", size=HEADING_SIZE, bold=True)
        table = doc.add_table(rows=1, cols=3)
        table.style = "Table Grid"
        for cell, header in zip(table.rows[0].cells, ["เวลา", "ผู้พูด", "ข้อความ"]):
            cell.text = header
        for seg in segments:
            cells = table.add_row().cells
            cells[0].text = thai_numeral(_timecode(seg["start_ms"]))
            cells[1].text = seg["speaker"]
            cells[2].text = seg["text"]

    _signature_block(doc)
    return _to_bytes(doc)


def _timecode(ms: int) -> str:
    total = int(ms // 1000)
    return f"{total // 60:02d}:{total % 60:02d}"
