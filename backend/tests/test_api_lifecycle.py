"""
M2 · M4 · M9 — นำเข้าไฟล์ ตรวจทาน รับรอง และวงจรชีวิตของมติ

ชุดนี้คือด่านที่หลักการ "ห้ามละเมิด" ของ requirement ถูกบังคับใช้จริง

    python -m unittest tests.test_api_lifecycle -v
"""

from __future__ import annotations

import tests  # noqa: F401  — ต้องมาก่อน import app เพื่อตั้ง env ของการทดสอบให้ทัน

import os
import shutil
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from app.core.config import settings
from app.db import models as m
from tests.support import DbCase, build_fixture


class UploadCase(DbCase):
    """เคสที่แตะไฟล์จริง — ปิดคิว Celery ไว้ เพราะที่ทดสอบคือด่านรับไฟล์ ไม่ใช่ตัว worker"""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.f = await build_fixture(self.sessionmaker)
        self.task = patch("app.api.meetings.process_meeting_task", MagicMock())
        self.mock_task = self.task.start()
        self.addCleanup(self.task.stop)
        self.addCleanup(lambda: shutil.rmtree(settings.UPLOAD_DIR, ignore_errors=True))

    async def new_meeting(self, sequence_no: int = 9) -> str:
        r = await self.client.post(
            "/api/meetings",
            json={
                "series_id": str(self.f.series.id),
                "sequence_no": sequence_no,
                "meeting_date": "2026-09-20",
            },
        )
        return r.json()["id"]

    async def upload(self, meeting_id: str, name: str, content: bytes, fail: str = "false"):
        return await self.client.post(
            f"/api/meetings/{meeting_id}/upload",
            files={"file": (name, content, "application/octet-stream")},
            data={"simulate_asr_failure": fail},
        )


class Upload(UploadCase):
    """FR-M2-01, 02, 03"""

    async def test_transcript_upload_is_accepted_and_queued(self):
        mid = await self.new_meeting()
        r = await self.upload(mid, "meeting6.txt", "ที่ประชุมมีมติให้ดำเนินการ".encode())
        self.assertEqual(r.status_code, 202)
        self.assertEqual(r.json()["status"], "processing")

        meeting = await self.fetch(m.Meeting, mid)
        self.assertEqual(meeting.status, "processing")
        self.assertEqual(meeting.source_kind, "transcript")
        self.assertTrue(os.path.exists(meeting.audio_uri))
        self.mock_task.delay.assert_called_once()

    async def test_audio_upload_sets_source_kind_audio(self):
        mid = await self.new_meeting()
        await self.upload(mid, "meeting.m4a", b"\x00" * 1024)
        meeting = await self.fetch(m.Meeting, mid)
        self.assertEqual(meeting.source_kind, "audio")

    async def test_upload_resets_pipeline_to_pending(self):
        mid = await self.new_meeting()
        await self.upload(mid, "a.txt", b"x")
        meeting = await self.fetch(m.Meeting, mid)
        self.assertEqual([step["state"] for step in meeting.pipeline], ["pending"] * 5)

    async def test_upload_is_audited(self):
        mid = await self.new_meeting()
        await self.upload(mid, "บันทึกการประชุม.txt", b"x")
        self.assertEqual(await self.count(m.AuditLog, action="upload_meeting"), 1)

    async def test_unsupported_extension_is_415(self):
        mid = await self.new_meeting()
        r = await self.upload(mid, "payload.exe", b"MZ")
        self.assertEqual(r.status_code, 415)
        self.assertIn(".exe", r.json()["detail"])
        self.mock_task.delay.assert_not_called()

    async def test_empty_file_is_422_and_leaves_no_junk(self):
        mid = await self.new_meeting()
        r = await self.upload(mid, "empty.txt", b"")
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"], "ไฟล์ที่อัปโหลดว่างเปล่า")
        self.assertEqual(os.listdir(settings.UPLOAD_DIR), [])

    async def test_oversized_file_is_413_and_partial_write_removed(self):
        mid = await self.new_meeting()
        with patch("app.api.meetings.MAX_UPLOAD_BYTES", 16):
            r = await self.upload(mid, "big.wav", b"\x00" * 4096)
        self.assertEqual(r.status_code, 413)
        self.assertEqual(os.listdir(settings.UPLOAD_DIR), [])

    async def test_upload_to_missing_meeting_is_404(self):
        r = await self.upload("00000000-0000-0000-0000-000000000000", "a.txt", b"x")
        self.assertEqual(r.status_code, 404)


