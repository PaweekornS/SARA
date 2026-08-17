"""
สรุปเนื้อหาการประชุม + สกัดมติจากการประชุม
"""

from __future__ import annotations

import concurrent.futures
import logging
import math
from dataclasses import dataclass, field
from datetime import date

from app.core.config import settings
from app.services.llm import LlmError, chat_json

# ── Global Variables & Constants ─────────────────────────────────────────────

logger = logging.getLogger(__name__)

CLOSE_CONFIDENCE_FLOOR = 0.75
CHARS_PER_TOKEN = 1.5
SAFETY_MARGIN_TOKENS = 1000
MIN_CHUNK_TOKENS = 2000
TARGET_CHUNK_TOKENS = 3500

SYSTEM_PROMPT = """คุณคือเลขานุการที่ประชุมของหน่วยงานราชการไทย มีหน้าที่อ่านบันทึกคำต่อคำของการประชุมแล้วทำ 2 อย่าง:
1. สรุปสาระสำคัญของการประชุม (summary):
   - สรุปสาระสำคัญและประเด็นสำคัญทั้งหมดที่ที่ประชุมได้หารืออย่างครบถ้วนกระชับในภาษาราชการ
2. สกัดมติที่ที่ประชุมเห็นชอบ/ตัดสินใจ/มอบหมาย (new_resolutions):
   - text: ข้อความมติเต็มในภาษาราชการ (เช่น "มอบหมายให้ฝ่ายพัสดุจัดทำร่างขอบเขตของงาน (TOR)...", "อนุมัติงบประมาณ...")
   - assignee_mention: ฝ่ายหรือบุคคลที่ได้รับมอบหมายตามที่พูดในที่ประชุม (เช่น "ฝ่ายพัสดุ", "ฝ่ายการเงิน", "ฝ่ายบริหารทั่วไป")
   - category: procurement | policy | personnel | budget | operations | other
   - confidence: 0.0 - 1.0 (ความมั่นใจ เช่น 0.9)

ตอบกลับเป็น JSON เท่านั้นในรูปแบบ:
{
  "summary": "สรุปสาระสำคัญและประเด็นที่ที่ประชุมได้หารือ...",
  "new_resolutions": [
    {
      "text": "ข้อความมติเต็ม",
      "assignee_mention": "ฝ่ายพัสดุ",
      "category": "procurement",
      "confidence": 0.9
    }
  ]
}

ถ้าไม่พบมติ ให้ใส่ new_resolutions เป็นลิสต์ว่าง ห้ามแต่งข้อมูลขึ้นมาเอง"""


# ── Classes & Dataclasses ────────────────────────────────────────────────────

@dataclass
class SegmentView:
    """ท่อนคำพูดในรูปที่ส่งให้โมเดล — index ใช้อ้างกลับมาหา segment จริง"""

    index: int
    speaker_label: str
    start_ms: int
    text: str


@dataclass
class OpenResolutionView:
    """มติค้างของ series"""

    ref: str
    text: str
    status: str
    assignees: str
    due_date: str | None


@dataclass
class NewResolution:
    text: str
    segment_index: int | None = None
    category: str = "other"
    assignee_mention: str = ""
    due_date: str | None = None
    confidence: float = 0.85


@dataclass
class ResolutionUpdate:
    ref: str
    segment_index: int | None = None
    proposed_status: str = "in_progress"
    evidence: str = ""
    confidence: float = 0.0


@dataclass
class SpeakerMention:
    speaker_label: str
    name_mention: str
    segment_index: int | None = None
    confidence: float = 0.0


@dataclass
class ExtractionResult:
    summary: str = ""
    key_points: list[str] = field(default_factory=list)
    new_resolutions: list[NewResolution] = field(default_factory=list)
    updates: list[ResolutionUpdate] = field(default_factory=list)
    speakers: list[SpeakerMention] = field(default_factory=list)


