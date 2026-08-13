"""M2 · M3 · M9 — รับไฟล์ ประมวลผล ตรวจทาน และรับรองรายงานการประชุม"""

from __future__ import annotations

import os
import shutil
import uuid
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_actor, current_org
from app.api.serializers import resolutions_out
from app.core.config import settings
from app.db.models import (
    Meeting,
    MeetingSeries,
    MeetingStatus,
    Organization,
    Person,
    PersonAlias,
    Proposal,
    Resolution,
    ResolutionAssignee,
    ResolutionLink,
    ResolutionStatus,
    TranscriptSegment,
)
from app.db.session import get_db
from app.schemas import (
    Ack,
    MeetingIn,
    MeetingOut,
    ProposalDecision,
    ProposalOut,
    SegmentOut,
    SpeakerPatch,
    UploadAccepted,
)
from app.services.audio_file import audio_media_type, resolve_audio_path
from app.services.docx_export import build_minutes_docx
from app.services.resolutions import (
    audit,
    change_status,
    get_or_404,
    next_ref_no,
    set_assignees,
    utcnow,
)
from app.services.thai_format import fiscal_year_of
from app.workers.tasks import process_meeting_task

router = APIRouter(prefix="/meetings", tags=["Meetings"])

ALLOWED_AUDIO = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
ALLOWED_TRANSCRIPT = {".txt", ".docx", ".doc", ".md"}
MAX_UPLOAD_BYTES = settings.MAX_UPLOAD_MB * 1024 * 1024

INITIAL_PIPELINE = [
    {"stage": "upload", "state": "pending", "detail": "รับไฟล์และตรวจความสมบูรณ์"},
    {"stage": "asr", "state": "pending", "detail": "ถอดเสียงด้วย AI4Thai ASR"},
    {"stage": "diarize", "state": "pending", "detail": "แยกผู้พูด"},
    {"stage": "extract", "state": "pending", "detail": "สกัดมติและจับคู่กับมติเดิมของชุดการประชุม"},
    {"stage": "done", "state": "pending", "detail": "พร้อมให้ตรวจทาน"},
]


@router.post("", response_model=MeetingOut, status_code=201)
async def create_meeting(payload: MeetingIn, db: AsyncSession = Depends(get_db)):
    """FR-M1-02 ผูก Meeting เข้ากับ Series พร้อมระบุครั้งที่และวันที่ประชุม"""
    series = await get_or_404(db, MeetingSeries, payload.series_id, "ชุดการประชุม")

    dupe = (
        await db.execute(
            select(Meeting).where(
                Meeting.series_id == series.id, Meeting.sequence_no == payload.sequence_no
            )
        )
    ).scalars().first()
    if dupe:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"มีการประชุมครั้งที่ {payload.sequence_no} ในชุดนี้อยู่แล้ว",
        )

    meeting = Meeting(
        series_id=series.id,
        sequence_no=payload.sequence_no,
        fiscal_year=fiscal_year_of(payload.meeting_date),
        meeting_date=payload.meeting_date,
        title=payload.title or f"การประชุมครั้งที่ {payload.sequence_no}",
        source_kind=payload.source_kind,
        status=MeetingStatus.DRAFT,
        pipeline=[dict(step) for step in INITIAL_PIPELINE],
    )
    db.add(meeting)
    await db.commit()
    await db.refresh(meeting)
    return meeting


