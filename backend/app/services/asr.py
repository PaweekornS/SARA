"""
ถอดเสียงด้วย AI4Thai ASR (M2)

⚠ หลักการที่ห้ามละเมิด (FR-M2-04 · งานล้างหนี้ข้อ 1):
   ถ้าถอดเสียงไม่สำเร็จ ต้องโยน AsrError ออกไปให้ pipeline หยุดและแจ้งผู้ใช้ตามจริง
   ห้ามคืน transcript ปลอมกลับไปเด็ดขาด เพราะรายงานการประชุมมีผลผูกพันทางกฎหมาย
   ข้อมูลปลอมในระบบสารบรรณอันตรายกว่าระบบล่ม
"""

from __future__ import annotations

import glob
import logging
import os
import re
import subprocess
from dataclasses import dataclass, field

from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

client = OpenAI(
    base_url=f"{settings.ASR_URL.rstrip('/')}/v1",
    api_key=settings.APP_AI4THAI_API_KEY,
)

# เผื่อ margin จากลิมิต 25 MB ของ API
MAX_FILE_SIZE = 24 * 1024 * 1024
CHUNK_SECONDS = 600


class AsrError(RuntimeError):
    """ถอดเสียงไม่สำเร็จ — pipeline ต้องหยุดที่ขั้นนี้"""


@dataclass
class Segment:
    text: str
    start_ms: int = 0
    end_ms: int = 0
    speaker_label: str = "SPEAKER_00"
    confidence: float = 1.0


@dataclass
class Transcript:
    segments: list[Segment] = field(default_factory=list)
    #  ASR คืน speaker label มาเองหรือไม่ — ใช้ตัดสินว่าต้องให้คนระบุผู้พูดเองไหม
    has_speaker_labels: bool = False

    @property
    def text(self) -> str:
        return "\n".join(s.text for s in self.segments)


def transcribe_audio(file_path: str) -> Transcript:
    """ถอดเสียงทั้งไฟล์ คืน segment พร้อม timestamp — โยน AsrError เมื่อทำไม่ได้"""
    if not os.path.exists(file_path):
        raise AsrError(f"ไม่พบไฟล์เสียงที่ {file_path}")

    size = os.path.getsize(file_path)
    if size == 0:
        raise AsrError("ไฟล์เสียงว่างเปล่า (0 ไบต์)")

    logger.info("ASR: %s (%.2f MB)", file_path, size / 1024 / 1024)

    if size <= MAX_FILE_SIZE:
        return _transcribe_one(file_path, offset_ms=0)

    chunks = _split_audio(file_path)
    if not chunks:
        raise AsrError(
            "ไฟล์ใหญ่เกิน 24 MB และแบ่งไฟล์ด้วย ffmpeg ไม่สำเร็จ จึงถอดเสียงต่อไม่ได้"
        )

    merged = Transcript()
    offset = 0
    try:
        for i, chunk in enumerate(chunks, start=1):
            logger.info("ASR chunk %s/%s", i, len(chunks))
            part = _transcribe_one(chunk, offset_ms=offset)
            merged.segments.extend(part.segments)
            merged.has_speaker_labels = merged.has_speaker_labels or part.has_speaker_labels
            offset = part.segments[-1].end_ms if part.segments else offset + CHUNK_SECONDS * 1000
    finally:
        for chunk in chunks:
            try:
                os.remove(chunk)
            except OSError as err:
                logger.warning("ลบไฟล์ชั่วคราวไม่สำเร็จ %s: %s", chunk, err)

    if not merged.segments:
        raise AsrError("ถอดเสียงสำเร็จแต่ไม่ได้ข้อความกลับมา ตรวจสอบว่าไฟล์มีเสียงพูดจริง")
    return merged


def _transcribe_one(file_path: str, offset_ms: int) -> Transcript:
    """
    เรียก ASR ครั้งเดียว — ขอ verbose_json ก่อนเพื่อให้ได้ timestamp ระดับ segment
    ถ้า endpoint ไม่รองรับค่อยถอยไป json ธรรมดาแล้วตัดประโยคเอง
    """
    try:
        with open(file_path, "rb") as fh:
            raw = client.audio.transcriptions.create(
                model=settings.ASR_MODEL,
                file=fh,
                language="th",
                response_format="verbose_json",
            )
        return _from_verbose(raw, offset_ms)
    except AsrError:
        raise
    except Exception as verbose_err:  # noqa: BLE001 — ต้องรู้ทุกสาเหตุที่ verbose ไม่ผ่าน
        logger.info("verbose_json ใช้ไม่ได้ (%s) — ลองแบบ json ธรรมดา", verbose_err)

    try:
        with open(file_path, "rb") as fh:
            raw = client.audio.transcriptions.create(
                model=settings.ASR_MODEL,
                file=fh,
                language="th",
                response_format="json",
            )
    except Exception as err:  # noqa: BLE001
        raise AsrError(f"เรียก AI4Thai ASR ไม่สำเร็จ: {err}") from err

    text = (getattr(raw, "text", "") or "").strip()
    if not text:
        raise AsrError("AI4Thai ASR ตอบกลับมาโดยไม่มีข้อความ")
    return Transcript(segments=_split_sentences(text, offset_ms), has_speaker_labels=False)


