"""
ตรวจตรรกะที่พังแล้วเจ็บจริง โดยไม่ต้องต่อ DB หรือเรียกโมเดล

    python -m unittest discover -s tests -v

เน้นจุดที่ requirement ระบุว่าห้ามพลาด:
  * false close (§4.2) — ข้อเสนอปิดมติที่ความมั่นใจต่ำต้องไม่ถูกเสนอ
  * มติผูกผิดข้อ — ref ที่โมเดลแต่งขึ้นต้องถูกกรองทิ้ง
  * เดาชื่อคน (§12) — ชื่อที่ชนกันต้องคืนว่าไม่รู้ ไม่ใช่เดาสักคน
"""

import unittest
from datetime import date
from types import SimpleNamespace

from app.db.models import ResolutionStatus
from app.services import extraction
from app.services.agenda_builder import agenda_topic
from app.services.qa import relevance, thai_grams
from app.services.resolutions import overdue_days
from app.services.thai_format import fiscal_year_of, thai_date, thai_numeral


def fake_resolution(status=ResolutionStatus.CONFIRMED, due=date(2026, 7, 18)):
    return SimpleNamespace(status=status, due_date=due)


class ExtractionMapping(unittest.TestCase):
    """แปลงผลจากโมเดลเป็นข้อเสนอ — ชั้นนี้คือด่านกรองของมั่วจากโมเดล"""

    def test_drops_updates_that_reference_unknown_resolutions(self):
        data = {
            "updates": [
                {"ref": "มติ 5/2569 ข้อ 4.1", "proposed_status": "done", "confidence": 0.9},
                {"ref": "มติ ที่ไม่มีอยู่จริง", "proposed_status": "done", "confidence": 0.99},
            ]
        }
        result = extraction._to_result(data, valid_refs={"มติ 5/2569 ข้อ 4.1"}, max_index=5)
        self.assertEqual(len(result.updates), 1)
        self.assertEqual(result.updates[0].ref, "มติ 5/2569 ข้อ 4.1")

    def test_low_confidence_close_is_downgraded_not_proposed(self):
        """§4.2 false close อันตรายกว่า missed close — ไม่มั่นใจพอ ห้ามเสนอปิด"""
        data = {"updates": [{"ref": "R1", "proposed_status": "done", "confidence": 0.4}]}
        result = extraction._to_result(data, valid_refs={"R1"}, max_index=5)
        self.assertEqual(result.updates[0].proposed_status, "in_progress")

    def test_confident_close_survives(self):
        data = {"updates": [{"ref": "R1", "proposed_status": "done", "confidence": 0.92}]}
        result = extraction._to_result(data, valid_refs={"R1"}, max_index=5)
        self.assertEqual(result.updates[0].proposed_status, "done")

    def test_segment_index_out_of_range_becomes_none(self):
        data = {"new_resolutions": [{"text": "มติใหม่", "segment_index": 99, "confidence": 0.8}]}
        result = extraction._to_result(data, valid_refs=set(), max_index=3)
        self.assertIsNone(result.new_resolutions[0].segment_index)

    def test_ignores_malformed_payload(self):
        result = extraction._to_result({"new_resolutions": "ไม่ใช่ลิสต์"}, valid_refs=set(), max_index=3)
        self.assertEqual(result.new_resolutions, [])

    def test_invalid_due_date_is_dropped_not_guessed(self):
        data = {"new_resolutions": [{"text": "มติ", "due_date": "เร็ว ๆ นี้", "confidence": 0.8}]}
        result = extraction._to_result(data, valid_refs=set(), max_index=3)
        self.assertIsNone(result.new_resolutions[0].due_date)


