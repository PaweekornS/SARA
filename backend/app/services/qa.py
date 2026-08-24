"""
ถาม-ตอบข้ามการประชุม (M8) — RAG System (Retrieval-Augmented Generation)

ลำดับการค้นตาม FR-M8-04: ดึงจากทะเบียนมติก่อน แล้วค่อย fallback ไปค้นบันทึกคำต่อคำ
ใช้เทคนิค RAG Chunking (sliding window สำหรับคำต่อคำ) และ Hybrid Candidate Ranking

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

# ── Global Variables & Constants ─────────────────────────────────────────────

logger = logging.getLogger(__name__)

RESOLUTION_THRESHOLD = 0.08
SEGMENT_THRESHOLD = 0.05

LINK_LABEL_TH = {
  "created": "เกิดมติ",
  "referenced": "ถูกอ้างถึง",
  "progress_reported": "รายงานความคืบหน้า",
  "closed": "ปิดมติ",
  "superseded": "ถูกแทนที่",
}

_PUNCT = re.compile(r"[\s.,!?\"'()“”]")


# ── Classes & Dataclasses ────────────────────────────────────────────────────

@dataclass
class QaResult:
  answer: str
  source: str
  citations: list[dict]
  timeline: list[dict]


@dataclass
class RagChunk:
  chunk_id: str
  meeting_id: UUID
  meeting_seq: int
  fiscal_year: int
  text: str
  segment_ids: list[UUID]
  start_ms: int


# ── Functions ────────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
  return _PUNCT.sub("", text or "").lower()


def _extract_terms(text: str) -> list[str]:
  """ดึงคำคีย์เวิร์ด และ n-grams คำค้นสำหรับการเปรียบเทียบใน RAG Index"""
  clean = _normalize(text)
  if not clean:
    return []
  ngram_size = 4
  if len(clean) < ngram_size:
    return [clean]
  terms = set()
  for i in range(len(clean) - ngram_size + 1):
    terms.add(clean[i : i + ngram_size])
  return list(terms)


def thai_grams(text: str) -> list[str]:
  """รักษา Backward Compatibility ของ API helper"""
  return _extract_terms(text)


def relevance(haystack: str, query: str | list[str]) -> float:
  """RAG Scoring: คำนวณความสอดคล้องระหว่างเนื้อหากับคำถาม"""
  if not haystack:
    return 0.0
  if isinstance(query, list):
    if not query:
      return 0.0
    hay = _normalize(haystack)
    return sum(1 for g in query if g in hay) / len(query)

  clean_query = _normalize(query)
  clean_hay = _normalize(haystack)
  if not clean_query or not clean_hay:
    return 0.0

  if clean_query in clean_hay:
    return 1.0

  terms = _extract_terms(clean_query)
  if not terms:
    return 0.0
  matches = sum(1 for term in terms if term in clean_hay)
  return matches / len(terms)


def _create_sliding_window_chunks(
    segments_with_meetings: list[tuple[TranscriptSegment, Meeting]],
    window_size: int = 3,
) -> list[RagChunk]:
  """RAG Chunking Method: รวม TranscriptSegment ต่อเนื่องกัน 3-4 segment

  เป็น 1 context chunk เพื่อไม่ให้ข้อความขาดความหมายเมื่อส่งให้ LLM
  """
  if not segments_with_meetings:
    return []

  meetings_map: dict[UUID, list[tuple[TranscriptSegment, Meeting]]] = {}
  for seg, meeting in segments_with_meetings:
    meetings_map.setdefault(meeting.id, []).append((seg, meeting))

  chunks: list[RagChunk] = []
  for meeting_id, item_list in meetings_map.items():
    item_list.sort(key=lambda x: x[0].start_ms)
    n = len(item_list)
    if n == 0:
      continue
    for i in range(0, n, max(1, window_size - 1)):
      window = item_list[i : i + window_size]
      combined_text = " ".join(seg.text for seg, _ in window)
      seg_ids = [seg.id for seg, _ in window]
      m = window[0][1]
      chunks.append(
          RagChunk(
              chunk_id=f"{m.id}_{i}",
              meeting_id=m.id,
              meeting_seq=m.sequence_no,
              fiscal_year=m.fiscal_year,
              text=combined_text,
              segment_ids=seg_ids,
              start_ms=window[0][0].start_ms,
          )
      )
  return chunks


async def answer_question(
    db: AsyncSession, series_id: UUID, question: str
) -> QaResult:
  question_terms = _extract_terms(question)

  resolutions = (
      await db.execute(
          select(Resolution).where(Resolution.series_id == series_id)
      )
  ).scalars().all()

  scored_res: list[tuple[float, Resolution]] = []
  for r in resolutions:
    haystack = f"{r.text} {r.category} {r.ref_no}"
    score = relevance(haystack, question_terms)
    if score >= RESOLUTION_THRESHOLD:
      scored_res.append((score, r))
  scored_res.sort(key=lambda x: x[0], reverse=True)

  if scored_res:
    best_score, best_res = scored_res[0]
    links = (
        await db.execute(
            select(ResolutionLink)
            .where(ResolutionLink.resolution_id == best_res.id)
            .order_by(ResolutionLink.created_at)
        )
    ).scalars().all()

    meetings_by_id: dict[UUID, Meeting] = {
        m.id: m
        for m in (
            await db.execute(
                select(Meeting).where(Meeting.series_id == series_id)
            )
        ).scalars().all()
    }

    timeline = []
    citations = []
    for link in links:
      m = meetings_by_id.get(link.meeting_id)
      seq_label = (
          f"ครั้งที่ {m.sequence_no}/{m.fiscal_year}" if m else "(ไม่ทราบครั้ง)"
      )
      timeline.append({
          "meeting_seq": m.sequence_no if m else 0,
          "date": (
              m.meeting_date.isoformat() if m and m.meeting_date else None
          ),
          "meeting_date": (
              m.meeting_date.isoformat() if m and m.meeting_date else None
          ),
          "label": LINK_LABEL_TH.get(link.link_type, link.link_type),
          "action": LINK_LABEL_TH.get(link.link_type, link.link_type),
          "detail": link.evidence_text or "-",
      })
      if link.evidence_text:
        citations.append({
            "meeting_id": str(link.meeting_id),
            "meeting_seq": m.sequence_no if m else 0,
            "segment_id": str(link.segment_id) if link.segment_id else None,
            "quote": link.evidence_text,
            "text": link.evidence_text,
        })

    overdue = overdue_days(best_res)
    overdue_note = f" (เกินกำหนด {overdue} วัน)" if overdue > 0 else ""
    context = (
        f"มติ: {best_res.ref_no} — {best_res.text}\n"
        f"สถานะปัจจุบัน: {STATUS_LABEL_TH.get(best_res.status, best_res.status)}{overdue_note}\n"
        f"กำหนดเสร็จ: {thai_date(best_res.due_date) if best_res.due_date else '-'}\n"
        f"ประวัติการดำเนินการ:\n"
        + "\n".join(
            f"- {item['action']} ในการประชุม{item['meeting_seq']}:"
            f" {item['detail']}"
            for item in timeline
        )
    )

    try:
      answer = answer_from_context(question, context)
    except LlmError as err:
      logger.warning("LLM ตอบคำถามไม่สำเร็จ ถอยไปใช้ข้อความสรุปตรง ๆ: %s", err)
      status_th = STATUS_LABEL_TH.get(best_res.status, best_res.status)
      answer = (
          f"{best_res.ref_no} ({best_res.text}) ปัจจุบันมีสถานะ {status_th}"
      )

    return QaResult(
        answer=answer,
        source="resolution",
        citations=citations,
        timeline=timeline,
    )

  raw_segments = (
      await db.execute(
          select(TranscriptSegment, Meeting)
          .join(Meeting, TranscriptSegment.meeting_id == Meeting.id)
          .where(Meeting.series_id == series_id)
      )
  ).all()

  rag_chunks = _create_sliding_window_chunks(raw_segments, window_size=3)

  scored_chunks: list[tuple[float, RagChunk]] = []
  for chunk in rag_chunks:
    score = relevance(chunk.text, question_terms)
    if score >= SEGMENT_THRESHOLD:
      scored_chunks.append((score, chunk))
  scored_chunks.sort(key=lambda x: x[0], reverse=True)

  top_chunks = [ch for _, ch in scored_chunks[:3]]
  if not top_chunks:
    return QaResult(
        answer=(
            "ไม่พบข้อมูลที่ตรงกับคำถามนี้ ทั้งในทะเบียนมติและบันทึกการประชุม"
        ),
        source="none",
        citations=[],
        timeline=[],
    )

  context = "\n\n".join(
      f"[การประชุมครั้งที่ {ch.meeting_seq}/{ch.fiscal_year}]\n{ch.text}"
      for ch in top_chunks
  )

  try:
    answer = answer_from_context(question, context)
  except LlmError as err:
    logger.warning("LLM ล้มเหลว: %s", err)
    answer = (
        "พบเนื้อหาที่เกี่ยวข้องในบันทึกการประชุม"
        f" ครั้งที่ {top_chunks[0].meeting_seq}/{top_chunks[0].fiscal_year}:"
        f" “{top_chunks[0].text[:140]}...”"
    )

  citations = [
      {
          "meeting_id": str(ch.meeting_id),
          "meeting_seq": ch.meeting_seq,
          "segment_id": str(ch.segment_ids[0]) if ch.segment_ids else None,
          "quote": ch.text,
          "text": ch.text,
      }
      for ch in top_chunks
  ]

  return QaResult(
      answer=answer,
      source="transcript",
      citations=citations,
      timeline=[],
  )
