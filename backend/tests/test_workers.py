"""
งานเบื้องหลัง — pipeline ของการประชุม การส่งออก และ scheduler

หลักการที่ชุดนี้เฝ้าอยู่ (FR-M2-04):
    ถ้าขั้นไหนล้มเหลว ต้องหยุดทั้ง pipeline บันทึก error จริง และ **ห้ามสร้างข้อมูลทดแทน**
    เคสหลายอันด้านล่างจึงตรวจถึงระดับ "มีกี่แถวในฐานข้อมูล" ไม่ใช่แค่สถานะที่ตอบกลับมา

    python -m unittest tests.test_workers -v
"""

from __future__ import annotations

import tests  # noqa: F401  — ต้องมาก่อน import app เพื่อตั้ง env ของการทดสอบให้ทัน

import os
import shutil
import tempfile
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.config import settings
from app.db import models as m
from app.services import extraction
from app.services.asr import AsrError, Segment, Transcript
from app.services.llm import LlmError
from app.workers import tasks
from tests.support import DbCase, build_fixture

SCRIPT = [
    ("SPEAKER_00", 9_000, "เรียนคณะกรรมการทุกท่าน ขอเปิดการประชุมครับ"),
    ("SPEAKER_01", 402_000, "เรื่องคณะทำงานที่ค้างจากคราวที่แล้ว ตอนนี้แต่งตั้งเรียบร้อยแล้วครับ"),
    ("SPEAKER_00", 471_000, "ดีครับ ถือว่าเรื่องนี้ดำเนินการเสร็จแล้ว ขอบคุณท่านประธานครับ"),
    ("SPEAKER_00", 1_246_000, "ที่ประชุมมีมติให้ฝ่ายไอทีจัดอบรมการใช้งานระบบให้เจ้าหน้าที่ทุกฝ่าย"),
]


def fake_transcript(has_labels: bool = True) -> Transcript:
    return Transcript(
        segments=[
            Segment(text=text, start_ms=start, end_ms=start + 8000, speaker_label=label, confidence=0.94)
            for label, start, text in SCRIPT
        ],
        has_speaker_labels=has_labels,
    )


class PipelineCase(DbCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.f = await build_fixture(self.sessionmaker)
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))
        self.audio = os.path.join(self.tmpdir, "meeting.m4a")
        with open(self.audio, "wb") as fh:
            fh.write(b"\x00" * 2048)

        self.meeting = (
            await self.add(
                m.Meeting(
                    series_id=self.f.series.id, sequence_no=3, fiscal_year=2569,
                    meeting_date=date(2026, 8, 20), title="การประชุมครั้งที่ 3/2569",
                    audio_uri=self.audio, source_kind="audio", status=m.MeetingStatus.PROCESSING,
                    pipeline=[
                        {"stage": stage, "state": "pending", "detail": ""}
                        for stage in ("upload", "asr", "extract", "done")
                    ],
                )
            )
        )[0]

    async def run_pipeline(self, simulate_failure: bool = False) -> dict:
        return await tasks._process_meeting(self.meeting.id, self.audio, simulate_failure)

    async def stages(self) -> dict[str, dict]:
        meeting = await self.fetch(m.Meeting, self.meeting.id)
        return {step["stage"]: step for step in meeting.pipeline}


