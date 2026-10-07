"""
งาน LLM ต่อบันทึกการประชุม 1 ครั้ง

1. summarize()        สรุปตาม template + สกัด action items
2. detect_completed() ตรวจว่างานค้างจากการประชุมก่อน ๆ ถูกรายงานว่าเสร็จแล้วหรือยัง
                      ผลเป็นแค่ "ข้อเสนอ" ผู้ใช้ต้องกดยืนยันเอง

บันทึกยาวเกิน context ของโมเดลจะถูกแบ่งเป็นช่วงแล้วเรียกขนานกัน แล้วรวมผลทีหลัง
"""

from __future__ import annotations

import concurrent.futures
import logging
import math
from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from app.core.config import settings
from app.services.llm import LlmError, chat_json, detect_language, language_rule
from app.services.templates import get_template

logger = logging.getLogger(__name__)

CHARS_PER_TOKEN = 1.5
SAFETY_MARGIN_TOKENS = 1000
# ช่วงละ ~3,500 tokens ให้แต่ละช่วงตอบกลับใน 15-25 วินาที ไม่ชน 504 ของ gateway
TARGET_CHUNK_TOKENS = 3500
MAX_PARALLEL_CALLS = 4
COMPLETION_CONFIDENCE_FLOOR = 0.75

COMPLETION_PROMPT = """คุณคือผู้ช่วยติดตามงาน
จะได้รับ (1) รายการงานค้างจากการประชุมครั้งก่อน มีเลขกำกับ และ (2) บันทึกการประชุมครั้งนี้
ให้หาว่างานค้างข้อไหนถูกพูดถึงในบันทึกว่า "ทำเสร็จแล้ว" อย่างชัดเจน
ถ้าแค่พูดถึง กำลังทำ หรือเลื่อนออกไป ไม่นับว่าเสร็จ

ตอบกลับเป็น JSON เท่านั้น:
{
  "completed": [
    {"item": 2, "segment_index": 15, "evidence": "ข้อความในบันทึกที่ยืนยันว่าเสร็จ", "confidence": 0.9}
  ]
}
ถ้าไม่มีงานไหนเสร็จ ให้ตอบ {"completed": []}"""


# ── ข้อมูลขาเข้า-ขาออก ─────────────────────────────────────────────────

@dataclass
class SegmentView:
    """ท่อนคำพูดในรูปที่ส่งให้โมเดล — index ใช้อ้างกลับมาหา segment จริง"""

    index: int
    speaker_label: str
    text: str


@dataclass
class ActionItemDraft:
    text: str
    owner: str = ""
    due_date: str | None = None
    segment_index: int | None = None


@dataclass
class SummaryResult:
    summary: str = ""
    key_points: list[str] = field(default_factory=list)
    action_items: list[ActionItemDraft] = field(default_factory=list)
    details: dict[str, object] = field(default_factory=dict)


@dataclass
class OpenItemView:
    number: int
    text: str
    owner: str = ""


@dataclass
class CompletionHint:
    number: int
    evidence: str
    segment_index: int | None
    confidence: float


# ── สรุปการประชุม ──────────────────────────────────────────────────────

def summarize(segments: list[SegmentView], template: str, title: str = "") -> SummaryResult:
    if not segments:
        return SummaryResult()

    tmpl = get_template(template)
    system = tmpl["system_prompt"]
    max_index = segments[-1].index
    header = f"การประชุม: {title}\n\n" if title else ""

    def build_user(transcript: str, part: str) -> str:
        return f"{header}=== บันทึกการประชุม{part} ===\n{transcript}"

    responses = _run_chunked(segments, system, build_user)

    merged = SummaryResult()
    for data in responses:
        partial = _to_summary(data, tmpl["detail_labels"], max_index)
        if partial.summary and partial.summary not in merged.summary:
            merged.summary = f"{merged.summary} {partial.summary}".strip()
        merged.key_points.extend(p for p in partial.key_points if p not in merged.key_points)
        merged.action_items.extend(partial.action_items)
        for key, value in partial.details.items():
            merged.details[key] = _merge_detail(merged.details.get(key), value)
    return merged


def _to_summary(data: dict, detail_labels: dict[str, str], max_index: int) -> SummaryResult:
    result = SummaryResult(summary=_clean(data.get("summary")))
    result.key_points = [_clean(p) for p in _as_list(data.get("key_points")) if _clean(p)]
    if not result.summary and result.key_points:
        result.summary = " ".join(result.key_points)

    for item in _as_list(data.get("action_items")):
        if not isinstance(item, dict):
            continue
        text = _clean(item.get("task") or item.get("text"))
        if not text:
            continue
        result.action_items.append(
            ActionItemDraft(
                text=text,
                owner=_clean(item.get("owner") or item.get("assigned_speaker") or item.get("assignee")),
                due_date=_date(item.get("deadline") or item.get("due_date")),
                segment_index=_index(item.get("segment_index"), max_index),
            )
        )

    #  เก็บเฉพาะฟิลด์ที่ template ประกาศไว้ กันโมเดลแถมคีย์แปลก ๆ มาเต็มหน้าจอ
    for key in detail_labels:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            result.details[key] = value.strip()
        elif isinstance(value, list) and value:
            result.details[key] = value
    return result