class Retry(UploadCase):
    """FR-M2-05"""

    async def test_retry_requeues_and_resets_pipeline(self):
        mid = await self.new_meeting()
        await self.upload(mid, "a.txt", b"x")
        self.mock_task.reset_mock()

        r = await self.client.post(f"/api/meetings/{mid}/retry")
        self.assertEqual(r.status_code, 202)
        self.mock_task.delay.assert_called_once()
        meeting = await self.fetch(m.Meeting, mid)
        self.assertEqual([step["state"] for step in meeting.pipeline], ["pending"] * 5)

    async def test_retry_without_source_file_is_409(self):
        mid = await self.new_meeting()
        await self.upload(mid, "a.txt", b"x")
        meeting = await self.fetch(m.Meeting, mid)
        os.remove(meeting.audio_uri)

        r = await self.client.post(f"/api/meetings/{mid}/retry")
        self.assertEqual(r.status_code, 409)
        self.assertIn("ไม่พบไฟล์ต้นฉบับ", r.json()["detail"])


class TranscriptAndSpeakers(DbCase):
    """FR-M2-07, 08 · FR-M3-04"""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.f = await build_fixture(self.sessionmaker)
        self.unmapped = (
            await self.add(
                m.TranscriptSegment(
                    meeting_id=self.f.meeting2.id, speaker_label="SPEAKER_01", person_id=None,
                    start_ms=1_040_000, end_ms=1_050_000,
                    text="ขอบคุณท่านประธานครับ ผมจะประสานฝ่ายการเงินก่อน", confidence=0.9,
                )
            )
        )[0]

    async def test_transcript_returned_in_time_order_with_timestamps(self):
        r = await self.client.get(f"/api/meetings/{self.f.meeting2.id}/transcript")
        rows = r.json()
        self.assertEqual([row["start_ms"] for row in rows], [688_000, 1_040_000])
        for row in rows:
            self.assertGreater(row["end_ms"], row["start_ms"])

    async def test_mapping_a_speaker_updates_every_segment_of_that_label(self):
        await self.add(
            m.TranscriptSegment(
                meeting_id=self.f.meeting2.id, speaker_label="SPEAKER_01", person_id=None,
                start_ms=1_200_000, end_ms=1_210_000, text="รับทราบครับ", confidence=0.9,
            )
        )
        r = await self.client.patch(
            f"/api/meetings/{self.f.meeting2.id}/speakers",
            json={"speaker_label": "SPEAKER_01", "person_id": str(self.f.supply.id)},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("2", r.json()["detail"])
        self.assertEqual(
            await self.count(m.TranscriptSegment, speaker_label="SPEAKER_01", person_id=self.f.supply.id), 2
        )

    async def test_confirming_a_speaker_remembers_the_alias_permanently(self):
        await self.client.patch(
            f"/api/meetings/{self.f.meeting2.id}/speakers",
            json={
                "speaker_label": "SPEAKER_01",
                "person_id": str(self.f.supply.id),
                "save_alias": "พี่กาญ",
            },
        )
        aliases = (await self.client.get("/api/people/aliases")).json()
        self.assertIn("พี่กาญ", [a["alias"] for a in aliases])
        self.assertEqual(await self.count(m.AuditLog, action="confirm_alias"), 1)

    async def test_unmapping_a_speaker_is_allowed(self):
        r = await self.client.patch(
            f"/api/meetings/{self.f.meeting2.id}/speakers",
            json={"speaker_label": "SPEAKER_00", "person_id": None},
        )
        self.assertEqual(r.status_code, 200)
        segment = await self.fetch(m.TranscriptSegment, self.f.segment.id)
        self.assertIsNone(segment.person_id)


class ReviewAndApprove(DbCase):
    """M9 — ไม่มีทางอื่นที่ข้อเสนอจะมีผลได้ นอกจากผ่าน endpoint ตัดสินข้อเสนอ"""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.f = await build_fixture(self.sessionmaker)
        self.meeting = (
            await self.add(
                m.Meeting(
                    series_id=self.f.series.id, sequence_no=3, fiscal_year=2569,
                    meeting_date=date(2026, 8, 20), title="การประชุมครั้งที่ 3/2569",
                    source_kind="transcript", status=m.MeetingStatus.DRAFT,
                    pipeline=[{"stage": "done", "state": "ok"}],
                )
            )
        )[0]
        self.segment = (
            await self.add(
                m.TranscriptSegment(
                    meeting_id=self.meeting.id, speaker_label="SPEAKER_00",
                    person_id=self.f.chair.id, start_ms=471_000, end_ms=480_000,
                    text="ถือว่าเรื่องนี้ดำเนินการเสร็จแล้ว ขอบคุณครับ", confidence=0.93,
                )
            )
        )[0]

    async def add_proposal(self, **kwargs) -> m.Proposal:
        defaults = dict(
            meeting_id=self.meeting.id, title="ข้อเสนอ", evidence_text=self.segment.text,
            evidence_start_ms=self.segment.start_ms, segment_id=self.segment.id, confidence=0.9,
        )
        defaults.update(kwargs)
        return (await self.add(m.Proposal(**defaults)))[0]

    async def review(self) -> dict:
        r = await self.client.get(f"/api/meetings/{self.meeting.id}/review")
        self.assertEqual(r.status_code, 200)
        return r.json()

    # ── หน้าตรวจทาน ────────────────────────────────────────────────────

    async def test_review_bundles_everything_the_reviewer_needs(self):
        await self.add_proposal(kind="new_resolution", title="มติใหม่")
        body = await self.review()
        self.assertEqual(set(body), {
            "meeting", "segments", "proposals", "created_resolutions",
            "closed_resolutions", "blockers", "can_approve",
        })
        self.assertEqual(len(body["segments"]), 1)
        self.assertEqual(len(body["proposals"]), 1)

    async def test_review_reports_blockers(self):
        await self.add_proposal(kind="new_resolution", title="มติใหม่")
        await self.add(
            m.TranscriptSegment(
                meeting_id=self.meeting.id, speaker_label="SPEAKER_02", person_id=None,
                start_ms=900_000, end_ms=905_000, text="ครับ", confidence=0.8,
            )
        )
        body = await self.review()
        self.assertEqual(body["blockers"]["pending_proposals"], 1)
        self.assertEqual(body["blockers"]["unmapped_speakers"], ["SPEAKER_02"])
        self.assertFalse(body["can_approve"])

    async def test_review_allows_approve_when_clean(self):
        self.assertTrue((await self.review())["can_approve"])

    async def test_review_of_missing_meeting_is_404(self):
        r = await self.client.get("/api/meetings/00000000-0000-0000-0000-000000000000/review")
        self.assertEqual(r.status_code, 404)

    # ── ตัดสินข้อเสนอ ──────────────────────────────────────────────────

    async def test_accepting_new_resolution_uses_the_edited_values(self):
        """FR-M9-02 ทุกอย่างที่โมเดลผลิตต้องแก้ได้ก่อนยืนยัน"""
        proposal = await self.add_proposal(kind="new_resolution", title="ข้อความที่โมเดลเสนอ")
        due = (date.today() + timedelta(days=30)).isoformat()
        r = await self.client.post(
            f"/api/meetings/{self.meeting.id}/proposals/{proposal.id}",
            json={
                "decision": "accepted",
                "text": "ข้อความที่เลขานุการแก้แล้ว",
                "assignee_ids": [str(self.f.supply.id)],
                "due_date": due,
            },
        )
        self.assertEqual(r.status_code, 200)

        rows = (await self.client.get(f"/api/series/{self.f.series.id}/resolutions")).json()
        created = [row for row in rows if row["origin_meeting_id"] == str(self.meeting.id)]
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]["text"], "ข้อความที่เลขานุการแก้แล้ว")
        self.assertEqual(created[0]["due_date"], due)
        self.assertEqual(created[0]["assignee_ids"], [str(self.f.supply.id)])
        #  มติที่เพิ่งยืนยันยังไม่มีผลผูกพันจนกว่ารายงานจะถูกรับรอง
        self.assertEqual(created[0]["status"], "proposed")

    async def test_accepting_new_resolution_numbers_it_and_links_evidence(self):
        proposal = await self.add_proposal(kind="new_resolution", title="มติใหม่")
        await self.client.post(
            f"/api/meetings/{self.meeting.id}/proposals/{proposal.id}", json={"decision": "accepted"}
        )
        rows = (await self.client.get(f"/api/series/{self.f.series.id}/resolutions")).json()
        created = next(r for r in rows if r["origin_meeting_id"] == str(self.meeting.id))
        self.assertEqual(created["ref_no"], "มติ 3/2569 ข้อ 4.1")

        links = (await self.client.get(f"/api/resolutions/{created['id']}/links")).json()
        self.assertEqual(links[0]["link_type"], "created")
        self.assertEqual(links[0]["evidence_text"], self.segment.text)
        self.assertEqual(links[0]["evidence_start_ms"], self.segment.start_ms)

    async def test_accepting_status_change_moves_the_existing_resolution(self):
        proposal = await self.add_proposal(
            kind="status_change", resolution_id=self.f.open_res.id, proposed_status="done",
            title="เสนอปิดมติ", confidence=0.95,
        )
        r = await self.client.post(
            f"/api/meetings/{self.meeting.id}/proposals/{proposal.id}", json={"decision": "accepted"}
        )
        self.assertEqual(r.status_code, 200)
        resolution = await self.fetch(m.Resolution, self.f.open_res.id)
        self.assertEqual(resolution.status, "done")
        self.assertEqual(resolution.closed_meeting_id, self.meeting.id)
        self.assertIsNotNone(resolution.closed_at)

    async def test_rejecting_a_proposal_changes_nothing(self):
        proposal = await self.add_proposal(
            kind="status_change", resolution_id=self.f.open_res.id, proposed_status="done",
            title="เสนอปิดมติ",
        )
        r = await self.client.post(
            f"/api/meetings/{self.meeting.id}/proposals/{proposal.id}", json={"decision": "rejected"}
        )
        self.assertEqual(r.status_code, 200)
        resolution = await self.fetch(m.Resolution, self.f.open_res.id)
        self.assertEqual(resolution.status, "confirmed")

    async def test_deciding_twice_is_409(self):
        proposal = await self.add_proposal(kind="new_resolution", title="มติใหม่")
        await self.client.post(
            f"/api/meetings/{self.meeting.id}/proposals/{proposal.id}", json={"decision": "accepted"}
        )
        r = await self.client.post(
            f"/api/meetings/{self.meeting.id}/proposals/{proposal.id}", json={"decision": "accepted"}
        )
        self.assertEqual(r.status_code, 409)

    async def test_proposal_from_another_meeting_is_400(self):
        proposal = await self.add_proposal(kind="new_resolution", title="มติใหม่")
        r = await self.client.post(
            f"/api/meetings/{self.f.meeting1.id}/proposals/{proposal.id}",
            json={"decision": "accepted"},
        )
        self.assertEqual(r.status_code, 400)

    async def test_speaker_identity_without_person_is_422(self):
        """§12 ห้ามเดาชื่อคน — ยืนยันโดยไม่บอกว่าใครไม่ได้"""
        proposal = await self.add_proposal(
            kind="speaker_identity", speaker_label="SPEAKER_00", title="ระบุตัวผู้พูด", confidence=0.4
        )
        r = await self.client.post(
            f"/api/meetings/{self.meeting.id}/proposals/{proposal.id}", json={"decision": "accepted"}
        )
        self.assertEqual(r.status_code, 422)
        self.assertIn("ต้องระบุ", r.json()["detail"])

    async def test_speaker_identity_with_person_maps_and_remembers(self):
        proposal = await self.add_proposal(
            kind="speaker_identity", speaker_label="SPEAKER_00", title="ระบุตัวผู้พูด", confidence=0.4
        )
        r = await self.client.post(
            f"/api/meetings/{self.meeting.id}/proposals/{proposal.id}",
            json={
                "decision": "accepted",
                "person_id": str(self.f.supply.id),
                "save_alias": "พี่กาญ",
            },
        )
        self.assertEqual(r.status_code, 200)
        segment = await self.fetch(m.TranscriptSegment, self.segment.id)
        self.assertEqual(segment.person_id, self.f.supply.id)
        aliases = (await self.client.get("/api/people/aliases")).json()
        self.assertIn("พี่กาญ", [a["alias"] for a in aliases])

    async def test_accepting_is_audited(self):
        proposal = await self.add_proposal(kind="new_resolution", title="มติใหม่")
        await self.client.post(
            f"/api/meetings/{self.meeting.id}/proposals/{proposal.id}", json={"decision": "accepted"}
        )
        self.assertEqual(await self.count(m.AuditLog, action="accept_proposal"), 1)

    # ── รับรองรายงาน ───────────────────────────────────────────────────

    async def test_cannot_approve_with_pending_proposals(self):
        await self.add_proposal(kind="new_resolution", title="มติใหม่")
        r = await self.client.post(f"/api/meetings/{self.meeting.id}/approve")
        self.assertEqual(r.status_code, 409)
        self.assertIn("ข้อเสนอรอการตรวจ", r.json()["detail"])

    async def test_cannot_approve_with_unidentified_speakers(self):
        await self.add(
            m.TranscriptSegment(
                meeting_id=self.meeting.id, speaker_label="SPEAKER_09", person_id=None,
                start_ms=1, end_ms=2, text="ครับ", confidence=0.5,
            )
        )
        r = await self.client.post(f"/api/meetings/{self.meeting.id}/approve")
        self.assertEqual(r.status_code, 409)
        self.assertIn("ผู้พูดที่ยังไม่ได้ระบุตัว", r.json()["detail"])

    async def test_cannot_approve_while_processing(self):
        async with self.sessionmaker() as s:
            meeting = await s.get(m.Meeting, self.meeting.id)
            meeting.status = m.MeetingStatus.PROCESSING
            await s.commit()
        r = await self.client.post(f"/api/meetings/{self.meeting.id}/approve")
        self.assertEqual(r.status_code, 409)

    async def test_cannot_approve_after_failure(self):
        async with self.sessionmaker() as s:
            meeting = await s.get(m.Meeting, self.meeting.id)
            meeting.status = m.MeetingStatus.FAILED
            await s.commit()
        r = await self.client.post(f"/api/meetings/{self.meeting.id}/approve")
        self.assertEqual(r.status_code, 409)

    async def test_approve_promotes_proposed_resolutions_to_confirmed(self):
        proposal = await self.add_proposal(kind="new_resolution", title="มติใหม่")
        await self.client.post(
            f"/api/meetings/{self.meeting.id}/proposals/{proposal.id}", json={"decision": "accepted"}
        )
        from urllib.parse import quote

        r = await self.client.post(
            f"/api/meetings/{self.meeting.id}/approve",
            headers={"X-Actor": quote("นางสาวปรียานุช วัฒนสิน")},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "approved")
        self.assertEqual(r.json()["approved_by"], "นางสาวปรียานุช วัฒนสิน")
        self.assertIsNotNone(r.json()["approved_at"])

        rows = (await self.client.get(f"/api/series/{self.f.series.id}/resolutions")).json()
        created = next(r for r in rows if r["origin_meeting_id"] == str(self.meeting.id))
        self.assertEqual(created["status"], "confirmed")
        self.assertEqual(await self.count(m.AuditLog, action="meeting_approved"), 1)

    async def test_approving_never_closes_a_resolution_by_itself(self):
        """
        FR-M4-06 · §4.2 — จุดที่ระบบมีสิทธิ์เปลี่ยนสถานะเองมีเพียง proposed → confirmed
        ข้อเสนอปิดมติที่ถูกปฏิเสธไว้ ต้องไม่ถูกปิดตอนรับรองรายงาน
        """
        proposal = await self.add_proposal(
            kind="status_change", resolution_id=self.f.open_res.id, proposed_status="done",
            title="เสนอปิดมติ", confidence=0.99,
        )
        await self.client.post(
            f"/api/meetings/{self.meeting.id}/proposals/{proposal.id}", json={"decision": "rejected"}
        )
        r = await self.client.post(f"/api/meetings/{self.meeting.id}/approve")
        self.assertEqual(r.status_code, 200)

        resolution = await self.fetch(m.Resolution, self.f.open_res.id)
        self.assertEqual(resolution.status, "confirmed")
        self.assertIsNone(resolution.closed_at)


