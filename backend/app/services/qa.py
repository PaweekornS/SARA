"""
ถาม-ตอบข้ามการประชุมใน collection เดียว (hybrid RAG)

ค้น 2 ทางแล้วรวมกัน:
  1. เชิงความหมาย — Qdrant (สรุป + บันทึกคำต่อคำ) จับคำถามที่ใช้คำต่างจากในบันทึก
  2. เชิงคำ      — character 4-gram บน DB (สรุป + action items + บันทึก) จับชื่อคน ตัวเลข ศัพท์เฉพาะ
                   ที่ embedding ขนาดเล็กมักพลาด ภาษาไทยไม่มีช่องว่างระหว่างคำจึงใช้ n-gram แทนการตัดคำ
action items แก้ไขได้ตลอดจึงค้นจาก DB เท่านั้น ถ้า Qdrant ล่ม ระบบยังตอบได้ด้วยทางที่ 2

การอ้างอิงทั้งหมดมาจากขั้นตอนค้นหา ไม่ได้มาจากโมเดล
โมเดลมีหน้าที่แค่เรียบเรียงคำตอบจากหลักฐานที่หามาได้ จึงอ้างอิงมั่วไม่ได้
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ActionItem, Meeting, MeetingStatus, TranscriptSegment
from app.services import vector_store
from app.services.llm import LlmError, answer_from_context
from app.services.thai_format import thai_date

logger = logging.getLogger(__name__)

NGRAM = 4
MIN_SCORE = 0.08
VECTOR_K = 4
LEXICAL_K = 3
TOP_K = 6

_PUNCT = re.compile(r"[\s.,!?\"'()“”]")


@dataclass
class Evidence:
    kind: str  # summary | action_item | transcript
    meeting_id: UUID
    meeting_label: str
    text: str
    segment_id: UUID | None = None
    start_ms: int | None = None
    score: float = 0.0
    source: str = "lexical"  # lexical | vector


@dataclass
class QaResult:
    answer: str
    citations: list[dict]


def _normalize(text: str) -> str:
    return _PUNCT.sub("", text or "").lower()


def query_terms(text: str) -> list[str]:
    clean = _normalize(text)
    if len(clean) < NGRAM:
        return [clean] if clean else []
    return list({clean[i : i + NGRAM] for i in range(len(clean) - NGRAM + 1)})


def relevance(haystack: str, terms: list[str]) -> float:
    if not haystack or not terms:
        return 0.0
    hay = _normalize(haystack)
    return sum(1 for t in terms if t in hay) / len(terms)


def meeting_label(meeting: Meeting) -> str:
    when = f" ({thai_date(meeting.meeting_date)})" if meeting.meeting_date else ""
    return f"{meeting.title or 'การประชุม'}{when}"


async def _ready_meetings(db: AsyncSession, user_id: UUID, collection_id: UUID) -> dict[UUID, Meeting]:
    rows = (
        await db.execute(
            select(Meeting).where(
                Meeting.user_id == user_id,
                Meeting.collection_id == collection_id,
                Meeting.status == MeetingStatus.READY,
            )
        )
    ).scalars().all()
    return {m.id: m for m in rows}


async def lexical_evidence(db: AsyncSession, meetings: dict[UUID, Meeting]) -> list[Evidence]:
    if not meetings:
        return []

    evidence = [Evidence("summary", m.id, meeting_label(m), m.summary) for m in meetings.values() if m.summary]

    items = (await db.execute(select(ActionItem).where(ActionItem.meeting_id.in_(meetings)))).scalars().all()
    for item in items:
        state = "เสร็จแล้ว" if item.done else "ยังค้าง"
        owner = f" · ผู้รับผิดชอบ {item.owner}" if item.owner else ""
        due = f" · กำหนด {thai_date(item.due_date)}" if item.due_date else ""
        evidence.append(
            Evidence("action_item", item.meeting_id, meeting_label(meetings[item.meeting_id]),
                     f"งาน: {item.text} ({state}{owner}{due})")
        )

    segments = (
        await db.execute(
            select(TranscriptSegment)
            .where(TranscriptSegment.meeting_id.in_(meetings))
            .order_by(TranscriptSegment.meeting_id, TranscriptSegment.start_ms)
        )
    ).scalars().all()
    per_meeting: dict[UUID, list[TranscriptSegment]] = {}
    for seg in segments:
        per_meeting.setdefault(seg.meeting_id, []).append(seg)
    for meeting_id, segs in per_meeting.items():
        for chunk in vector_store.build_chunks(meeting_id, "", segs):
            evidence.append(
                Evidence("transcript", meeting_id, meeting_label(meetings[meeting_id]), chunk.text,
                         chunk.segment_id, chunk.start_ms)
            )
    return evidence


def rank_lexical(evidence: list[Evidence], question: str, limit: int) -> list[Evidence]:
    terms = query_terms(question)
    for e in evidence:
        e.score = relevance(e.text, terms)
    hits = [e for e in evidence if e.score >= MIN_SCORE]
    hits.sort(key=lambda e: e.score, reverse=True)
    return hits[:limit]


async def vector_evidence(
    user_id: UUID, collection_id: UUID, question: str, meetings: dict[UUID, Meeting]
) -> list[Evidence]:
    """คืน [] ถ้า Qdrant ใช้ไม่ได้ — ผู้ใช้ยังได้คำตอบจากการค้นแบบคำ"""
    try:
        #  embedding ใช้ CPU ราว 10-50 ms ต่อคำถาม ไม่ควรรันบน event loop ตรง ๆ
        hits = await asyncio.to_thread(vector_store.search, user_id, collection_id, question, VECTOR_K)
    except vector_store.VectorStoreError as err:
        logger.warning("ค้นเชิงความหมายไม่ได้ ใช้การค้นแบบคำอย่างเดียว: %s", err)
        return []
    #  ตัดจุดของการประชุมที่ถูกลบ/ย้าย/ยังไม่พร้อมทิ้ง เผื่อดัชนีใน Qdrant ไม่ตรงกับ DB
    return [
        Evidence(h.kind, h.meeting_id, meeting_label(meetings[h.meeting_id]), h.text, h.segment_id, h.start_ms,
                 h.score, source="vector")
        for h in hits
        if h.meeting_id in meetings
    ]


def merge(vector_hits: list[Evidence], lexical_hits: list[Evidence]) -> list[Evidence]:
    merged: list[Evidence] = []
    seen: set[str] = set()
    for e in [*vector_hits, *lexical_hits]:
        key = _normalize(e.text)
        if key in seen:
            continue
        seen.add(key)
        merged.append(e)
    return merged[:TOP_K]


async def answer_question(db: AsyncSession, user_id: UUID, collection_id: UUID, question: str) -> QaResult:
    meetings = await _ready_meetings(db, user_id, collection_id)
    if not meetings:
        return QaResult(answer="collection นี้ยังไม่มีการประชุมที่ประมวลผลเสร็จ", citations=[])

    vector_hits = await vector_evidence(user_id, collection_id, question, meetings)
    lexical_hits = rank_lexical(await lexical_evidence(db, meetings), question, LEXICAL_K)
    top = merge(vector_hits, lexical_hits)
    if not top:
        return QaResult(answer="ไม่พบข้อมูลที่เกี่ยวข้องกับคำถามนี้ในการประชุมของ collection นี้", citations=[])

    context = "\n\n".join(f"[{e.meeting_label}] {e.text}" for e in top)
    try:
        answer = await asyncio.to_thread(answer_from_context, question, context)
    except LlmError as err:
        logger.warning("LLM ตอบคำถามไม่สำเร็จ แสดงหลักฐานที่ค้นเจอแทน: %s", err)
        answer = f"พบข้อมูลที่เกี่ยวข้องใน{top[0].meeting_label}: “{top[0].text[:200]}”"

    citations = [
        {
            "kind": e.kind,
            "source": e.source,
            "meeting_id": str(e.meeting_id),
            "meeting_label": e.meeting_label,
            "segment_id": str(e.segment_id) if e.segment_id else None,
            "start_ms": e.start_ms,
            "quote": e.text,
        }
        for e in top
    ]
    return QaResult(answer=answer, citations=citations)