def _from_verbose(raw, offset_ms: int) -> Transcript:
    """แปลงผล verbose_json เป็น segment — รองรับกรณี API แนบ speaker มาให้ด้วย"""
    raw_segments = getattr(raw, "segments", None) or []
    if not raw_segments:
        text = (getattr(raw, "text", "") or "").strip()
        if not text:
            raise AsrError("AI4Thai ASR ตอบกลับมาโดยไม่มีข้อความ")
        return Transcript(segments=_split_sentences(text, offset_ms), has_speaker_labels=False)

    segments: list[Segment] = []
    has_speakers = False
    for item in raw_segments:
        data = item if isinstance(item, dict) else getattr(item, "model_dump", lambda: {})()
        text = (data.get("text") or "").strip()
        if not text:
            continue
        speaker = data.get("speaker") or data.get("speaker_label")
        if speaker:
            has_speakers = True
        segments.append(
            Segment(
                text=text,
                start_ms=offset_ms + int(float(data.get("start", 0)) * 1000),
                end_ms=offset_ms + int(float(data.get("end", 0)) * 1000),
                speaker_label=str(speaker) if speaker else "SPEAKER_00",
                confidence=_confidence_of(data),
            )
        )

    if not segments:
        raise AsrError("AI4Thai ASR คืน segment ที่ไม่มีข้อความเลย")
    return Transcript(segments=segments, has_speaker_labels=has_speakers)


def _confidence_of(data: dict) -> float:
    """avg_logprob ของ Whisper อยู่ราว -1..0 — แปลงเป็น 0..1 แบบหยาบ ๆ พอให้ UI ไฮไลต์จุดเสี่ยงได้"""
    logprob = data.get("avg_logprob")
    if logprob is None:
        return 1.0
    try:
        return max(0.0, min(1.0, 1.0 + float(logprob)))
    except (TypeError, ValueError):
        return 1.0


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?。])\s+|\n+")


def _split_sentences(text: str, offset_ms: int) -> list[Segment]:
    """
    ตัดข้อความจริงเป็นท่อน ๆ เมื่อ ASR ไม่ให้ timestamp มา
    timestamp ที่ได้เป็นค่าประมาณตามสัดส่วนความยาวข้อความ ไม่ใช่ค่าที่วัดจากเสียงจริง
    (ยังเป็นข้อความจริงทุกตัวอักษร — ไม่ใช่การแต่งข้อมูลขึ้นมา)
    """
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(text) if p and p.strip()]
    if not parts:
        parts = [text]

    #  ประมาณอัตราการพูดภาษาไทยที่ ~12 ตัวอักษร/วินาที
    chars_per_ms = 12 / 1000
    segments: list[Segment] = []
    cursor = offset_ms
    for part in parts:
        duration = max(1500, int(len(part) / chars_per_ms))
        segments.append(Segment(text=part, start_ms=cursor, end_ms=cursor + duration))
        cursor += duration
    return segments


def _split_audio(file_path: str) -> list[str]:
    base, ext = os.path.splitext(file_path)
    pattern = f"{base}_chunk_%03d{ext}"
    cmd = [
        "ffmpeg", "-y",
        "-i", file_path,
        "-f", "segment",
        "-segment_time", str(CHUNK_SECONDS),
        "-c", "copy",
        pattern,
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        return sorted(glob.glob(f"{base}_chunk_*{ext}"))
    except subprocess.CalledProcessError as err:
        logger.error("ffmpeg แบ่งไฟล์ไม่สำเร็จ: %s", err.stderr)
        return []
    except FileNotFoundError:
        logger.error("ไม่พบคำสั่ง ffmpeg ในเครื่อง")
        return []


def load_transcript_file(file_path: str) -> Transcript:
    """FR-M2-02 อัปโหลด transcript ที่มีอยู่แล้วเพื่อข้ามขั้น ASR"""
    ext = os.path.splitext(file_path)[1].lower()
    if ext in (".txt", ".md"):
        with open(file_path, encoding="utf-8", errors="replace") as fh:
            text = fh.read().strip()
    elif ext == ".docx":
        try:
            from docx import Document
        except ImportError as err:  # pragma: no cover
            raise AsrError("อ่านไฟล์ .docx ไม่ได้เพราะยังไม่ได้ติดตั้ง python-docx") from err
        text = "\n".join(p.text for p in Document(file_path).paragraphs).strip()
    else:
        raise AsrError(f"ยังไม่รองรับไฟล์ transcript นามสกุล {ext}")

    if not text:
        raise AsrError("ไฟล์ transcript ว่างเปล่า")
    return Transcript(segments=_split_sentences(text, 0), has_speaker_labels=False)
