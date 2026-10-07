"""การประชุม — อัปโหลด, ดูผล, แก้ไข, ส่งออก และส่งอีเมลสรุป"""

from __future__ import annotations

import logging
import os
from datetime import date
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
)
from fastapi.responses import FileResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, owned_or_404
from app.core.config import settings
from app.db.models import (
    ActionItem,
    Collection,
    Meeting,
    MeetingStatus,
    TranscriptSegment,
    User,
    _now,
)
from app.db.session import get_db
from app.schemas import (
    ActionItemIn,
    ActionItemOut,
    EmailIn,
    EmailOut,
    MeetingOut,
    MeetingPatch,
    SegmentOut,
    SpeakerRename,
)
from app.services import email as email_service
from app.services import vector_store
from app.services.docx_export import build_meeting_docx
from app.services.ratelimit import enforce
from app.services.storage import remove_files, save_upload, source_kind_of
from app.services.templates import get_template, is_known_template
from app.services.thai_format import thai_date
from app.workers.tasks import fresh_pipeline, process_meeting_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meetings", tags=["Meetings"], dependencies=[Depends(current_user)])

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
# ตายตัวแทน mimetypes เพราะ mimetypes อ่านค่าจาก registry ของเครื่อง (Windows ให้ audio/mp3)
AUDIO_MIME = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
}