class PipelineFailures(PipelineCase):
    """FR-M2-04 — จุดที่ v1 เคยใส่ transcript ปลอมเมื่อ ASR พัง"""

    async def test_simulated_asr_failure_halts_and_stores_nothing(self):
        result = await self.run_pipeline(simulate_failure=True)
        self.assertEqual(result, {"status": "FAILED", "stage": "asr"})

        meeting = await self.fetch(m.Meeting, self.meeting.id)
        self.assertEqual(meeting.status, "failed")

        stages = await self.stages()
        self.assertEqual(stages["upload"]["state"], "ok")
        self.assertEqual(stages["asr"]["state"], "failed")
        self.assertIn("ไม่มีการสร้าง transcript ทดแทน", stages["asr"]["error"])
        #  ขั้นถัดไปต้องไม่เดินต่อ
        for stage in ("extract", "done"):
            self.assertEqual(stages[stage]["state"], "pending")

        #  หลักฐานที่แข็งที่สุดว่าไม่มีข้อมูลปลอม: ฐานข้อมูลว่างเปล่า
        self.assertEqual(await self.count(m.TranscriptSegment, meeting_id=self.meeting.id), 0)
        self.assertEqual(await self.count(m.Proposal, meeting_id=self.meeting.id), 0)

    async def test_real_asr_error_halts_the_same_way(self):
        with patch.object(tasks, "transcribe_audio", side_effect=AsrError("ASR ตอบ HTTP 504")):
            result = await self.run_pipeline()
        self.assertEqual(result["stage"], "asr")
        self.assertIn("HTTP 504", (await self.stages())["asr"]["error"])
        self.assertEqual(await self.count(m.TranscriptSegment, meeting_id=self.meeting.id), 0)

    async def test_unexpected_asr_exception_is_also_caught(self):
        with patch.object(tasks, "transcribe_audio", side_effect=ValueError("ไฟล์เสียงเสียหาย")):
            result = await self.run_pipeline()
        self.assertEqual(result["stage"], "asr")
        self.assertEqual((await self.fetch(m.Meeting, self.meeting.id)).status, "failed")
        self.assertEqual(await self.count(m.TranscriptSegment, meeting_id=self.meeting.id), 0)

    async def test_missing_source_file_fails_at_upload_stage(self):
        os.remove(self.audio)
        result = await self.run_pipeline()
        self.assertEqual(result, {"status": "FAILED", "stage": "upload"})
        self.assertIn("ไม่พบไฟล์", (await self.stages())["upload"]["error"])

    async def test_llm_failure_keeps_the_real_transcript_but_stops_the_pipeline(self):
        """ผลถอดเสียงมาจากไฟล์จริง จึงเก็บไว้ได้ แต่ห้ามเดินต่อไปเป็นมติที่ไม่ได้สกัดจริง"""
        with patch.object(tasks, "transcribe_audio", return_value=fake_transcript()), patch.object(
            extraction, "extract", side_effect=LlmError("โมเดลไม่ตอบ")
        ):
            result = await self.run_pipeline()

        self.assertEqual(result["stage"], "extract")
        self.assertEqual((await self.fetch(m.Meeting, self.meeting.id)).status, "failed")
        self.assertEqual(await self.count(m.TranscriptSegment, meeting_id=self.meeting.id), len(SCRIPT))
        self.assertEqual(await self.count(m.Proposal, meeting_id=self.meeting.id), 0)

    async def test_missing_meeting_is_skipped_quietly(self):
        from uuid import uuid4

        result = await tasks._process_meeting(uuid4(), self.audio, False)
        self.assertEqual(result["status"], "SKIPPED")