# ── Functions ────────────────────────────────────────────────────────────────

def extract(
    segments: list[SegmentView],
    open_resolutions: list[OpenResolutionView] | None = None,
    meeting_label: str = "",
) -> ExtractionResult:
    """
    สรุปเนื้อหา ASR และสกัดมติที่เกิดขึ้นจากการประชุมแบบ Parallel Concurrent Chunks
    """
    if not segments:
        return ExtractionResult()

    context = _build_context(open_resolutions)
    max_index = len(segments) - 1
    chunks = _chunk_segments(segments, _transcript_token_budget(context, meeting_label))

    def _call_chunk(idx: int, chunk_segments: list[SegmentView]) -> tuple[int, dict]:
        transcript = "\n".join(f"[{s.index}] ({s.speaker_label}) {s.text}" for s in chunk_segments)
        context_sec = f"=== มติค้างของชุดการประชุมนี้ ===\n{context}\n\n" if context else ""
        user = (
            f"การประชุม: {meeting_label}\n\n"
            f"{context_sec}"
            f"=== บันทึกคำต่อคำของการประชุม (ช่วงที่ {idx}/{len(chunks)}) ===\n{transcript}"
        )
        try:
            data = chat_json(SYSTEM_PROMPT, user, temperature=0.1)
            return idx, data
        except LlmError:
            logger.exception("สกัดมติไม่สำเร็จที่ช่วง %s/%s", idx, len(chunks))
            raise

    if len(chunks) == 1:
        chunk_results = [_call_chunk(1, chunks[0])]
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(chunks), 4)) as executor:
            futures = [executor.submit(_call_chunk, i, ch) for i, ch in enumerate(chunks, start=1)]
            chunk_results = [f.result() for f in futures]
            chunk_results.sort(key=lambda x: x[0])

    merged = ExtractionResult()
    latest_updates: dict[str, ResolutionUpdate] = {}

    for i, data in chunk_results:
        partial = _to_result(data, max_index=max_index)
        if partial.summary:
            if not merged.summary:
                merged.summary = partial.summary
            elif partial.summary not in merged.summary:
                merged.summary += f" {partial.summary}"
        merged.key_points.extend(partial.key_points)
        merged.new_resolutions.extend(partial.new_resolutions)
        merged.speakers.extend(partial.speakers)
        for update in partial.updates:
            latest_updates[update.ref] = update

    merged.updates = list(latest_updates.values())
    return merged


def _build_context(open_resolutions: list[OpenResolutionView] | None) -> str:
    if not open_resolutions:
        return ""
    return "\n".join(
        f"- {r.ref} | สถานะ {r.status} | ผู้รับผิดชอบ {r.assignees or '-'}"
        f" | กำหนด {r.due_date or '-'}\n  ข้อความมติ: {r.text}"
        for r in open_resolutions
    )


def _approx_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / CHARS_PER_TOKEN))


