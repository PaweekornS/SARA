"""
งานเบื้องหลังทั้งหมด (Celery)

pipeline ของการประชุม 1 ครั้ง: upload → asr → diarize → extract → done
ทุกขั้นเขียนสถานะกลับลง DB ทันทีเพื่อให้หน้าจอเห็นความคืบหน้าจริง (FR-M2-03)

⚠ FR-M2-04: ถ้าขั้นไหนล้มเหลว ต้องหยุดทั้ง pipeline บันทึกข้อความ error จริง
   และตั้งสถานะเป็น failed — ห้ามเดินต่อด้วยข้อมูลที่แต่งขึ้น
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import date, timedelta
from uuid import UUID

from celery import Celery
from celery.schedules import crontab
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.models import (
    ActionStatus,
    LinkType,
    Meeting,
    MeetingSeries,
    MeetingStatus,
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
from app.services import extraction
from app.services.asr import AsrError, Transcript, load_transcript_file, transcribe_audio
from app.services.llm import LlmError
from app.services.resolutions import overdue_days, utcnow
from app.services.thai_format import thai_date

logger = logging.getLogger(__name__)

celery_app = Celery("sara", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=settings.TIMEZONE,
    enable_utc=False,
    beat_schedule={
        #  FR-M7-06 scheduler สำหรับ trigger ตามเวลา
        "scan-due-resolutions-every-morning": {
            "task": "scan_due_resolutions",
            "schedule": crontab(hour=8, minute=0),
        },
    },
)


def run_async(coro):
    """
    แต่ละ task รันบน event loop ของตัวเอง
    asyncpg ผูก connection ไว้กับ loop ที่สร้างมัน การใช้ loop ร่วมกันข้าม task จึงพัง
    """
    return asyncio.run(coro)


@asynccontextmanager
async def session_scope() -> AsyncSession:
    """สร้าง engine ใหม่ต่อหนึ่งงาน แล้วปิดให้เรียบร้อย — worker ไม่ได้รันงานถี่พอให้ต้องใช้ pool ร่วม"""
    engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            yield session
    finally:
        await engine.dispose()


# ── pipeline ────────────────────────────────────────────────────────────

async def _set_stage(
    session: AsyncSession, meeting: Meeting, stage: str, state: str, detail=None, error=None
) -> None:
    pipeline = [dict(step) for step in (meeting.pipeline or [])]
    for step in pipeline:
        if step.get("stage") == stage:
            step["state"] = state
            if detail is not None:
                step["detail"] = detail
            if error is not None:
                step["error"] = error
    meeting.pipeline = pipeline
    await session.commit()


@celery_app.task(name="process_meeting_task", bind=True, max_retries=0)
def process_meeting_task(self, meeting_id: str, file_path: str, simulate_asr_failure: bool = False):
    return run_async(_process_meeting(UUID(meeting_id), file_path, simulate_asr_failure))


async def _process_meeting(meeting_id: UUID, file_path: str, simulate_asr_failure: bool) -> dict:
    async with session_scope() as session:
        meeting = await session.get(Meeting, meeting_id)
        if meeting is None:
            return {"status": "SKIPPED", "reason": "ไม่พบการประชุม"}

        series = await session.get(MeetingSeries, meeting.series_id)

        #  ล้างผลลัพธ์ของรอบก่อนออกก่อนเสมอ เพื่อไม่ให้ retry แล้วข้อมูลซ้อนกัน
        await _clear_previous_run(session, meeting)

        # 1) upload
        await _set_stage(session, meeting, "upload", "running")
        if not os.path.exists(file_path):
            await _fail(session, meeting, "upload", f"ไม่พบไฟล์ {file_path}")
            return {"status": "FAILED", "stage": "upload"}
        await _set_stage(session, meeting, "upload", "ok", detail=f"{os.path.getsize(file_path) / 1024 / 1024:.1f} MB")

        # 2) asr
        await _set_stage(session, meeting, "asr", "running")
        try:
            if simulate_asr_failure:
                #  โหมดสาธิตสำหรับแสดงว่าเมื่อ ASR ล้ม ระบบหยุดจริงและไม่แต่งข้อมูล
                raise AsrError("โหมดจำลอง: ASR API ไม่ตอบสนอง (HTTP 504 หลัง retry 3 ครั้ง)")
            if meeting.source_kind == "transcript":
                transcript = load_transcript_file(file_path)
            else:
                transcript = transcribe_audio(file_path)
        except AsrError as err:
            await _fail(session, meeting, "asr", f"{err} — หยุด pipeline ไม่มีการสร้าง transcript ทดแทน")
            return {"status": "FAILED", "stage": "asr"}
        except Exception as err:  # noqa: BLE001
            await _fail(session, meeting, "asr", f"ถอดเสียงไม่สำเร็จ: {err}")
            return {"status": "FAILED", "stage": "asr"}

        await _set_stage(
            session, meeting, "asr", "ok",
            detail=f"ได้ {len(transcript.segments)} ท่อน จาก {settings.ASR_MODEL}",
        )

        # 3) diarize
        await _set_stage(session, meeting, "diarize", "running")
        segments = await _store_segments(session, meeting, transcript)
        if transcript.has_speaker_labels:
            speakers = len({s.speaker_label for s in segments})
            diarize_detail = f"แยกได้ {speakers} ผู้พูดจากผลของ ASR"
        else:
            diarize_detail = "ASR ไม่คืนข้อมูลผู้พูด — ให้ระบุผู้พูดเองในหน้าตรวจทาน"
        await _set_stage(session, meeting, "diarize", "ok", detail=diarize_detail)

        # 4) extract + linking
        await _set_stage(session, meeting, "extract", "running")
        try:
            created = await _extract_and_link(session, meeting, series, segments)
        except LlmError as err:
            await _fail(session, meeting, "extract", f"สกัดมติไม่สำเร็จ: {err}")
            return {"status": "FAILED", "stage": "extract"}
        except Exception as err:  # noqa: BLE001
            logger.exception("extract ล้มเหลว")
            await _fail(session, meeting, "extract", f"สกัดมติไม่สำเร็จ: {err}")
            return {"status": "FAILED", "stage": "extract"}

        await _set_stage(session, meeting, "extract", "ok", detail=f"สร้างข้อเสนอ {created} รายการ")

        # 5) done
        await _set_stage(session, meeting, "done", "ok", detail="พร้อมให้ตรวจทาน")
        meeting.status = MeetingStatus.DRAFT
        await session.commit()

        return {"status": "SUCCESS", "meeting_id": str(meeting_id), "proposals": created}


async def _clear_previous_run(session: AsyncSession, meeting: Meeting) -> None:
    for row in (
        await session.execute(select(TranscriptSegment).where(TranscriptSegment.meeting_id == meeting.id))
    ).scalars().all():
        await session.delete(row)
    for row in (
        await session.execute(
            select(Proposal).where(Proposal.meeting_id == meeting.id, Proposal.decision == "pending")
        )
    ).scalars().all():
        await session.delete(row)
    await session.commit()


async def _fail(session: AsyncSession, meeting: Meeting, stage: str, message: str) -> None:
    logger.error("การประชุม %s ล้มเหลวที่ขั้น %s: %s", meeting.id, stage, message)
    await _set_stage(session, meeting, stage, "failed", error=message)
    meeting.status = MeetingStatus.FAILED
    await session.commit()


async def _store_segments(
    session: AsyncSession, meeting: Meeting, transcript: Transcript
) -> list[TranscriptSegment]:
    rows = [
        TranscriptSegment(
            meeting_id=meeting.id,
            speaker_label=seg.speaker_label,
            start_ms=seg.start_ms,
            end_ms=seg.end_ms,
            text=seg.text,
            confidence=seg.confidence,
        )
        for seg in transcript.segments
    ]
    session.add_all(rows)
    await session.commit()
    for row in rows:
        await session.refresh(row)
    return rows


async def _extract_and_link(
    session: AsyncSession,
    meeting: Meeting,
    series: MeetingSeries | None,
    segments: list[TranscriptSegment],
) -> int:
    """
    FR-M4-01, 02, 04, 05 — สกัดมติใหม่ และจับคู่คำพูดใหม่กับมติค้างของ series

    ทุกอย่างที่ได้จากโมเดลถูกบันทึกเป็น Proposal ที่ยังไม่มีผล
    มติจริงจะเกิดก็ต่อเมื่อมีคนกดยืนยันในหน้าตรวจทานเท่านั้น
    """
    open_resolutions = list(
        (
            await session.execute(
                select(Resolution).where(
                    Resolution.series_id == meeting.series_id,
                    Resolution.status.in_(ResolutionStatus.OPEN),
                )
            )
        ).scalars().all()
    )

    views = []
    for r in open_resolutions:
        names = (
            await session.execute(
                select(Person)
                .join(ResolutionAssignee, ResolutionAssignee.person_id == Person.id)
                .where(ResolutionAssignee.resolution_id == r.id)
            )
        ).scalars().all()
        views.append(
            extraction.OpenResolutionView(
                ref=r.ref_no,
                text=r.text,
                status=r.status,
                assignees=", ".join(p.full_name for p in names),
                due_date=r.due_date.isoformat() if r.due_date else None,
            )
        )

    segment_views = [
        extraction.SegmentView(index=i, speaker_label=s.speaker_label, start_ms=s.start_ms, text=s.text)
        for i, s in enumerate(segments)
    ]

    result = extraction.extract(
        segment_views,
        views,
        meeting_label=f"ครั้งที่ {meeting.sequence_no}/{meeting.fiscal_year} วันที่ {thai_date(meeting.meeting_date)}",
    )

    by_ref = {r.ref_no: r for r in open_resolutions}
    created = 0

    #  ข้อเสนอเปลี่ยนสถานะของมติเดิม + บันทึกว่ามตินั้นถูกอ้างถึงในการประชุมนี้
    for update in result.updates:
        target = by_ref.get(update.ref)
        if target is None:
            continue
        segment = segments[update.segment_index] if update.segment_index is not None else None
        session.add(
            Proposal(
                meeting_id=meeting.id,
                kind="status_change",
                resolution_id=target.id,
                proposed_status=update.proposed_status,
                title=f"เสนอเปลี่ยนสถานะ {target.ref_no} เป็น {update.proposed_status}",
                evidence_text=update.evidence or (segment.text if segment else ""),
                evidence_start_ms=segment.start_ms if segment else None,
                segment_id=segment.id if segment else None,
                confidence=update.confidence,
            )
        )
        session.add(
            ResolutionLink(
                resolution_id=target.id,
                meeting_id=meeting.id,
                link_type=LinkType.REFERENCED,
                segment_id=segment.id if segment else None,
                evidence_text=update.evidence or (segment.text if segment else ""),
                evidence_start_ms=segment.start_ms if segment else None,
                confidence=update.confidence,
            )
        )
        created += 1

    #  ข้อเสนอมติใหม่
    for item in result.new_resolutions:
        segment = segments[item.segment_index] if item.segment_index is not None else None
        session.add(
            Proposal(
                meeting_id=meeting.id,
                kind="new_resolution",
                title=item.text,
                evidence_text=segment.text if segment else item.text,
                evidence_start_ms=segment.start_ms if segment else None,
                segment_id=segment.id if segment else None,
                confidence=item.confidence,
            )
        )
        created += 1

    created += await _speaker_proposals(session, meeting, segments, result.speakers)
    await session.commit()
    return created


async def _speaker_proposals(
    session: AsyncSession,
    meeting: Meeting,
    segments: list[TranscriptSegment],
    mentions: list[extraction.SpeakerMention],
) -> int:
    """
    FR-M3-03 — ถ้า resolve ชื่อได้แน่ชัดจาก alias ที่เคยยืนยันแล้วก็ผูกให้เลย
    ถ้าไม่มั่นใจ ห้ามเดา ให้สร้างข้อเสนอถามคนแทน
    """
    people = list((await session.execute(select(Person))).scalars().all())
    aliases = list((await session.execute(select(PersonAlias))).scalars().all())

    candidates: list[tuple[str, str]] = [(str(p.id), p.full_name) for p in people]
    candidates += [(str(a.person_id), a.alias) for a in aliases]

    labels = {s.speaker_label for s in segments}
    resolved: dict[str, UUID] = {}
    created = 0

    for mention in mentions:
        if mention.speaker_label not in labels:
            continue
        person_id, confidence = extraction.resolve_person(mention.name_mention, candidates)
        sample = next((s for s in segments if s.speaker_label == mention.speaker_label), None)

        if person_id and confidence >= 0.9:
            resolved[mention.speaker_label] = UUID(person_id)
            continue

        session.add(
            Proposal(
                meeting_id=meeting.id,
                kind="speaker_identity",
                speaker_label=mention.speaker_label,
                candidate_person_ids=[person_id] if person_id else [],
                title=f"ระบุตัวผู้พูด {mention.speaker_label} (ได้ยินเรียกว่า “{mention.name_mention}”)",
                evidence_text=sample.text if sample else "",
                evidence_start_ms=sample.start_ms if sample else None,
                segment_id=sample.id if sample else None,
                confidence=confidence,
            )
        )
        created += 1

    for label, person_id in resolved.items():
        for segment in segments:
            if segment.speaker_label == label:
                segment.person_id = person_id

    #  ผู้พูดที่ไม่มีใครเอ่ยชื่อถึงเลย ยังต้องให้เลขาฯ ระบุเองในหน้าตรวจทาน
    for label in sorted(labels - set(resolved) - {m.speaker_label for m in mentions}):
        sample = next((s for s in segments if s.speaker_label == label), None)
        session.add(
            Proposal(
                meeting_id=meeting.id,
                kind="speaker_identity",
                speaker_label=label,
                candidate_person_ids=[],
                title=f"ระบุตัวผู้พูด {label}",
                evidence_text=sample.text if sample else "",
                evidence_start_ms=sample.start_ms if sample else None,
                segment_id=sample.id if sample else None,
                confidence=0.0,
            )
        )
        created += 1

    return created


# ── การส่งออก (M7) ──────────────────────────────────────────────────────

@celery_app.task(name="send_outbound_action_task", bind=True, max_retries=2, default_retry_delay=60)
def send_outbound_action_task(self, action_id: str):
    return run_async(_send_action(UUID(action_id), self))


async def _send_action(action_id: UUID, task) -> dict:
    from app.services.mcp_agent import McpError, send_email_via_mcp

    async with session_scope() as session:
        action = await session.get(OutboundAction, action_id)
        if action is None:
            return {"status": "SKIPPED"}
        if action.status != ActionStatus.APPROVED:
            #  ป้องกันการส่งซ้ำ และกันไม่ให้ของที่ยังไม่อนุมัติหลุดออกไป
            return {"status": "SKIPPED", "reason": action.status}

        recipient = await session.get(Person, action.recipient_person_id)
        if recipient is None or not recipient.email:
            action.status = ActionStatus.FAILED
            action.error = "ผู้รับไม่มีอีเมลในทะเบียนบุคคล"
            await session.commit()
            return {"status": "FAILED"}

        try:
            await send_email_via_mcp(
                to_email=recipient.email,
                subject=action.subject,
                greeting=f"เรียน {recipient.position or recipient.full_name}",
                body=action.body,
                rows=(action.payload or {}).get("rows", []),
            )
        except McpError as err:
            action.status = ActionStatus.FAILED
            action.error = str(err)
            await session.commit()
            logger.error("ส่งอีเมลไม่สำเร็จ: %s", err)
            raise task.retry(exc=err)

        action.status = ActionStatus.SENT
        action.sent_at = utcnow()
        action.error = None
        await session.commit()
        return {"status": "SENT", "to": recipient.email}


@celery_app.task(name="scan_due_resolutions")
def scan_due_resolutions():
    """FR-M7-03 · FR-M7-06 — สร้างรายการเตือนล่วงหน้าเข้าคิว "รออนุมัติ" ทุกเช้า"""
    return run_async(_scan_due())


async def _scan_due() -> dict:
    from app.services.mcp_agent import build_reminder_body

    today = date.today()
    horizon = today + timedelta(days=settings.REMINDER_LEAD_DAYS)
    queued = 0

    async with session_scope() as session:
        rows = (
            await session.execute(
                select(Resolution).where(
                    Resolution.status.in_(ResolutionStatus.OPEN),
                    Resolution.due_date.is_not(None),
                    Resolution.due_date <= horizon,
                )
            )
        ).scalars().all()

        for resolution in rows:
            assignees = (
                await session.execute(
                    select(Person)
                    .join(ResolutionAssignee, ResolutionAssignee.person_id == Person.id)
                    .where(ResolutionAssignee.resolution_id == resolution.id)
                )
            ).scalars().all()

            for person in assignees:
                if not person.email:
                    continue
                #  กันสแปม: เตือนคนเดิมเรื่องเดิมได้ไม่เกิน 1 ครั้งต่อรอบที่กำหนด
                recent = (
                    await session.execute(
                        select(OutboundAction).where(
                            OutboundAction.resolution_id == resolution.id,
                            OutboundAction.recipient_person_id == person.id,
                            OutboundAction.action_type == "send_resolution_reminder",
                            OutboundAction.created_at
                            >= utcnow() - timedelta(days=settings.REMINDER_COOLDOWN_DAYS),
                        )
                    )
                ).scalars().first()
                if recent:
                    continue

                od = overdue_days(resolution, today)
                subject = (
                    f"แจ้งเตือน: {resolution.ref_no} เกินกำหนดแล้ว {od} วัน"
                    if od
                    else f"แจ้งเตือน: {resolution.ref_no} ครบกำหนดวันที่ {thai_date(resolution.due_date)}"
                )
                session.add(
                    OutboundAction(
                        series_id=resolution.series_id,
                        resolution_id=resolution.id,
                        action_type="send_resolution_reminder",
                        recipient_person_id=person.id,
                        subject=subject,
                        body=build_reminder_body(resolution, person, od),
                        #  FR-M7-07 ยังไม่ส่งจนกว่าจะมีคนอนุมัติ
                        status=ActionStatus.PENDING_APPROVAL,
                        scheduled_for=utcnow(),
                    )
                )
                queued += 1

        await session.commit()

    logger.info("สร้างรายการเตือน %s รายการ", queued)
    return {"queued": queued}
