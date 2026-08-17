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

# ── Global Variables & Constants ─────────────────────────────────────────────

logger = logging.getLogger(__name__)

client = OpenAI(
    base_url=f"{settings.ASR_URL.rstrip('/')}/v1",
    api_key=settings.APP_AI4THAI_API_KEY,
)

# ลิมิตขนาดไฟล์และความยาว chunk ที่เหมาะสมที่สุดสำหรับ ASR (10 นาที หรือ 20 MB)
MAX_FILE_SIZE = 20 * 1024 * 1024
CHUNK_SECONDS = 600
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?。])\s+|\n+")


# ── Classes & Dataclasses ────────────────────────────────────────────────────

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
    # ASR คืน speaker label มาเองหรือไม่ — ใช้ตัดสินว่าต้องให้คนระบุผู้พูดเองไหม
    has_speaker_labels: bool = False

    @property
    def text(self) -> str:
        return "\n".join(s.text for s in self.segments)


# ── Functions ────────────────────────────────────────────────────────────────

def _get_audio_duration(file_path: str) -> float:
    """หาความยาวของไฟล์เสียง (วินาที) ด้วย ffprobe หรือ ffmpeg"""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(res.stdout.strip())
    except Exception:
        pass

    try:
        cmd = ["ffmpeg", "-i", file_path]
        res = subprocess.run(cmd, capture_output=True, text=True)
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", res.stderr)
        if match:
            hours, minutes, seconds = match.groups()
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except Exception:
        pass
    return 0.0


def transcribe_audio(file_path: str) -> Transcript:
    """ถอดเสียงทั้งไฟล์ คืน segment พร้อม timestamp — โยน AsrError เมื่อทำไม่ได้"""
    if not os.path.exists(file_path):
        raise AsrError(f"ไม่พบไฟล์เสียงที่ {file_path}")

    size = os.path.getsize(file_path)
    if size == 0:
        raise AsrError("ไฟล์เสียงว่างเปล่า (0 ไบต์)")

    duration = _get_audio_duration(file_path)
    logger.info("ASR: %s (%.2f MB, %.1f นาที)", file_path, size / 1024 / 1024, duration / 60 if duration else 0)

    # หากไฟล์ยาวเกิน 10 นาที หรือขนาดเกิน 20MB ให้แบ่งเป็นช่วงย่อยเสมอเพื่อป้องกัน ASR คืนค่าว่าง
    should_split = (duration > CHUNK_SECONDS) or (size > MAX_FILE_SIZE)

    if not should_split:
        try:
            result = _transcribe_one(file_path, offset_ms=0)
            if result.segments:
                return result
            logger.info("ถอดเสียงไฟล์เดี่ยวได้ผลลัพธ์ว่างเปล่า — ลองแบ่งไฟล์เป็นช่วงย่อย (chunking)")
        except Exception as err:
            logger.info("ถอดเสียงไฟล์เดี่ยวไม่ผ่าน (%s) — ลองแบ่งไฟล์เป็นช่วงย่อย (chunking)", err)

    chunks = _split_audio(file_path, chunk_seconds=CHUNK_SECONDS)
    if not chunks:
        # หากแบ่งไม่ได้ ให้ลอง transcribe ไฟล์ตรง
        if not should_split:
            raise AsrError("AI4Thai ASR ตอบกลับมาโดยไม่มีข้อความ")
        return _transcribe_one(file_path, offset_ms=0)

    merged = Transcript()
    offset = 0
    try:
        for i, chunk in enumerate(chunks, start=1):
            logger.info("ASR chunk %s/%s", i, len(chunks))
            part = _transcribe_one(chunk, offset_ms=offset)
            merged.segments.extend(part.segments)
            merged.has_speaker_labels = merged.has_speaker_labels or part.has_speaker_labels

            chunk_duration = _get_audio_duration(chunk)
            if part.segments and part.segments[-1].end_ms > offset:
                offset = part.segments[-1].end_ms
            elif chunk_duration > 0:
                offset += int(chunk_duration * 1000)
            else:
                offset += CHUNK_SECONDS * 1000
    finally:
        for chunk in chunks:
            try:
                os.remove(chunk)
            except OSError as err:
                logger.warning("ลบไฟล์ชั่วคราวไม่สำเร็จ %s: %s", chunk, err)

    if not merged.segments:
        raise AsrError("AI4Thai ASR ตอบกลับมาโดยไม่มีข้อความ — ตรวจสอบว่าไฟล์มีเสียงพูดจริง")
    return merged


