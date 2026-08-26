"""
SARA Public API Router (M7 & v3.0.0-PROD)

Provides:
1. POST /public/summarize & POST /v1/public/summarize:
   Stateless meeting file summarization and pass-through email dispatch for public users and developers.
2. GET & POST /public/resolutions/{token}:
   HMAC-SHA256 magic link response page for passwordless resolution status updates (FR-M7-08).
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import time
from collections import defaultdict
from html import escape
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import read_magic_token
from app.db.models import Person, Resolution, ResolutionStatus
from app.db.session import get_db
from app.mcp_server import MAX_PUBLIC_RECIPIENTS, send_public_summary_email
from app.services.agenda_builder import STATUS_LABEL_TH
from app.services.asr import AsrError, Segment, Transcript, load_transcript_file, transcribe_audio
from app.services.extraction import SegmentView, extract
from app.services.resolutions import change_status, overdue_days
from app.services.templates import MeetingTemplateType, get_template, list_templates
from app.services.thai_format import thai_date

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/public", tags=["Public API"])

# ── In-Memory IP Rate Limiter (10 requests / min / IP) ───────────────────────
_REQUEST_TIMESTAMPS: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_WINDOW_SECONDS = 60
MAX_REQUESTS_PER_WINDOW = 15


def _check_rate_limit(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    timestamps = [ts for ts in _REQUEST_TIMESTAMPS[client_ip] if now - ts < RATE_LIMIT_WINDOW_SECONDS]
    if len(timestamps) >= MAX_REQUESTS_PER_WINDOW:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="เกินขีดจำกัดการเรียกใช้งาน (Rate Limit: 10 requests / minute / IP) กรุณารอสักครู่",
        )
    timestamps.append(now)
    _REQUEST_TIMESTAMPS[client_ip] = timestamps


# ── Stateless Summarize & Dispatch ───────────────────────────────────────────

@router.get("/templates")
async def get_public_templates():
    """Return available meeting summarization templates."""
    return {"status": "success", "templates": list_templates()}


@router.post("/summarize")
async def summarize_public_file(
    request: Request,
    file: UploadFile = File(..., description="Audio (.mp3, .m4a, .wav) or Document (.pdf, .docx, .txt)"),
    template: str = Form("general", description="Template ID: general, marketing, finance, tech_standup"),
    recipients: str | None = Form(None, description="Optional comma-separated or JSON list of email recipients (max 10)"),
    email_subject: str | None = Form(None, description="Custom subject for outbound email dispatch"),
    webhook_url: str | None = Form(None, description="Optional callback URL"),
):
    """
    Stateless public API endpoint for instant file transcription, domain summarization,
    and optional email dispatch.
    """
    _check_rate_limit(request)
    start_time = time.time()

    # 1. Parse & Validate Recipients
    recipient_list: list[str] = []
    if recipients:
        raw_recipients = recipients.strip()
        if raw_recipients.startswith("[") and raw_recipients.endswith("]"):
            try:
                recipient_list = [str(e).strip() for e in json.loads(raw_recipients) if str(e).strip()]
            except json.JSONDecodeError:
                recipient_list = [e.strip() for e in raw_recipients.strip("[]").split(",") if e.strip()]
        else:
            recipient_list = [e.strip() for e in raw_recipients.split(",") if e.strip()]

    if len(recipient_list) > MAX_PUBLIC_RECIPIENTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"จำกัดผู้รับไม่เกิน {MAX_PUBLIC_RECIPIENTS} อีเมลต่อคำขอ (ระบุมา {len(recipient_list)} อีเมล)",
        )

    # Validate email formatting
    email_regex = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    for email in recipient_list:
        if not email_regex.match(email):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"รูปแบบอีเมลไม่ถูกต้อง: {email}",
            )

    # 2. Save temporary upload file
    orig_name = file.filename or "upload.mp3"
    ext = os.path.splitext(orig_name)[1].lower()
    if not ext:
        ext = ".mp3"

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        temp_path = tmp.name
        content = await file.read()
        tmp.write(content)

    try:
        # 3. Transcribe or Parse Document
        is_audio = ext in (".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg", ".wma")
        if is_audio:
            transcript = transcribe_audio(temp_path)
        else:
            transcript = load_transcript_file(temp_path)

        if not transcript.segments:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ไม่สามารถถอดเสียงหรืออ่านข้อความจากไฟล์ที่อัปโหลดได้ (ไฟล์ว่างเปล่าหรือเสียงไม่ชัดเจน)",
            )

        # 4. Process LLM Extraction using Domain Template
        tmpl_def = get_template(template)
        seg_views = [
            SegmentView(
                index=i,
                speaker_label=s.speaker_label,
                start_ms=s.start_ms,
                text=s.text,
            )
            for i, s in enumerate(transcript.segments)
        ]

        extracted = extract(
            segments=seg_views,
            open_resolutions=None,
            meeting_label=orig_name,
            template=template,
        )

        # Compute audio/speaker metadata
        unique_speakers = sorted(list({s.speaker_label for s in transcript.segments if s.speaker_label}))
        max_duration_sec = (transcript.segments[-1].end_ms / 1000.0) if transcript.segments else 0.0

        # Construct response structure
        result_payload = {
            "summary": extracted.summary,
            "key_points": extracted.key_points,
        }
        # Merge raw template fields
        for k, v in (extracted.raw_data or {}).items():
            if k not in result_payload:
                result_payload[k] = v

        # 5. Outbound Email Dispatch if recipients specified
        email_dispatch_meta = {"dispatched": False, "recipient_count": 0}
        if recipient_list:
            subject = email_subject or f"สรุปการประชุม: {orig_name} ({tmpl_def['name']})"
            items = [
                {
                    "text": res.text,
                    "assignees": res.assignee_mention or "-",
                    "due_date": res.due_date or "-",
                    "status": "ข้อตกลงร่วม",
                }
                for res in extracted.new_resolutions
            ]
            dispatch_res = await send_public_summary_email(
                recipients=recipient_list,
                subject=subject,
                summary_text=extracted.summary,
                template_name=tmpl_def["name"],
                items=items,
            )
            email_dispatch_meta = {
                "dispatched": True,
                "recipient_count": dispatch_res.get("dispatched_count", len(recipient_list)),
                "recipients": recipient_list,
            }

        processing_time = round(time.time() - start_time, 2)

        return {
            "status": "success",
            "processing_time_sec": processing_time,
            "template_applied": tmpl_def["id"],
            "template_name": tmpl_def["name"],
            "audio_meta": {
                "duration_sec": max_duration_sec,
                "speakers_detected": len(unique_speakers) or 1,
                "speakers_list": unique_speakers or ["Speaker 1"],
            },
            "transcript": [
                {
                    "speaker": s.speaker_label,
                    "start_ms": s.start_ms,
                    "end_ms": s.end_ms,
                    "text": s.text,
                }
                for s in transcript.segments
            ],
            "result": result_payload,
            "email_dispatch": email_dispatch_meta,
        }

    except AsrError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err
    except Exception as err:
        logger.exception("Stateless summarize error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"เกิดข้อผิดพลาดในการประมวลผลไฟล์: {err}",
        ) from err
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


# ── Direct Email Dispatch ───────────────────────────────────────────────────

class SendEmailPayload(BaseModel):
    recipients: list[str]
    subject: str
    summary_text: str
    template_name: str = "General"
    items: list[dict] | None = None


@router.post("/send-email")
async def send_direct_email(payload: SendEmailPayload):
    """Directly send meeting summary or action items to up to 10 recipients via SMTP."""
    if not payload.recipients:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="กรุณาระบุอีเมลผู้รับอย่างน้อย 1 รายการ",
        )

    clean_recipients = [r.strip() for r in payload.recipients if r.strip()]
    if len(clean_recipients) > MAX_PUBLIC_RECIPIENTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"จำกัดผู้รับไม่เกิน {MAX_PUBLIC_RECIPIENTS} อีเมลต่อครั้ง",
        )

    email_regex = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    for email in clean_recipients:
        if not email_regex.match(email):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"รูปแบบอีเมลไม่ถูกต้อง: {email}",
            )

    try:
        dispatch_res = await send_public_summary_email(
            recipients=clean_recipients,
            subject=payload.subject,
            summary_text=payload.summary_text,
            template_name=payload.template_name,
            items=payload.items or [],
        )
        return {
            "status": "success",
            "dispatched_count": dispatch_res.get("dispatched_count", len(clean_recipients)),
            "recipients": clean_recipients,
            "subject": payload.subject,
        }
    except Exception as err:
        logger.exception("Failed to dispatch email")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ไม่สามารถส่งอีเมลได้: {err}",
        ) from err


# ── Magic Link Resolution Response (FR-M7-08) ────────────────────────────────

ALLOWED = {
    ResolutionStatus.IN_PROGRESS: "กำลังดำเนินการ",
    ResolutionStatus.BLOCKED: "ติดปัญหา ยังดำเนินการต่อไม่ได้",
}

PAGE = """<!DOCTYPE html><html lang="th"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>แจ้งความคืบหน้ามติ · SARA</title>
<style>
 body {{ font-family: "IBM Plex Sans Thai", Tahoma, sans-serif; background:#f4f5f7; color:#131a26;
        margin:0; padding:24px; line-height:1.7; }}
 .card {{ max-width:640px; margin:24px auto; background:#fff; border:1px solid #dfe3ea;
         border-radius:10px; padding:24px; }}
 .quote {{ border-left:3px solid #9a7517; background:#fbf3df; padding:12px 16px; margin:16px 0; }}
 .meta {{ color:#6b7688; font-size:14px; }}
 button {{ background:#1e3a6e; color:#fff; border:0; border-radius:8px; padding:10px 18px;
          font-size:15px; cursor:pointer; margin-right:8px; font-family:inherit; }}
 .ok {{ color:#196b45; font-weight:600; }}
 .err {{ color:#b3261e; font-weight:600; }}
 textarea {{ width:100%; min-height:80px; border:1px solid #c8cfda; border-radius:8px;
            padding:10px; font-family:inherit; font-size:15px; }}
</style></head><body><div class="card">{content}</div></body></html>"""


def _page(content: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(PAGE.format(content=content), status_code=status_code)


def esc(value) -> str:
    return escape(str(value), quote=True)


async def _load(token: str, db: AsyncSession) -> tuple[Resolution, Person]:
    data = read_magic_token(token)
    if not data:
        raise HTTPException(status_code=403, detail="ลิงก์ไม่ถูกต้องหรือหมดอายุแล้ว")
    resolution = await db.get(Resolution, UUID(data["r"]))
    person = await db.get(Person, UUID(data["p"]))
    if resolution is None or person is None:
        raise HTTPException(status_code=404, detail="ไม่พบมติหรือผู้รับผิดชอบตามลิงก์นี้")
    return resolution, person


@router.get("/resolutions/{token}", response_class=HTMLResponse)
async def show(token: str, db: AsyncSession = Depends(get_db)):
    try:
        resolution, person = await _load(token, db)
    except HTTPException as err:
        return _page(f'<p class="err">{esc(err.detail)}</p>', err.status_code)

    od = overdue_days(resolution)
    buttons = "".join(
        f'<button type="submit" name="status" value="{key}">{esc(label)}</button>'
        for key, label in ALLOWED.items()
    )
    return _page(
        f"<h2>แจ้งความคืบหน้ามติ / งานที่ได้รับมอบหมาย</h2>"
        f'<p class="meta">เรียน {esc(person.full_name)}</p>'
        f'<div class="quote">{esc(resolution.text)}</div>'
        f'<p class="meta">{esc(resolution.ref_no)} · กำหนดแล้วเสร็จ {esc(thai_date(resolution.due_date))}'
        f'{f" · เกินกำหนดแล้ว {od} วัน" if od else ""}<br/>'
        f"สถานะปัจจุบัน: {esc(STATUS_LABEL_TH.get(resolution.status, resolution.status))}</p>"
        f'<form method="post" action="{settings.API_V1_STR}/public/resolutions/{esc(token)}">'
        f'<p><textarea name="note" placeholder="รายละเอียดความคืบหน้า (ไม่บังคับ)"></textarea></p>'
        f"<p>{buttons}</p></form>"
        f'<p class="meta">หากดำเนินการแล้วเสร็จ กรุณาแจ้งฝ่ายเลขานุการ '
        f"เนื่องจากการปิดมติที่สมบูรณ์ต้องได้รับการยืนยันจากที่ประชุม</p>"
    )


@router.post("/resolutions/{token}", response_class=HTMLResponse)
async def update(
    token: str,
    status: str = Form(...),
    note: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    if status not in ALLOWED:
        return _page('<p class="err">สถานะที่เลือกไม่ถูกต้อง</p>', 400)
    try:
        resolution, person = await _load(token, db)
    except HTTPException as err:
        return _page(f'<p class="err">{esc(err.detail)}</p>', err.status_code)

    try:
        await change_status(
            db,
            resolution,
            new_status=status,
            actor=person.full_name,
            reason=f"แจ้งผ่าน magic link: {note.strip()}" if note.strip() else "แจ้งผ่าน magic link",
        )
    except ValueError as err:
        return _page(f'<p class="err">{esc(str(err))}</p>', 400)

    label = ALLOWED[status]
    return _page(
        f'<h2 class="ok">บันทึกความคืบหน้าเรียบร้อย</h2>'
        f"<p>ปรับสถานะของมติ <strong>{esc(resolution.ref_no)}</strong> เป็น "
        f"<strong>{esc(label)}</strong> แล้ว</p>"
        f'<p class="meta">ระบบได้บันทึกประวัติและจะนำรายงานนี้ไปประกอบการประชุมครั้งถัดไป</p>'
    )
