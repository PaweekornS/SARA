"""
สกัดมติ + จับคู่กับมติเดิมข้ามการประชุม (M4) — โมดูลที่เป็นจุดขายของ v2

หลักการออกแบบที่ห้ามละเมิด (§4.2):
  False close อันตรายกว่า missed close หลายเท่า
  ทุกอย่างในไฟล์นี้จึง tune ไปทาง conservative:
    * โมเดลเสนอได้อย่างเดียว ผลลัพธ์ออกมาเป็น Proposal ที่ยังไม่มีผลจนกว่าคนจะกดยืนยัน
    * ข้อเสนอปิดมติต้องมีประโยคที่ "รายงานผลชัดเจน" ไม่ใช่แค่พูดถึงเรื่องนั้น
    * ชื่อคนที่ไม่มั่นใจ ไม่เดา — ส่งเป็นข้อเสนอให้คนเลือกแทน
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date

from app.core.config import settings
from app.services.llm import LlmError, chat_json

logger = logging.getLogger(__name__)

#  ต่ำกว่านี้ถือว่าโมเดลไม่มั่นใจพอจะเสนอปิดมติ
CLOSE_CONFIDENCE_FLOOR = 0.75

#  BPE ของโมเดลตัดคำไทยละเอียดกว่าอังกฤษมาก ตัวเลขนี้เป็นค่าประมาณแบบระวังไว้ก่อน
#  (ประเมินสูงกว่าจำนวน token จริง เพื่อให้แบ่งช่วงถี่กว่าที่จำเป็นดีกว่าเผลอส่งเกิน)
CHARS_PER_TOKEN = 1.5
SAFETY_MARGIN_TOKENS = 1000
MIN_CHUNK_TOKENS = 2000


@dataclass
class SegmentView:
    """ท่อนคำพูดในรูปที่ส่งให้โมเดล — index ใช้อ้างกลับมาหา segment จริง"""

    index: int
    speaker_label: str
    start_ms: int
    text: str


@dataclass
class OpenResolutionView:
    """มติค้างของ series ที่ส่งไปเป็นบริบท (FR-M4-04)"""

    ref: str
    text: str
    status: str
    assignees: str
    due_date: str | None


@dataclass
class NewResolution:
    text: str
    segment_index: int | None
    category: str = "other"
    assignee_mention: str = ""
    due_date: str | None = None
    confidence: float = 0.0


@dataclass
class ResolutionUpdate:
    ref: str
    segment_index: int | None
    proposed_status: str
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
    new_resolutions: list[NewResolution] = field(default_factory=list)
    updates: list[ResolutionUpdate] = field(default_factory=list)
    speakers: list[SpeakerMention] = field(default_factory=list)


SYSTEM_PROMPT = """คุณคือเลขานุการที่ประชุมของหน่วยงานราชการไทย มีหน้าที่อ่านบันทึกคำต่อคำของการประชุม แล้วสกัดข้อมูล 3 อย่าง

1. มติใหม่ (new_resolutions)
   - มติคือข้อตกลงที่ที่ประชุม "ตัดสินใจแล้ว" และมีผลผูกพัน มักขึ้นต้นว่า ที่ประชุมมีมติ / มอบหมายให้ / อนุมัติให้ / ให้...ดำเนินการ
   - ห้ามสร้างมติจากการอภิปรายทั่วไป ความคิดเห็น การตั้งคำถาม หรือข้อเสนอที่ยังไม่ได้ข้อสรุป
   - ประโยคอย่าง "ผมว่าน่าจะดีนะ" "เดี๋ยวค่อยว่ากันอีกที" "น่าจะลองดู" ไม่ใช่มติ

2. การรายงานผลของมติเดิม (updates)
   - ดูจากรายการมติค้างที่ให้ไว้ ว่ามีท่อนไหนในที่ประชุมนี้พูดถึงและรายงานความคืบหน้าหรือไม่
   - proposed_status ให้เลือกจาก: in_progress (เริ่ม/กำลังทำ) | blocked (ติดปัญหา) | done (ทำเสร็จแล้วจริง ๆ)
   - ให้ done เฉพาะเมื่อมีการยืนยันว่าดำเนินการเสร็จสิ้นแล้วอย่างชัดเจน เช่น ลงนามแล้ว แต่งตั้งแล้ว ส่งมอบแล้ว
   - ถ้าแค่เอ่ยถึงเรื่องนั้นโดยไม่ได้รายงานผล ห้ามใส่ใน updates