@router.post("", response_model=MeetingOut, status_code=202)
async def upload_meeting(
    file: UploadFile = File(...),
    collection_id: UUID = Form(...),
    title: str = Form(default="", max_length=200),
    meeting_date: date | None = Form(default=None),
    template: str | None = Form(default=None),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """รับไฟล์เสียงหรือเอกสาร สร้างการประชุม แล้วส่งเข้าคิวประมวลผลเบื้องหลัง"""
    collection = await owned_or_404(db, Collection, collection_id, user, "collection")
    template = template or collection.default_template
    if not is_known_template(template):
        raise HTTPException(status_code=422, detail=f"ไม่รู้จักรูปแบบสรุป {template}")
    kind = source_kind_of(file.filename or "")
    path = await save_upload(file)

    meeting = Meeting(
        user_id=user.id,
        collection_id=collection.id,
        title=title.strip() or (file.filename or "การประชุม"),
        meeting_date=meeting_date,
        template=template,
        source_kind=kind,
        source_filename=file.filename or "",
        file_uri=path,
        status=MeetingStatus.PROCESSING,
        pipeline=fresh_pipeline(),
        processing_started_at=_now(),
        processing_attempts=0,
    )
    db.add(meeting)
    await db.commit()
    await db.refresh(meeting)

    process_meeting_task.delay(str(meeting.id))
    return meeting


@router.get("/{meeting_id}", response_model=MeetingOut)
async def get_meeting(meeting_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return await owned_or_404(db, Meeting, meeting_id, user, "การประชุม")


@router.patch("/{meeting_id}", response_model=MeetingOut)
async def patch_meeting(
    meeting_id: UUID,
    payload: MeetingPatch,
    background: BackgroundTasks,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    meeting = await owned_or_404(db, Meeting, meeting_id, user, "การประชุม")
    changes = payload.model_dump(exclude_unset=True)

    if changes.get("collection_id"):
        target = await owned_or_404(db, Collection, changes["collection_id"], user, "collection")
        await db.execute(
            update(ActionItem).where(ActionItem.meeting_id == meeting.id).values(collection_id=target.id)
        )
        background.add_task(vector_store.move_meeting, meeting.id, target.id)
    elif "collection_id" in changes:
        changes.pop("collection_id")

    for key, value in changes.items():
        setattr(meeting, key, value)
    await db.commit()
    await db.refresh(meeting)
    return meeting


@router.delete("/{meeting_id}", status_code=204)
async def delete_meeting(
    meeting_id: UUID, background: BackgroundTasks, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    meeting = await owned_or_404(db, Meeting, meeting_id, user, "การประชุม")
    await db.delete(meeting)
    await db.commit()
    remove_files([meeting])
    background.add_task(vector_store.delete_meetings, [meeting.id])


@router.post("/{meeting_id}/retry", response_model=MeetingOut, status_code=202)
async def retry(meeting_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """ประมวลผลใหม่ได้เฉพาะการประชุมที่ล้มเหลว — กันไม่ให้ทับ action items ที่ผู้ใช้แก้แล้ว"""
    meeting = await owned_or_404(db, Meeting, meeting_id, user, "การประชุม")
    if meeting.status != MeetingStatus.FAILED:
        raise HTTPException(status_code=409, detail="ประมวลผลใหม่ได้เฉพาะการประชุมที่ล้มเหลว")

    meeting.status = MeetingStatus.PROCESSING
    meeting.pipeline = fresh_pipeline()
    meeting.processing_started_at = _now()
    meeting.processing_attempts = 0
    await db.commit()
    await db.refresh(meeting)
    process_meeting_task.delay(str(meeting.id))
    return meeting


@router.get("/{meeting_id}/audio")
async def get_audio(meeting_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """ไฟล์เสียงต้นฉบับให้หน้าจอเล่นตาม transcript — FileResponse รองรับ Range จึงเลื่อนไปจุดไหนก็ได้"""
    meeting = await owned_or_404(db, Meeting, meeting_id, user, "การประชุม")
    if meeting.source_kind != "audio" or not meeting.file_uri or not os.path.exists(meeting.file_uri):
        raise HTTPException(status_code=404, detail="การประชุมนี้ไม่มีไฟล์เสียง")
    ext = os.path.splitext(meeting.file_uri)[1].lower()
    media_type = AUDIO_MIME.get(ext, "application/octet-stream")
    return FileResponse(meeting.file_uri, media_type=media_type)


@router.get("/{meeting_id}/segments", response_model=list[SegmentOut])
async def get_segments(meeting_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await owned_or_404(db, Meeting, meeting_id, user, "การประชุม")
    rows = await db.execute(
        select(TranscriptSegment).where(TranscriptSegment.meeting_id == meeting_id).order_by(TranscriptSegment.start_ms)
    )
    return rows.scalars().all()


@router.patch("/{meeting_id}/speakers", response_model=list[SegmentOut])
async def rename_speaker(
    meeting_id: UUID,
    payload: SpeakerRename,
    background: BackgroundTasks,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    """ตั้งชื่อให้ผู้พูด เช่น SPEAKER_01 → "คุณมิ้น" มีผลทุกท่อนของผู้พูดนั้นในการประชุมนี้"""
    meeting = await owned_or_404(db, Meeting, meeting_id, user, "การประชุม")
    await db.execute(
        update(TranscriptSegment)
        .where(TranscriptSegment.meeting_id == meeting_id, TranscriptSegment.speaker_label == payload.speaker_label)
        .values(speaker_name=payload.speaker_name.strip())
    )
    await db.commit()
    segments = await get_segments(meeting_id, user, db)
    if meeting.status == MeetingStatus.READY:
        #  ชื่อผู้พูดอยู่ในข้อความที่ทำดัชนีไว้ ต้องทำใหม่ให้ถามว่า "คุณมิ้นพูดเรื่องอะไร" แล้วเจอ
        chunks = vector_store.build_chunks(meeting.id, meeting.summary, segments)
        background.add_task(_reindex_quietly, meeting.user_id, meeting.collection_id, meeting.id, chunks)
    return segments


def _reindex_quietly(user_id: UUID, collection_id: UUID, meeting_id: UUID, chunks: list) -> None:
    try:
        vector_store.index_meeting(user_id, collection_id, meeting_id, chunks)
    except vector_store.VectorStoreError as err:
        logger.warning("ทำดัชนีใหม่หลังเปลี่ยนชื่อผู้พูดไม่สำเร็จ: %s", err)


@router.get("/{meeting_id}/action-items", response_model=list[ActionItemOut])
async def list_action_items(meeting_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await owned_or_404(db, Meeting, meeting_id, user, "การประชุม")
    rows = await db.execute(
        select(ActionItem).where(ActionItem.meeting_id == meeting_id).order_by(ActionItem.created_at)
    )
    return rows.scalars().all()


@router.post("/{meeting_id}/action-items", response_model=ActionItemOut, status_code=201)
async def add_action_item(
    meeting_id: UUID, payload: ActionItemIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    meeting = await owned_or_404(db, Meeting, meeting_id, user, "การประชุม")
    item = ActionItem(user_id=user.id, meeting_id=meeting.id, collection_id=meeting.collection_id, **payload.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def _export_context(db: AsyncSession, meeting: Meeting) -> tuple[Collection, list[ActionItem], list[str]]:
    collection = await db.get(Collection, meeting.collection_id)
    items = (
        await db.execute(select(ActionItem).where(ActionItem.meeting_id == meeting.id).order_by(ActionItem.created_at))
    ).scalars().all()
    names = (
        await db.execute(
            select(TranscriptSegment.speaker_name).where(TranscriptSegment.meeting_id == meeting.id).distinct()
        )
    ).scalars().all()
    return collection, list(items), sorted(n for n in names if n)


def _readable_details(meeting: Meeting) -> dict[str, object]:
    labels = get_template(meeting.template)["detail_labels"]
    return {labels.get(key, key): value for key, value in (meeting.details or {}).items()}


def _require_ready(meeting: Meeting) -> None:
    if meeting.status != MeetingStatus.READY:
        raise HTTPException(status_code=409, detail="การประชุมนี้ยังประมวลผลไม่เสร็จ")


@router.get("/{meeting_id}/export")
async def export_docx(meeting_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    meeting = await owned_or_404(db, Meeting, meeting_id, user, "การประชุม")
    _require_ready(meeting)
    collection, items, speakers = await _export_context(db, meeting)

    content = build_meeting_docx(
        title=meeting.title,
        collection_name=collection.name,
        meeting_date=meeting.meeting_date,
        template_name=get_template(meeting.template)["name"],
        summary=meeting.summary,
        key_points=meeting.key_points or [],
        details=_readable_details(meeting),
        action_items=[{"text": i.text, "owner": i.owner, "due_date": i.due_date, "done": i.done} for i in items],
        speakers=speakers,
    )
    return Response(
        content=content,
        media_type=DOCX_MIME,
        headers={"Content-Disposition": f'attachment; filename="sara-meeting-{meeting.id}.docx"'},
    )


@router.post("/{meeting_id}/email", response_model=EmailOut)
async def email_summary(
    meeting_id: UUID, payload: EmailIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    """ส่งสรุปการประชุมนี้ทางอีเมล — เนื้อหามาจาก DB เท่านั้น ผู้ใช้กำหนดได้แค่ผู้รับและหัวเรื่อง"""
    meeting = await owned_or_404(db, Meeting, meeting_id, user, "การประชุม")
    _require_ready(meeting)

    recipients = sorted({str(r).lower() for r in payload.recipients})
    if len(recipients) > settings.MAX_EMAIL_RECIPIENTS:
        raise HTTPException(status_code=422, detail=f"ส่งได้ไม่เกิน {settings.MAX_EMAIL_RECIPIENTS} อีเมลต่อครั้ง")
    enforce(
        f"email:{user.id}",
        len(recipients),
        settings.EMAIL_RECIPIENTS_PER_DAY,
        86400,
        f"ส่งอีเมลได้ไม่เกิน {settings.EMAIL_RECIPIENTS_PER_DAY} ผู้รับต่อวัน",
    )

    _, items, _ = await _export_context(db, meeting)
    subject = (payload.subject or "").strip() or f"สรุปการประชุม: {meeting.title}"
    rows = [
        {
            "text": i.text,
            "assignees": i.owner,
            "due_date": thai_date(i.due_date) if i.due_date else "",
            "status": "เสร็จแล้ว" if i.done else "ยังค้าง",
        }
        for i in items
    ] if payload.include_action_items else []
    html = email_service.render_summary_html(
        subject=subject,
        summary=meeting.summary,
        key_points=meeting.key_points or [],
        action_items=rows,
        template_name=get_template(meeting.template)["name"],
        sender_name=user.name or user.email,
    )

    sent, failed = [], []
    for address in recipients:
        try:
            email_service.send_html(address, subject, html, reply_to=user.email)
            sent.append(address)
        except email_service.EmailError:
            failed.append(address)
    return EmailOut(sent=sent, failed=failed)
