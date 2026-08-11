"""
สร้างร่างระเบียบวาระของการประชุมครั้งถัดไป (M5)

โครงวาระตามระเบียบสารบรรณ (FR-M5-02):
  ๑ ประธานแจ้ง · ๒ รับรองรายงานครั้งก่อน · ๓ เรื่องสืบเนื่อง · ๔ เรื่องเสนอเพื่อพิจารณา · ๕ เรื่องอื่น ๆ

วาระที่ ๓ คือหัวใจ — ระบบไล่มติค้างของ series มาให้เองทั้งหมด
แทนที่เลขาฯ จะต้องเปิดรายงานเก่าย้อนหลังทีละไฟล์ (ปัญหา P1)
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AgendaDraft,
    AgendaItem,
    Meeting,
    MeetingSeries,
    Person,
    Resolution,
    ResolutionAssignee,
    ResolutionStatus,
)
from app.services.resolutions import overdue_days
from app.services.thai_format import thai_date

STATUS_LABEL_TH = {
    ResolutionStatus.PROPOSED: "รอรับรอง",
    ResolutionStatus.CONFIRMED: "รับรองแล้ว",
    ResolutionStatus.IN_PROGRESS: "กำลังดำเนินการ",
    ResolutionStatus.BLOCKED: "ติดปัญหา",
    ResolutionStatus.DONE: "ดำเนินการแล้วเสร็จ",
    ResolutionStatus.CANCELLED: "ยกเลิก",
    ResolutionStatus.SUPERSEDED: "ถูกแทนที่",
}

SECTION_TITLES = {
    1: "เรื่องที่ประธานแจ้งให้ที่ประชุมทราบ",
    2: "เรื่องรับรองรายงานการประชุม",
    3: "เรื่องสืบเนื่องจากการประชุมครั้งก่อน",
    4: "เรื่องเสนอเพื่อพิจารณา",
    5: "เรื่องอื่น ๆ",
}

_LEADING_VERBS = ("ที่ประชุมมีมติให้", "มอบหมายให้", "อนุมัติให้", "อนุมัติ", "ให้")


def agenda_topic(text: str) -> str:
    """
    หัวข้อวาระเขียนเป็น "เรื่อง ..." ตามรูปแบบราชการ
    เก็บข้อความเต็มเสมอ ห้ามตัดด้วย ... เพราะจะติดไปในเอกสารที่ export
    """
    topic = text.strip()
    for verb in _LEADING_VERBS:
        if topic.startswith(verb):
            topic = topic[len(verb) :].strip()
            break
    return f"เรื่อง {topic}"


async def generate_agenda(db: AsyncSession, series: MeetingSeries, today: date | None = None) -> AgendaDraft:
    today = today or date.today()

    meetings = (
        await db.execute(
            select(Meeting)
            .where(Meeting.series_id == series.id)
            .order_by(Meeting.sequence_no.desc())
        )
    ).scalars().all()
    last_meeting = meetings[0] if meetings else None
    last_seq = last_meeting.sequence_no if last_meeting else 0

    #  ลบร่างเดิมของ series นี้ทิ้งก่อน — มีร่างที่ใช้งานได้ทีละฉบับพอ
    for old in (
        await db.execute(select(AgendaDraft).where(AgendaDraft.series_id == series.id))
    ).scalars().all():
        await db.delete(old)

    draft = AgendaDraft(
        series_id=series.id,
        target_meeting_date=series.next_meeting_date,
        target_sequence_no=last_seq + 1,
        status="draft",
    )
    db.add(draft)
    await db.flush()

    order = 0

    def push(section_no: int, item_no: int, title: str, body: str, resolution_id=None) -> None:
        nonlocal order
        db.add(
            AgendaItem(
                agenda_draft_id=draft.id,
                section_no=section_no,
                item_no=item_no,
                title=title,
                body=body,
                resolution_id=resolution_id,
                sort_order=order,
            )
        )
        order += 1

    push(1, 1, SECTION_TITLES[1], "")

    if last_meeting:
        push(
            2,
            1,
            f"รับรองรายงานการประชุมครั้งที่ {last_seq}/{last_meeting.fiscal_year}",
            f"เมื่อวันที่ {thai_date(last_meeting.meeting_date)} ฝ่ายเลขานุการได้จัดทำรายงานการประชุม"
            "เสร็จเรียบร้อยแล้ว จึงเสนอที่ประชุมเพื่อพิจารณารับรอง",
        )
    else:
        push(2, 1, "รับรองรายงานการประชุม", "(ยังไม่มีการประชุมครั้งก่อนในชุดนี้)")

    #  วาระที่ ๓ — มติค้างทั้งหมดของ series เรียงตามความช้าที่สุดก่อน (FR-M5-01, 03)
    open_resolutions = (
        await db.execute(
            select(Resolution).where(
                Resolution.series_id == series.id,
                Resolution.status.in_(ResolutionStatus.OPEN),
            )
        )
    ).scalars().all()
    open_resolutions.sort(key=lambda r: overdue_days(r, today), reverse=True)

    meeting_by_id = {m.id: m for m in meetings}

    for i, r in enumerate(open_resolutions, start=1):
        names = await _assignee_names(db, r.id)
        origin = meeting_by_id.get(r.origin_meeting_id)
        od = overdue_days(r, today)
        lines = [
            f"มติเดิม: “{r.text}”",
            f"ที่มา: การประชุมครั้งที่ "
            f"{origin.sequence_no if origin else '-'}/{origin.fiscal_year if origin else series.fiscal_year} "
            f"{r.origin_agenda_item or ''} ({r.ref_no})".strip(),
            f"ผู้รับผิดชอบ: {', '.join(names) if names else '-'}",
            f"กำหนดแล้วเสร็จ: {thai_date(r.due_date) if r.due_date else 'ไม่ระบุ'}",
            f"สถานะปัจจุบัน: {STATUS_LABEL_TH.get(r.status, r.status)}"
            + (f" · เกินกำหนดแล้ว {od} วัน" if od > 0 else ""),
        ]
        if (r.postpone_count or 0) >= 3:
            lines.append(f"⚑ มติข้อนี้ถูกเลื่อนกำหนดมาแล้ว {r.postpone_count} ครั้ง")
        lines.append("จึงเสนอที่ประชุมเพื่อทราบและพิจารณาเร่งรัดการดำเนินการ")

        push(3, i, agenda_topic(r.text), "\n".join(lines), r.id)

    push(4, 1, SECTION_TITLES[4], "(ฝ่ายเลขานุการเพิ่มเติมตามที่ได้รับแจ้ง)")
    push(5, 1, SECTION_TITLES[5], "")

    await db.flush()
    return draft


async def _assignee_names(db: AsyncSession, resolution_id: UUID) -> list[str]:
    rows = await db.execute(
        select(Person)
        .join(ResolutionAssignee, ResolutionAssignee.person_id == Person.id)
        .where(ResolutionAssignee.resolution_id == resolution_id)
    )
    people = list(rows.scalars().all())
    #  หน่วยงานขึ้นก่อนบุคคล อ่านแล้วรู้ทันทีว่าใครรับผิดชอบจริง
    people.sort(key=lambda p: (not p.is_department, p.full_name))
    return [p.full_name for p in people]