class ResolutionLifecycle(DbCase):
    """FR-M4-03, 08, 09 · §4.1"""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.f = await build_fixture(self.sessionmaker)

    async def set_status(self, resolution, status: str, **extra):
        return await self.client.post(
            f"/api/resolutions/{resolution.id}/status", json={"status": status, **extra}
        )

    async def test_get_resolution_includes_assignees(self):
        r = await self.client.get(f"/api/resolutions/{self.f.open_res.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["assignee_ids"]), 2)

    async def test_missing_resolution_is_404_thai(self):
        r = await self.client.get("/api/resolutions/00000000-0000-0000-0000-000000000000")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["detail"], "ไม่พบมติ")

    async def test_links_are_in_chronological_order(self):
        r = await self.client.get(f"/api/resolutions/{self.f.blocked_res.id}/links")
        types = [link["link_type"] for link in r.json()]
        self.assertEqual(types, ["created", "progress_reported"])

    # ── state machine ─────────────────────────────────────────────────

    async def test_every_allowed_transition_is_accepted(self):
        allowed = m.ResolutionStatus.TRANSITIONS
        for source, targets in allowed.items():
            for target in targets:
                with self.subTest(source=source, target=target):
                    row = (
                        await self.add(
                            m.Resolution(
                                series_id=self.f.series.id, ref_no=f"มติ ทดสอบ {source}->{target}",
                                text="มติสำหรับทดสอบการเปลี่ยนสถานะ", status=source,
                            )
                        )
                    )[0]
                    r = await self.set_status(row, target, reason="เหตุผลประกอบการเปลี่ยนสถานะ")
                    self.assertEqual(r.status_code, 200, r.text)
                    self.assertEqual(r.json()["status"], target)

    async def test_every_forbidden_transition_is_409(self):
        statuses = list(m.ResolutionStatus.TRANSITIONS)
        for source in statuses:
            allowed = set(m.ResolutionStatus.TRANSITIONS[source])
            for target in statuses:
                if target == source or target in allowed:
                    continue
                with self.subTest(source=source, target=target):
                    row = (
                        await self.add(
                            m.Resolution(
                                series_id=self.f.series.id, ref_no=f"มติ ห้าม {source}->{target}",
                                text="มติสำหรับทดสอบการเปลี่ยนสถานะที่ต้องถูกปฏิเสธ", status=source,
                            )
                        )
                    )[0]
                    r = await self.set_status(row, target, reason="พยายามข้ามขั้น")
                    self.assertEqual(r.status_code, 409, r.text)
                    self.assertIn("state machine", r.json()["detail"])

    async def test_superseded_is_terminal(self):
        row = (
            await self.add(
                m.Resolution(
                    series_id=self.f.series.id, ref_no="มติ ถูกแทนที่",
                    text="มติที่ถูกแทนที่แล้ว", status=m.ResolutionStatus.SUPERSEDED,
                )
            )
        )[0]
        for target in ("confirmed", "in_progress", "done", "cancelled"):
            r = await self.set_status(row, target, reason="ลองเปลี่ยน")
            self.assertEqual(r.status_code, 409)

    async def test_closing_without_reason_is_422(self):
        r = await self.set_status(self.f.open_res, "done", reason="   ")
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"], "การปิดหรือยกเลิกมติต้องระบุเหตุผลกำกับเสมอ")
        resolution = await self.fetch(m.Resolution, self.f.open_res.id)
        self.assertEqual(resolution.status, "confirmed")

    async def test_cancelling_without_reason_is_422(self):
        r = await self.set_status(self.f.open_res, "cancelled")
        self.assertEqual(r.status_code, 422)

    async def test_closing_with_reason_records_everything(self):
        r = await self.set_status(
            self.f.open_res, "done", reason="ฝ่ายพัสดุส่งร่าง TOR ครบแล้ว",
            meeting_id=str(self.f.meeting2.id), evidence="ที่ประชุมรับทราบและถือว่าแล้วเสร็จ",
            evidence_start_ms=900_000,
        )
        self.assertEqual(r.status_code, 200)

        history = (await self.client.get(f"/api/resolutions/{self.f.open_res.id}/history")).json()
        self.assertEqual(history[0]["field"], "status")
        self.assertEqual(history[0]["old_value"], "confirmed")
        self.assertEqual(history[0]["new_value"], "done")
        self.assertEqual(history[0]["reason"], "ฝ่ายพัสดุส่งร่าง TOR ครบแล้ว")

        links = (await self.client.get(f"/api/resolutions/{self.f.open_res.id}/links")).json()
        self.assertEqual(links[-1]["link_type"], "closed")
        self.assertEqual(links[-1]["evidence_start_ms"], 900_000)
        self.assertEqual(await self.count(m.AuditLog, action="change_resolution_status"), 1)

    async def test_reopening_clears_the_closed_marks(self):
        await self.set_status(self.f.open_res, "done", reason="เสร็จแล้ว")
        await self.set_status(self.f.open_res, "in_progress", reason="พบว่ายังไม่ครบ ขอเปิดใหม่")
        resolution = await self.fetch(m.Resolution, self.f.open_res.id)
        self.assertEqual(resolution.status, "in_progress")
        self.assertIsNone(resolution.closed_at)
        self.assertIsNone(resolution.closed_meeting_id)

    async def test_same_status_is_a_no_op(self):
        r = await self.set_status(self.f.open_res, "confirmed")
        self.assertEqual(r.status_code, 200)
        history = (await self.client.get(f"/api/resolutions/{self.f.open_res.id}/history")).json()
        self.assertEqual(history, [])

    async def test_confirming_from_a_meeting_replaces_the_referenced_link(self):
        """ระบบเคยบันทึกลิงก์ referenced ตอนสกัด — พอคนยืนยันแล้วต้องไม่เหลือหลักฐานซ้ำสองบรรทัด"""
        await self.add(
            m.ResolutionLink(
                resolution_id=self.f.open_res.id, meeting_id=self.f.meeting1.id,
                link_type=m.LinkType.REFERENCED, evidence_text="ระบบบันทึกไว้ตอนสกัด",
                confidence=0.8,
            )
        )
        await self.set_status(
            self.f.open_res, "in_progress", reason="เริ่มดำเนินการ", meeting_id=str(self.f.meeting1.id)
        )
        links = (await self.client.get(f"/api/resolutions/{self.f.open_res.id}/links")).json()
        from_meeting1 = [link for link in links if link["meeting_id"] == str(self.f.meeting1.id)]
        self.assertEqual(len(from_meeting1), 1)
        self.assertEqual(from_meeting1[0]["link_type"], "progress_reported")

    # ── แก้ไขด้วยมือ ──────────────────────────────────────────────────

    async def test_patch_text_records_history(self):
        r = await self.client.patch(
            f"/api/resolutions/{self.f.open_res.id}",
            json={"text": "ข้อความมติที่แก้ไขแล้ว", "reason": "ที่ประชุมขอปรับถ้อยคำ"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["text"], "ข้อความมติที่แก้ไขแล้ว")
        history = (await self.client.get(f"/api/resolutions/{self.f.open_res.id}/history")).json()
        self.assertEqual(history[0]["field"], "text")
        self.assertEqual(history[0]["reason"], "ที่ประชุมขอปรับถ้อยคำ")

    async def test_pushing_the_due_date_out_counts_as_a_postponement(self):
        later = (self.f.open_res.due_date + timedelta(days=30)).isoformat()
        r = await self.client.patch(
            f"/api/resolutions/{self.f.open_res.id}", json={"due_date": later}
        )
        self.assertEqual(r.json()["postpone_count"], 1)

    async def test_pulling_the_due_date_in_is_not_a_postponement(self):
        sooner = (self.f.open_res.due_date - timedelta(days=5)).isoformat()
        r = await self.client.patch(
            f"/api/resolutions/{self.f.open_res.id}", json={"due_date": sooner}
        )
        self.assertEqual(r.json()["postpone_count"], 0)

    async def test_changing_assignees_records_history(self):
        r = await self.client.patch(
            f"/api/resolutions/{self.f.open_res.id}",
            json={"assignee_ids": [str(self.f.it.id)]},
        )
        self.assertEqual(r.json()["assignee_ids"], [str(self.f.it.id)])
        fields = [h["field"] for h in (await self.client.get(f"/api/resolutions/{self.f.open_res.id}/history")).json()]
        self.assertIn("assignee_ids", fields)

    async def test_patch_with_identical_values_writes_no_history(self):
        r = await self.client.patch(
            f"/api/resolutions/{self.f.open_res.id}", json={"text": self.f.open_res.text}
        )
        self.assertEqual(r.status_code, 200)
        history = (await self.client.get(f"/api/resolutions/{self.f.open_res.id}/history")).json()
        self.assertEqual(history, [])

    async def test_history_is_newest_first(self):
        await self.client.patch(f"/api/resolutions/{self.f.open_res.id}", json={"text": "แก้ครั้งที่ 1"})
        await self.client.patch(f"/api/resolutions/{self.f.open_res.id}", json={"text": "แก้ครั้งที่ 2"})
        history = (await self.client.get(f"/api/resolutions/{self.f.open_res.id}/history")).json()
        self.assertEqual(history[0]["new_value"], "แก้ครั้งที่ 2")
