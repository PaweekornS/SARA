"""
M5 · M7 — ร่างระเบียบวาระ เอกสาร .docx คิวส่งออก และ magic link

    python -m unittest tests.test_api_output -v
"""

from __future__ import annotations

import tests  # noqa: F401  — ต้องมาก่อน import app เพื่อตั้ง env ของการทดสอบให้ทัน

import io
import zipfile
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from app.core.security import magic_link_url, make_magic_token
from app.db import models as m
from app.services.thai_format import thai_date
from tests.support import DbCase, build_fixture


def docx_text(blob: bytes) -> str:
    """ดึงข้อความทั้งหมดออกจากไฟล์ .docx โดยไม่ต้องเปิด Word"""
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


class AgendaGeneration(DbCase):
    """FR-M5-01 ถึง 03 · FR-M9-04"""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.f = await build_fixture(self.sessionmaker)

    async def generate(self):
        return await self.client.post(f"/api/series/{self.f.series.id}/agenda/generate")

    async def test_generate_produces_the_official_five_sections(self):
        r = await self.generate()
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertEqual(body["target_sequence_no"], 3)
        self.assertEqual(body["target_meeting_date"], "2026-09-20")
        self.assertEqual(sorted({item["section_no"] for item in body["items"]}), [1, 2, 3, 4, 5])

    async def test_section_two_points_at_the_previous_meeting(self):
        items = (await self.generate()).json()["items"]
        section2 = next(i for i in items if i["section_no"] == 2)
        self.assertIn("ครั้งที่ 2/2569", section2["title"])

    async def test_section_three_lists_every_open_resolution_worst_first(self):
        items = (await self.generate()).json()["items"]
        section3 = [i for i in items if i["section_no"] == 3]
        self.assertEqual(len(section3), 2)  # confirmed + blocked · ไม่รวม done/cancelled
        self.assertEqual(section3[0]["resolution_id"], str(self.f.open_res.id))

    async def test_section_three_body_carries_all_required_details(self):
        """FR-M5-03 ต้องมีครบ: มติเดิม · ที่มา · ผู้รับผิดชอบ · กำหนด · สถานะ · วันที่เกิน"""
        items = (await self.generate()).json()["items"]
        body = next(i for i in items if i["resolution_id"] == str(self.f.open_res.id))["body"]
        self.assertIn("มติเดิม:", body)
        self.assertIn("ที่มา: การประชุมครั้งที่ 2/2569", body)
        self.assertIn(self.f.open_res.ref_no, body)
        self.assertIn("ผู้รับผิดชอบ: ฝ่ายพัสดุ, นางกาญจนา พูลสวัสดิ์", body)
        self.assertIn(f"กำหนดแล้วเสร็จ: {thai_date(self.f.open_res.due_date)}", body)
        self.assertIn("สถานะปัจจุบัน: รับรองแล้ว", body)
        self.assertIn(f"เกินกำหนดแล้ว {self.f.overdue_by} วัน", body)

    async def test_section_three_flags_repeatedly_postponed_items(self):
        items = (await self.generate()).json()["items"]
        body = next(i for i in items if i["resolution_id"] == str(self.f.blocked_res.id))["body"]
        self.assertIn("ถูกเลื่อนกำหนดมาแล้ว 3 ครั้ง", body)

    async def test_agenda_topic_keeps_the_full_text(self):
        """หัวข้อถูกเขียนลงเอกสารราชการโดยตรง จึงห้ามมีจุดไข่ปลาตัดข้อความ"""
        items = (await self.generate()).json()["items"]
        for item in items:
            self.assertNotIn("…", item["title"])
            self.assertNotIn("...", item["title"])

    async def test_generate_is_blocked_by_unapproved_meetings(self):
        """FR-M9-04 มติจากรายงานที่ยังไม่รับรองยังไม่มีผลผูกพัน"""
        await self.add(
            m.Meeting(
                series_id=self.f.series.id, sequence_no=3, fiscal_year=2569,
                meeting_date=date(2026, 8, 20), source_kind="audio", status=m.MeetingStatus.DRAFT,
            )
        )
        r = await self.generate()
        self.assertEqual(r.status_code, 409)
        self.assertIn("ยังไม่ได้รับรองรายงาน", r.json()["detail"])

    async def test_generate_is_blocked_while_a_meeting_is_processing(self):
        await self.add(
            m.Meeting(
                series_id=self.f.series.id, sequence_no=4, fiscal_year=2569,
                meeting_date=date(2026, 8, 20), source_kind="audio",
                status=m.MeetingStatus.PROCESSING,
            )
        )
        self.assertEqual((await self.generate()).status_code, 409)

    async def test_regenerating_replaces_the_previous_draft(self):
        first = (await self.generate()).json()
        second = (await self.generate()).json()
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(await self.count(m.AgendaDraft, series_id=self.f.series.id), 1)

    async def test_generate_is_audited(self):
        await self.generate()
        self.assertEqual(await self.count(m.AuditLog, action="generate_agenda"), 1)

    async def test_series_without_meetings_still_produces_a_draft(self):
        r = await self.client.post(f"/api/series/{self.f.other_series.id}/agenda/generate")
        self.assertEqual(r.status_code, 201)
        items = r.json()["items"]
        section2 = next(i for i in items if i["section_no"] == 2)
        self.assertIn("ยังไม่มีการประชุมครั้งก่อน", section2["body"])

    async def test_generate_for_missing_series_is_404(self):
        r = await self.client.post(
            "/api/series/00000000-0000-0000-0000-000000000000/agenda/generate"
        )
        self.assertEqual(r.status_code, 404)