@router.post("/{meeting_id}/upload", response_model=UploadAccepted, status_code=202)
async def upload(
    meeting_id: UUID,
    file: UploadFile = File(...),
    simulate_asr_failure: bool = Form(default=False),
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(current_org),
    actor: str = Depends(current_actor),
):
    """FR-M2-01, 02 — รับไฟล์เสียงหรือ transcript แล้วส่งเข้าคิวประมวลผลเบื้องหลัง"""
    meeting = await get_or_404(db, Meeting, meeting_id, "การประชุม")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_AUDIO | ALLOWED_TRANSCRIPT:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"ไม่รองรับไฟล์นามสกุล {ext or '(ไม่ทราบ)'}",
        )

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    target = os.path.join(settings.UPLOAD_DIR, f"{meeting_id}_{uuid.uuid4().hex[:8]}{ext}")

    size = 0
    with open(target, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                os.remove(target)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"ไฟล์ใหญ่เกิน {settings.MAX_UPLOAD_MB} MB",
                )
            out.write(chunk)

    if size == 0:
        os.remove(target)
        raise HTTPException(status_code=422, detail="ไฟล์ที่อัปโหลดว่างเปล่า")

    meeting.audio_uri = target
    meeting.source_kind = "audio" if ext in ALLOWED_AUDIO else "transcript"
    meeting.status = MeetingStatus.PROCESSING
    meeting.pipeline = [dict(step) for step in INITIAL_PIPELINE]
    await audit(db, org.id, actor, "upload_meeting", "meeting", meeting.id, file.filename or "")
    await db.commit()

    process_meeting_task.delay(str(meeting.id), target, bool(simulate_asr_failure))

    return UploadAccepted(
        meeting_id=meeting.id,
        status=MeetingStatus.PROCESSING,
        message="รับไฟล์แล้ว กำลังประมวลผลเบื้องหลัง",
    )


@router.get("/{meeting_id}", response_model=MeetingOut)
async def get_meeting(meeting_id: UUID, db: AsyncSession = Depends(get_db)):
    return await get_or_404(db, Meeting, meeting_id, "การประชุม")


@router.get("/{meeting_id}/status", response_model=MeetingOut)
async def meeting_status(meeting_id: UUID, db: AsyncSession = Depends(get_db)):
    """FR-M2-03 สถานะแบบเป็นขั้น ให้ frontend poll ระหว่างประมวลผล"""
    return await get_or_404(db, Meeting, meeting_id, "การประชุม")


@router.post("/{meeting_id}/retry", response_model=UploadAccepted, status_code=202)
async def retry(meeting_id: UUID, db: AsyncSession = Depends(get_db)):
    """FR-M2-05 retry ด้วยมือเมื่อ job ล้มเหลว"""
    meeting = await get_or_404(db, Meeting, meeting_id, "การประชุม")
    if not meeting.audio_uri or not os.path.exists(meeting.audio_uri):
        raise HTTPException(status_code=409, detail="ไม่พบไฟล์ต้นฉบับของการประชุมนี้แล้ว กรุณาอัปโหลดใหม่")

    meeting.status = MeetingStatus.PROCESSING
    meeting.pipeline = [dict(step) for step in INITIAL_PIPELINE]
    await db.commit()

    process_meeting_task.delay(str(meeting.id), meeting.audio_uri, False)
    return UploadAccepted(meeting_id=meeting.id, status=MeetingStatus.PROCESSING, message="เริ่มประมวลผลใหม่")


@router.get("/{meeting_id}/transcript", response_model=list[SegmentOut])
async def transcript(meeting_id: UUID, db: AsyncSession = Depends(get_db)):
    rows = await db.execute(
        select(TranscriptSegment)
        .where(TranscriptSegment.meeting_id == meeting_id)
        .order_by(TranscriptSegment.start_ms)
    )
    return list(rows.scalars().all())


@router.get("/{meeting_id}/audio")
async def audio(meeting_id: UUID, db: AsyncSession = Depends(get_db)):
    """ส่งไฟล์เสียงต้นฉบับ ให้หน้าตรวจทานกดฟังย้อนตาม timestamp ของแต่ละท่อนได้

    FileResponse ของ Starlette ตอบ Range/206 ให้เอง จึงกระโดดไปวินาทีที่อ้างอิงได้
    โดยไม่ต้องโหลดไฟล์ทั้งก้อน
    ยังไม่มีการยืนยันตัวตน เหมือน endpoint อื่นทั้งระบบ — ใครมี meeting_id ก็ฟังได้
    """
    meeting = await get_or_404(db, Meeting, meeting_id, "การประชุม")
    path = resolve_audio_path(meeting.audio_uri, settings.UPLOAD_DIR)
    if path is None:
        raise HTTPException(status_code=404, detail="ไม่พบไฟล์เสียงของการประชุมนี้")
    return FileResponse(path, media_type=audio_media_type(path))