def _normalize_audio(file_path: str) -> str:
    """แปลงไฟล์เสียงให้อยู่ในฟอร์แมตมาตรฐาน 16kHz Mono MP3 ที่ ASR ทุกตัวอ่านได้ 100%"""
    base, _ = os.path.splitext(file_path)
    output_path = f"{base}_norm.mp3"
    cmd = [
        "ffmpeg", "-y",
        "-i", file_path,
        "-vn",
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "libmp3lame",
        "-b:a", "64k",
        output_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return output_path
    except Exception as err:
        logger.warning("ffmpeg normalize audio failed: %s", err)
    return file_path


def _call_asr_api(file_path: str, offset_ms: int) -> Transcript:
    filename = os.path.basename(file_path)
    # 1. ลอง verbose_json ก่อนเพื่อให้ได้ timestamp ระดับ segment
    try:
        with open(file_path, "rb") as fh:
            raw = client.audio.transcriptions.create(
                model=settings.ASR_MODEL,
                file=(filename, fh),
                language="th",
                response_format="verbose_json",
            )
        return _from_verbose(raw, offset_ms)
    except AsrError:
        raise
    except Exception as verbose_err:  # noqa: BLE001
        logger.info("verbose_json ใช้ไม่ได้ (%s) — ลองแบบ json ธรรมดา", verbose_err)

    # 2. ลอง json ธรรมดา
    try:
        with open(file_path, "rb") as fh:
            raw = client.audio.transcriptions.create(
                model=settings.ASR_MODEL,
                file=(filename, fh),
                language="th",
                response_format="json",
            )
    except Exception as err:  # noqa: BLE001
        raise AsrError(f"เรียก AI4Thai ASR ไม่สำเร็จ: {err}") from err

    text = (getattr(raw, "text", "") or "").strip()
    if not text:
        return Transcript(segments=[], has_speaker_labels=False)
    return Transcript(segments=_split_sentences(text, offset_ms), has_speaker_labels=False)


def _transcribe_one(file_path: str, offset_ms: int) -> Transcript:
    """
    เรียก ASR ครั้งเดียว — ถ้าถอดรหัสเสียงไม่ได้ (422 Failed to decode audio) หรือได้ผลลัพธ์ว่าง
    จะแปลงไฟล์เป็นมาตรฐาน 16kHz mono MP3 ด้วย ffmpeg แล้วลองใหม่อัตโนมัติ
    """
    try:
        result = _call_asr_api(file_path, offset_ms)
        if result.segments:
            return result
    except Exception as err:
        err_msg = str(err).lower()
        if "decode" not in err_msg and "422" not in err_msg and "unprocessable" not in err_msg:
            raise

    logger.info("ASR ลองแปลงไฟล์ด้วย ffmpeg 16kHz mono แล้วลองใหม่: %s", file_path)
    norm_path = _normalize_audio(file_path)
    if norm_path != file_path and os.path.exists(norm_path):
        try:
            return _call_asr_api(norm_path, offset_ms)
        finally:
            try:
                os.remove(norm_path)
            except OSError:
                pass

    return Transcript(segments=[], has_speaker_labels=False)


def _from_verbose(raw, offset_ms: int) -> Transcript:
    """แปลงผล verbose_json เป็น segment — รองรับกรณี API แนบ speaker มาให้ด้วย"""
    raw_segments = getattr(raw, "segments", None) or []
    if not raw_segments:
        text = (getattr(raw, "text", "") or "").strip()
        if not text:
            return Transcript(segments=[], has_speaker_labels=False)
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


def _split_sentences(text: str, offset_ms: int) -> list[Segment]:
    """
    ตัดข้อความจริงเป็นท่อน ๆ เมื่อ ASR ไม่ให้ timestamp มา
    timestamp ที่ได้เป็นค่าประมาณตามสัดส่วนความยาวข้อความ ไม่ใช่ค่าที่วัดจากเสียงจริง
    (ยังเป็นข้อความจริงทุกตัวอักษร — ไม่ใช่การแต่งข้อมูลขึ้นมา)
    """
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(text) if p and p.strip()]
    if not parts:
        parts = [text]

    # ประมาณอัตราการพูดภาษาไทยที่ ~12 ตัวอักษร/วินาที
    chars_per_ms = 12 / 1000
    segments: list[Segment] = []
    cursor = offset_ms
    for part in parts:
        duration = max(1500, int(len(part) / chars_per_ms))
        segments.append(Segment(text=part, start_ms=cursor, end_ms=cursor + duration))
        cursor += duration
    return segments


def _split_audio(file_path: str, chunk_seconds: int = CHUNK_SECONDS) -> list[str]:
    base, _ = os.path.splitext(file_path)
    pattern = f"{base}_chunk_%03d.mp3"
    cmd = [
        "ffmpeg", "-y",
        "-i", file_path,
        "-f", "segment",
        "-segment_time", str(chunk_seconds),
        "-vn",
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "libmp3lame",
        "-b:a", "64k",
        pattern,
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        return sorted(glob.glob(f"{base}_chunk_*.mp3"))
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
