"""
M1 · M3 · M6 · M8 — ชุดการประชุม ทะเบียนบุคคล แดชบอร์ด และถาม-ตอบ
Persona: NovaTech Studio & SaaS

    python -m unittest tests.test_api_registry -v
"""

from __future__ import annotations

import tests  # noqa: F401  — ต้องมาก่อน import app เพื่อตั้ง env ของการทดสอบให้ทัน

from datetime import date
from unittest.mock import patch

from app.db import models as m
from app.services.llm import LlmError
from tests.support import DbCase, build_fixture


class SeriesApi(DbCase):
    """FR-M1-01 ถึง 05"""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.f = await build_fixture(self.sessionmaker)

    async def test_create_series(self):
        r = await self.client.post(
            "/api/series",
            json={
                "name": "Alpha App Launch Sprint",
                "committee_type": "Product Launch & Growth",
                "fiscal_year": 2026,
                "cadence": "weekly",
                "next_meeting_date": "2026-09-15",
                "member_ids": [str(self.f.phat.id)],
            },
        )
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertEqual(body["name"], "Alpha App Launch Sprint")
        self.assertEqual(body["member_ids"], [str(self.f.phat.id)])
        self.assertEqual(body["org_id"], str(self.f.org.id))

    async def test_create_series_writes_audit(self):
        await self.client.post("/api/series", json={"name": "ชุดใหม่", "fiscal_year": 2026})
        self.assertEqual(await self.count(m.AuditLog, action="create_series"), 1)

    async def test_list_series_only_from_this_org(self):
        r = await self.client.get("/api/series")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 2)

    async def test_get_series(self):
        r = await self.client.get(f"/api/series/{self.f.series.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["fiscal_year"], 2026)

    async def test_get_missing_series_is_404_with_thai_detail(self):
        r = await self.client.get("/api/series/00000000-0000-0000-0000-000000000000")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["detail"], "ไม่พบชุดการประชุม")

    async def test_bad_uuid_is_422_not_500(self):
        r = await self.client.get("/api/series/not-a-uuid")
        self.assertEqual(r.status_code, 422)

    async def test_patch_series_only_touches_given_fields(self):
        r = await self.client.patch(
            f"/api/series/{self.f.series.id}", json={"next_meeting_date": "2026-10-01"}
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["next_meeting_date"], "2026-10-01")
        self.assertEqual(r.json()["name"], self.f.series.name)

    async def test_delete_series_cascades_to_children(self):
        r = await self.client.delete(f"/api/series/{self.f.series.id}")
        self.assertEqual(r.status_code, 204)
        #  ไม่เหลือการประชุมหรือมติที่ชี้ไปชุดที่ถูกลบ
        self.assertEqual(await self.count(m.Meeting, series_id=self.f.series.id), 0)
        self.assertEqual(await self.count(m.Resolution, series_id=self.f.series.id), 0)
        self.assertEqual(await self.count(m.AuditLog, action="delete_series"), 1)

    async def test_series_resolutions_sorted_by_overdue(self):
        r = await self.client.get(f"/api/series/{self.f.series.id}/resolutions")
        rows = r.json()
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["ref_no"], self.f.open_res.ref_no)

    async def test_filter_resolutions_by_status(self):
        r = await self.client.get(f"/api/series/{self.f.series.id}/resolutions?status=blocked")
        self.assertEqual([row["ref_no"] for row in r.json()], [self.f.blocked_res.ref_no])

    async def test_filter_resolutions_by_assignee(self):
        r = await self.client.get(
            f"/api/series/{self.f.series.id}/resolutions?assignee={self.f.karn.id}"
        )
        self.assertEqual([row["ref_no"] for row in r.json()], [self.f.blocked_res.ref_no])

    async def test_filter_resolutions_overdue_only(self):
        r = await self.client.get(f"/api/series/{self.f.series.id}/resolutions?overdue=true")
        self.assertEqual([row["ref_no"] for row in r.json()], [self.f.open_res.ref_no])

    async def test_resolution_out_carries_assignee_ids(self):
        r = await self.client.get(f"/api/series/{self.f.series.id}/resolutions?status=confirmed")
        self.assertEqual(len(r.json()[0]["assignee_ids"]), 2)