class AgendaEditingAndExport(DbCase):
    """FR-M5-04, 05, 07"""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.f = await build_fixture(self.sessionmaker)
        self.draft = (
            await self.client.post(f"/api/series/{self.f.series.id}/agenda/generate")
        ).json()

    async def test_get_agenda(self):
        r = await self.client.get(f"/api/agenda/{self.draft['id']}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["items"]), len(self.draft["items"]))

    async def test_missing_agenda_is_404(self):
        r = await self.client.get("/api/agenda/00000000-0000-0000-0000-000000000000")
        self.assertEqual(r.status_code, 404)

    async def test_patch_items_replaces_the_whole_list_in_order(self):
        items = [
            {"section_no": 1, "item_no": 1, "title": "เรื่องที่ประธานแจ้ง", "body": ""},
            {"section_no": 4, "item_no": 1, "title": "เรื่องที่เลขานุการเพิ่มเอง", "body": "รายละเอียด"},
        ]
        r = await self.client.patch(f"/api/agenda/{self.draft['id']}/items", json={"items": items})
        self.assertEqual(r.status_code, 200)
        out = r.json()["items"]
        self.assertEqual(len(out), 2)
        self.assertEqual([i["sort_order"] for i in out], [0, 1])
        self.assertEqual(out[1]["title"], "เรื่องที่เลขานุการเพิ่มเอง")

    async def test_patch_items_can_reorder(self):
        original = self.draft["items"]
        reversed_items = [
            {
                "section_no": i["section_no"], "item_no": i["item_no"], "title": i["title"],
                "body": i["body"], "resolution_id": i["resolution_id"],
            }
            for i in reversed(original)
        ]
        r = await self.client.patch(
            f"/api/agenda/{self.draft['id']}/items", json={"items": reversed_items}
        )
        self.assertEqual(r.json()["items"][0]["title"], original[-1]["title"])

    async def test_export_agenda_docx(self):
        r = await self.client.get(f"/api/agenda/{self.draft['id']}/export")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.headers["content-type"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.assertIn("agenda-3-2569.docx", r.headers["content-disposition"])

        xml = docx_text(r.content)
        self.assertIn("ระเบียบวาระ", xml)
        self.assertIn("ครุภัณฑ์คอมพิวเตอร์", xml)  # ข้อความมติเต็ม ไม่ถูกตัด

    async def test_exported_agenda_uses_thai_official_typography(self):
        r = await self.client.get(f"/api/agenda/{self.draft['id']}/export")
        xml = docx_text(r.content)
        self.assertIn("TH Sarabun New", xml)
        #  เลขวาระเป็นเลขไทย และปีเป็นพุทธศักราช
        self.assertIn("๓", xml)
        self.assertIn("๒๕๖๙", xml)

    async def test_export_rejects_other_formats(self):
        r = await self.client.get(f"/api/agenda/{self.draft['id']}/export?format=pdf")
        self.assertEqual(r.status_code, 400)

    async def test_agenda_summary_rows(self):
        r = await self.client.get(f"/api/agenda/{self.draft['id']}/summary")
        self.assertEqual(r.status_code, 200)
        rows = r.json()["rows"]
        self.assertEqual(len(rows), 2)
        top = rows[0]
        self.assertEqual(top["ref_no"], self.f.open_res.ref_no)
        self.assertEqual(top["status"], "รับรองแล้ว")
        self.assertEqual(top["overdue"], self.f.overdue_by)
        self.assertEqual(top["assignees"], "ฝ่ายพัสดุ, นางกาญจนา พูลสวัสดิ์")

    async def test_export_minutes_docx(self):
        r = await self.client.get(f"/api/meetings/{self.f.meeting2.id}/export")
        self.assertEqual(r.status_code, 200)
        self.assertIn("minutes-2-2569.docx", r.headers["content-disposition"])
        xml = docx_text(r.content)
        self.assertIn("รายงานการประชุม", xml)
        self.assertIn("นายธนกฤต", xml)          # ผู้เข้าประชุมมาจากผู้พูดที่ระบุตัวแล้ว
        self.assertIn("ครุภัณฑ์คอมพิวเตอร์", xml)  # ตารางมติที่เกิดในการประชุมนี้

    async def test_export_minutes_rejects_other_formats(self):
        r = await self.client.get(f"/api/meetings/{self.f.meeting2.id}/export?format=pdf")
        self.assertEqual(r.status_code, 400)


class OutboundQueue(DbCase):
    """FR-M7-07, 09 — ไม่มีเส้นทางไหนที่ส่งออกได้โดยไม่ผ่านการอนุมัติ"""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.f = await build_fixture(self.sessionmaker)
        self.sender = patch("app.api.actions.send_outbound_action_task", MagicMock())
        self.mock_sender = self.sender.start()
        self.addCleanup(self.sender.stop)
        self.action = await self.queue(self.f.supply)

    async def queue(self, recipient, status=m.ActionStatus.PENDING_APPROVAL) -> m.OutboundAction:
        return (
            await self.add(
                m.OutboundAction(
                    series_id=self.f.series.id, resolution_id=self.f.open_res.id,
                    action_type="send_resolution_reminder", recipient_person_id=recipient.id,
                    subject=f"แจ้งเตือน: {self.f.open_res.ref_no} เกินกำหนดแล้ว",
                    body="ระบบขอแจ้งเตือนมติที่อยู่ในความรับผิดชอบของท่าน", status=status,
                )
            )
        )[0]

    async def test_queued_actions_start_as_pending_approval(self):
        r = await self.client.get("/api/actions/pending")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 1)
        self.assertEqual(r.json()[0]["status"], "pending_approval")

    async def test_list_actions_can_filter_by_status(self):
        await self.queue(self.f.chair, status=m.ActionStatus.SENT)
        self.assertEqual(len((await self.client.get("/api/actions")).json()), 2)
        self.assertEqual(len((await self.client.get("/api/actions?status=sent")).json()), 1)

    async def test_get_action(self):
        r = await self.client.get(f"/api/actions/{self.action.id}")
        self.assertEqual(r.status_code, 200)
        self.assertIn("แจ้งเตือน", r.json()["subject"])

    async def test_missing_action_is_404(self):
        r = await self.client.get("/api/actions/00000000-0000-0000-0000-000000000000")
        self.assertEqual(r.status_code, 404)

    async def test_approve_marks_approver_and_hands_off_to_the_worker(self):
        from urllib.parse import quote

        r = await self.client.post(
            f"/api/actions/{self.action.id}/approve",
            headers={"X-Actor": quote("นางสาวปรียานุช วัฒนสิน")},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "approved")
        self.assertEqual(r.json()["approved_by"], "นางสาวปรียานุช วัฒนสิน")
        self.mock_sender.delay.assert_called_once_with(str(self.action.id))
        self.assertEqual(await self.count(m.AuditLog, action="approve_outbound_action"), 1)

    async def test_approving_twice_is_409(self):
        await self.client.post(f"/api/actions/{self.action.id}/approve")
        r = await self.client.post(f"/api/actions/{self.action.id}/approve")
        self.assertEqual(r.status_code, 409)

    async def test_recipient_without_email_cannot_be_approved(self):
        action = await self.queue(self.f.it)  # ผู้รับที่ไม่มีอีเมลในทะเบียน
        r = await self.client.post(f"/api/actions/{action.id}/approve")
        self.assertEqual(r.status_code, 422)
        self.assertIn("ยังไม่มีอีเมล", r.json()["detail"])
        self.assertEqual((await self.fetch(m.OutboundAction, action.id)).status, "pending_approval")
        self.mock_sender.delay.assert_not_called()

    async def test_cancel_before_sending(self):
        r = await self.client.post(f"/api/actions/{self.action.id}/cancel")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "cancelled")
        self.assertEqual(await self.count(m.AuditLog, action="cancel_outbound_action"), 1)

    async def test_cannot_cancel_something_already_sent(self):
        action = await self.queue(self.f.chair, status=m.ActionStatus.SENT)
        r = await self.client.post(f"/api/actions/{action.id}/cancel")
        self.assertEqual(r.status_code, 409)
        self.assertIn("ส่งออกไปแล้ว", r.json()["detail"])

    async def test_retry_only_applies_to_failed_actions(self):
        r = await self.client.post(f"/api/actions/{self.action.id}/retry")
        self.assertEqual(r.status_code, 409)

    async def test_retry_clears_the_error_and_requeues(self):
        action = await self.queue(self.f.supply, status=m.ActionStatus.FAILED)
        async with self.sessionmaker() as s:
            row = await s.get(m.OutboundAction, action.id)
            row.error = "SMTP ปฏิเสธการเชื่อมต่อ"
            await s.commit()

        r = await self.client.post(f"/api/actions/{action.id}/retry")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "approved")
        self.assertIsNone(r.json()["error"])
        self.mock_sender.delay.assert_called_once_with(str(action.id))


