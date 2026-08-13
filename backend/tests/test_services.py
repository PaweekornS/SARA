"""
ชั้นบริการที่ทดสอบได้โดยไม่ต้องต่อฐานข้อมูล

    python -m unittest tests.test_services -v
"""

from __future__ import annotations

import tests  # noqa: F401  — ต้องมาก่อน import app เพื่อตั้ง env ของการทดสอบให้ทัน

import io
import unittest
import zipfile
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException

from app.core import security
from app.db.models import ResolutionStatus
from app.services import extraction
from app.services.agenda_builder import STATUS_LABEL_TH, agenda_topic
from app.services.docx_export import build_agenda_docx, build_minutes_docx
from app.services.mcp_agent import _sse_url, build_reminder_body
from app.services.qa import relevance, thai_grams
from app.services.resolutions import change_status, next_ref_no, overdue_days
from app.services.thai_format import fiscal_year_of, thai_date, thai_numeral


def xml_of(blob: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


class ThaiFormatting(unittest.TestCase):
    def test_buddhist_era(self):
        self.assertEqual(thai_date(date(2026, 7, 18)), "18 กรกฎาคม 2569")

    def test_short_month(self):
        self.assertEqual(thai_date(date(2026, 7, 18), short=True), "18 กรก. 2569")

    def test_none_date_renders_as_dash_not_crash(self):
        self.assertEqual(thai_date(None), "-")

    def test_every_month_has_a_thai_name(self):
        for month in range(1, 13):
            self.assertTrue(thai_date(date(2026, month, 1)).split()[1])

    def test_thai_numerals_leave_non_digits_alone(self):
        self.assertEqual(thai_numeral("5/2569"), "๕/๒๕๖๙")
        self.assertEqual(thai_numeral("ครั้งที่ 12"), "ครั้งที่ ๑๒")

    def test_fiscal_year_starts_in_october(self):
        self.assertEqual(fiscal_year_of(date(2026, 9, 30)), 2569)
        self.assertEqual(fiscal_year_of(date(2026, 10, 1)), 2570)
        self.assertEqual(fiscal_year_of(date(2026, 1, 1)), 2569)

    def test_reference_number_format(self):
        self.assertEqual(next_ref_no(6, 2569, 2), "มติ 6/2569 ข้อ 4.2")

    def test_status_labels_cover_every_status(self):
        for status in ResolutionStatus.TRANSITIONS:
            self.assertIn(status, STATUS_LABEL_TH)


class StateMachine(unittest.TestCase):
    """§4.1 — ตารางนี้คือกติกาของทั้งระบบ เปลี่ยนเมื่อไหร่ต้องรู้ตัว"""

    def test_a_resolution_cannot_be_closed_before_it_is_confirmed(self):
        self.assertNotIn(
            ResolutionStatus.DONE, ResolutionStatus.TRANSITIONS[ResolutionStatus.PROPOSED]
        )

    def test_superseded_is_terminal(self):
        self.assertEqual(ResolutionStatus.TRANSITIONS[ResolutionStatus.SUPERSEDED], ())

    def test_blocked_work_can_resume(self):
        self.assertIn(
            ResolutionStatus.IN_PROGRESS, ResolutionStatus.TRANSITIONS[ResolutionStatus.BLOCKED]
        )

    def test_a_closed_resolution_can_be_reopened(self):
        self.assertEqual(ResolutionStatus.TRANSITIONS[ResolutionStatus.DONE], (ResolutionStatus.IN_PROGRESS,))

    def test_open_statuses_are_exactly_the_unfinished_ones(self):
        self.assertEqual(
            set(ResolutionStatus.OPEN),
            {ResolutionStatus.CONFIRMED, ResolutionStatus.IN_PROGRESS, ResolutionStatus.BLOCKED},
        )

    def test_every_target_is_itself_a_known_status(self):
        known = set(ResolutionStatus.TRANSITIONS)
        for source, targets in ResolutionStatus.TRANSITIONS.items():
            for target in targets:
                self.assertIn(target, known, f"{source} -> {target}")


class MagicToken(unittest.TestCase):
    """โทเคนนี้ให้สิทธิ์อัปเดตมติได้โดยไม่ต้องล็อกอิน จึงต้องปลอมไม่ได้"""

    def setUp(self) -> None:
        self.resolution_id = uuid4()
        self.person_id = uuid4()
        self.token = security.make_magic_token(self.resolution_id, self.person_id)

    def test_round_trip_carries_both_ids(self):
        data = security.read_magic_token(self.token)
        self.assertEqual(data["r"], str(self.resolution_id))
        self.assertEqual(data["p"], str(self.person_id))

    def test_tampered_payload_is_rejected(self):
        body, signature = self.token.split(".", 1)
        other = security.make_magic_token(uuid4(), self.person_id).split(".", 1)[0]
        self.assertIsNone(security.read_magic_token(f"{other}.{signature}"))

    def test_tampered_signature_is_rejected(self):
        body, _ = self.token.split(".", 1)
        self.assertIsNone(security.read_magic_token(f"{body}.AAAA"))

    def test_expired_token_is_rejected(self):
        expired = security.make_magic_token(self.resolution_id, self.person_id, ttl_days=-1)
        self.assertIsNone(security.read_magic_token(expired))

    def test_malformed_tokens_return_none_instead_of_raising(self):
        for bad in ("", ".", "ไม่ใช่โทเคน", "a.b.c", "!!!!.????"):
            self.assertIsNone(security.read_magic_token(bad))

    def test_url_includes_the_api_prefix(self):
        """router ทั้งหมด mount ใต้ /api — ลิงก์ที่ขาด prefix จะพาผู้รับไป 404"""
        url = security.magic_link_url(self.resolution_id, self.person_id)
        self.assertIn("/api/public/resolutions/", url)


class McpAgent(unittest.TestCase):
    def test_reminder_quotes_the_resolution_word_for_word(self):
        """FR-M7-03 ผู้รับต้องเห็นสิ่งที่ตัวเองรับปากไว้ตรงตามรายงาน ไม่ใช่สรุปย่อ"""
        resolution = SimpleNamespace(
            id=uuid4(), ref_no="มติ 5/2569 ข้อ 4.1",
            text="มอบหมายให้ฝ่ายพัสดุจัดทำร่างขอบเขตของงาน (TOR) ให้แล้วเสร็จภายใน 30 วัน",
            due_date=date(2026, 7, 18),
        )
        person = SimpleNamespace(id=uuid4(), full_name="นางกาญจนา พูลสวัสดิ์")

        body = build_reminder_body(resolution, person, overdue=26)
        self.assertIn(resolution.text, body)
        self.assertIn("มติ 5/2569 ข้อ 4.1", body)
        self.assertIn("เกินกำหนดแล้ว 26 วัน", body)
        self.assertIn("18 กรกฎาคม 2569", body)
        self.assertIn("/api/public/resolutions/", body)

    def test_reminder_before_the_due_date_reads_differently(self):
        resolution = SimpleNamespace(
            id=uuid4(), ref_no="มติ 5/2569 ข้อ 4.2", text="ข้อความมติ", due_date=date(2026, 9, 30)
        )
        person = SimpleNamespace(id=uuid4(), full_name="ผู้รับผิดชอบ")
        body = build_reminder_body(resolution, person, overdue=0)
        self.assertIn("ครบกำหนดวันที่ 30 กันยายน 2569", body)
        self.assertNotIn("เกินกำหนด", body)

    def test_sse_url_derived_from_mcp_url(self):
        self.assertEqual(_sse_url.__module__, "app.services.mcp_agent")
        for given, expected in [
            ("http://mcp:8001/mcp", "http://mcp:8001/sse"),
            ("http://mcp:8001/sse", "http://mcp:8001/sse"),
            ("http://mcp:8001", "http://mcp:8001/sse"),
        ]:
            with patch("app.services.mcp_agent.settings.MCP_SERVER_URL", given):
                self.assertEqual(_sse_url(), expected)


class SystemInitiatedChanges(unittest.IsolatedAsyncioTestCase):
    """
    FR-M4-06 · §4.2 — false close อันตรายกว่า missed close
    ระบบมีสิทธิ์เปลี่ยนสถานะเองได้จุดเดียวคือ proposed → confirmed ตอนรับรองรายงาน
    """

    def resolution(self, status: str):
        return SimpleNamespace(
            id=uuid4(), status=status, updated_at=None, closed_at=None, closed_meeting_id=None
        )

    async def test_system_cannot_close_a_resolution(self):
        row = self.resolution(ResolutionStatus.CONFIRMED)
        with self.assertRaises(HTTPException) as ctx:
            await change_status(
                MagicMock(), row, ResolutionStatus.DONE, reason="ระบบคิดว่าเสร็จแล้ว",
                actor="ระบบ", system_initiated=True,
            )
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(row.status, ResolutionStatus.CONFIRMED)

    async def test_system_cannot_cancel_a_resolution(self):
        row = self.resolution(ResolutionStatus.CONFIRMED)
        with self.assertRaises(HTTPException) as ctx:
            await change_status(
                MagicMock(), row, ResolutionStatus.CANCELLED, reason="ระบบยกเลิกเอง",
                actor="ระบบ", system_initiated=True,
            )
        self.assertEqual(ctx.exception.status_code, 403)

    async def test_system_may_confirm_a_proposed_resolution(self):
        row = self.resolution(ResolutionStatus.PROPOSED)
        await change_status(
            MagicMock(), row, ResolutionStatus.CONFIRMED, reason="ที่ประชุมรับรองรายงานการประชุม",
            actor="ฝ่ายเลขานุการ", system_initiated=True,
        )
        self.assertEqual(row.status, ResolutionStatus.CONFIRMED)

    async def test_illegal_transition_is_checked_before_anything_else(self):
        row = self.resolution(ResolutionStatus.SUPERSEDED)
        with self.assertRaises(HTTPException) as ctx:
            await change_status(
                MagicMock(), row, ResolutionStatus.IN_PROGRESS, reason="เปิดใหม่", actor="คน"
            )
        self.assertEqual(ctx.exception.status_code, 409)

    async def test_closing_without_a_reason_is_refused(self):
        row = self.resolution(ResolutionStatus.CONFIRMED)
        with self.assertRaises(HTTPException) as ctx:
            await change_status(MagicMock(), row, ResolutionStatus.DONE, reason="  ", actor="คน")
        self.assertEqual(ctx.exception.status_code, 422)


class OverdueRules(unittest.TestCase):
    def row(self, status: str, due=date(2026, 7, 18)):
        return SimpleNamespace(status=status, due_date=due)

    def test_open_statuses_accrue_overdue_days(self):
        for status in ResolutionStatus.OPEN:
            self.assertEqual(overdue_days(self.row(status), date(2026, 8, 11)), 24)

    def test_settled_statuses_never_accrue(self):
        for status in (
            ResolutionStatus.DONE, ResolutionStatus.CANCELLED,
            ResolutionStatus.SUPERSEDED, ResolutionStatus.PROPOSED,
        ):
            self.assertEqual(overdue_days(self.row(status), date(2026, 8, 11)), 0)

    def test_no_due_date(self):
        self.assertEqual(overdue_days(self.row(ResolutionStatus.CONFIRMED, None), date(2026, 8, 11)), 0)

    def test_not_yet_due_is_zero_not_negative(self):
        self.assertEqual(overdue_days(self.row(ResolutionStatus.CONFIRMED), date(2026, 7, 1)), 0)

    def test_due_today_is_zero(self):
        self.assertEqual(overdue_days(self.row(ResolutionStatus.CONFIRMED), date(2026, 7, 18)), 0)


class DocxOutput(unittest.TestCase):
    """FR-M5-04, 05, 06 — เอกสารต้องเปิดใน Word ได้และเป็นไปตามระเบียบสารบรรณ"""

    def agenda(self) -> bytes:
        return build_agenda_docx(
            series_name="คณะกรรมการบริหาร ปีงบประมาณ 2569",
            fiscal_year=2569,
            sequence_no=6,
            meeting_date=date(2026, 8, 20),
            sections=[
                (1, "เรื่องที่ประธานแจ้งให้ที่ประชุมทราบ", []),
                (2, "เรื่องรับรองรายงานการประชุม", [("รับรองรายงานการประชุมครั้งที่ 5/2569", "รายละเอียด")]),
                (
                    3,
                    "เรื่องสืบเนื่องจากการประชุมครั้งก่อน",
                    [("เรื่อง ฝ่ายพัสดุจัดทำร่างขอบเขตของงาน", "มติเดิม: ข้อความยาว ๆ ที่ต้องไม่ถูกตัด")],
                ),
                (4, "เรื่องเสนอเพื่อพิจารณา", []),
                (5, "เรื่องอื่น ๆ", []),
            ],
            template_path=None,
        )

    def test_agenda_is_a_valid_docx(self):
        with zipfile.ZipFile(io.BytesIO(self.agenda())) as archive:
            self.assertIn("word/document.xml", archive.namelist())
            self.assertIsNone(archive.testzip())

    def test_agenda_uses_th_sarabun_new(self):
        self.assertIn("TH Sarabun New", xml_of(self.agenda()))

    def test_agenda_declares_the_complex_script_font(self):
        """ภาษาไทยเป็น complex script — ถ้าไม่ตั้ง w:cs ฟอนต์จะไม่ถูกใช้จริงใน Word"""
        self.assertIn("w:cs=", xml_of(self.agenda()))

    def test_agenda_uses_thai_numerals_for_section_numbers(self):
        xml = xml_of(self.agenda())
        self.assertIn("๑", xml)
        self.assertIn("๕", xml)

    def test_agenda_uses_buddhist_era(self):
        self.assertIn("๒๕๖๙", xml_of(self.agenda()))

    def test_agenda_keeps_body_text_whole(self):
        xml = xml_of(self.agenda())
        self.assertIn("มติเดิม", xml)
        self.assertNotIn("…", xml)

    def test_minutes_contains_attendees_and_resolutions(self):
        blob = build_minutes_docx(
            series_name="คณะกรรมการบริหาร ปีงบประมาณ 2569",
            fiscal_year=2569,
            sequence_no=5,
            meeting_date=date(2026, 6, 18),
            attendees=["นายธนกฤต อารีวงศ์ ผู้อำนวยการ"],
            resolutions=[
                {
                    "title": "จัดทำ TOR",
                    "text": "มอบหมายให้ฝ่ายพัสดุจัดทำร่างขอบเขตของงาน",
                    "assignees": "ฝ่ายพัสดุ",
                    "due_date": date(2026, 7, 18),
                }
            ],
            segments=[{"start_ms": 12_000, "speaker": "นายธนกฤต อารีวงศ์", "text": "ขอเปิดการประชุมครับ"}],
            template_path=None,
        )
        xml = xml_of(blob)
        self.assertIn("นายธนกฤต", xml)
        self.assertIn("ฝ่ายพัสดุ", xml)
        self.assertIn("ขอเปิดการประชุมครับ", xml)

    def test_minutes_survives_empty_content(self):
        blob = build_minutes_docx(
            series_name="ชุดว่าง", fiscal_year=2569, sequence_no=1,
            meeting_date=date(2026, 1, 1), attendees=[], resolutions=[], segments=[],
            template_path=None,
        )
        self.assertGreater(len(blob), 0)


class ExtractionFilters(unittest.TestCase):
    """ด่านกรองของที่โมเดลแต่งขึ้น — ปล่อยผ่านเมื่อไหร่ กลายเป็นมติผูกผิดข้อทันที"""

    def test_unknown_reference_is_dropped(self):
        data = {
            "updates": [
                {"ref": "มติ 5/2569 ข้อ 4.1", "proposed_status": "done", "confidence": 0.9},
                {"ref": "มติ ที่โมเดลแต่งขึ้น", "proposed_status": "done", "confidence": 0.99},
            ]
        }
        result = extraction._to_result(data, valid_refs={"มติ 5/2569 ข้อ 4.1"}, max_index=5)
        self.assertEqual([u.ref for u in result.updates], ["มติ 5/2569 ข้อ 4.1"])

    def test_low_confidence_close_is_downgraded(self):
        data = {"updates": [{"ref": "R1", "proposed_status": "done", "confidence": 0.4}]}
        result = extraction._to_result(data, valid_refs={"R1"}, max_index=5)
        self.assertEqual(result.updates[0].proposed_status, "in_progress")

    def test_close_exactly_at_the_floor_survives(self):
        data = {
            "updates": [
                {"ref": "R1", "proposed_status": "done", "confidence": extraction.CLOSE_CONFIDENCE_FLOOR}
            ]
        }
        result = extraction._to_result(data, valid_refs={"R1"}, max_index=5)
        self.assertEqual(result.updates[0].proposed_status, "done")

    def test_unknown_status_is_dropped(self):
        data = {"updates": [{"ref": "R1", "proposed_status": "เสร็จแล้วมั้ง", "confidence": 0.9}]}
        result = extraction._to_result(data, valid_refs={"R1"}, max_index=5)
        self.assertEqual(result.updates, [])

    def test_segment_index_out_of_range_becomes_none(self):
        data = {"new_resolutions": [{"text": "มติใหม่", "segment_index": 99, "confidence": 0.8}]}
        result = extraction._to_result(data, valid_refs=set(), max_index=3)
        self.assertIsNone(result.new_resolutions[0].segment_index)

    def test_malformed_payload_is_ignored(self):
        result = extraction._to_result(
            {"new_resolutions": "ไม่ใช่ลิสต์", "updates": None, "speakers": 5},
            valid_refs=set(), max_index=3,
        )
        self.assertEqual((result.new_resolutions, result.updates, result.speakers), ([], [], []))

    def test_resolution_without_text_is_dropped(self):
        data = {"new_resolutions": [{"text": "   ", "confidence": 0.9}]}
        self.assertEqual(extraction._to_result(data, set(), 3).new_resolutions, [])

    def test_invalid_due_date_is_dropped_not_guessed(self):
        data = {"new_resolutions": [{"text": "มติ", "due_date": "เร็ว ๆ นี้", "confidence": 0.8}]}
        self.assertIsNone(extraction._to_result(data, set(), 3).new_resolutions[0].due_date)

    def test_valid_due_date_survives(self):
        data = {"new_resolutions": [{"text": "มติ", "due_date": "2026-09-30", "confidence": 0.8}]}
        self.assertEqual(extraction._to_result(data, set(), 3).new_resolutions[0].due_date, "2026-09-30")

    def test_confidence_is_clamped(self):
        data = {"new_resolutions": [{"text": "ก", "confidence": 5}, {"text": "ข", "confidence": -2}]}
        result = extraction._to_result(data, set(), 3)
        self.assertEqual([r.confidence for r in result.new_resolutions], [1.0, 0.0])

    def test_speaker_mention_needs_both_label_and_name(self):
        data = {"speakers": [{"speaker_label": "SPEAKER_00"}, {"name_mention": "พี่หนึ่ง"}]}
        self.assertEqual(extraction._to_result(data, set(), 3).speakers, [])

    def test_empty_transcript_short_circuits_without_calling_the_model(self):
        self.assertEqual(extraction.extract([], [], "ครั้งที่ 1/2569").new_resolutions, [])


class PersonResolution(unittest.TestCase):
    """§12 ให้ AI เดาชื่อคนไทยจะพังแน่นอน — ตรงกันเป๊ะเท่านั้นจึงจะผูกให้"""

    candidates = [
        ("p1", "นายสุรชัย ทองอินทร์"),
        ("p1", "พี่หนึ่ง"),
        ("p2", "นางสาวปรียานุช วัฒนสิน"),
        ("p3", "พี่หนึ่ง"),  # ชื่อเล่นชนกันสองคน
    ]

    def test_exact_alias_resolves_with_high_confidence(self):
        person_id, confidence = extraction.resolve_person("ท่านรอง", [("p1", "ท่านรอง")])
        self.assertEqual(person_id, "p1")
        self.assertGreaterEqual(confidence, 0.9)

    def test_ambiguous_alias_refuses_to_guess(self):
        self.assertEqual(extraction.resolve_person("พี่หนึ่ง", self.candidates), (None, 0.0))

    def test_partial_match_is_allowed_but_less_confident(self):
        person_id, confidence = extraction.resolve_person("ปรียานุช", self.candidates)
        self.assertEqual(person_id, "p2")
        self.assertLess(confidence, 0.9)

    def test_unknown_name_returns_nothing(self):
        self.assertEqual(extraction.resolve_person("คนที่ไม่มีในทะเบียน", self.candidates)[0], None)

    def test_blank_mention(self):
        self.assertEqual(extraction.resolve_person("   ", self.candidates), (None, 0.0))

    def test_no_candidates(self):
        self.assertEqual(extraction.resolve_person("ใครสักคน", []), (None, 0.0))


class ThaiSearch(unittest.TestCase):
    """ภาษาไทยไม่เว้นวรรคระหว่างคำ การตัดด้วยช่องว่างจึงพลาดเกือบทุกครั้ง"""

    def test_matches_across_missing_word_boundaries(self):
        grams = thai_grams("เรื่องระบบสารบรรณอิเล็กทรอนิกส์ เคยมีมติว่าอะไรบ้าง")
        hit = relevance("ให้ฝ่ายเทคโนโลยีสารสนเทศเร่งรัดผู้รับจ้างติดตั้งระบบสารบรรณอิเล็กทรอนิกส์", grams)
        miss = relevance("จัดซื้อครุภัณฑ์คอมพิวเตอร์ทดแทน จำนวน 42 เครื่อง", grams)
        self.assertGreater(hit, 0.1)
        self.assertGreater(hit, miss)

    def test_punctuation_and_spacing_do_not_change_the_match(self):
        grams = thai_grams("ระบบสารบรรณอิเล็กทรอนิกส์")
        self.assertEqual(
            relevance("ระบบสารบรรณอิเล็กทรอนิกส์", grams),
            relevance('“ระบบสารบรรณ อิเล็กทรอนิกส์”', grams),
        )

    def test_short_question_produces_no_grams(self):
        self.assertEqual(thai_grams("มติ"), [])
        self.assertEqual(relevance("อะไรก็ได้", []), 0.0)


class AgendaTopic(unittest.TestCase):
    def test_strips_leading_verb(self):
        cases = {
            "มอบหมายให้ฝ่ายพัสดุจัดทำร่าง": "เรื่อง ฝ่ายพัสดุจัดทำร่าง",
            "ที่ประชุมมีมติให้ฝ่ายไอทีเร่งรัด": "เรื่อง ฝ่ายไอทีเร่งรัด",
            "อนุมัติปรับปรุงห้องประชุมใหญ่": "เรื่อง ปรับปรุงห้องประชุมใหญ่",
            "ให้ทุกฝ่ายจัดทำแผน": "เรื่อง ทุกฝ่ายจัดทำแผน",
        }
        for text, expected in cases.items():
            self.assertEqual(agenda_topic(text), expected)

    def test_never_truncates(self):
        long_text = "มอบหมายให้ฝ่ายพัสดุ" + "ดำเนินการตามระเบียบพัสดุอย่างเคร่งครัด" * 10
        topic = agenda_topic(long_text)
        self.assertNotIn("…", topic)
        self.assertGreater(len(topic), 300)


if __name__ == "__main__":
    unittest.main()