class MeetingBinding(DbCase):
    """FR-M1-02 ผูกการประชุมเข้าชุดพร้อมครั้งที่"""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.f = await build_fixture(self.sessionmaker)

    async def test_create_meeting_derives_fiscal_year(self):
        r = await self.client.post(
            "/api/meetings",
            json={"series_id": str(self.f.series.id), "sequence_no": 3, "meeting_date": "2026-09-20"},
        )
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertEqual(body["fiscal_year"], 2569)
        self.assertEqual(body["title"], "การประชุมครั้งที่ 3")
        self.assertEqual(body["status"], "draft")
        self.assertEqual(len(body["pipeline"]), 5)

    async def test_fiscal_year_rolls_over_in_october(self):
        r = await self.client.post(
            "/api/meetings",
            json={"series_id": str(self.f.series.id), "sequence_no": 4, "meeting_date": "2026-10-01"},
        )
        self.assertEqual(r.json()["fiscal_year"], 2570)

    async def test_duplicate_sequence_in_same_series_is_409(self):
        r = await self.client.post(
            "/api/meetings",
            json={"series_id": str(self.f.series.id), "sequence_no": 1, "meeting_date": "2026-09-20"},
        )
        self.assertEqual(r.status_code, 409)
        self.assertIn("ครั้งที่ 1", r.json()["detail"])

    async def test_same_sequence_in_other_series_is_allowed(self):
        r = await self.client.post(
            "/api/meetings",
            json={
                "series_id": str(self.f.other_series.id),
                "sequence_no": 1,
                "meeting_date": "2026-09-20",
            },
        )
        self.assertEqual(r.status_code, 201)

    async def test_meeting_in_missing_series_is_404(self):
        r = await self.client.post(
            "/api/meetings",
            json={
                "series_id": "00000000-0000-0000-0000-000000000000",
                "sequence_no": 9,
                "meeting_date": "2026-09-20",
            },
        )
        self.assertEqual(r.status_code, 404)


