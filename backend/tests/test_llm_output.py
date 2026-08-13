"""
ตรวจการล้างผลลัพธ์จากโมเดลก่อนส่งต่อให้ผู้ใช้

    python -m unittest discover -s tests -v

ต้องรันในสภาพแวดล้อมที่มี openai และค่า config ครบ (ในคอนเทนเนอร์)
เพราะ app.services.llm ต่อ client ตอน import

จุดที่พังแล้วเจ็บจริง: thaillm-8b แนบ <think>...</think> มาด้วย ถ้าไม่ตัด
ผู้ใช้จะเห็นภาษาอังกฤษที่โมเดลคิดดัง ๆ นำหน้าคำตอบไทยในหน้าถาม-ตอบ
"""

import unittest

from app.services.llm import _strip_reasoning


class StripReasoning(unittest.TestCase):
    def test_removes_think_block_and_keeps_the_answer(self):
        raw = "<think>\nOkay, the user is asking about egg prices.\n</think>\nราคาไข่ปรับขึ้น 4 บาทต่อฟอง"
        self.assertEqual(_strip_reasoning(raw), "ราคาไข่ปรับขึ้น 4 บาทต่อฟอง")

    def test_removes_several_blocks(self):
        self.assertEqual(_strip_reasoning("<think>a</think>ตอบ<think>b</think>ท้าย"), "ตอบท้าย")

    def test_tag_is_case_insensitive(self):
        self.assertEqual(_strip_reasoning("<THINK>x</THINK>ตอบ"), "ตอบ")

    def test_unclosed_block_drops_everything_after_it(self):
        # คำตอบถูกตัดกลางทาง เหลือแต่ความคิด — ต้องไม่ปล่อยออกไป
        self.assertEqual(_strip_reasoning("<think>reasoning that never ends"), "")

    def test_answer_before_an_unclosed_block_survives(self):
        self.assertEqual(_strip_reasoning("ราคาไข่ขึ้น<think>hmm"), "ราคาไข่ขึ้น")

    def test_plain_answer_is_untouched(self):
        self.assertEqual(_strip_reasoning("  ราคาไข่ขึ้น  "), "ราคาไข่ขึ้น")

    def test_does_not_eat_thai_angle_brackets(self):
        self.assertEqual(_strip_reasoning("ข้อ <ก> และ <ข>"), "ข้อ <ก> และ <ข>")


if __name__ == "__main__":
    unittest.main()
