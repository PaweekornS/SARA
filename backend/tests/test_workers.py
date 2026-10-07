"""
pipeline ของการประชุม

หลักการที่ชุดนี้เฝ้าอยู่: ถ้า upload / asr / summarize ล้ม ต้องหยุด บันทึก error จริง
และ **ห้ามสร้างข้อมูลทดแทน** ส่วน followup ล้มได้โดยไม่ทำให้การประชุมเสีย

    python -m unittest tests.test_workers -v
"""

from __future__ import annotations

import os
import shutil
import tempfile
from unittest.mock import patch

import tests  # noqa: F401
from app.db import models as m
from app.services import extraction
from app.services.asr import AsrError, Segment, Transcript
from app.services.llm import LlmError
from app.workers import tasks
from tests.support import DbCase, build_workspace

SCRIPT = [
    ("SPEAKER_00", "แบบโฆษณาส่งเรียบร้อยแล้วเมื่อวานครับ"),
    ("SPEAKER_01", "สัปดาห์นี้ขอให้กานต์ทำ hotfix ภายในวันพฤหัส"),
]


def fake_transcript() -> Transcript:
    return Transcript(segments=[Segment(text=t, start_ms=i * 5000, end_ms=i * 5000 + 4000, speaker_label=lbl)
                                for i, (lbl, t) in enumerate(SCRIPT)])


SUMMARY = extraction.SummaryResult(
    summary="ทีมรายงานความคืบหน้า",
    key_points=["แบบโฆษณาเสร็จ"],
    action_items=[extraction.ActionItemDraft(text="ทำ hotfix", owner="กานต์", due_date="2026-09-10", segment_index=1)],
    details={"decisions": ["ปล่อย hotfix"]},
)


class PipelineCase(DbCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.w = await build_workspace(self, "me@x.com", "ฉัน")
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))
        self.path = os.path.join(self.tmpdir, "meeting.m4a")
        with open(self.path, "wb") as fh:
            fh.write(b"\x00" * 2048)
        (self.meeting,) = await self.add(
            m.Meeting(user_id=self.w.user.id, collection_id=self.w.collection.id, title="ครั้งที่ 2",
                      template="general", source_kind="audio", file_uri=self.path,
                      status=m.MeetingStatus.PROCESSING, pipeline=tasks.fresh_pipeline())
        )

    async def run_pipeline(self, transcript=None, summary=SUMMARY, hints=None, asr_error=None, llm_error=None, hint_error=None):
        asr = patch.object(tasks, "transcribe_audio", side_effect=asr_error, return_value=transcript or fake_transcript())
        summ = patch.object(tasks.extraction, "summarize", side_effect=llm_error, return_value=summary)
        detect = patch.object(tasks.extraction, "detect_completed", side_effect=hint_error, return_value=hints or [])
        with asr, summ, detect as self.detect:
            return await tasks.process_meeting(self.meeting.id)

    async def stages(self) -> dict[str, dict]:
        meeting = await self.fetch(m.Meeting, self.meeting.id)
        return {step["stage"]: step for step in meeting.pipeline}


class Success(PipelineCase):
    async def test_meeting_becomes_ready_with_summary_and_items(self):
        result = await self.run_pipeline()
        self.assertEqual(result["status"], "SUCCESS")
        meeting = await self.fetch(m.Meeting, self.meeting.id)
        self.assertEqual(meeting.status, m.MeetingStatus.READY)
        self.assertEqual(meeting.summary, "ทีมรายงานความคืบหน้า")
        self.assertEqual(meeting.details, {"decisions": ["ปล่อย hotfix"]})
        self.assertTrue(all(s["state"] == "ok" for s in (await self.stages()).values()))

    async def test_action_items_link_back_to_their_segment(self):
        await self.run_pipeline()
        from sqlalchemy import select

        async with self.sessionmaker() as s:
            item = (await s.execute(select(m.ActionItem).where(m.ActionItem.meeting_id == self.meeting.id))).scalar_one()
            segment = await s.get(m.TranscriptSegment, item.source_segment_id)
        self.assertEqual((item.owner, str(item.due_date), item.user_id), ("กานต์", "2026-09-10", self.w.user.id))
        self.assertEqual(segment.text, SCRIPT[1][1])

    async def test_open_items_from_earlier_meetings_get_a_suggestion(self):
        hint = extraction.CompletionHint(number=1, evidence="ส่งเรียบร้อยแล้ว", segment_index=0, confidence=0.9)
        await self.run_pipeline(hints=[hint])
        sent = self.detect.call_args.args[1]
        self.assertEqual([o.text for o in sent], ["ส่งแบบโฆษณา"])  # เฉพาะงานที่ยังค้าง ไม่รวมงานที่เสร็จแล้ว
        item = await self.fetch(m.ActionItem, self.w.open_item.id)
        self.assertEqual(item.suggested_done_meeting_id, self.meeting.id)
        self.assertFalse(item.done)  # เป็นแค่ข้อเสนอ ผู้ใช้ต้องยืนยันเอง

    async def test_other_collections_are_not_checked(self):
        (other,) = await self.add(m.Collection(user_id=self.w.user.id, name="อื่น"))
        async with self.sessionmaker() as s:
            (await s.get(m.Meeting, self.meeting.id)).collection_id = other.id
            await s.commit()
        await self.run_pipeline()
        self.detect.assert_not_called()

    async def test_meeting_is_indexed_for_qa(self):
        from app.services import vector_store

        await self.run_pipeline()
        hits = vector_store.search(self.w.user.id, self.w.collection.id, "ทำ hotfix ภายในวันพฤหัส", 10)
        self.assertIn(self.meeting.id, {h.meeting_id for h in hits})
        self.assertEqual((await self.stages())["index"]["state"], "ok")

    async def test_index_failure_is_skipped_not_fatal(self):
        from app.services import vector_store

        with patch.object(vector_store, "index_meeting", side_effect=vector_store.VectorStoreError("down")):
            await self.run_pipeline()
        self.assertEqual((await self.fetch(m.Meeting, self.meeting.id)).status, m.MeetingStatus.READY)
        self.assertEqual((await self.stages())["index"]["state"], "skipped")

    async def test_followup_failure_is_skipped_not_fatal(self):
        await self.run_pipeline(hint_error=LlmError("504"))
        self.assertEqual((await self.fetch(m.Meeting, self.meeting.id)).status, m.MeetingStatus.READY)
        self.assertEqual((await self.stages())["followup"]["state"], "skipped")

    async def test_rerun_does_not_duplicate(self):
        await self.run_pipeline()
        await self.run_pipeline()
        self.assertEqual(await self.count(m.TranscriptSegment, meeting_id=self.meeting.id), 2)
        self.assertEqual(await self.count(m.ActionItem, meeting_id=self.meeting.id), 1)