class PipelineSuccess(PipelineCase):
    """FR-M2-03, 06 · FR-M4-01, 04, 05 · FR-M3-03"""

    def extraction_result(self) -> extraction.ExtractionResult:
        return extraction.ExtractionResult(
            new_resolutions=[
                extraction.NewResolution(
                    text="ให้ฝ่ายไอทีจัดอบรมการใช้งานระบบสารบรรณให้เจ้าหน้าที่ทุกฝ่าย",
                    segment_index=3, category="operations", confidence=0.92,
                )
            ],
            updates=[
                extraction.ResolutionUpdate(
                    ref=self.f.open_res.ref_no, segment_index=2, proposed_status="done",
                    evidence="ถือว่าเรื่องนี้ดำเนินการเสร็จแล้ว", confidence=0.93,
                )
            ],
            speakers=[
                extraction.SpeakerMention(
                    speaker_label="SPEAKER_00", name_mention="ท่านประธาน", segment_index=2, confidence=0.9
                ),
                extraction.SpeakerMention(
                    speaker_label="SPEAKER_01", name_mention="พี่หนึ่ง", segment_index=1, confidence=0.6
                ),
            ],
        )

    async def run_ok(self, has_labels: bool = True) -> dict:
        with patch.object(tasks, "transcribe_audio", return_value=fake_transcript(has_labels)), patch.object(
            extraction, "extract", return_value=self.extraction_result()
        ):
            return await self.run_pipeline()

    async def test_all_stages_complete_and_meeting_becomes_reviewable(self):
        result = await self.run_ok()
        self.assertEqual(result["status"], "SUCCESS")
        stages = await self.stages()
        self.assertEqual({s["state"] for s in stages.values()}, {"ok"})
        self.assertEqual((await self.fetch(m.Meeting, self.meeting.id)).status, "draft")

    async def test_segments_are_stored_with_timestamps(self):
        await self.run_ok()
        self.assertEqual(await self.count(m.TranscriptSegment, meeting_id=self.meeting.id), len(SCRIPT))
        rows = (await self.client.get(f"/api/meetings/{self.meeting.id}/transcript")).json()
        self.assertEqual([r["start_ms"] for r in rows], [s[1] for s in SCRIPT])


    async def test_extraction_output_lands_as_proposals_not_as_facts(self):
        """โมเดลเสนอได้อย่างเดียว — มติจริงเกิดตอนคนกดยืนยันเท่านั้น"""
        await self.run_ok()
        kinds = [
            p.kind
            for p in (await self.proposals())
        ]
        self.assertEqual(kinds.count("new_resolution"), 1)
        self.assertEqual(kinds.count("status_change"), 1)

        #  มติเดิมยังไม่ถูกแตะ แม้ข้อเสนอจะบอกว่าเสร็จแล้ว
        self.assertEqual((await self.fetch(m.Resolution, self.f.open_res.id)).status, "confirmed")
        #  และยังไม่มีมติใหม่เกิดขึ้นในฐานข้อมูล
        self.assertEqual(await self.count(m.Resolution, origin_meeting_id=self.meeting.id), 0)

    async def test_status_change_proposal_also_records_a_referenced_link(self):
        """FR-M4-04 ไทม์ไลน์ต้องเห็นว่ามติเดิมถูกพูดถึงในการประชุมนี้ ตั้งแต่ก่อนมีใครยืนยัน"""
        await self.run_ok()
        links = (await self.client.get(f"/api/resolutions/{self.f.open_res.id}/links")).json()
        from_this_meeting = [l for l in links if l["meeting_id"] == str(self.meeting.id)]
        self.assertEqual(len(from_this_meeting), 1)
        self.assertEqual(from_this_meeting[0]["link_type"], "referenced")

    async def test_confident_alias_binds_the_speaker_without_asking(self):
        """FR-M3-03 alias ที่ยืนยันไว้แล้วใช้ผูกได้เลย"""
        await self.run_ok()
        segments = (await self.client.get(f"/api/meetings/{self.meeting.id}/transcript")).json()
        speaker00 = [s for s in segments if s["speaker_label"] == "SPEAKER_00"]
        self.assertTrue(all(s["person_id"] == str(self.f.chair.id) for s in speaker00))

    async def test_uncertain_speaker_becomes_a_question_not_a_guess(self):
        """§12 ชื่อที่ไม่มั่นใจต้องกลายเป็นข้อเสนอให้คนเลือก ไม่ใช่เดาให้"""
        await self.run_ok()
        speaker_proposals = [p for p in await self.proposals() if p.kind == "speaker_identity"]
        labels = {p.speaker_label for p in speaker_proposals}
        self.assertIn("SPEAKER_01", labels)

        segments = (await self.client.get(f"/api/meetings/{self.meeting.id}/transcript")).json()
        speaker01 = [s for s in segments if s["speaker_label"] == "SPEAKER_01"]
        self.assertTrue(all(s["person_id"] is None for s in speaker01))

    async def test_rerunning_does_not_duplicate_anything(self):
        await self.run_ok()
        first = await self.count(m.Proposal, meeting_id=self.meeting.id)
        await self.run_ok()
        self.assertEqual(await self.count(m.TranscriptSegment, meeting_id=self.meeting.id), len(SCRIPT))
        self.assertEqual(await self.count(m.Proposal, meeting_id=self.meeting.id), first)

    async def test_rerunning_keeps_proposals_a_human_already_decided(self):
        await self.run_ok()
        proposal = next(p for p in await self.proposals() if p.kind == "new_resolution")
        await self.client.post(
            f"/api/meetings/{self.meeting.id}/proposals/{proposal.id}", json={"decision": "rejected"}
        )
        await self.run_ok()
        decided = [p for p in await self.proposals() if p.decision == "rejected"]
        self.assertEqual(len(decided), 1)

    async def proposals(self) -> list[m.Proposal]:
        from sqlalchemy import select

        async with self.sessionmaker() as s:
            rows = await s.execute(select(m.Proposal).where(m.Proposal.meeting_id == self.meeting.id))
            return list(rows.scalars().all())


