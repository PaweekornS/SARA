"""
API ที่ไม่ต้องเข้าสู่ระบบ — ให้คนทั่วไปลองสรุปไฟล์ได้ทันทีโดยไม่บันทึกอะไรลง DB

จำกัดโควตาต่อ IP ใน Redis และไม่มีการส่งอีเมลจากทางนี้
(ถ้า deploy หลัง reverse proxy ต้องรัน uvicorn ด้วย --proxy-headers ไม่งั้นทุกคนจะได้ IP ของ proxy)
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status

from app.core.config import settings
from app.services.asr import (
    AsrError,
    Transcript,
    load_transcript_file,
    transcribe_audio,
)
from app.services.extraction import SegmentView, summarize
from app.services.llm import LlmError
from app.services.ratelimit import enforce
from app.services.storage import source_kind_of
from app.services.templates import get_template, list_templates

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/public", tags=["Public"])

MAX_PUBLIC_UPLOAD_MB = 25


@router.get("/templates")
async def templates():
    return list_templates()


def _process(path: str, kind: str, template: str, title: str) -> tuple[Transcript, object]:
    transcript = transcribe_audio(path) if kind == "audio" else load_transcript_file(path)
    if not transcript.segments:
        raise AsrError("ไม่พบเสียงพูดหรือข้อความในไฟล์")
    views = [SegmentView(index=i, speaker_label=s.speaker_label, text=s.text) for i, s in enumerate(transcript.segments)]
    return transcript, summarize(views, template, title)


@router.post("/summarize")
async def summarize_file(
    request: Request,
    file: UploadFile = File(..., description="ไฟล์เสียง (.mp3 .m4a .wav ...) หรือเอกสาร (.txt .docx .pdf .md)"),
    template: str = Form("general"),
):
    client_ip = request.client.host if request.client else "unknown"
    enforce(
        f"public:{client_ip}", 1, settings.PUBLIC_SUMMARIZE_PER_HOUR, 3600,
        "ใช้งานแบบไม่เข้าสู่ระบบครบโควตาชั่วโมงนี้แล้ว — เข้าสู่ระบบเพื่อใช้งานต่อและบันทึกผลไว้ได้",
    )
    kind = source_kind_of(file.filename or "")
    tmpl = get_template(template)

    content = await file.read(MAX_PUBLIC_UPLOAD_MB * 1024 * 1024 + 1)
    if len(content) > MAX_PUBLIC_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"แบบไม่เข้าสู่ระบบรับไฟล์ได้ไม่เกิน {MAX_PUBLIC_UPLOAD_MB} MB")
    if not content:
        raise HTTPException(status_code=422, detail="ไฟล์ที่อัปโหลดว่างเปล่า")

    suffix = os.path.splitext(file.filename or "")[1].lower()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        path = tmp.name

    try:
        #  ASR และ LLM เป็นงาน blocking ยาวหลายนาที ห้ามรันบน event loop ตรง ๆ
        transcript, result = await asyncio.to_thread(_process, path, kind, tmpl["id"], file.filename or "")
    except (AsrError, LlmError) as err:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(err)) from err
    finally:
        try:
            os.remove(path)
        except OSError:
            pass

    return {
        "template": {"id": tmpl["id"], "name": tmpl["name"], "detail_labels": tmpl["detail_labels"]},
        "summary": result.summary,
        "key_points": result.key_points,
        "details": result.details,
        "action_items": [
            {"text": a.text, "owner": a.owner, "due_date": a.due_date} for a in result.action_items
        ],
        "transcript": [
            {"speaker": s.speaker_label, "start_ms": s.start_ms, "end_ms": s.end_ms, "text": s.text}
            for s in transcript.segments
        ],
    }