class PersonResolution(unittest.TestCase):
    """§12 ให้ AI เดาชื่อคนไทยจะพังแน่นอน — ตรงกันเป๊ะเท่านั้นจึงจะผูกให้"""

    candidates = [
        ("p1", "นายสุรชัย ทองอินทร์"),
        ("p1", "พี่หนึ่ง"),
        ("p2", "นางสาวปรียานุช วัฒนสิน"),
        ("p3", "พี่หนึ่ง"),  # ชื่อเล่นชนกัน
    ]

    def test_exact_alias_resolves(self):
        person_id, confidence = extraction.resolve_person("ท่านรอง", [("p1", "ท่านรอง")])
        self.assertEqual(person_id, "p1")
        self.assertGreaterEqual(confidence, 0.9)

    def test_ambiguous_alias_refuses_to_guess(self):
        person_id, confidence = extraction.resolve_person("พี่หนึ่ง", self.candidates)
        self.assertIsNone(person_id)
        self.assertEqual(confidence, 0.0)

    def test_unknown_name_returns_nothing(self):
        person_id, _ = extraction.resolve_person("คนที่ไม่มีในทะเบียน", self.candidates)
        self.assertIsNone(person_id)

    def test_blank_mention(self):
        self.assertEqual(extraction.resolve_person("   ", self.candidates), (None, 0.0))


class OverdueRules(unittest.TestCase):
    def test_open_resolution_past_due(self):
        self.assertEqual(overdue_days(fake_resolution(), date(2026, 8, 11)), 24)

    def test_closed_resolution_is_never_overdue(self):
        self.assertEqual(
            overdue_days(fake_resolution(status=ResolutionStatus.DONE), date(2026, 8, 11)), 0
        )

    def test_cancelled_resolution_is_never_overdue(self):
        self.assertEqual(
            overdue_days(fake_resolution(status=ResolutionStatus.CANCELLED), date(2026, 8, 11)), 0
        )

    def test_no_due_date(self):
        self.assertEqual(overdue_days(fake_resolution(due=None), date(2026, 8, 11)), 0)

    def test_not_yet_due(self):
        self.assertEqual(overdue_days(fake_resolution(), date(2026, 7, 1)), 0)


class StateMachine(unittest.TestCase):
    def test_cannot_close_before_confirming(self):
        self.assertNotIn(ResolutionStatus.DONE, ResolutionStatus.TRANSITIONS[ResolutionStatus.PROPOSED])

    def test_superseded_is_terminal(self):
        self.assertEqual(ResolutionStatus.TRANSITIONS[ResolutionStatus.SUPERSEDED], ())

    def test_blocked_can_resume(self):
        self.assertIn(
            ResolutionStatus.IN_PROGRESS, ResolutionStatus.TRANSITIONS[ResolutionStatus.BLOCKED]
        )


class ThaiSearch(unittest.TestCase):
    """ภาษาไทยไม่เว้นวรรค การตัดคำด้วยช่องว่างจึงพลาด — n-gram ต้องยังจับได้"""

    def test_matches_across_missing_word_boundaries(self):
        grams = thai_grams("เรื่องระบบสารบรรณอิเล็กทรอนิกส์ เคยมีมติว่าอะไรบ้าง")
        hit = relevance("ให้ฝ่ายเทคโนโลยีสารสนเทศเร่งรัดผู้รับจ้างติดตั้งระบบสารบรรณอิเล็กทรอนิกส์", grams)
        miss = relevance("จัดซื้อครุภัณฑ์คอมพิวเตอร์ทดแทน จำนวน 42 เครื่อง", grams)
        self.assertGreater(hit, 0.1)
        self.assertGreater(hit, miss)

    def test_empty_question(self):
        self.assertEqual(relevance("อะไรก็ได้", []), 0.0)


class ThaiFormatting(unittest.TestCase):
    def test_buddhist_era(self):
        self.assertEqual(thai_date(date(2026, 7, 18)), "18 กรกฎาคม 2569")

    def test_thai_numerals(self):
        self.assertEqual(thai_numeral("5/2569"), "๕/๒๕๖๙")

    def test_fiscal_year_starts_in_october(self):
        self.assertEqual(fiscal_year_of(date(2026, 9, 30)), 2569)
        self.assertEqual(fiscal_year_of(date(2026, 10, 1)), 2570)


class AgendaTopic(unittest.TestCase):
    def test_strips_leading_verb_and_keeps_full_text(self):
        topic = agenda_topic("มอบหมายให้ฝ่ายพัสดุจัดทำร่างขอบเขตของงาน (TOR) สำหรับการจัดซื้อครุภัณฑ์")
        self.assertTrue(topic.startswith("เรื่อง ฝ่ายพัสดุ"))
        #  ห้ามมี ... ในหัวข้อ เพราะข้อความนี้ถูกเขียนลงเอกสารราชการโดยตรง
        self.assertNotIn("…", topic)


if __name__ == "__main__":
    unittest.main()
