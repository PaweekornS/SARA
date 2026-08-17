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

# ── Global Variables & Constants ─────────────────────────────────────────────

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


# ── Functions ────────────────────────────────────────────────────────────────

def agenda_topic(text: str) -> str:
    """
    หัวข้อวาระตามรูปแบบราชการ "เรื่อง ..."
    """
    topic = text.strip()
    if topic.startswith("เรื่อง "):
        return topic
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
        order += 1
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

    # วาระ 1: ประธานแจ้ง
    push(1, 1, SECTION_TITLES[1], "")

    # วาระ 2: รับรองรายงานครั้งก่อน
    if last_meeting:
        date_str = thai_date(last_meeting.meeting_date)
        body = f"รับรองรายงานการประชุมครั้งที่ {last_seq}/{series.fiscal_year} เมื่อวันที่ {date_str}"
    else:
        body = "การประชุมครั้งแรกของชุดนี้ — ยังไม่มีรายงานการประชุมครั้งก่อน"
    push(2, 1, f"รับรองรายงานการประชุมครั้งที่ {last_seq or 1}", body)

    # วาระ 3: เรื่องสืบเนื่อง
    open_res = (
        await db.execute(
            select(Resolution)
            .where(
                Resolution.series_id == series.id,
                Resolution.status.in_(ResolutionStatus.OPEN),
            )
            .order_by(Resolution.created_at)
        )
    ).scalars().all()

    item_no = 0
    for res in open_res:
        item_no += 1
        assignees = await assignee_names(db, res.id)
        overdue = overdue_days(res, today)
        due_str = thai_date(res.due_date) if res.due_date else "ไม่ระบุ"
        status_th = STATUS_LABEL_TH.get(res.status, res.status)

        body_lines = [
            f"อ้างอิง: {res.ref_no}",
            f"ข้อความมติ: {res.text}",
            f"ผู้รับผิดชอบ: {assignees or 'ยังไม่ระบุ'}",
            f"กำหนดเสร็จ: {due_str} (สถานะ: {status_th})",
        ]
        if overdue > 0:
            body_lines.append(f"⚠ เกินกำหนดมาแล้ว {overdue} วัน — ขอให้ผู้รับผิดชอบรายงานความคืบหน้าและปัญหาอุปสรรค")
        if (res.postpone_count or 0) >= 3:
            body_lines.append(f"⚠ มตินี้ถูกเลื่อนกำหนดมาแล้ว {res.postpone_count} ครั้ง ขอให้ที่ประชุมพิจารณาแนวทางแก้ไข")

        push(3, item_no, agenda_topic(res.text), "\n".join(body_lines), resolution_id=res.id)

    if item_no == 0:
        push(3, 1, "ไม่มีเรื่องสืบเนื่อง", "ไม่มีมติค้างที่ต้องติดตามในการประชุมครั้งนี้")

    # วาระ 4: เรื่องเสนอเพื่อพิจารณา
    push(4, 1, SECTION_TITLES[4], "ให้ฝ่ายที่เกี่ยวข้องนำเสนอเรื่องตามลำดับ")

    # วาระ 5: เรื่องอื่น ๆ
    push(5, 1, SECTION_TITLES[5], "")

    await db.commit()
    await db.refresh(draft)
    return draft


async def assignee_names(db: AsyncSession, resolution_id: UUID) -> str:
    rows = (
        await db.execute(
            select(Person.full_name)
            .join(ResolutionAssignee, ResolutionAssignee.person_id == Person.id)
            .where(ResolutionAssignee.resolution_id == resolution_id)
        )
    ).scalars().all()
    return ", ".join(rows)