class PeopleApi(DbCase):
    """FR-M3-01 ถึง 06"""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.f = await build_fixture(self.sessionmaker)

    async def test_list_people_sorted_by_name(self):
        r = await self.client.get("/api/people")
        names = [p["full_name"] for p in r.json()]
        self.assertEqual(len(names), 5)
        self.assertEqual(names, sorted(names))

    async def test_create_person(self):
        r = await self.client.post(
            "/api/people",
            json={
                "full_name": "สมชาย (Dev)",
                "position": "Frontend Engineer",
                "department": "Engineering",
                "email": "somchai@novatech.io",
            },
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["full_name"], "สมชาย (Dev)")
        self.assertEqual(await self.count(m.AuditLog, action="create_person"), 1)

    async def test_create_department_as_assignee(self):
        """FR-M3-05 ผู้รับผิดชอบเป็นหน่วยงาน/ทีมงานได้"""
        r = await self.client.post(
            "/api/people", json={"full_name": "ทีม QA & Testing", "is_department": True}
        )
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.json()["is_department"])

    async def test_patch_person(self):
        r = await self.client.patch(
            f"/api/people/{self.f.mint.id}", json={"full_name": "มิ้น (Mint)", "position": "Head of Growth"}
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["position"], "Head of Growth")

    async def test_delete_person(self):
        r = await self.client.delete(f"/api/people/{self.f.phat.id}")
        self.assertEqual(r.status_code, 204)
        self.assertEqual(await self.count(m.AuditLog, action="delete_person"), 1)

    async def test_delete_missing_person_is_404(self):
        r = await self.client.delete("/api/people/00000000-0000-0000-0000-000000000000")
        self.assertEqual(r.status_code, 404)

    async def test_list_aliases(self):
        r = await self.client.get("/api/people/aliases")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()), 4)

    async def test_add_alias(self):
        """FR-M3-02 alias หลายค่าต่อคน"""
        r = await self.client.post(
            "/api/people/aliases", json={"person_id": str(self.f.phat.id), "alias": "Founder"}
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(await self.count(m.PersonAlias, person_id=self.f.phat.id), 3)

    async def test_duplicate_alias_returns_existing_not_error(self):
        r = await self.client.post(
            "/api/people/aliases", json={"person_id": str(self.f.phat.id), "alias": "Product Lead"}
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(await self.count(m.PersonAlias, person_id=self.f.phat.id), 2)

    async def test_blank_alias_is_422(self):
        r = await self.client.post(
            "/api/people/aliases", json={"person_id": str(self.f.phat.id), "alias": "   "}
        )
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"], "ชื่อเรียกว่างไม่ได้")

    async def test_alias_for_missing_person_is_404(self):
        r = await self.client.post(
            "/api/people/aliases",
            json={"person_id": "00000000-0000-0000-0000-000000000000", "alias": "ใครสักคน"},
        )
        self.assertEqual(r.status_code, 404)

    async def test_remove_alias(self):
        aliases = (await self.client.get("/api/people/aliases")).json()
        r = await self.client.delete(f"/api/people/aliases/{aliases[0]['id']}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(await self.count(m.PersonAlias), 3)


class Dashboard(DbCase):
    """FR-M6-01 ถึง 05"""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.f = await build_fixture(self.sessionmaker)
        self.body = (
            await self.client.get(f"/api/series/{self.f.series.id}/dashboard")
        ).json()

    async def test_headline_counts(self):
        stats = self.body["stats"]
        self.assertEqual(stats["total"], 4)
        self.assertEqual(stats["open"], 2)   # confirmed + blocked
        self.assertEqual(stats["done"], 1)
        self.assertEqual(stats["overdue"], 1)
        self.assertEqual(stats["flagged"], 1)

    async def test_closure_rate_excludes_cancelled_and_superseded(self):
        """มติที่ยกเลิกไม่เคยต้องปิด จึงไม่ควรเป็นตัวหาร — 1/3 ไม่ใช่ 1/4"""
        self.assertEqual(self.body["stats"]["closure_rate"], 33)

    async def test_avg_days_to_close(self):
        self.assertEqual(self.body["stats"]["avg_days_to_close"], 14)

    async def test_overdue_list_excludes_closed_and_cancelled(self):
        """มติที่ปิด/ยกเลิกแล้วเลยกำหนดมานาน แต่ต้องไม่ถูกนับว่าเกินกำหนด"""
        refs = [r["ref_no"] for r in self.body["overdue"]]
        self.assertEqual(refs, [self.f.open_res.ref_no])

    async def test_flagged_list_is_postponed_three_times(self):
        refs = [r["ref_no"] for r in self.body["flagged"]]
        self.assertEqual(refs, [self.f.blocked_res.ref_no])

    async def test_status_counts(self):
        self.assertEqual(
            self.body["status_counts"],
            {"confirmed": 1, "blocked": 1, "done": 1, "cancelled": 1},
        )

    async def test_assignee_load_sorted_by_overdue_first(self):
        load = self.body["load"]
        self.assertEqual(load[0]["overdue"], 1)
        self.assertEqual({row["name"] for row in load}, {"ทีมพัฒนาและวิศวกรรม", "มิ้น (Mint)", "กานต์ (Karn)"})

    async def test_empty_series_does_not_divide_by_zero(self):
        r = await self.client.get(f"/api/series/{self.f.other_series.id}/dashboard")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["stats"]["closure_rate"], 0)
        self.assertEqual(r.json()["stats"]["avg_days_to_close"], 0)

    async def test_dashboard_of_missing_series_is_404(self):
        r = await self.client.get("/api/series/00000000-0000-0000-0000-000000000000/dashboard")
        self.assertEqual(r.status_code, 404)


class Bootstrap(DbCase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.f = await build_fixture(self.sessionmaker)

    async def test_bootstrap_shape_matches_frontend_database(self):
        r = await self.client.get("/api/bootstrap")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(
            set(body),
            {
                "org", "people", "aliases", "series", "meetings", "segments", "resolutions",
                "links", "history", "proposals", "agendas", "actions", "audit", "qa",
            },
        )
        self.assertEqual(len(body["people"]), 5)
        self.assertEqual(len(body["series"]), 2)
        self.assertEqual(len(body["meetings"]), 2)
        self.assertEqual(len(body["resolutions"]), 4)
        self.assertEqual(len(body["links"]), 3)
        self.assertEqual(len(body["segments"]), 1)

    async def test_bootstrap_keeps_thai_text_intact(self):
        body = (await self.client.get("/api/bootstrap")).json()
        self.assertEqual(body["org"]["name"], "NovaTech Studio (Demo Workspace)")
        self.assertIn("โฆษณา", body["resolutions"][0]["text"] + body["resolutions"][1]["text"] + body["resolutions"][2]["text"] + body["resolutions"][3]["text"])

    async def test_bootstrap_without_organization_is_503_with_instructions(self):
        async with self.engine.begin() as conn:
            from sqlalchemy import text as sql

            await conn.execute(sql('TRUNCATE TABLE "organization" CASCADE'))
        r = await self.client.get("/api/bootstrap")
        self.assertEqual(r.status_code, 503)
        self.assertIn("app.seed", r.json()["detail"])

    async def test_audit_entry_exposes_metadata_field(self):
        await self.add(
            m.AuditLog(
                org_id=self.f.org.id, actor="ภัทร (Phat)", action="test",
                entity_type="meeting", entity_id=str(self.f.meeting1.id), meta="รายละเอียดไทย",
            )
        )
        body = (await self.client.get("/api/bootstrap")).json()
        self.assertEqual(body["audit"][0]["metadata"], "รายละเอียดไทย")


class ActorHeader(DbCase):
    """
    ชื่อผู้กระทำเป็นภาษาไทย แต่ HTTP header ส่งได้เฉพาะ latin-1
    ถ้าไม่ decode ให้ถูก ชื่อในบันทึกจะกลายเป็นเครื่องหมายคำถามทั้งหมด
    """

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.f = await build_fixture(self.sessionmaker)

    async def test_percent_encoded_thai_actor_is_stored_readable(self):
        from urllib.parse import quote

        actor = "ภัทร (Phat)"
        r = await self.client.post(
            f"/api/resolutions/{self.f.open_res.id}/status",
            json={"status": "in_progress", "reason": "เริ่มดำเนินการแล้ว"},
            headers={"X-Actor": quote(actor)},
        )
        self.assertEqual(r.status_code, 200)
        history = (await self.client.get(f"/api/resolutions/{self.f.open_res.id}/history")).json()
        self.assertEqual(history[0]["changed_by"], actor)

    async def test_missing_actor_falls_back_to_default(self):
        await self.client.post(
            f"/api/resolutions/{self.f.open_res.id}/status",
            json={"status": "in_progress", "reason": "เริ่มดำเนินการ"},
        )
        history = (await self.client.get(f"/api/resolutions/{self.f.open_res.id}/history")).json()
        self.assertEqual(history[0]["changed_by"], "ฝ่ายเลขานุการ")


class CrossMeetingQa(DbCase):
    """M8 — การอ้างอิงทั้งหมดมาจากขั้นค้นหา ไม่ได้มาจากโมเดล จึงอ้างมั่วไม่ได้"""

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.f = await build_fixture(self.sessionmaker)
        #  ไม่เรียกโมเดลจริงระหว่างทดสอบ — บังคับให้ใช้คำตอบจากข้อเท็จจริงที่ค้นเจอ
        self.llm = patch(
            "app.services.qa.answer_from_context", side_effect=LlmError("ปิดโมเดลระหว่างทดสอบ")
        )
        self.llm.start()
        self.addCleanup(self.llm.stop)

    async def ask(self, question: str) -> dict:
        r = await self.client.post(
            f"/api/series/{self.f.series.id}/ask", json={"question": question}
        )
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    async def test_answer_from_resolution_table_has_citations_and_timeline(self):
        body = await self.ask("เรื่องระบบชำระเงิน Payment Gateway เคยมีมติว่าอะไรบ้าง")
        self.assertEqual(body["source"], "resolution_table")
        self.assertTrue(body["citations"])
        self.assertTrue(body["timeline"])
        for citation in body["citations"]:
            self.assertTrue(citation["quote"].strip())

    async def test_timeline_labels_are_thai_event_names(self):
        body = await self.ask("Payment Gateway")
        labels = " ".join(entry["label"] for entry in body["timeline"])
        self.assertIn("เกิดมติ", labels)
        self.assertIn("รายงานความคืบหน้า", labels)

    async def test_falls_back_to_transcript_search(self):
        body = await self.ask("งบประมาณรวม 500,000 บาทเดิมยังเหลือไหม")
        self.assertIn(body["source"], ("resolution_table", "semantic_search"))

    async def test_refuses_to_guess_when_nothing_matches(self):
        body = await self.ask("สนามกีฬาและสระว่ายน้ำของหน่วยงานเปิดกี่โมง")
        self.assertEqual(body["source"], "semantic_search")
        self.assertEqual(body["citations"], [])
        self.assertIn("ไม่คาดเดา", body["answer"])

    async def test_blank_question_is_422(self):
        r = await self.client.post(f"/api/series/{self.f.series.id}/ask", json={"question": "   "})
        self.assertEqual(r.status_code, 422)

    async def test_question_is_logged_and_returned_in_bootstrap(self):
        await self.ask("Payment Gateway")
        body = (await self.client.get("/api/bootstrap")).json()
        self.assertEqual(len(body["qa"][str(self.f.series.id)]), 1)

    async def test_other_series_does_not_see_these_resolutions(self):
        r = await self.client.post(
            f"/api/series/{self.f.other_series.id}/ask", json={"question": "Payment Gateway"}
        )
        body = r.json()
        self.assertEqual(body["citations"], [])

    async def test_ask_on_missing_series_is_404(self):
        r = await self.client.post(
            "/api/series/00000000-0000-0000-0000-000000000000/ask", json={"question": "อะไรก็ได้"}
        )
        self.assertEqual(r.status_code, 404)