3. การเอ่ยชื่อผู้พูด (speakers)
   - ถ้าในบทสนทนามีการเรียกชื่อกัน เช่น "ขอบคุณพี่หนึ่งครับ" ให้บันทึกว่า speaker ท่อนใกล้เคียงน่าจะชื่ออะไร

ตอบกลับเป็น JSON เท่านั้น ตามรูปแบบนี้เป๊ะ ๆ
{
  "new_resolutions": [
    {"text": "ข้อความมติเต็มในภาษาราชการ", "segment_index": 12, "category": "procurement|policy|personnel|budget|operations|other", "assignee_mention": "ชื่อหรือหน่วยงานที่รับผิดชอบตามที่พูดในที่ประชุม", "due_date": "YYYY-MM-DD หรือ null", "confidence": 0.0-1.0}
  ],
  "updates": [
    {"ref": "เลขที่มติเดิมจากรายการที่ให้ไว้", "segment_index": 8, "proposed_status": "in_progress|blocked|done", "evidence": "ยกประโยคที่เป็นหลักฐานมาคำต่อคำ", "confidence": 0.0-1.0}
  ],
  "speakers": [
    {"speaker_label": "SPEAKER_01", "name_mention": "พี่หนึ่ง", "segment_index": 5, "confidence": 0.0-1.0}
  ]
}