def _transcript_token_budget(context: str, meeting_label: str) -> int:
    wrapper = (
        f"การประชุม: {meeting_label}\n\n"
        f"=== มติค้างของชุดการประชุมนี้ ===\n{context}\n\n"
        f"=== บันทึกคำต่อคำของการประชุมครั้งนี้ (ช่วงที่ 1/1) ===\n"
    )
    overhead = _approx_tokens(SYSTEM_PROMPT) + _approx_tokens(wrapper)
    budget = (
        settings.LLM_CONTEXT_TOKENS
        - settings.LLM_RESPONSE_RESERVE_TOKENS
        - overhead
        - SAFETY_MARGIN_TOKENS
    )
    # คุมขนาด chunk ให้พอดี ~3,500 tokens เพื่อให้แต่ละ chunk ตอบกลับใน 15-25 วินาที ไม่ชน 504 Gateway Timeout
    effective = max(budget, min(1000, settings.LLM_CONTEXT_TOKENS // 2))
    return min(effective, TARGET_CHUNK_TOKENS)


def _chunk_segments(segments: list[SegmentView], budget_tokens: int) -> list[list[SegmentView]]:
    chunks: list[list[SegmentView]] = []
    current: list[SegmentView] = []
    current_tokens = 0

    for segment in segments:
        line_tokens = max(1, math.ceil(len(segment.text) / CHARS_PER_TOKEN))
        if current and current_tokens + line_tokens > budget_tokens:
            chunks.append(current)
            current, current_tokens = [], 0
        current.append(segment)
        current_tokens += line_tokens

    if current:
        chunks.append(current)
    return chunks


def _to_result(data: dict, valid_refs: set[str] | None = None, max_index: int = 0) -> ExtractionResult:
    valid_refs_set = valid_refs or set()
    result = ExtractionResult()
    result.summary = _clean(data.get("summary"))

    raw_points = data.get("key_points")
    if isinstance(raw_points, list) and raw_points:
        points = [_clean(p) for p in raw_points if _clean(p)]
        result.key_points = points
        if not result.summary:
            result.summary = " ".join(points)

    for item in _as_list(data.get("new_resolutions")):
        text = _clean(item.get("text"))
        if not text:
            continue
        result.new_resolutions.append(
            NewResolution(
                text=text,
                segment_index=_index(item.get("segment_index"), max_index),
                category=_clean(item.get("category")) or "other",
                assignee_mention=_clean(item.get("assignee_mention")),
                due_date=_date(item.get("due_date")),
                confidence=_confidence(item.get("confidence") if item.get("confidence") is not None else 0.85),
            )
        )

    for item in _as_list(data.get("updates")):
        ref = _clean(item.get("ref"))
        status = _clean(item.get("proposed_status"))
        if valid_refs_set and ref not in valid_refs_set:
            continue
        if status not in ("in_progress", "blocked", "done"):
            continue
        conf = _confidence(item.get("confidence") if item.get("confidence") is not None else 0.9)
        if status == "done" and conf < CLOSE_CONFIDENCE_FLOOR:
            status = "in_progress"
        result.updates.append(
            ResolutionUpdate(
                ref=ref,
                segment_index=_index(item.get("segment_index"), max_index),
                proposed_status=status,
                evidence=_clean(item.get("evidence")),
                confidence=conf,
            )
        )

    for item in _as_list(data.get("speakers")):
        label = _clean(item.get("speaker_label"))
        mention = _clean(item.get("name_mention"))
        if not label or not mention:
            continue
        result.speakers.append(
            SpeakerMention(
                speaker_label=label,
                name_mention=mention,
                segment_index=_index(item.get("segment_index"), max_index),
                confidence=_confidence(item.get("confidence") if item.get("confidence") is not None else 0.8),
            )
        )

    return result


def _as_list(value) -> list[dict]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def _clean(value) -> str:
    return str(value).strip() if isinstance(value, (str, int, float)) else ""


def _confidence(value) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.85


def _index(value, max_index: int) -> int | None:
    try:
        idx = int(value)
    except (TypeError, ValueError):
        return None
    return idx if 0 <= idx <= max_index else None


def _date(value) -> str | None:
    text = _clean(value)
    if not text or text.lower() in ("null", "none", "-"):
        return None
    try:
        date.fromisoformat(text[:10])
    except ValueError:
        return None
    return text[:10]


def resolve_person(mention: str, candidates: list[tuple[str, str]]) -> tuple[str | None, float]:
    needle = mention.strip()
    if not needle:
        return None, 0.0

    exact = [pid for pid, label in candidates if label.strip() == needle]
    if len(exact) == 1:
        return exact[0], 0.95
    if len(exact) > 1:
        return None, 0.0

    contains = [pid for pid, label in candidates if needle and needle in label]
    if len(contains) == 1:
        return contains[0], 0.7

    return None, 0.0