class Failures(PipelineCase):
    async def assert_failed_at(self, stage: str):
        meeting = await self.fetch(m.Meeting, self.meeting.id)
        self.assertEqual(meeting.status, m.MeetingStatus.FAILED)
        self.assertEqual((await self.stages())[stage]["state"], "failed")
        self.assertEqual(await self.count(m.ActionItem, meeting_id=self.meeting.id), 0)

    async def test_asr_error_halts_and_stores_nothing(self):
        await self.run_pipeline(asr_error=AsrError("HTTP 504"))
        await self.assert_failed_at("asr")
        self.assertEqual(await self.count(m.TranscriptSegment, meeting_id=self.meeting.id), 0)

    async def test_empty_transcript_is_a_failure(self):
        await self.run_pipeline(transcript=Transcript(segments=[]))
        await self.assert_failed_at("asr")

    async def test_llm_failure_keeps_transcript_but_stops(self):
        await self.run_pipeline(llm_error=LlmError("timeout"))
        await self.assert_failed_at("summarize")
        self.assertEqual(await self.count(m.TranscriptSegment, meeting_id=self.meeting.id), 2)
        self.assertEqual((await self.fetch(m.Meeting, self.meeting.id)).summary, "")

    async def test_missing_file_fails_at_upload(self):
        os.remove(self.path)
        await self.run_pipeline()
        await self.assert_failed_at("upload")

    async def test_missing_meeting_is_skipped(self):
        import uuid

        self.assertEqual((await tasks.process_meeting(uuid.uuid4()))["status"], "SKIPPED")


class Resilience(PipelineCase):
    """worker ล่ม / งานถูกส่งซ้ำ / งานหายจากคิว ต้องไม่ทำให้การประชุมค้าง processing ตลอดไป"""

    async def set_meeting(self, **fields):
        async with self.sessionmaker() as s:
            meeting = await s.get(m.Meeting, self.meeting.id)
            for key, value in fields.items():
                setattr(meeting, key, value)
            await s.commit()

    async def test_redelivered_task_after_completion_is_skipped(self):
        await self.run_pipeline()
        result = await self.run_pipeline()
        self.assertEqual(result["status"], "SKIPPED")
        self.assertEqual(await self.count(m.ActionItem, meeting_id=self.meeting.id), 1)

    async def test_redelivery_after_a_worker_crash_runs_again(self):
        await self.set_meeting(processing_attempts=1)  # รอบแรก worker ตายไปกลางทาง
        self.assertEqual((await self.run_pipeline())["status"], "SUCCESS")

    async def test_file_that_keeps_crashing_the_worker_stops_looping(self):
        from app.core.config import settings

        await self.set_meeting(processing_attempts=settings.MAX_PROCESSING_ATTEMPTS)
        result = await self.run_pipeline()
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual((await self.fetch(m.Meeting, self.meeting.id)).status, m.MeetingStatus.FAILED)

    async def test_sweeper_fails_meetings_stuck_past_the_time_limit(self):
        from datetime import timedelta

        from app.db.models import _now

        (fresh,) = await self.add(
            m.Meeting(user_id=self.w.user.id, collection_id=self.w.collection.id, title="เพิ่งเริ่ม",
                      status=m.MeetingStatus.PROCESSING, pipeline=tasks.fresh_pipeline(),
                      processing_started_at=_now())
        )
        await self.set_meeting(processing_started_at=_now() - tasks.STUCK_AFTER - timedelta(minutes=1))

        self.assertEqual(await tasks.sweep_stuck_meetings(), 1)
        stuck = await self.fetch(m.Meeting, self.meeting.id)
        self.assertEqual(stuck.status, m.MeetingStatus.FAILED)
        self.assertEqual(stuck.pipeline[0]["state"], "failed")
        self.assertEqual((await self.fetch(m.Meeting, fresh.id)).status, m.MeetingStatus.PROCESSING)

    async def test_ready_meetings_are_never_swept(self):
        from datetime import timedelta

        from app.db.models import _now

        await self.set_meeting(status=m.MeetingStatus.READY, processing_started_at=_now() - timedelta(days=3))
        self.assertEqual(await tasks.sweep_stuck_meetings(), 0)