confidence คือความมั่นใจของคุณเอง ถ้าไม่แน่ใจให้ใส่ค่าต่ำ อย่าใส่ 1.0 ทุกอัน
ถ้าไม่พบอะไรเลยในหมวดไหน ให้ใส่ลิสต์ว่าง ห้ามแต่งข้อมูลขึ้นมาเอง"""


def extract(
    segments: list[SegmentView],
    open_resolutions: list[OpenResolutionView],
    meeting_label: str,
) -> ExtractionResult:
    """
    สกัดมติใหม่ + จับคู่มติเดิม + เบาะแสชื่อผู้พูด

    การประชุมยาว ๆ ทำให้บันทึกคำต่อคำเกิน context ของโมเดลได้ง่าย (thaillm-8b รับได้
    LLM_CONTEXT_TOKENS token ต่อคำขอ) จึงแบ่งส่งเป็นช่วง ๆ ตามจำนวนที่ประมาณว่าพอดี
    แต่ละช่วงเห็นบริบทมติค้างชุดเดียวกันเสมอ เพื่อให้จับคู่กับมติเดิมได้จากทุกช่วง
    """
    if not segments:
        return ExtractionResult()

    context = _build_context(open_resolutions)
    valid_refs = {r.ref for r in open_resolutions}
    max_index = len(segments) - 1

    chunks = _chunk_segments(segments, _transcript_token_budget(context, meeting_label))
    if len(chunks) > 1:
        logger.info(
            "บันทึกยาวเกินขีดจำกัด context ของโมเดล แบ่งส่งเป็น %s ช่วง (%s ท่อนทั้งหมด)",
            len(chunks), len(segments),
        )

    merged = ExtractionResult()
    latest_updates: dict[str, ResolutionUpdate] = {}

    for i, chunk in enumerate(chunks, start=1):
        transcript = "\n".join(f"[{s.index}] ({s.speaker_label}) {s.text}" for s in chunk)
        user = (
            f"การประชุม: {meeting_label}\n\n"
            f"=== มติค้างของชุดการประชุมนี้ ===\n{context}\n\n"
            f"=== บันทึกคำต่อคำของการประชุมครั้งนี้ (ช่วงที่ {i}/{len(chunks)}) ===\n{transcript}"
        )

        try:
            data = chat_json(SYSTEM_PROMPT, user, temperature=0.1)
        except LlmError:
            logger.exception("สกัดมติไม่สำเร็จที่ช่วง %s/%s", i, len(chunks))
            raise

        partial = _to_result(data, valid_refs=valid_refs, max_index=max_index)
        merged.new_resolutions.extend(partial.new_resolutions)
        merged.speakers.extend(partial.speakers)
        for update in partial.updates:
            #  ช่วงหลังพูดถึงมติเดิมเรื่องเดียวกัน ถือเป็นรายงานที่ใหม่กว่าในเนื้อการประชุมเดียวกัน
            latest_updates[update.ref] = update

    merged.updates = list(latest_updates.values())
    return merged


def _build_context(open_resolutions: list[OpenResolutionView]) -> str:
    if not open_resolutions:
        return "(ยังไม่มีมติค้างจากการประชุมครั้งก่อน)"
    return "\n".join(
        f"- {r.ref} | สถานะ {r.status} | ผู้รับผิดชอบ {r.assignees or '-'}"
        f" | กำหนด {r.due_date or '-'}\n  ข้อความมติ: {r.text}"
        for r in open_resolutions
    )


def _approx_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / CHARS_PER_TOKEN))


def _transcript_token_budget(context: str, meeting_label: str) -> int:
    """token ที่เหลือให้บันทึกคำต่อคำ หลังหักระบบพรอมป์ต์ + บริบทมติค้าง + ที่กันไว้ให้คำตอบ"""
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
    return max(budget, MIN_CHUNK_TOKENS)


def _chunk_segments(segments: list[SegmentView], budget_tokens: int) -> list[list[SegmentView]]:
    """
    แบ่งท่อนคำพูดเป็นช่วง ๆ ให้แต่ละช่วงไม่เกินงบ token ที่ประมาณไว้
    ท่อนเดียวที่ใหญ่เกินงบเองก็ยังถูกส่งเดี่ยว ๆ ไป (ไม่ตัดเนื้อหาทิ้ง ปล่อยให้ gateway ตัดสิน)
    """
    chunks: list[list[SegmentView]] = []
    current: list[SegmentView] = []
    current_tokens = 0

    for segment in segments:
        line_tokens = _approx_tokens(f"[{segment.index}] ({segment.speaker_label}) {segment.text}\n")
        if current and current_tokens + line_tokens > budget_tokens:
            chunks.append(current)
            current, current_tokens = [], 0
        current.append(segment)
        current_tokens += line_tokens

    if current:
        chunks.append(current)
    return chunks


def _to_result(data: dict, valid_refs: set[str], max_index: int) -> ExtractionResult:
    """
    แปลงผลจากโมเดลเป็น dataclass พร้อมกรองของที่ใช้ไม่ได้ทิ้ง
    โมเดลเล็กชอบสร้าง ref ที่ไม่มีอยู่จริงหรือ index เกินขอบ ถ้าปล่อยผ่านจะกลายเป็นมติผูกผิดข้อ
    """
    result = ExtractionResult()

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
                confidence=_confidence(item.get("confidence")),
            )
        )

    for item in _as_list(data.get("updates")):
        ref = _clean(item.get("ref"))
        status = _clean(item.get("proposed_status"))
        if ref not in valid_refs:
            logger.info("ข้ามข้อเสนอที่อ้างมติซึ่งไม่มีอยู่จริง: %r", ref)
            continue
        if status not in ("in_progress", "blocked", "done"):
            continue
        confidence = _confidence(item.get("confidence"))
        #  §4.2 ปิดมติเป็นการกระทำที่ย้อนคืนยาก จึงไม่เสนอเลยถ้าโมเดลเองยังไม่มั่นใจ
        if status == "done" and confidence < CLOSE_CONFIDENCE_FLOOR:
            logger.info("ไม่เสนอปิดมติ %s เพราะ confidence %.2f ต่ำเกินไป", ref, confidence)
            status = "in_progress"
        result.updates.append(
            ResolutionUpdate(
                ref=ref,
                segment_index=_index(item.get("segment_index"), max_index),
                proposed_status=status,
                evidence=_clean(item.get("evidence")),
                confidence=confidence,
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
                confidence=_confidence(item.get("confidence")),
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
        return 0.5


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


# ── entity resolution ชื่อคนไทย (M3) ────────────────────────────────────

def resolve_person(mention: str, candidates: list[tuple[str, str]]) -> tuple[str | None, float]:
    """
    จับคู่คำเรียกกับบุคคลในทะเบียน โดยเทียบตัวอักษรตรง ๆ เท่านั้น ไม่ใช้โมเดลเดา

    candidates คือ [(person_id, ข้อความที่ใช้เทียบ)] ซึ่งรวมทั้งชื่อจริงและ alias ที่เคยยืนยันแล้ว
    คืน (person_id, confidence) — ถ้าไม่มั่นใจคืน (None, 0) เพื่อให้ชั้นบนสร้างข้อเสนอถามคนแทน

    §12 ระบุว่าการให้ AI เดาชื่อคนไทยจะพังแน่นอน หลักการคือ "ให้มนุษย์ยืนยันครั้งแรก แล้วระบบจำ"
    """
    needle = mention.strip()
    if not needle:
        return None, 0.0

    exact = [pid for pid, label in candidates if label.strip() == needle]
    if len(exact) == 1:
        return exact[0], 0.95
    if len(exact) > 1:
        return None, 0.0  # ชนกันหลายคน ต้องให้คนตัดสิน

    contains = [pid for pid, label in candidates if needle and needle in label]
    if len(contains) == 1:
        return contains[0], 0.7

    return None, 0.0