@router.patch("/{meeting_id}/speakers", response_model=Ack)
async def map_speaker(
    meeting_id: UUID,
    payload: SpeakerPatch,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(current_org),
    actor: str = Depends(current_actor),
):
    """FR-M2-07 · FR-M3-04 — จับคู่ speaker label เข้ากับบุคคลจริง แล้วจำ alias ไว้ถาวร"""
    await get_or_404(db, Meeting, meeting_id, "การประชุม")

    rows = await db.execute(
        select(TranscriptSegment).where(
            TranscriptSegment.meeting_id == meeting_id,
            TranscriptSegment.speaker_label == payload.speaker_label,
        )
    )
    segments = list(rows.scalars().all())
    for segment in segments:
        segment.person_id = payload.person_id

    if payload.person_id and payload.save_alias:
        await _remember_alias(db, payload.person_id, payload.save_alias, "confirmed_extraction", 0.9)
        await audit(
            db, org.id, actor, "confirm_alias", "person", payload.person_id,
            f'ยืนยัน "{payload.save_alias}" จากการประชุม',
        )

    await db.commit()
    return Ack(detail=f"ปรับผู้พูด {len(segments)} ท่อนแล้ว")


# ── หน้าตรวจทาน (M9) ────────────────────────────────────────────────────

@router.get("/{meeting_id}/review")
async def review(meeting_id: UUID, db: AsyncSession = Depends(get_db)):
    """FR-M9-01 ชุดข้อมูลสำหรับหน้า review รวมทุกอย่างที่ต้องตรวจไว้ในครั้งเดียว"""
    meeting = await get_or_404(db, Meeting, meeting_id, "การประชุม")

    segments = list(
        (
            await db.execute(
                select(TranscriptSegment)
                .where(TranscriptSegment.meeting_id == meeting_id)
                .order_by(TranscriptSegment.start_ms)
            )
        ).scalars().all()
    )
    proposals = list(
        (await db.execute(select(Proposal).where(Proposal.meeting_id == meeting_id))).scalars().all()
    )
    created = list(
        (
            await db.execute(select(Resolution).where(Resolution.origin_meeting_id == meeting_id))
        ).scalars().all()
    )
    closed = list(
        (
            await db.execute(select(Resolution).where(Resolution.closed_meeting_id == meeting_id))
        ).scalars().all()
    )

    unmapped = sorted({s.speaker_label for s in segments if s.person_id is None})
    pending = [p for p in proposals if p.decision == "pending"]

    return {
        "meeting": MeetingOut.model_validate(meeting),
        "segments": [SegmentOut.model_validate(s) for s in segments],
        "proposals": [ProposalOut.model_validate(p) for p in proposals],
        "created_resolutions": await resolutions_out(db, created),
        "closed_resolutions": await resolutions_out(db, closed),
        "blockers": {
            "pending_proposals": len(pending),
            "unmapped_speakers": unmapped,
        },
        "can_approve": meeting.status not in (MeetingStatus.PROCESSING, MeetingStatus.FAILED)
        and not pending
        and not unmapped,
    }