def _merge_detail(current, new):
    if current is None:
        return new
    if isinstance(current, list) and isinstance(new, list):
        return current + [v for v in new if v not in current]
    if isinstance(current, str) and isinstance(new, str) and new not in current:
        return f"{current} {new}"
    return current


# ── ตรวจงานค้างที่เสร็จแล้ว ────────────────────────────────────────────

def detect_completed(segments: list[SegmentView], open_items: list[OpenItemView]) -> list[CompletionHint]:
    if not segments or not open_items:
        return []

    valid_numbers = {item.number for item in open_items}
    max_index = segments[-1].index
    listing = "\n".join(
        f"{item.number}. {item.text}" + (f" (ผู้รับผิดชอบ: {item.owner})" if item.owner else "")
        for item in open_items
    )

    def build_user(transcript: str, part: str) -> str:
        return f"=== งานค้าง ===\n{listing}\n\n=== บันทึกการประชุมครั้งนี้{part} ===\n{transcript}"

    best: dict[int, CompletionHint] = {}
    for data in _run_chunked(segments, COMPLETION_PROMPT, build_user, overhead_text=listing):
        for raw in _as_list(data.get("completed")):
            if not isinstance(raw, dict):
                continue
            try:
                number = int(raw.get("item"))
            except (TypeError, ValueError):
                continue
            confidence = _confidence(raw.get("confidence"))
            if number not in valid_numbers or confidence < COMPLETION_CONFIDENCE_FLOOR:
                continue
            hint = CompletionHint(
                number=number,
                evidence=_clean(raw.get("evidence")),
                segment_index=_index(raw.get("segment_index"), max_index),
                confidence=confidence,
            )
            if number not in best or hint.confidence > best[number].confidence:
                best[number] = hint
    return sorted(best.values(), key=lambda h: h.number)


# ── การแบ่งช่วงและเรียกโมเดล ──────────────────────────────────────────

def _run_chunked(
    segments: list[SegmentView],
    system: str,
    build_user: Callable[[str, str], str],
    overhead_text: str = "",
) -> list[dict]:
    system += language_rule(detect_language(" ".join(s.text for s in segments[:200])))
    budget = _transcript_token_budget(system + overhead_text)
    chunks = chunk_segments(segments, budget)
    total = len(chunks)

    def call(idx: int, chunk: list[SegmentView]) -> dict:
        transcript = "\n".join(f"[{s.index}] ({s.speaker_label}) {s.text}" for s in chunk)
        part = f" (ช่วงที่ {idx}/{total})" if total > 1 else ""
        try:
            return chat_json(system, build_user(transcript, part), temperature=0.1)
        except LlmError:
            logger.exception("เรียกโมเดลไม่สำเร็จที่ช่วง %s/%s", idx, total)
            raise

    if total == 1:
        return [call(1, chunks[0])]
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(total, MAX_PARALLEL_CALLS)) as pool:
        futures = [pool.submit(call, i, chunk) for i, chunk in enumerate(chunks, start=1)]
        return [f.result() for f in futures]


def _approx_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / CHARS_PER_TOKEN))


def _transcript_token_budget(overhead_text: str) -> int:
    budget = (
        settings.LLM_CONTEXT_TOKENS
        - settings.LLM_RESPONSE_RESERVE_TOKENS
        - _approx_tokens(overhead_text)
        - SAFETY_MARGIN_TOKENS
    )
    return max(500, min(budget, TARGET_CHUNK_TOKENS))


def chunk_segments(segments: list[SegmentView], budget_tokens: int) -> list[list[SegmentView]]:
    chunks: list[list[SegmentView]] = []
    current: list[SegmentView] = []
    current_tokens = 0
    for segment in segments:
        tokens = _approx_tokens(segment.text)
        if current and current_tokens + tokens > budget_tokens:
            chunks.append(current)
            current, current_tokens = [], 0
        current.append(segment)
        current_tokens += tokens
    if current:
        chunks.append(current)
    return chunks


# ── ทำความสะอาดค่าจากโมเดล ────────────────────────────────────────────

def _as_list(value) -> list:
    return value if isinstance(value, list) else []


def _clean(value) -> str:
    return str(value).strip() if isinstance(value, (str, int, float)) else ""


def _confidence(value) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


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
