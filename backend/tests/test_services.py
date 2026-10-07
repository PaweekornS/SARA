"""
ชั้นบริการที่ทดสอบได้โดยไม่ต้องต่อฐานข้อมูล

    python -m unittest tests.test_services -v
"""

from __future__ import annotations

import io
import time
import unittest
import zipfile
from datetime import date
from unittest.mock import MagicMock, patch

import jwt

import tests  # noqa: F401  — ต้องมาก่อน import app เพื่อตั้ง env ของการทดสอบให้ทัน
from app.core import security
from app.core.config import INSECURE_SECRET, Settings, settings
from app.services import extraction, ratelimit
from app.services.docx_export import build_meeting_docx
from app.services.email import render_summary_html
from app.services.llm import LlmError, _parse_json, answer_from_context
from app.services.qa import query_terms, relevance
from app.services.templates import TEMPLATES, get_template, is_known_template
from app.services.thai_format import thai_date


def xml_of(blob: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def segs(*texts: str) -> list[extraction.SegmentView]:
    return [extraction.SegmentView(index=i, speaker_label=f"SPEAKER_0{i % 3}", text=t) for i, t in enumerate(texts)]


class ThaiFormatting(unittest.TestCase):
    def test_buddhist_era(self):
        self.assertEqual(thai_date(date(2026, 7, 18)), "18 กรกฎาคม 2569")

    def test_short_month(self):
        self.assertEqual(thai_date(date(2026, 7, 18), short=True), "18 ก.ค. 2569")

    def test_none_date_renders_as_dash_not_crash(self):
        self.assertEqual(thai_date(None), "-")


class LlmJsonParsing(unittest.TestCase):
    """โมเดลชอบใส่ขึ้นบรรทัดใหม่จริง ๆ ในสตริง ห่อด้วย ``` หรือแนบคำอธิบายมาด้วย"""

    def test_raw_newline_inside_a_string_value_is_still_parsed(self):
        raw = '{"summary": "บรรทัดแรก\nบรรทัดที่สอง"}'
        self.assertEqual(_parse_json(raw)["summary"], "บรรทัดแรก\nบรรทัดที่สอง")

    def test_fenced_code_block_is_stripped_before_parsing(self):
        self.assertEqual(_parse_json('```json\n{"action_items": []}\n```'), {"action_items": []})

    def test_falls_back_to_the_largest_brace_span_when_prose_surrounds_it(self):
        raw = 'นี่คือผลลัพธ์ {"action_items": []} หวังว่าจะเป็นประโยชน์'
        self.assertEqual(_parse_json(raw), {"action_items": []})

    def test_think_tag_is_filtered_out(self):
        self.assertEqual(_parse_json('<think>\nคิด...\n</think>\n{"a": 1}'), {"a": 1})

    def test_bare_array_is_wrapped_under_a_neutral_key(self):
        self.assertEqual(_parse_json('ผลคือ [1, 2]'), {"items": [1, 2]})

    def test_broken_json_raises_llm_error(self):
        with self.assertRaises(LlmError):
            _parse_json('{"summary": [เขียนไม่ครบ')

    def test_no_json_at_all_raises_llm_error(self):
        with self.assertRaises(LlmError):
            _parse_json("ขออภัยครับ ไม่พบข้อมูล")

    @patch("app.services.llm.chat")
    def test_answer_from_context_filters_out_think_tag(self, mock_chat):
        mock_chat.return_value = "<think>\nกำลังคิด\n</think>\n\nอนุมัติงบห้าแสนบาท"
        self.assertEqual(answer_from_context("งบเท่าไร", "บริบท"), "อนุมัติงบห้าแสนบาท")


class SpeakerLabels(unittest.TestCase):
    def test_speaker_label_normalization(self):
        from app.services.asr import _normalize_speaker_label

        self.assertEqual(_normalize_speaker_label("SPEAKER_00"), "Speaker 1")
        self.assertEqual(_normalize_speaker_label(None, 2), "Speaker 3")

    def test_split_sentences_detects_speaker_tags(self):
        from app.services.asr import _split_sentences

        segments = _split_sentences("[Speaker 1]: สวัสดีครับ\n[Speaker 2]: สวัสดีค่ะ", 0)
        self.assertEqual([s.speaker_label for s in segments[:2]], ["Speaker 1", "Speaker 2"])


class SummaryParsing(unittest.TestCase):
    LABELS = get_template("general")["detail_labels"]

    def parse(self, data: dict, max_index: int = 5) -> extraction.SummaryResult:
        return extraction._to_summary(data, self.LABELS, max_index)

    def test_action_item_fields_are_mapped(self):
        result = self.parse({"action_items": [
            {"task": "ส่งแบบ", "owner": "มิ้น", "deadline": "2026-09-05", "segment_index": 2}
        ]})
        item = result.action_items[0]
        self.assertEqual((item.text, item.owner, item.due_date, item.segment_index), ("ส่งแบบ", "มิ้น", "2026-09-05", 2))

    def test_legacy_keys_from_older_prompts_still_work(self):
        result = self.parse({"action_items": [{"text": "ทำ A", "assigned_speaker": "Speaker 2", "due_date": "2026-01-02"}]})
        self.assertEqual(result.action_items[0].owner, "Speaker 2")

    def test_item_without_text_is_dropped(self):
        self.assertEqual(self.parse({"action_items": [{"owner": "มิ้น"}, "ไม่ใช่ dict"]}).action_items, [])

    def test_vague_deadline_is_dropped_not_guessed(self):
        self.assertIsNone(self.parse({"action_items": [{"task": "x", "deadline": "วันศุกร์นี้"}]}).action_items[0].due_date)

    def test_segment_index_out_of_range_becomes_none(self):
        self.assertIsNone(self.parse({"action_items": [{"task": "x", "segment_index": 99}]}).action_items[0].segment_index)

    def test_only_declared_detail_keys_are_kept(self):
        result = self.parse({"decisions": ["อนุมัติ"], "new_resolutions": [{"text": "x"}], "random": "y"})
        self.assertEqual(result.details, {"decisions": ["อนุมัติ"]})

    def test_key_points_fill_in_a_missing_summary(self):
        self.assertEqual(self.parse({"key_points": ["ก", "ข"]}).summary, "ก ข")


class SummarizeChunking(unittest.TestCase):
    def test_empty_transcript_does_not_call_the_model(self):
        with patch("app.services.extraction.chat_json") as chat:
            self.assertEqual(extraction.summarize([], "general").action_items, [])
        chat.assert_not_called()

    def test_short_transcript_is_one_call(self):
        with patch("app.services.extraction.chat_json", return_value={"summary": "ok"}) as chat:
            extraction.summarize(segs("สวัสดี", "ลาก่อน"), "general")
        self.assertEqual(chat.call_count, 1)

    def test_long_transcript_is_split_and_merged(self):
        long = segs(*["ข้อความยาว " * 400 for _ in range(6)])
        replies = iter([
            {"summary": f"ช่วง {i}", "key_points": ["ซ้ำ"], "action_items": [{"task": f"งาน {i}"}], "decisions": [f"ตกลง {i}"]}
            for i in range(10)
        ])
        with patch("app.services.extraction.chat_json", side_effect=lambda *a, **k: next(replies)) as chat:
            result = extraction.summarize(long, "general")
        self.assertGreater(chat.call_count, 1)
        self.assertEqual(len(result.action_items), chat.call_count)
        self.assertEqual(result.key_points, ["ซ้ำ"])
        self.assertEqual(len(result.details["decisions"]), chat.call_count)

    def test_every_segment_lands_in_exactly_one_chunk(self):
        segments = segs(*[f"ท่อนที่ {i} " * 50 for i in range(40)])
        chunks = extraction.chunk_segments(segments, 500)
        self.assertEqual([s.index for c in chunks for s in c], list(range(40)))

    def test_failure_on_any_chunk_aborts(self):
        long = segs(*["ข้อความยาว " * 400 for _ in range(6)])
        with patch("app.services.extraction.chat_json", side_effect=LlmError("504")):
            with self.assertRaises(LlmError):
                extraction.summarize(long, "general")


class CompletionDetection(unittest.TestCase):
    OPEN = [extraction.OpenItemView(1, "แก้ rate limit"), extraction.OpenItemView(2, "ทำ landing page")]

    def detect(self, completed: list) -> list[extraction.CompletionHint]:
        with patch("app.services.extraction.chat_json", return_value={"completed": completed}):
            return extraction.detect_completed(segs("rate limit เสร็จแล้ว"), self.OPEN)

    def test_confident_hint_is_kept(self):
        hints = self.detect([{"item": 1, "evidence": "เสร็จแล้ว", "segment_index": 0, "confidence": 0.9}])
        self.assertEqual([(h.number, h.segment_index) for h in hints], [(1, 0)])

    def test_low_confidence_and_unknown_items_are_dropped(self):
        self.assertEqual(self.detect([{"item": 1, "confidence": 0.5}, {"item": 9, "confidence": 0.99}, {"item": "x"}]), [])

    def test_nothing_open_means_no_model_call(self):
        with patch("app.services.extraction.chat_json") as chat:
            self.assertEqual(extraction.detect_completed(segs("x"), []), [])
        chat.assert_not_called()


class Templates(unittest.TestCase):
    def test_every_template_asks_for_action_items(self):
        for tmpl in TEMPLATES.values():
            self.assertIn('"action_items"', tmpl["system_prompt"], tmpl["id"])
            self.assertNotIn("new_resolutions", tmpl["system_prompt"])

    def test_unknown_template_falls_back_to_general(self):
        self.assertEqual(get_template("ไม่มีจริง")["id"], "general")
        self.assertFalse(is_known_template("ไม่มีจริง"))


class SessionTokens(unittest.TestCase):
    def test_round_trip(self):
        self.assertEqual(security.read_access_token(security.create_access_token("abc")), "abc")

    def test_wrong_signature_is_rejected(self):
        forged = jwt.encode({"sub": "abc", "exp": time.time() + 60}, "other-secret", algorithm="HS256")
        self.assertIsNone(security.read_access_token(forged))

    def test_expired_token_is_rejected(self):
        old = jwt.encode({"sub": "abc", "exp": time.time() - 1}, settings.APP_SECRET_KEY, algorithm="HS256")
        self.assertIsNone(security.read_access_token(old))

    def test_alg_none_is_rejected(self):
        unsigned = jwt.encode({"sub": "abc", "exp": time.time() + 60}, None, algorithm="none")
        self.assertIsNone(security.read_access_token(unsigned))

    def test_garbage_is_rejected(self):
        self.assertIsNone(security.read_access_token("not-a-token"))


class GoogleTokenVerification(unittest.TestCase):
    INFO = {"iss": "https://accounts.google.com", "sub": "1", "email": "a@b.com", "email_verified": True}

    def test_audience_is_always_our_client_id(self):
        with patch.object(security.google_id_token, "verify_oauth2_token", return_value=self.INFO) as verify:
            security.verify_google_token("tok")
        self.assertEqual(verify.call_args.args[2], settings.GOOGLE_CLIENT_ID)

    def test_old_mock_tokens_are_not_accepted(self):
        with self.assertRaises(security.InvalidGoogleToken):
            security.verify_google_token("mock-google-token-:victim@x.com:Victim")

    def test_unverified_email_is_rejected(self):
        with patch.object(security.google_id_token, "verify_oauth2_token", return_value={**self.INFO, "email_verified": False}):
            with self.assertRaises(security.InvalidGoogleToken):
                security.verify_google_token("tok")

    def test_foreign_issuer_is_rejected(self):
        with patch.object(security.google_id_token, "verify_oauth2_token", return_value={**self.INFO, "iss": "evil.com"}):
            with self.assertRaises(security.InvalidGoogleToken):
                security.verify_google_token("tok")


class ProdSettingsGuard(unittest.TestCase):
    BASE = {"DATABASE_URL": "postgresql+asyncpg://x", "APP_AI4THAI_API_KEY": "k", "_env_file": None}

    def test_prod_refuses_default_secret(self):
        with self.assertRaises(ValueError):
            Settings(**self.BASE, ENV="prod", APP_SECRET_KEY=INSECURE_SECRET, GOOGLE_CLIENT_ID="id")

    def test_prod_refuses_missing_google_client(self):
        with self.assertRaises(ValueError):
            Settings(**self.BASE, ENV="prod", APP_SECRET_KEY="x" * 40, GOOGLE_CLIENT_ID="")

    def test_prod_disables_demo_login_by_default(self):
        prod = Settings(**self.BASE, ENV="prod", APP_SECRET_KEY="x" * 40, GOOGLE_CLIENT_ID="id")
        self.assertFalse(prod.demo_login_enabled)


class RateLimit(unittest.TestCase):
    def setUp(self):
        self.store: dict[str, int] = {}
        fake = MagicMock()
        fake.incrby.side_effect = lambda k, n: self.store.__setitem__(k, self.store.get(k, 0) + n) or self.store[k]
        fake.decrby.side_effect = lambda k, n: self.store.__setitem__(k, self.store[k] - n)
        patcher = patch.object(ratelimit, "_redis", return_value=fake)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_allows_up_to_the_limit_then_refuses(self):
        results = [ratelimit.consume("k", 1, 3, 60) for _ in range(4)]
        self.assertEqual(results, [True, True, True, False])

    def test_refused_request_does_not_eat_quota(self):
        ratelimit.consume("k", 2, 3, 60)
        self.assertFalse(ratelimit.consume("k", 5, 3, 60))
        self.assertTrue(ratelimit.consume("k", 1, 3, 60))

    def test_redis_outage_fails_open(self):
        import redis

        with patch.object(ratelimit, "_redis", side_effect=redis.ConnectionError("down")):
            self.assertTrue(ratelimit.consume("k", 1, 1, 60))


class Retrieval(unittest.TestCase):
    def test_thai_match_without_word_boundaries(self):
        self.assertGreater(relevance("ที่ประชุมอนุมัติงบประมาณการตลาด", query_terms("งบประมาณการตลาดเท่าไร")), 0.3)

    def test_unrelated_text_scores_low(self):
        self.assertLess(relevance("ฝ่ายไอทีย้ายเซิร์ฟเวอร์", query_terms("งบประมาณการตลาด")), 0.08)


class Outputs(unittest.TestCase):
    def test_docx_contains_summary_details_and_items(self):
        blob = build_meeting_docx(
            title="ประชุมทีม", collection_name="โปรเจกต์ A", meeting_date=date(2026, 9, 1),
            template_name="ทั่วไป", summary="สรุปสั้น ๆ", key_points=["ประเด็น 1"],
            details={"ข้อตกลง": ["อนุมัติงบ"]},
            action_items=[{"text": "ส่งแบบ", "owner": "มิ้น", "due_date": date(2026, 9, 5), "done": False}],
            speakers=["มิ้น"],
        )
        xml = xml_of(blob)
        for expected in ("ประชุมทีม", "สรุปสั้น ๆ", "อนุมัติงบ", "ส่งแบบ", "ผู้รับผิดชอบ: มิ้น", "2569", "TH Sarabun New"):
            self.assertIn(expected, xml)

    def test_email_escapes_html_from_meeting_content(self):
        html = render_summary_html(
            subject="<script>x</script>", summary="สรุป <img src=x onerror=alert(1)>", key_points=[],
            action_items=[{"text": "<b>งาน</b>", "assignees": "", "due_date": "", "status": "ยังค้าง"}],
            template_name="ทั่วไป", sender_name="<i>ผู้ส่ง</i>",
        )
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img", html)
        self.assertNotIn("<b>งาน</b>", html)
        self.assertIn("&lt;b&gt;งาน&lt;/b&gt;", html)


if __name__ == "__main__":
    unittest.main()
