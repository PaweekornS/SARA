"""M2 · M3 · M9 — รับไฟล์ ประมวลผล ตรวจทาน และรับรองรายงานการประชุม"""

from __future__ import annotations

import os
import shutil
import uuid
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_actor, current_org
from app.api.serializers import resolutions_out
from app.core.config import settings
from app.db.models import (
    ActionStatus,
    Meeting,
    MeetingSeries,
    MeetingStatus,
    Organization,
    OutboundAction,
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
from app.services.agenda_builder import STATUS_LABEL_TH
from app.services.docx_export import build_minutes_docx
from app.services.resolutions import (
    audit,
    change_status,
    get_or_404,
    next_ref_no,
    set_assignees,
    utcnow,
)
from app.services.thai_format import fiscal_year_of, thai_date
from app.workers.tasks import process_meeting_task

# ── Global Variables & Constants ─────────────────────────────────────────────

router = APIRouter(prefix="/meetings", tags=["Meetings"])

ALLOWED_AUDIO = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
ALLOWED_TRANSCRIPT = {".txt", ".docx", ".doc", ".md"}
MAX_UPLOAD_BYTES = settings.MAX_UPLOAD_MB * 1024 * 1024

INITIAL_PIPELINE = [
    {"stage": "upload", "state": "pending", "detail": "รับไฟล์และตรวจความสมบูรณ์"},
    {"stage": "asr", "state": "pending", "detail": "ถอดเสียงด้วย AI4Thai ASR"},
    {"stage": "extract", "state": "pending", "detail": "สรุปเนื้อหาและสกัดมติ"},
    {"stage": "done", "state": "pending", "detail": "พร้อมให้ตรวจทาน"},
]


# ── Functions & Route Handlers ───────────────────────────────────────────────

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
                    status_code=413,
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

    return UploadAccepted(
        meeting_id=meeting.id,
        status=MeetingStatus.PROCESSING,
        message="เริ่มประมวลผลใหม่อีกครั้ง",
    )


@router.get("/{meeting_id}/segments", response_model=list[SegmentOut])
async def get_segments(meeting_id: UUID, db: AsyncSession = Depends(get_db)):
    await get_or_404(db, Meeting, meeting_id, "การประชุม")
    rows = await db.execute(
        select(TranscriptSegment)
        .where(TranscriptSegment.meeting_id == meeting_id)
        .order_by(TranscriptSegment.start_ms)
    )
    return list(rows.scalars().all())


@router.patch("/{meeting_id}/speakers", response_model=Ack)
async def patch_speaker(
    meeting_id: UUID,
    payload: SpeakerPatch,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(current_org),
    actor: str = Depends(current_actor),
):
    """
    FR-M3-04 ระบุตัวตนผู้พูดแทน label SPEAKER_XX
    และเพิ่ม alias ถาวรลงทะเบียนบุคคลถ้าผู้ใช้ติ๊กให้จำ (FR-M3-05)
    """
    meeting = await get_or_404(db, Meeting, meeting_id, "การประชุม")

    person = None
    if payload.person_id:
        person = await get_or_404(db, Person, payload.person_id, "บุคคล")

    segments = (
        await db.execute(
            select(TranscriptSegment).where(
                TranscriptSegment.meeting_id == meeting.id,
                TranscriptSegment.speaker_label == payload.speaker_label,
            )
        )
    ).scalars().all()

    for seg in segments:
        seg.person_id = payload.person_id
        seg.speaker_name = person.full_name if person else None

    if payload.save_alias and payload.person_id:
        alias_clean = payload.save_alias.strip()
        if alias_clean:
            dupe = (
                await db.execute(
                    select(PersonAlias).where(
                        PersonAlias.org_id == org.id,
                        PersonAlias.person_id == payload.person_id,
                        PersonAlias.alias == alias_clean,
                    )
                )
            ).scalars().first()
            if not dupe:
                db.add(
                    PersonAlias(
                        org_id=org.id,
                        person_id=payload.person_id,
                        alias=alias_clean,
                        source="manual",
                        confidence=1.0,
                    )
                )

    await audit(
        db,
        org.id,
        actor,
        "assign_speaker",
        "meeting",
        meeting.id,
        f"{payload.speaker_label} -> {person.full_name if person else 'None'}",
    )
    await db.commit()
    return Ack()


@router.get("/{meeting_id}/proposals", response_model=list[ProposalOut])
async def get_proposals(meeting_id: UUID, db: AsyncSession = Depends(get_db)):
    await get_or_404(db, Meeting, meeting_id, "การประชุม")
    rows = await db.execute(
        select(Proposal).where(Proposal.meeting_id == meeting_id).order_by(Proposal.created_at)
    )
    return list(rows.scalars().all())


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
    FR-M3-03 มนุษย์ตัดสินใจว่าจะเอาตามที่ AI เสนอไหม

    ถ้ากดรับ:
      - proposal เปลี่ยนเป็น approved
      - สร้าง Resolution ใหม่จริง / เปลี่ยนสถานะมติเดิมจริง / ผูก speaker จริง
    ถ้าปฏิเสธ:
      - proposal เปลี่ยนเป็น rejected ไม่เกิดผลข้างเคียงใด ๆ ต่อ DB (FR-M3-03)
    """
    meeting = await get_or_404(db, Meeting, meeting_id, "การประชุม")
    proposal = await get_or_404(db, Proposal, proposal_id, "ข้อเสนอของระบบ")
    if proposal.meeting_id != meeting.id:
        raise HTTPException(status_code=400, detail="proposal นี้ไม่ได้มาจากการประชุมนี้")
    if proposal.status != "pending":
        raise HTTPException(status_code=409, detail=f"proposal นี้ถูกตัดสินไปแล้ว ({proposal.status})")

    proposal.status = payload.action
    proposal.decided_by = actor
    proposal.decided_at = utcnow()
    proposal.decision_reason = payload.override_reason

    data = dict(proposal.payload or {})

    if payload.action == "approved":
        ptype = proposal.proposal_type

        if ptype == "new_resolution":
            res_count = (
                await db.execute(
                    select(Resolution).where(Resolution.origin_meeting_id == meeting.id)
                )
            ).scalars().all()
            item_no = len(res_count) + 1
            ref = next_ref_no(meeting.sequence_no, meeting.fiscal_year, item_no)
            res = Resolution(
                series_id=meeting.series_id,
                origin_meeting_id=meeting.id,
                ref_no=ref,
                text=payload.override_text or data.get("text") or "",
                category=data.get("category") or "other",
                status=ResolutionStatus.PROPOSED,
                due_date=date.fromisoformat(payload.override_due_date) if payload.override_due_date else None,
                confidence_score=proposal.confidence_score,
            )
            db.add(res)
            await db.flush()

            assignee_ids = payload.override_assignee_ids
            if assignee_ids is None and data.get("suggested_person_id"):
                assignee_ids = [UUID(data["suggested_person_id"])]
            if assignee_ids:
                await set_assignees(db, res, assignee_ids)

            db.add(
                ResolutionLink(
                    resolution_id=res.id,
                    meeting_id=meeting.id,
                    link_type=LinkType.CREATED,
                    segment_id=UUID(data["segment_id"]) if data.get("segment_id") else None,
                    evidence_text=data.get("text") or "",
                    evidence_start_ms=data.get("start_ms"),
                    confidence=proposal.confidence_score,
                )
            )

        elif ptype == "update_resolution":
            target_id = proposal.target_resolution_id
            if not target_id:
                raise HTTPException(status_code=400, detail="proposal ประเภทนี้ต้องมี target_resolution_id")
            target = await get_or_404(db, Resolution, target_id, "มติเป้าหมาย")
            new_status = payload.override_status or data.get("proposed_status") or "in_progress"
            await change_status(
                db,
                target,
                new_status=new_status,
                reason=payload.override_reason or data.get("evidence") or "ยืนยันจาก proposal",
                actor=actor,
                meeting_id=meeting.id,
                evidence=data.get("evidence"),
                evidence_start_ms=data.get("start_ms"),
                segment_id=UUID(data["segment_id"]) if data.get("segment_id") else None,
            )

        elif ptype == "speaker_alias":
            person_id = payload.override_assignee_ids[0] if payload.override_assignee_ids else None
            if not person_id and data.get("suggested_person_id"):
                person_id = UUID(data["suggested_person_id"])
            if person_id and data.get("speaker_label"):
                await patch_speaker(
                    meeting.id,
                    SpeakerPatch(
                        speaker_label=data["speaker_label"],
                        person_id=person_id,
                        save_alias=data.get("name_mention"),
                    ),
                    db=db,
                    org=org,
                    actor=actor,
                )

    await audit(
        db,
        org.id,
        actor,
        f"decide_proposal_{payload.action}",
        "proposal",
        proposal.id,
        payload.override_reason or "",
    )
    await db.commit()
    return Ack()


@router.post("/{meeting_id}/approve", response_model=MeetingOut)
async def approve_meeting(
    meeting_id: UUID,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(current_org),
    actor: str = Depends(current_actor),
):
    """
    FR-M9-01 ถึง 04 การรับรองรายงานการประชุม (จุดตัดสำคัญของกระบวนการ)

    เมื่อรับรอง:
      1. มติสถานะ proposed ทั้งหมดใน meeting นี้ กลายเป็น confirmed ทันที (FR-M9-02)
      2. meeting เปลี่ยนสถานะเป็น approved
      3. ปลดล็อกให้สร้างร่างวาระครั้งถัดไปและส่งอีเมลแจ้งเตือนได้ (FR-M9-03)
      4. บันทึกลง AuditLog (FR-M9-04)
    """
    meeting = await get_or_404(db, Meeting, meeting_id, "การประชุม")

    proposed_res = (
        await db.execute(
            select(Resolution).where(
                Resolution.origin_meeting_id == meeting.id,
                Resolution.status == ResolutionStatus.PROPOSED,
            )
        )
    ).scalars().all()

    for res in proposed_res:
        await change_status(
            db,
            res,
            ResolutionStatus.CONFIRMED,
            reason=f"รับรองรายงานการประชุมครั้งที่ {meeting.sequence_no}/{meeting.fiscal_year}",
            actor=actor,
            meeting_id=meeting.id,
        )

    meeting.status = MeetingStatus.APPROVED
    meeting.approved_by = actor
    meeting.approved_at = utcnow()

    # ── สร้างอีเมลสรุปสาระสำคัญและมติเข้าคิวส่งออก (Outbound Action) ─────────
    series = await db.get(MeetingSeries, meeting.series_id)
    series_name = series.name if series else "การประชุม"

    meeting_resolutions = (
        await db.execute(
            select(Resolution)
            .where(Resolution.origin_meeting_id == meeting.id)
            .order_by(Resolution.ref_no)
        )
    ).scalars().all()

    res_rows = []
    for r in meeting_resolutions:
        assignees = (
            await db.execute(
                select(Person)
                .join(ResolutionAssignee, ResolutionAssignee.person_id == Person.id)
                .where(ResolutionAssignee.resolution_id == r.id)
            )
        ).scalars().all()
        res_rows.append({
            "text": r.text,
            "assignees": ", ".join(p.full_name for p in assignees) or "-",
            "due_date": thai_date(r.due_date) if r.due_date else "-",
            "status": STATUS_LABEL_TH.get(r.status, r.status),
        })

    summary_text = getattr(meeting, "summary", None) or meeting.title or "สรุปสาระสำคัญจากการประชุม"
    body_text = (
        f"สรุปสาระสำคัญจากการประชุม{series_name} ครั้งที่ {meeting.sequence_no}/{meeting.fiscal_year}\n"
        f"เมื่อวันที่ {thai_date(meeting.meeting_date)}:\n\n"
        f"{summary_text}"
    )

    recipient = (
        await db.execute(
            select(Person).where(
                Person.org_id == org.id,
                Person.is_department == False,
                Person.email.is_not(None),
            )
        )
    ).scalars().first()

    db.add(
        OutboundAction(
            series_id=meeting.series_id,
            meeting_id=meeting.id,
            action_type="send_meeting_summary_email",
            recipient_person_id=recipient.id if recipient else None,
            subject=f"สรุปสาระสำคัญและมติการประชุม{series_name} ครั้งที่ {meeting.sequence_no}/{meeting.fiscal_year}",
            body=body_text,
            payload={"rows": res_rows},
            status=ActionStatus.PENDING_APPROVAL,
            scheduled_for=utcnow(),
        )
    )

    await audit(db, org.id, actor, "approve_meeting", "meeting", meeting.id, f"ครั้งที่ {meeting.sequence_no}")
    await db.commit()
    await db.refresh(meeting)
    return meeting


@router.get("/{meeting_id}/export")
async def export_minutes_docx(meeting_id: UUID, db: AsyncSession = Depends(get_db)):
    """FR-M5-05 ส่งออกรายงานการประชุมเป็น .docx ตามรูปแบบราชการ"""
    meeting = await get_or_404(db, Meeting, meeting_id, "การประชุม")
    series = await get_or_404(db, MeetingSeries, meeting.series_id, "ชุดการประชุม")

    speakers = (
        await db.execute(
            select(TranscriptSegment.speaker_name)
            .where(TranscriptSegment.meeting_id == meeting.id)
            .distinct()
        )
    ).scalars().all()
    attendees = [s for s in speakers if s]

    resolutions = await resolutions_out(db, select(Resolution).where(Resolution.origin_meeting_id == meeting.id))

    res_dicts = [
        {
            "ref_no": r.ref_no,
            "text": r.text,
            "category": r.category,
            "due_date": r.due_date,
            "assignees": ", ".join(r.assignee_names),
        }
        for r in resolutions
    ]

    content = build_minutes_docx(
        series_name=series.name,
        sequence_no=meeting.sequence_no,
        fiscal_year=meeting.fiscal_year,
        meeting_date=meeting.meeting_date,
        attendees=attendees,
        summary=meeting.summary or "",
        key_points=meeting.key_points or [],
        resolutions=res_dicts,
        template_path=settings.MINUTES_TEMPLATE_PATH or None,
    )

    filename = f"minutes_{series.id}_{meeting.sequence_no}.docx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