@router.post("/{meeting_id}/proposals/{proposal_id}", response_model=Ack)
async def decide_proposal(
    meeting_id: UUID,
    proposal_id: UUID,
    payload: ProposalDecision,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(current_org),
    actor: str = Depends(current_actor),
):
    """
    ตัดสินข้อเสนอของระบบ — จุดที่ human-in-the-loop เกิดขึ้นจริง
    ไม่มีทางอื่นที่ทำให้ข้อเสนอมีผลได้นอกจากผ่าน endpoint นี้
    """
    meeting = await get_or_404(db, Meeting, meeting_id, "การประชุม")
    proposal = await get_or_404(db, Proposal, proposal_id, "ข้อเสนอ")
    if proposal.meeting_id != meeting.id:
        raise HTTPException(status_code=400, detail="ข้อเสนอนี้ไม่ได้อยู่ในการประชุมที่ระบุ")
    if proposal.decision != "pending":
        raise HTTPException(status_code=409, detail="ข้อเสนอนี้ถูกตัดสินไปแล้ว")

    if payload.decision == "rejected":
        proposal.decision = "rejected"
        await db.commit()
        return Ack(detail="ปฏิเสธข้อเสนอแล้ว")

    if proposal.kind == "status_change" and proposal.resolution_id and proposal.proposed_status:
        resolution = await get_or_404(db, Resolution, proposal.resolution_id, "มติ")
        await change_status(
            db,
            resolution,
            proposal.proposed_status,
            reason="ยืนยันจากรายงานในที่ประชุม",
            actor=actor,
            meeting_id=meeting.id,
            evidence=proposal.evidence_text,
            evidence_start_ms=proposal.evidence_start_ms,
            segment_id=proposal.segment_id,
        )

    elif proposal.kind == "new_resolution":
        count = len(
            (
                await db.execute(select(Resolution).where(Resolution.origin_meeting_id == meeting.id))
            ).scalars().all()
        )
        resolution = Resolution(
            series_id=meeting.series_id,
            ref_no=next_ref_no(meeting.sequence_no, meeting.fiscal_year, count + 1),
            origin_meeting_id=meeting.id,
            origin_segment_id=proposal.segment_id,
            origin_agenda_item=f"วาระที่ 4.{count + 1}",
            text=(payload.text or proposal.title).strip(),
            status=ResolutionStatus.PROPOSED,
            due_date=payload.due_date,
            original_due_date=payload.due_date,
            extraction_confidence=proposal.confidence,
        )
        db.add(resolution)
        await db.flush()
        if payload.assignee_ids:
            await set_assignees(db, resolution, payload.assignee_ids)
        db.add(
            ResolutionLink(
                resolution_id=resolution.id,
                meeting_id=meeting.id,
                link_type="created",
                segment_id=proposal.segment_id,
                evidence_text=proposal.evidence_text,
                evidence_start_ms=proposal.evidence_start_ms,
                confidence=proposal.confidence,
            )
        )

    elif proposal.kind == "speaker_identity":
        if not payload.person_id:
            raise HTTPException(status_code=422, detail="ต้องระบุว่าผู้พูดคนนี้คือใครก่อนยืนยัน")
        rows = await db.execute(
            select(TranscriptSegment).where(
                TranscriptSegment.meeting_id == meeting.id,
                TranscriptSegment.speaker_label == proposal.speaker_label,
            )
        )
        for segment in rows.scalars().all():
            segment.person_id = payload.person_id
        if payload.save_alias:
            await _remember_alias(
                db, payload.person_id, payload.save_alias, "confirmed_extraction", proposal.confidence
            )

    proposal.decision = "accepted"
    await audit(db, org.id, actor, "accept_proposal", "proposal", proposal.id, proposal.kind)
    await db.commit()
    return Ack(detail="ยืนยันข้อเสนอแล้ว")