class SpeakerProposalRules(PipelineCase):
    async def test_speaker_nobody_named_still_needs_a_human(self):
        result = extraction.ExtractionResult(speakers=[])
        with patch.object(tasks, "transcribe_audio", return_value=fake_transcript()), patch.object(
            extraction, "extract", return_value=result
        ):
            await self.run_pipeline()

        from sqlalchemy import select

        async with self.sessionmaker() as s:
            rows = await s.execute(
                select(m.Proposal).where(
                    m.Proposal.meeting_id == self.meeting.id, m.Proposal.kind == "speaker_identity"
                )
            )
            labels = {p.speaker_label for p in rows.scalars().all()}
        self.assertEqual(labels, {"SPEAKER_00", "SPEAKER_01"})


class DueScanner(DbCase):
    """FR-M7-03, 06, 07"""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.f = await build_fixture(self.sessionmaker)

    async def test_queues_reminders_as_pending_approval_only(self):
        result = await tasks._scan_due()
        self.assertGreater(result["queued"], 0)

        from sqlalchemy import select

        async with self.sessionmaker() as s:
            rows = (await s.execute(select(m.OutboundAction))).scalars().all()
        self.assertTrue(rows)
        for action in rows:
            self.assertEqual(action.status, "pending_approval")
            self.assertEqual(action.action_type, "send_resolution_reminder")

    async def test_reminder_quotes_the_resolution_verbatim(self):
        await tasks._scan_due()
        from sqlalchemy import select

        async with self.sessionmaker() as s:
            action = (await s.execute(select(m.OutboundAction))).scalars().first()
        self.assertIn(self.f.open_res.text, action.body)
        self.assertIn(self.f.open_res.ref_no, action.subject)
        self.assertIn(f"เกินกำหนดแล้ว {self.f.overdue_by} วัน", action.subject)

    async def test_reminder_link_is_reachable(self):
        await tasks._scan_due()
        from sqlalchemy import select

        async with self.sessionmaker() as s:
            action = (await s.execute(select(m.OutboundAction))).scalars().first()
        link = action.body.rsplit("\n", 1)[-1].strip()
        r = await self.client.get(link.split("testserver", 1)[1])
        self.assertEqual(r.status_code, 200)

    async def test_recipients_without_email_are_skipped(self):
        """ผู้รับผิดชอบมติที่ติดปัญหาไม่มีอีเมลในทะเบียน จึงไม่ควรมีรายการของเขาในคิว"""
        await tasks._scan_due()
        self.assertEqual(await self.count(m.OutboundAction, recipient_person_id=self.f.it.id), 0)

    async def test_second_scan_does_not_spam_the_same_person(self):
        first = (await tasks._scan_due())["queued"]
        second = (await tasks._scan_due())["queued"]
        self.assertGreater(first, 0)
        self.assertEqual(second, 0)

    async def test_resolutions_beyond_the_lead_window_are_not_queued(self):
        async with self.sessionmaker() as s:
            row = await s.get(m.Resolution, self.f.open_res.id)
            row.due_date = date.today() + timedelta(days=settings.REMINDER_LEAD_DAYS + 30)
            await s.commit()
        await tasks._scan_due()
        self.assertEqual(await self.count(m.OutboundAction, resolution_id=self.f.open_res.id), 0)

    async def test_closed_resolutions_are_never_reminded(self):
        await tasks._scan_due()
        self.assertEqual(await self.count(m.OutboundAction, resolution_id=self.f.done_res.id), 0)
        self.assertEqual(await self.count(m.OutboundAction, resolution_id=self.f.cancelled_res.id), 0)


