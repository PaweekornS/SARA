"""
งานเบื้องหลัง (Celery)

pipeline ของการประชุม 1 ครั้ง: upload → asr → summarize → index → followup → done
ทุกขั้นเขียนสถานะกลับลง DB ทันทีเพื่อให้หน้าจอเห็นความคืบหน้าจริง

⚠ ถ้า upload / asr / summarize ล้มเหลว ต้องหยุดทั้ง pipeline บันทึกข้อความ error จริง
   และตั้งสถานะเป็น failed — ห้ามเดินต่อด้วยข้อมูลที่แต่งขึ้น
   ส่วน index และ followup เป็นของเสริม ถ้าล้มให้ข้ามไปได้โดยไม่ทำให้การประชุมล้มตาม
   (index ล้ม = ถาม-ตอบยังค้นการประชุมนี้แบบคำได้ แค่ไม่มีการค้นเชิงความหมาย)
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import date, timedelta
from uuid import UUID

from celery import Celery
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.models import ActionItem, Meeting, MeetingStatus, TranscriptSegment, _now
from app.services import extraction, vector_store
from app.services.asr import (
    AsrError,
    Transcript,
    load_transcript_file,
    transcribe_audio,
)
from app.services.llm import LlmError

logger = logging.getLogger(__name__)

TIME_LIMIT_SECONDS = settings.MEETING_TIME_LIMIT_MINUTES * 60
STUCK_AFTER = timedelta(minutes=settings.MEETING_TIME_LIMIT_MINUTES + 15)

celery_app = Celery("sara", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=settings.TIMEZONE,
    enable_utc=False,
    #  ack หลังทำเสร็จ — ถ้า worker ตายกลางงาน Redis จะส่งงานกลับเข้าคิวให้ worker ตัวอื่น
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    #  ต้องนานกว่า time limit ไม่งั้น Redis ส่งงานที่ยังรันอยู่ซ้ำให้อีกตัว
    broker_transport_options={"visibility_timeout": TIME_LIMIT_SECONDS * 2},
    task_soft_time_limit=TIME_LIMIT_SECONDS,
    task_time_limit=TIME_LIMIT_SECONDS + 60,
    beat_schedule={
        "sweep-stuck-meetings": {"task": "sweep_stuck_meetings_task", "schedule": 600.0},
    },
)

INITIAL_PIPELINE = [
    {"stage": "upload", "state": "pending", "detail": "รับไฟล์และตรวจความสมบูรณ์"},
    {"stage": "asr", "state": "pending", "detail": "ถอดเสียงด้วย AI4Thai ASR"},
    {"stage": "summarize", "state": "pending", "detail": "สรุปเนื้อหาและงานที่ต้องทำ"},
    {"stage": "index", "state": "pending", "detail": "จัดทำดัชนีสำหรับถาม-ตอบ"},
    {"stage": "followup", "state": "pending", "detail": "ตรวจงานค้างจากการประชุมก่อน ๆ"},
    {"stage": "done", "state": "pending", "detail": "พร้อมใช้งาน"},
]


def fresh_pipeline() -> list[dict]:
    return [dict(step) for step in INITIAL_PIPELINE]


def run_async(coro):
    """
    แต่ละ task รันบน event loop ของตัวเอง
    asyncpg ผูก connection ไว้กับ loop ที่สร้างมัน การใช้ loop ร่วมกันข้าม task จึงพัง
    """
    return asyncio.run(coro)


@asynccontextmanager
async def session_scope():
    """สร้าง engine ใหม่ต่อหนึ่งงาน แล้วปิดให้เรียบร้อย — worker ไม่ได้รันงานถี่พอให้ต้องใช้ pool ร่วม"""
    engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            yield session
    finally:
        await engine.dispose()


@celery_app.task(name="process_meeting_task", bind=True, max_retries=0)
def process_meeting_task(self, meeting_id: str):
    return run_async(process_meeting(UUID(meeting_id)))


async def process_meeting(meeting_id: UUID) -> dict:
    async with session_scope() as session:
        meeting = await session.get(Meeting, meeting_id)
        if meeting is None:
            return {"status": "SKIPPED", "reason": "ไม่พบการประชุม"}
        if meeting.status != MeetingStatus.PROCESSING:
            #  งานที่ถูกส่งซ้ำหลังจากรอบก่อนจบไปแล้ว หรือถูก sweep เป็น failed ไปแล้ว
            return {"status": "SKIPPED", "reason": meeting.status}

        meeting.processing_attempts = (meeting.processing_attempts or 0) + 1
        await session.commit()
        if meeting.processing_attempts > settings.MAX_PROCESSING_ATTEMPTS:
            #  worker ล่มระหว่างทำไฟล์นี้ซ้ำหลายรอบแล้ว (เช่นไฟล์ทำ memory เต็ม) — หยุดวน
            return await _fail(session, meeting, _current_stage(meeting), "ประมวลผลไม่สำเร็จหลายครั้ง กรุณาลองไฟล์ใหม่")
        return await _run_pipeline(session, meeting)


@celery_app.task(name="sweep_stuck_meetings_task")
def sweep_stuck_meetings_task():
    return run_async(sweep_stuck_meetings())


async def sweep_stuck_meetings() -> int:
    """การประชุมที่ค้าง processing นานเกิน time limit แปลว่างานหายไปแล้ว ตั้งเป็น failed ให้ผู้ใช้กด retry ได้"""
    cutoff = _now() - STUCK_AFTER
    async with session_scope() as session:
        stuck = (
            await session.execute(
                select(Meeting).where(
                    Meeting.status == MeetingStatus.PROCESSING,
                    Meeting.processing_started_at < cutoff,
                )
            )
        ).scalars().all()
        for meeting in stuck:
            await _fail(session, meeting, _current_stage(meeting), "ประมวลผลนานผิดปกติ ระบบหยุดงานนี้แล้ว กรุณากดประมวลผลใหม่")
        return len(stuck)


def _current_stage(meeting: Meeting) -> str:
    for step in meeting.pipeline or []:
        if step.get("state") in ("running", "pending"):
            return step["stage"]
    return "done"


async def _run_pipeline(session: AsyncSession, meeting: Meeting) -> dict:
    #  ล้างผลลัพธ์ของรอบก่อนออกก่อนเสมอ เพื่อไม่ให้ retry แล้วข้อมูลซ้อนกัน
    await _clear_previous_run(session, meeting)

    # 1) upload
    await _set_stage(session, meeting, "upload", "running")
    path = meeting.file_uri or ""
    if not os.path.exists(path):
        return await _fail(session, meeting, "upload", "ไม่พบไฟล์ที่อัปโหลด")
    await _set_stage(session, meeting, "upload", "ok", detail=f"{os.path.getsize(path) / 1024 / 1024:.1f} MB")

    # 2) asr
    await _set_stage(session, meeting, "asr", "running")
    try:
        transcript = load_transcript_file(path) if meeting.source_kind == "transcript" else transcribe_audio(path)
    except AsrError as err:
        return await _fail(session, meeting, "asr", f"{err} — หยุด pipeline ไม่มีการสร้าง transcript ทดแทน")
    except Exception as err:  # noqa: BLE001
        logger.exception("asr ล้มเหลว")
        return await _fail(session, meeting, "asr", f"ถอดเสียงไม่สำเร็จ: {err}")
    if not transcript.segments:
        return await _fail(session, meeting, "asr", "ไม่พบเสียงพูดหรือข้อความในไฟล์")

    segments = await _store_segments(session, meeting, transcript)
    await _set_stage(session, meeting, "asr", "ok", detail=f"ได้ {len(segments)} ท่อน")
    views = [extraction.SegmentView(index=i, speaker_label=s.speaker_label, text=s.text) for i, s in enumerate(segments)]

    # 3) summarize
    await _set_stage(session, meeting, "summarize", "running")
    try:
        result = extraction.summarize(views, meeting.template, meeting.title)
    except LlmError as err:
        return await _fail(session, meeting, "summarize", f"สรุปไม่สำเร็จ: {err}")
    except Exception as err:  # noqa: BLE001
        logger.exception("summarize ล้มเหลว")
        return await _fail(session, meeting, "summarize", f"สรุปไม่สำเร็จ: {err}")

    meeting.summary = result.summary
    meeting.key_points = result.key_points
    meeting.details = result.details
    for draft in result.action_items:
        source = segments[draft.segment_index] if draft.segment_index is not None else None
        session.add(
            ActionItem(
                user_id=meeting.user_id,
                meeting_id=meeting.id,
                collection_id=meeting.collection_id,
                text=draft.text,
                owner=draft.owner,
                due_date=date.fromisoformat(draft.due_date) if draft.due_date else None,
                source_segment_id=source.id if source else None,
            )
        )
    await _set_stage(session, meeting, "summarize", "ok", detail=f"งานที่ต้องทำ {len(result.action_items)} รายการ")

    # 4) index — ล้มได้โดยไม่กระทบผลสรุป
    await _set_stage(session, meeting, "index", "running")
    try:
        chunks = vector_store.build_chunks(meeting.id, meeting.summary, segments)
        count = await asyncio.to_thread(
            vector_store.index_meeting, meeting.user_id, meeting.collection_id, meeting.id, chunks
        )
        await _set_stage(session, meeting, "index", "ok", detail=f"{count} ช่วง")
    except Exception as err:  # noqa: BLE001
        logger.warning("ทำดัชนีไม่สำเร็จ ข้ามขั้นนี้: %s", err)
        await _set_stage(session, meeting, "index", "skipped", error=f"ข้ามขั้นนี้: {err}")

    # 5) followup — ล้มได้โดยไม่กระทบผลสรุป
    await _set_stage(session, meeting, "followup", "running")
    try:
        suggested = await _suggest_completed(session, meeting, segments, views)
        await _set_stage(session, meeting, "followup", "ok", detail=f"น่าจะเสร็จแล้ว {suggested} รายการ")
    except Exception as err:  # noqa: BLE001
        logger.warning("ตรวจงานค้างไม่สำเร็จ ข้ามขั้นนี้: %s", err)
        await _set_stage(session, meeting, "followup", "skipped", error=f"ข้ามขั้นนี้: {err}")

    # 6) done
    await _set_stage(session, meeting, "done", "ok")
    meeting.status = MeetingStatus.READY
    await session.commit()
    return {"status": "SUCCESS", "meeting_id": str(meeting.id), "action_items": len(result.action_items)}


async def _suggest_completed(
    session: AsyncSession,
    meeting: Meeting,
    segments: list[TranscriptSegment],
    views: list[extraction.SegmentView],
) -> int:
    open_items = (
        await session.execute(
            select(ActionItem)
            .where(
                ActionItem.collection_id == meeting.collection_id,
                ActionItem.meeting_id != meeting.id,
                ActionItem.done.is_(False),
            )
            .order_by(ActionItem.created_at)
        )
    ).scalars().all()
    if not open_items:
        return 0

    listing = [extraction.OpenItemView(number=i, text=item.text, owner=item.owner) for i, item in enumerate(open_items, 1)]
    hints = extraction.detect_completed(views, listing)
    for hint in hints:
        item = open_items[hint.number - 1]
        source = segments[hint.segment_index] if hint.segment_index is not None else None
        item.suggested_done_meeting_id = meeting.id
        item.suggested_done_evidence = hint.evidence or (source.text if source else "")
    return len(hints)


async def _set_stage(session: AsyncSession, meeting: Meeting, stage: str, state: str, detail=None, error=None) -> None:
    pipeline = [dict(step) for step in (meeting.pipeline or fresh_pipeline())]
    for step in pipeline:
        if step.get("stage") == stage:
            step["state"] = state
            if detail is not None:
                step["detail"] = detail
            if error is not None:
                step["error"] = error
    meeting.pipeline = pipeline
    await session.commit()


async def _clear_previous_run(session: AsyncSession, meeting: Meeting) -> None:
    await session.execute(delete(ActionItem).where(ActionItem.meeting_id == meeting.id))
    await session.execute(delete(TranscriptSegment).where(TranscriptSegment.meeting_id == meeting.id))
    meeting.summary = ""
    meeting.key_points = []
    meeting.details = {}
    meeting.status = MeetingStatus.PROCESSING
    meeting.pipeline = fresh_pipeline()
    await session.commit()


async def _fail(session: AsyncSession, meeting: Meeting, stage: str, message: str) -> dict:
    logger.error("การประชุม %s ล้มเหลวที่ขั้น %s: %s", meeting.id, stage, message)
    await _set_stage(session, meeting, stage, "failed", error=message)
    meeting.status = MeetingStatus.FAILED
    await session.commit()
    return {"status": "FAILED", "stage": stage}


async def _store_segments(session: AsyncSession, meeting: Meeting, transcript: Transcript) -> list[TranscriptSegment]:
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
    await session.flush()
    return rows
