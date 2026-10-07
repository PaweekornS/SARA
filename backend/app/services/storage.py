"""เก็บและลบไฟล์ที่ผู้ใช้อัปโหลด (shared volume ระหว่าง API กับ worker)"""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import Iterable

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.db.models import Meeting

logger = logging.getLogger(__name__)

ALLOWED_AUDIO = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
ALLOWED_TRANSCRIPT = {".txt", ".docx", ".md", ".pdf"}
MAX_UPLOAD_BYTES = settings.MAX_UPLOAD_MB * 1024 * 1024


def source_kind_of(filename: str) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext in ALLOWED_AUDIO:
        return "audio"
    if ext in ALLOWED_TRANSCRIPT:
        return "transcript"
    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail=f"ไม่รองรับไฟล์นามสกุล {ext or '(ไม่ทราบ)'}",
    )


async def save_upload(file: UploadFile) -> str:
    """เขียนไฟล์ลงดิสก์ทีละก้อน ถ้าใหญ่เกินหรือว่างเปล่าจะลบทิ้งแล้วตอบ error"""
    ext = os.path.splitext(file.filename or "")[1].lower()
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    target = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4().hex}{ext}")

    size = 0
    with open(target, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                break
            out.write(chunk)

    if size > MAX_UPLOAD_BYTES:
        os.remove(target)
        raise HTTPException(status_code=413, detail=f"ไฟล์ใหญ่เกิน {settings.MAX_UPLOAD_MB} MB")
    if size == 0:
        os.remove(target)
        raise HTTPException(status_code=422, detail="ไฟล์ที่อัปโหลดว่างเปล่า")
    return target


def remove_files(meetings: Iterable[Meeting]) -> None:
    for meeting in meetings:
        if meeting.file_uri and os.path.exists(meeting.file_uri):
            try:
                os.remove(meeting.file_uri)
            except OSError as err:
                logger.warning("ลบไฟล์ %s ไม่สำเร็จ: %s", meeting.file_uri, err)