class OutboundSender(DbCase):
    """FR-M7-01, 09 — ทางออกเดียวคือ MCP และต้องอนุมัติมาก่อนเท่านั้น"""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.f = await build_fixture(self.sessionmaker)
        self.task = MagicMock()
        self.task.retry.return_value = RuntimeError("celery retry")

    async def queue(self, recipient, status) -> m.OutboundAction:
        return (
            await self.add(
                m.OutboundAction(
                    series_id=self.f.series.id, resolution_id=self.f.open_res.id,
                    action_type="send_resolution_reminder", recipient_person_id=recipient.id,
                    subject="แจ้งเตือนมติ", body="เนื้อความแจ้งเตือน", status=status,
                )
            )
        )[0]

    async def test_approved_action_is_sent_through_mcp_and_marked(self):
        action = await self.queue(self.f.supply, m.ActionStatus.APPROVED)
        with patch("app.services.mcp_agent.send_email_via_mcp", new=AsyncMock()) as send:
            result = await tasks._send_action(action.id, self.task)

        self.assertEqual(result["status"], "SENT")
        send.assert_awaited_once()
        self.assertEqual(send.await_args.kwargs["to_email"], self.f.supply.email)

        row = await self.fetch(m.OutboundAction, action.id)
        self.assertEqual(row.status, "sent")
        self.assertIsNotNone(row.sent_at)
        self.assertIsNone(row.error)

    async def test_action_awaiting_approval_is_never_sent(self):
        action = await self.queue(self.f.supply, m.ActionStatus.PENDING_APPROVAL)
        with patch("app.services.mcp_agent.send_email_via_mcp", new=AsyncMock()) as send:
            result = await tasks._send_action(action.id, self.task)

        self.assertEqual(result, {"status": "SKIPPED", "reason": "pending_approval"})
        send.assert_not_awaited()

    async def test_already_sent_action_is_not_sent_twice(self):
        action = await self.queue(self.f.supply, m.ActionStatus.SENT)
        with patch("app.services.mcp_agent.send_email_via_mcp", new=AsyncMock()) as send:
            await tasks._send_action(action.id, self.task)
        send.assert_not_awaited()

    async def test_recipient_without_email_fails_with_a_readable_reason(self):
        action = await self.queue(self.f.it, m.ActionStatus.APPROVED)
        result = await tasks._send_action(action.id, self.task)
        self.assertEqual(result["status"], "FAILED")
        row = await self.fetch(m.OutboundAction, action.id)
        self.assertEqual(row.status, "failed")
        self.assertIn("ไม่มีอีเมล", row.error)

    async def test_mcp_failure_is_recorded_and_retried(self):
        from app.services.mcp_agent import McpError

        action = await self.queue(self.f.supply, m.ActionStatus.APPROVED)
        with patch(
            "app.services.mcp_agent.send_email_via_mcp",
            new=AsyncMock(side_effect=McpError("ต่อ MCP server ไม่ได้")),
        ):
            with self.assertRaises(RuntimeError):
                await tasks._send_action(action.id, self.task)

        row = await self.fetch(m.OutboundAction, action.id)
        self.assertEqual(row.status, "failed")
        self.assertIn("MCP server", row.error)
        self.task.retry.assert_called_once()

    async def test_missing_action_is_skipped(self):
        from uuid import uuid4

        self.assertEqual(await tasks._send_action(uuid4(), self.task), {"status": "SKIPPED"})
