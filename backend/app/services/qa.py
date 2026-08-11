"""
ถาม-ตอบข้ามการประชุม (M8)

ลำดับการค้นตาม FR-M8-04: ดึงจากทะเบียนมติก่อน แล้วค่อย fallback ไปค้นบันทึกคำต่อคำ

การอ้างอิงทั้งหมด (FR-M8-02) มาจากขั้นตอนค้นหา ไม่ได้มาจากโมเดล
โมเดลมีหน้าที่แค่เรียบเรียงคำตอบจากหลักฐานที่หามาได้ จึงอ้างอิงมั่วไม่ได้เลย
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Meeting, Resolution, ResolutionLink, TranscriptSegment
from app.services.agenda_builder import STATUS_LABEL_TH
from app.services.llm import LlmError, answer_from_context
from app.services.resolutions import overdue_days
from app.services.thai_format import thai_date

logger = logging.getLogger(__name__)

NGRAM = 5
RESOLUTION_THRESHOLD = 0.10
SEGMENT_THRESHOLD = 0.08

LINK_LABEL_TH = {
    "created": "เกิดมติ",
    "referenced": "ถูกอ้างถึง",
    "progress_reported": "รายงานความคืบหน้า",
    "closed": "ปิดมติ",
    "superseded": "ถูกแทนที่",
}

_PUNCT = re.compile(r"[\s.,!?\"'()“”]")


def _normalize(text: str) -> str:
    return _PUNCT.sub("", text or "")


def thai_grams(text: str) -> list[str]:
    """
    ภาษาไทยไม่เว้นวรรคระหว่างคำ การตัดด้วยช่องว่างจึงพลาดเกือบทุกครั้ง
    จึงเทียบด้วย n-gram ระดับตัวอักษรแทน — หยาบแต่ใช้ได้จริงโดยไม่ต้องมี tokenizer
    ถ้าจะยกระดับ ให้เปลี่ยนไปใช้ embedding + pgvector ตามคำถามข้อ 3 ใน §14
    """
    clean = _normalize(text)
    return list({clean[i : i + NGRAM] for i in range(len(clean) - NGRAM + 1)})


def relevance(haystack: str, grams: list[str]) -> float:
    if not grams:
        return 0.0
    hay = _normalize(haystack)
    return sum(1 for g in grams if g in hay) / len(grams)


@dataclass
class QaResult:
    answer: str
    source: str
    citations: list[dict]
    timeline: list[dict]


async def answer_question(db: AsyncSession, series_id: UUID, question: str) -> QaResult:
    grams = thai_grams(question)

    resolutions = (
        await db.execute(select(Resolution).where(Resolution.series_id == series_id))
    ).scalars().all()

    scored = sorted(
        (
            (r, relevance(f"{r.text} {r.ref_no}", grams))
            for r in resolutions
        ),
        key=lambda pair: pair[1],
        reverse=True,
    )
    hits = [(r, score) for r, score in scored if score >= RESOLUTION_THRESHOLD]

    if hits:
        return await _answer_from_resolutions(db, question, hits)
    return await _answer_from_transcript(db, series_id, question, grams)


async def _answer_from_resolutions(db: AsyncSession, question: str, hits) -> QaResult:
    top, _ = hits[0]

    links = (
        await db.execute(
            select(ResolutionLink)
            .where(ResolutionLink.resolution_id == top.id)
            .order_by(ResolutionLink.created_at)
        )
    ).scalars().all()

    meetings = {}
    for link in links:
        if link.meeting_id not in meetings:
            meetings[link.meeting_id] = await db.get(Meeting, link.meeting_id)

    citations = [
        {
            "meeting_id": link.meeting_id,
            "segment_id": link.segment_id,
            "resolution_id": link.resolution_id,
            "start_ms": link.evidence_start_ms,
            "quote": link.evidence_text,
        }
        for link in links
        if link.evidence_text
    ]

    #  FR-M8-03 คำถามเชิงมติต้องตอบเป็น timeline ไม่ใช่ย่อหน้าเดียว
    timeline = []
    for link in links:
        meeting = meetings.get(link.meeting_id)
        timeline.append(
            {
                "meeting_id": link.meeting_id,
                "date": meeting.meeting_date if meeting else None,
                "label": (
                    f"ครั้งที่ {meeting.sequence_no}/{meeting.fiscal_year} · "
                    if meeting
                    else ""
                )
                + LINK_LABEL_TH.get(link.link_type, link.link_type),
                "detail": link.evidence_text,
            }
        )

    od = overdue_days(top)
    facts = [
        f"มติที่ตรงที่สุด: {top.ref_no}",
        f"ข้อความมติ: {top.text}",
        f"สถานะปัจจุบัน: {STATUS_LABEL_TH.get(top.status, top.status)}",
    ]
    if top.due_date:
        facts.append(f"กำหนดแล้วเสร็จ: {thai_date(top.due_date)}")
    if od:
        facts.append(f"เกินกำหนดแล้ว {od} วัน")
    if (top.postpone_count or 0) >= 3:
        facts.append(f"ถูกเลื่อนกำหนดมาแล้ว {top.postpone_count} ครั้ง")
    if len(hits) > 1:
        others = " · ".join(
            f"{r.ref_no} ({STATUS_LABEL_TH.get(r.status, r.status)})" for r, _ in hits[1:4]
        )
        facts.append(f"มติอื่นที่เกี่ยวข้อง: {others}")
    for entry in timeline:
        facts.append(f"{entry['label']}: {entry['detail']}")

    context = "\n".join(facts)
    fallback = (
        f"พบมติที่เกี่ยวข้อง {len(hits)} ข้อในชุดการประชุมนี้ เรื่องที่ตรงที่สุดคือ {top.ref_no}\n\n"
        f"“{top.text}”\n\n" + " · ".join(facts[2:])
    )

    return QaResult(
        answer=_compose(question, context, fallback),
        source="resolution_table",
        citations=citations,
        timeline=timeline,
    )


async def _answer_from_transcript(
    db: AsyncSession, series_id: UUID, question: str, grams: list[str]
) -> QaResult:
    rows = (
        await db.execute(
            select(TranscriptSegment, Meeting)
            .join(Meeting, Meeting.id == TranscriptSegment.meeting_id)
            .where(Meeting.series_id == series_id)
        )
    ).all()

    scored = sorted(
        ((seg, meeting, relevance(seg.text, grams)) for seg, meeting in rows),
        key=lambda item: item[2],
        reverse=True,
    )
    hits = [item for item in scored if item[2] >= SEGMENT_THRESHOLD][:4]

    if not hits:
        return QaResult(
            answer=(
                "ไม่พบข้อมูลที่เกี่ยวข้องในชุดการประชุมนี้ "
                "ระบบจะไม่คาดเดาคำตอบเมื่อไม่มีหลักฐานอ้างอิง"
            ),
            source="semantic_search",
            citations=[],
            timeline=[],
        )

    citations = [
        {
            "meeting_id": meeting.id,
            "segment_id": seg.id,
            "resolution_id": None,
            "start_ms": seg.start_ms,
            "quote": seg.text,
        }
        for seg, meeting, _ in hits
    ]

    context = "\n".join(
        f"ครั้งที่ {meeting.sequence_no}/{meeting.fiscal_year}: {seg.text}" for seg, meeting, _ in hits
    )
    fallback = (
        f"ไม่พบมติที่ตรงกับคำถามในทะเบียนมติ จึงค้นจากคำต่อคำในบันทึกการประชุม "
        f"พบข้อความที่เกี่ยวข้อง {len(hits)} จุด ตามที่อ้างอิงด้านล่าง"
    )

    return QaResult(
        answer=_compose(question, context, fallback),
        source="semantic_search",
        citations=citations,
        timeline=[],
    )


def _compose(question: str, context: str, fallback: str) -> str:
    """ให้โมเดลเรียบเรียง แต่ถ้าโมเดลล่มก็ยังตอบได้จากข้อเท็จจริงที่ค้นเจอ"""
    try:
        return answer_from_context(question, context)
    except LlmError as err:
        logger.warning("เรียบเรียงคำตอบด้วยโมเดลไม่สำเร็จ ใช้คำตอบจากข้อมูลดิบแทน: %s", err)
        return fallback
