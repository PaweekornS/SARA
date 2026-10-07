"""
ส่งออกสรุปการประชุมเป็น .docx

ตั้งค่า w:cs (complex script) ด้วย ไม่งั้น Word จะใช้ฟอนต์อื่นเรนเดอร์ตัวอักษรไทย
"""

from __future__ import annotations

import io
from datetime import date

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

from app.services.thai_format import thai_date

FONT_NAME = "TH Sarabun New"
BODY_SIZE = Pt(16)
TITLE_SIZE = Pt(20)
HEADING_SIZE = Pt(18)


def _new_document() -> Document:
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


def _to_bytes(doc: Document) -> bytes:
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def _detail_lines(value) -> list[str]:
    """แปลงฟิลด์เฉพาะ template (string / list / list of dict) เป็นบรรทัดข้อความ"""
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, dict):
                lines.append(" · ".join(str(v) for v in item.values() if v not in (None, "")))
            elif str(item).strip():
                lines.append(str(item))
        return lines
    return []


def build_meeting_docx(
    title: str,
    collection_name: str,
    meeting_date: date | None,
    template_name: str,
    summary: str,
    key_points: list[str],
    details: dict[str, object],
    action_items: list[dict],
    speakers: list[str],
) -> bytes:
    doc = _new_document()

    _para(doc, title or "สรุปการประชุม", size=TITLE_SIZE, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    subtitle = " · ".join(p for p in (collection_name, thai_date(meeting_date) if meeting_date else "") if p)
    if subtitle:
        _para(doc, subtitle, align=WD_ALIGN_PARAGRAPH.CENTER)
    _para(doc, f"รูปแบบสรุป: {template_name}", size=Pt(14), align=WD_ALIGN_PARAGRAPH.CENTER)
    _para(doc)

    if speakers:
        _para(doc, "ผู้ร่วมประชุม", size=HEADING_SIZE, bold=True)
        _para(doc, ", ".join(speakers), indent_cm=1.0)
        _para(doc)

    _para(doc, "สรุปภาพรวม", size=HEADING_SIZE, bold=True)
    _para(doc, summary or "-", indent_cm=1.0)
    _para(doc)

    if key_points:
        _para(doc, "ประเด็นสำคัญ", size=HEADING_SIZE, bold=True)
        for point in key_points:
            _para(doc, f"• {point}", indent_cm=1.0)
        _para(doc)

    for label, value in details.items():
        lines = _detail_lines(value)
        if not lines:
            continue
        _para(doc, label, size=HEADING_SIZE, bold=True)
        for line in lines:
            _para(doc, f"• {line}", indent_cm=1.0)
        _para(doc)

    _para(doc, "งานที่ต้องทำต่อ", size=HEADING_SIZE, bold=True)
    if not action_items:
        _para(doc, "- ไม่มี -", indent_cm=1.0)
    for item in action_items:
        mark = "☑" if item.get("done") else "☐"
        _para(doc, f"{mark} {item['text']}", indent_cm=1.0)
        meta = []
        if item.get("owner"):
            meta.append(f"ผู้รับผิดชอบ: {item['owner']}")
        if item.get("due_date"):
            meta.append(f"กำหนด: {thai_date(item['due_date'])}")
        if meta:
            _para(doc, " · ".join(meta), size=Pt(14), indent_cm=1.8)

    return _to_bytes(doc)