@router.post("/{meeting_id}/approve", response_model=MeetingOut)
async def approve(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(current_org),
    actor: str = Depends(current_actor),
):
    """
    FR-M9-03 รับรองรายงานการประชุม
    เป็นจุดเดียวที่ระบบเปลี่ยนสถานะมติเองได้ คือ proposed → confirmed (§4.1)
    """
    meeting = await get_or_404(db, Meeting, meeting_id, "การประชุม")

    if meeting.status in (MeetingStatus.PROCESSING, MeetingStatus.FAILED):
        raise HTTPException(status_code=409, detail="ยังประมวลผลไม่เสร็จหรือประมวลผลไม่สำเร็จ")

    pending = (
        await db.execute(
            select(Proposal).where(Proposal.meeting_id == meeting.id, Proposal.decision == "pending")
        )
    ).scalars().all()
    if pending:
        raise HTTPException(
            status_code=409, detail=f"ยังมีข้อเสนอรอการตรวจอีก {len(pending)} รายการ"
        )

    unmapped = (
        await db.execute(
            select(TranscriptSegment.speaker_label)
            .where(TranscriptSegment.meeting_id == meeting.id, TranscriptSegment.person_id.is_(None))
            .distinct()
        )
    ).scalars().all()
    if unmapped:
        raise HTTPException(
            status_code=409, detail=f"ยังมีผู้พูดที่ยังไม่ได้ระบุตัวอีก {len(unmapped)} คน"
        )

    meeting.status = MeetingStatus.APPROVED
    meeting.approved_at = utcnow()
    meeting.approved_by = actor

    proposed = (
        await db.execute(
            select(Resolution).where(
                Resolution.origin_meeting_id == meeting.id,
                Resolution.status == ResolutionStatus.PROPOSED,
            )
        )
    ).scalars().all()
    for resolution in proposed:
        await change_status(
            db,
            resolution,
            ResolutionStatus.CONFIRMED,
            reason="ที่ประชุมรับรองรายงานการประชุม",
            actor=actor,
            meeting_id=meeting.id,
            system_initiated=True,
        )

    await audit(
        db, org.id, actor, "meeting_approved", "meeting", meeting.id,
        f"รับรองรายงานครั้งที่ {meeting.sequence_no}/{meeting.fiscal_year}",
    )
    await db.commit()
    await db.refresh(meeting)
    return meeting


@router.get("/{meeting_id}/export")
async def export_minutes(meeting_id: UUID, format: str = "docx", db: AsyncSession = Depends(get_db)):
    """FR-M5-05 รายงานการประชุมฉบับเต็มเป็น .docx ตาม template"""
    if format != "docx":
        raise HTTPException(status_code=400, detail="รองรับเฉพาะ format=docx")

    meeting = await get_or_404(db, Meeting, meeting_id, "การประชุม")
    series = await get_or_404(db, MeetingSeries, meeting.series_id, "ชุดการประชุม")

    segments = list(
        (
            await db.execute(
                select(TranscriptSegment)
                .where(TranscriptSegment.meeting_id == meeting_id)
                .order_by(TranscriptSegment.start_ms)
            )
        ).scalars().all()
    )
    people = {
        p.id: p for p in (await db.execute(select(Person))).scalars().all()
    }
    resolutions = list(
        (
            await db.execute(select(Resolution).where(Resolution.origin_meeting_id == meeting_id))
        ).scalars().all()
    )

    attendee_ids = list(dict.fromkeys(s.person_id for s in segments if s.person_id))
    attendees = [
        f"{people[pid].full_name} {people[pid].position}".strip() for pid in attendee_ids if pid in people
    ]

    resolution_rows = []
    for r in resolutions:
        names = (
            await db.execute(
                select(Person)
                .join(ResolutionAssignee, ResolutionAssignee.person_id == Person.id)
                .where(ResolutionAssignee.resolution_id == r.id)
            )
        ).scalars().all()
        resolution_rows.append(
            {
                "title": r.text[:60],
                "text": r.text,
                "assignees": ", ".join(p.full_name for p in names),
                "due_date": r.due_date,
            }
        )

    blob = build_minutes_docx(
        series_name=series.name,
        fiscal_year=meeting.fiscal_year,
        sequence_no=meeting.sequence_no,
        meeting_date=meeting.meeting_date,
        attendees=attendees,
        resolutions=resolution_rows,
        segments=[
            {
                "start_ms": s.start_ms,
                "speaker": people[s.person_id].full_name if s.person_id in people else s.speaker_label,
                "text": s.text,
            }
            for s in segments
        ],
        template_path=settings.MINUTES_TEMPLATE_PATH or None,
    )

    filename = f"minutes-{meeting.sequence_no}-{meeting.fiscal_year}.docx"
    return Response(
        content=blob,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


async def _remember_alias(
    db: AsyncSession, person_id: UUID, alias: str, source: str, confidence: float
) -> None:
    alias = alias.strip()
    if not alias:
        return
    exists = (
        await db.execute(
            select(PersonAlias).where(PersonAlias.person_id == person_id, PersonAlias.alias == alias)
        )
    ).scalars().first()
    if exists:
        return
    db.add(PersonAlias(person_id=person_id, alias=alias, source=source, confidence=confidence))
