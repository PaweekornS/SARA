"""
ดัชนีเวกเตอร์ (Qdrant) และ hybrid RAG — ใช้ Qdrant ในหน่วยความจำ + HashEmbedder

    python -m unittest tests.test_vector -v
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import tests  # noqa: F401
from app.db import models as m
from app.services import qa, vector_store
from tests.support import DbCase, build_workspace, fresh_vector_store, index_workspace


def seg(text: str, label: str = "SPEAKER_00", name: str = "", start: int = 0):
    return SimpleNamespace(id=uuid4(), speaker_label=label, speaker_name=name, start_ms=start, text=text)


class VectorStoreUnit(unittest.TestCase):
    def setUp(self):
        fresh_vector_store()
        self.alice, self.bob = uuid4(), uuid4()
        self.coll_a, self.coll_b = uuid4(), uuid4()

    def index(self, user, coll, meeting, *texts):
        segments = [seg(t, start=i * 1000) for i, t in enumerate(texts)]
        return vector_store.index_meeting(user, coll, meeting, vector_store.build_chunks(meeting, "", segments))

    def test_build_chunks_uses_overlapping_windows_and_speaker_names(self):
        segments = [seg(f"ท่อน {i}", name="คุณมิ้น" if i == 0 else "") for i in range(5)]
        chunks = vector_store.build_chunks(uuid4(), "สรุป", segments)
        self.assertEqual([c.kind for c in chunks], ["summary", "transcript", "transcript", "transcript"])
        self.assertIn("คุณมิ้น: ท่อน 0", chunks[1].text)
        self.assertIn("ท่อน 2", chunks[2].text)  # ท่อนรอยต่อซ้อนกัน ไม่หลุดหาย

    def test_search_never_crosses_users_or_collections(self):
        meeting_a, meeting_b, meeting_c = uuid4(), uuid4(), uuid4()
        self.index(self.alice, self.coll_a, meeting_a, "อนุมัติงบประมาณการตลาดห้าแสนบาท")
        self.index(self.bob, self.coll_b, meeting_b, "อนุมัติงบประมาณการตลาดห้าแสนบาท")
        self.index(self.alice, uuid4(), meeting_c, "อนุมัติงบประมาณการตลาดห้าแสนบาท")
        hits = vector_store.search(self.alice, self.coll_a, "งบประมาณการตลาด", 10)
        self.assertEqual({h.meeting_id for h in hits}, {meeting_a})

    def test_reindexing_replaces_instead_of_duplicating(self):
        meeting = uuid4()
        self.index(self.alice, self.coll_a, meeting, "ข้อความเก่าเรื่องงบประมาณ")
        self.index(self.alice, self.coll_a, meeting, "ข้อความใหม่เรื่องงบประมาณ")
        hits = vector_store.search(self.alice, self.coll_a, "ข้อความเรื่องงบประมาณ", 10)
        self.assertEqual([h.text for h in hits], ["SPEAKER_00: ข้อความใหม่เรื่องงบประมาณ"])

    def test_delete_and_move(self):
        keep, gone = uuid4(), uuid4()
        self.index(self.alice, self.coll_a, keep, "งบประมาณการตลาด")
        self.index(self.alice, self.coll_a, gone, "งบประมาณการตลาด")
        vector_store.delete_meetings([gone])
        hits = vector_store.search(self.alice, self.coll_a, "งบประมาณการตลาด", 10)
        self.assertEqual({h.meeting_id for h in hits}, {keep})

        vector_store.move_meeting(keep, self.coll_b)
        self.assertEqual(vector_store.search(self.alice, self.coll_a, "งบประมาณการตลาด", 10), [])
        self.assertEqual(len(vector_store.search(self.alice, self.coll_b, "งบประมาณการตลาด", 10)), 1)

    def test_unreachable_qdrant_raises_vector_store_error(self):
        from qdrant_client import QdrantClient

        from tests.fakes import HashEmbedder

        vector_store.configure(QdrantClient(url="http://127.0.0.1:1", timeout=1), HashEmbedder())
        with self.assertRaises(vector_store.VectorStoreError):
            vector_store.search(self.alice, self.coll_a, "อะไรก็ได้", 3)

    def test_best_effort_ops_do_not_raise_when_qdrant_is_down(self):
        with patch.object(vector_store, "_get", side_effect=vector_store.VectorStoreError("down")):
            vector_store.delete_meetings([uuid4()])
            vector_store.move_meeting(uuid4(), uuid4())


class HybridQa(DbCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.w = await build_workspace(self, "me@x.com", "ฉัน")
        index_workspace(self.w)

    async def ask(self, question: str) -> qa.QaResult:
        async with self.sessionmaker() as s:
            with patch("app.services.qa.answer_from_context", return_value="คำตอบ") as self.llm:
                return await qa.answer_question(s, self.w.user.id, self.w.collection.id, question)

    async def test_vector_and_lexical_hits_are_merged_without_duplicates(self):
        result = await self.ask("อนุมัติงบประมาณการตลาด")
        self.assertEqual({c["source"] for c in result.citations}, {"vector", "lexical"})
        quotes = [c["quote"] for c in result.citations]
        self.assertEqual(len(quotes), len(set(quotes)))

    async def test_action_items_come_live_from_the_database(self):
        async with self.sessionmaker() as s:
            (await s.get(m.ActionItem, self.w.open_item.id)).done = True
            await s.commit()
        result = await self.ask("ส่งแบบโฆษณา")
        item_quotes = [c["quote"] for c in result.citations if c["kind"] == "action_item"]
        self.assertTrue(any("ส่งแบบโฆษณา (เสร็จแล้ว" in q for q in item_quotes), item_quotes)

    async def test_qdrant_outage_falls_back_to_lexical(self):
        with patch.object(vector_store, "_get", side_effect=vector_store.VectorStoreError("down")):
            result = await self.ask("อนุมัติงบประมาณการตลาด")
        self.assertTrue(result.citations)
        self.assertEqual({c["source"] for c in result.citations}, {"lexical"})
        self.assertEqual(result.answer, "คำตอบ")

    async def test_stale_points_of_deleted_meetings_are_ignored(self):
        async with self.sessionmaker() as s:
            await s.delete(await s.get(m.Meeting, self.w.meeting.id))
            await s.commit()
        result = await self.ask("อนุมัติงบประมาณการตลาด")  # จุดใน Qdrant ยังอยู่ แต่การประชุมหายไปแล้ว
        self.assertEqual(result.citations, [])
        self.llm.assert_not_called()


class ApiKeepsIndexInSync(DbCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.w = await build_workspace(self, "me@x.com", "ฉัน")
        index_workspace(self.w)

    def points(self, collection_id=None):
        return vector_store.search(self.w.user.id, collection_id or self.w.collection.id, "งบประมาณการตลาด", 50)

    async def test_deleting_a_meeting_removes_its_points(self):
        self.assertTrue(self.points())
        await self.client.delete(f"/meetings/{self.w.meeting.id}", headers=self.w.headers)
        self.assertEqual(self.points(), [])

    async def test_deleting_a_collection_removes_its_points(self):
        await self.client.delete(f"/collections/{self.w.collection.id}", headers=self.w.headers)
        self.assertEqual(self.points(), [])

    async def test_moving_a_meeting_moves_its_points(self):
        (other,) = await self.add(m.Collection(user_id=self.w.user.id, name="อีกอัน"))
        await self.client.patch(f"/meetings/{self.w.meeting.id}", json={"collection_id": str(other.id)},
                                headers=self.w.headers)
        self.assertEqual(self.points(), [])
        self.assertTrue(self.points(other.id))

    async def test_renaming_a_speaker_reindexes_with_the_new_name(self):
        await self.client.patch(f"/meetings/{self.w.meeting.id}/speakers",
                                json={"speaker_label": "SPEAKER_00", "speaker_name": "คุณภัทร"}, headers=self.w.headers)
        texts = [h.text for h in self.points()]
        self.assertTrue(any(t.startswith("คุณภัทร:") for t in texts), texts)