class MagicLink(DbCase):
    """FR-M7-08 · §4.2 — ลิงก์นี้อัปเดตมติได้ข้อเดียว และปิดมติไม่ได้เด็ดขาด"""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.f = await build_fixture(self.sessionmaker)
        self.token = make_magic_token(self.f.open_res.id, self.f.supply.id)

    async def test_generated_url_points_at_a_route_that_exists(self):
        """ลิงก์ที่ส่งไปกับอีเมลต้องเปิดได้จริง ไม่ใช่ 404"""
        url = magic_link_url(self.f.open_res.id, self.f.supply.id)
        path = url.split("testserver", 1)[1]
        r = await self.client.get(path)
        self.assertEqual(r.status_code, 200, f"เปิด {path} ไม่ได้")

    async def test_page_shows_the_resolution_verbatim(self):
        r = await self.client.get(f"/api/public/resolutions/{self.token}")
        self.assertEqual(r.status_code, 200)
        self.assertIn(self.f.open_res.text, r.text)
        self.assertIn(self.f.supply.full_name, r.text)
        self.assertIn(f"เกินกำหนดแล้ว {self.f.overdue_by} วัน", r.text)

    async def test_page_offers_only_progress_reporting_never_closing(self):
        r = await self.client.get(f"/api/public/resolutions/{self.token}")
        self.assertIn('value="in_progress"', r.text)
        self.assertIn('value="blocked"', r.text)
        self.assertNotIn('value="done"', r.text)
        self.assertIn("การปิดมติต้องได้รับการยืนยันจากที่ประชุม", r.text)

    async def test_reporting_progress_updates_the_resolution(self):
        r = await self.client.post(
            f"/api/public/resolutions/{self.token}",
            data={"status": "in_progress", "note": "ร่าง TOR เสร็จ 80% แล้วครับ"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertIn("บันทึกเรียบร้อยแล้ว", r.text)

        resolution = await self.fetch(m.Resolution, self.f.open_res.id)
        self.assertEqual(resolution.status, "in_progress")
        history = (await self.client.get(f"/api/resolutions/{self.f.open_res.id}/history")).json()
        self.assertEqual(history[0]["changed_by"], f"{self.f.supply.full_name} (ผ่าน magic link)")
        self.assertEqual(history[0]["reason"], "ร่าง TOR เสร็จ 80% แล้วครับ")

    async def test_closing_through_the_link_is_refused(self):
        r = await self.client.post(
            f"/api/public/resolutions/{self.token}", data={"status": "done", "note": "เสร็จแล้ว"}
        )
        self.assertEqual(r.status_code, 422)
        self.assertEqual((await self.fetch(m.Resolution, self.f.open_res.id)).status, "confirmed")

    async def test_cancelling_through_the_link_is_refused(self):
        r = await self.client.post(
            f"/api/public/resolutions/{self.token}", data={"status": "cancelled"}
        )
        self.assertEqual(r.status_code, 422)

    async def test_tampered_token_is_rejected(self):
        body, signature = self.token.split(".", 1)
        forged = f"{body}.{'A' * len(signature)}"
        r = await self.client.get(f"/api/public/resolutions/{forged}")
        self.assertEqual(r.status_code, 403)
        self.assertIn("ลิงก์ไม่ถูกต้อง", r.text)

    async def test_garbage_token_is_rejected(self):
        r = await self.client.get("/api/public/resolutions/ไม่ใช่โทเคน")
        self.assertEqual(r.status_code, 403)

    async def test_expired_token_is_rejected(self):
        expired = make_magic_token(self.f.open_res.id, self.f.supply.id, ttl_days=-1)
        r = await self.client.get(f"/api/public/resolutions/{expired}")
        self.assertEqual(r.status_code, 403)

    async def test_token_for_a_deleted_resolution_is_404(self):
        async with self.sessionmaker() as s:
            row = await s.get(m.Resolution, self.f.open_res.id)
            await s.delete(row)
            await s.commit()
        r = await self.client.get(f"/api/public/resolutions/{self.token}")
        self.assertEqual(r.status_code, 404)

    async def test_illegal_transition_through_the_link_is_reported_not_crashed(self):
        async with self.sessionmaker() as s:
            row = await s.get(m.Resolution, self.f.open_res.id)
            row.status = m.ResolutionStatus.SUPERSEDED
            await s.commit()
        r = await self.client.post(
            f"/api/public/resolutions/{self.token}", data={"status": "in_progress"}
        )
        self.assertEqual(r.status_code, 409)
        self.assertIn("state machine", r.text)

    async def test_html_in_resolution_text_is_escaped(self):
        async with self.sessionmaker() as s:
            row = await s.get(m.Resolution, self.f.open_res.id)
            row.text = '<script>alert(1)</script> & "อ้างอิง"'
            await s.commit()
        r = await self.client.get(f"/api/public/resolutions/{self.token}")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("<script>", r.text)
