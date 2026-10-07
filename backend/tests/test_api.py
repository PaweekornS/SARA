"""
API ระดับ HTTP — เน้นเรื่องสิทธิ์: ผู้ใช้คนหนึ่งต้องมองไม่เห็นและแตะต้องข้อมูลของอีกคนไม่ได้

    python -m unittest tests.test_api -v
"""

from __future__ import annotations

import io
from unittest.mock import patch

import tests  # noqa: F401
from app.api import auth as auth_api
from app.core.config import settings
from app.db import models as m
from tests.support import DbCase, auth_headers, build_workspace

GOOGLE_INFO = {"iss": "https://accounts.google.com", "sub": "g-123", "email": "New@Example.com",
               "email_verified": True, "name": "ผู้ใช้ใหม่", "picture": "https://pic"}


class Auth(DbCase):
    async def test_protected_routes_require_login(self):
        for method, path in (("GET", "/collections"), ("GET", "/auth/me"), ("POST", "/meetings")):
            r = await self.client.request(method, path)
            self.assertEqual(r.status_code, 401, path)

    async def test_garbage_bearer_is_401(self):
        r = await self.client.get("/collections", headers={"Authorization": "Bearer nope"})
        self.assertEqual(r.status_code, 401)

    async def test_google_login_creates_user_and_first_collection_once(self):
        with patch.object(auth_api, "verify_google_token", return_value=GOOGLE_INFO):
            first = await self.client.post("/auth/google", json={"id_token": "t"})
            second = await self.client.post("/auth/google", json={"id_token": "t"})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["user"]["email"], "new@example.com")
        self.assertEqual(first.json()["user"]["id"], second.json()["user"]["id"])
        self.assertEqual(await self.count(m.User), 1)
        self.assertEqual(await self.count(m.Collection), 1)
        self.assertIn("httponly", first.headers["set-cookie"].lower())

    async def test_session_cookie_authenticates(self):
        with patch.object(auth_api, "verify_google_token", return_value=GOOGLE_INFO):
            login = await self.client.post("/auth/google", json={"id_token": "t"})
        r = await self.client.get("/auth/me", cookies={"access_token": login.json()["access_token"]})
        self.assertEqual(r.json()["email"], "new@example.com")

    async def test_invalid_google_token_is_401(self):
        r = await self.client.post("/auth/google", json={"id_token": "mock-google-token-:a@b.c:x"})
        self.assertEqual(r.status_code, 401)

    async def test_demo_login_always_uses_the_fixed_demo_account(self):
        (victim,) = await self.add(m.User(email="victim@gmail.com", name="เหยื่อ"))
        r = await self.client.post("/auth/demo", json={"name": "ใครก็ได้", "email": "victim@gmail.com"})
        self.assertEqual(r.json()["user"]["email"], auth_api.DEMO_EMAIL)
        self.assertNotEqual(r.json()["user"]["id"], str(victim.id))

    async def test_demo_login_is_hidden_on_prod(self):
        with patch.object(type(settings), "demo_login_enabled", property(lambda self: False)):
            r = await self.client.post("/auth/demo", json={})
        self.assertEqual(r.status_code, 404)

    async def test_token_for_deleted_user_is_401(self):
        (ghost,) = await self.add(m.User(email="ghost@x.com"))
        headers = auth_headers(ghost)
        async with self.sessionmaker() as s:
            await s.delete(await s.get(m.User, ghost.id))
            await s.commit()
        self.assertEqual((await self.client.get("/auth/me", headers=headers)).status_code, 401)


class Isolation(DbCase):
    """บ็อบรู้ id ของอลิซทุกตัว แต่ต้องได้ 404 ทุกทาง และข้อมูลของอลิซต้องไม่เปลี่ยน"""

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.alice = await build_workspace(self, "alice@x.com", "อลิซ")
        self.bob = await build_workspace(self, "bob@x.com", "บ็อบ")

    async def test_lists_only_show_own_collections(self):
        r = await self.client.get("/collections", headers=self.bob.headers)
        self.assertEqual([c["id"] for c in r.json()], [str(self.bob.collection.id)])

    async def test_every_route_with_someone_elses_id_is_404(self):
        a, h = self.alice, self.bob.headers
        c, mt, item = a.collection.id, a.meeting.id, a.open_item.id
        calls = [
            ("GET", f"/collections/{c}", None),
            ("PATCH", f"/collections/{c}", {"name": "ยึด"}),
            ("DELETE", f"/collections/{c}", None),
            ("GET", f"/collections/{c}/meetings", None),
            ("GET", f"/collections/{c}/action-items", None),
            ("POST", f"/collections/{c}/ask", {"question": "งบประมาณเท่าไร"}),
            ("GET", f"/collections/{c}/qa", None),
            ("DELETE", f"/collections/{c}/qa", None),
            ("GET", f"/meetings/{mt}", None),
            ("PATCH", f"/meetings/{mt}", {"title": "ยึด"}),
            ("DELETE", f"/meetings/{mt}", None),
            ("POST", f"/meetings/{mt}/retry", None),
            ("GET", f"/meetings/{mt}/segments", None),
            ("GET", f"/meetings/{mt}/audio", None),
            ("PATCH", f"/meetings/{mt}/speakers", {"speaker_label": "SPEAKER_00", "speaker_name": "x"}),
            ("GET", f"/meetings/{mt}/action-items", None),
            ("POST", f"/meetings/{mt}/action-items", {"text": "แทรก"}),
            ("GET", f"/meetings/{mt}/export", None),
            ("POST", f"/meetings/{mt}/email", {"recipients": ["bob@x.com"]}),
            ("PATCH", f"/action-items/{item}", {"done": True}),
            ("DELETE", f"/action-items/{item}", None),
            ("POST", f"/action-items/{item}/suggestion/accept", None),
            ("POST", f"/action-items/{item}/suggestion/dismiss", None),
        ]
        for method, path, body in calls:
            r = await self.client.request(method, path, json=body, headers=h)
            self.assertEqual(r.status_code, 404, f"{method} {path} → {r.status_code}")

        self.assertEqual((await self.fetch(m.Collection, c)).name, a.collection.name)
        self.assertEqual((await self.fetch(m.Meeting, mt)).title, a.meeting.title)
        self.assertFalse((await self.fetch(m.ActionItem, item)).done)
        self.assertEqual(await self.count(m.ActionItem, meeting_id=mt), 2)

    async def test_cannot_move_own_meeting_into_someone_elses_collection(self):
        r = await self.client.patch(
            f"/meetings/{self.bob.meeting.id}",
            json={"collection_id": str(self.alice.collection.id)},
            headers=self.bob.headers,
        )
        self.assertEqual(r.status_code, 404)

    async def test_cannot_upload_into_someone_elses_collection(self):
        with patch("app.api.meetings.process_meeting_task") as task:
            r = await self.client.post(
                "/meetings",
                data={"collection_id": str(self.alice.collection.id)},
                files={"file": ("a.txt", b"hello", "text/plain")},
                headers=self.bob.headers,
            )
        self.assertEqual(r.status_code, 404)
        task.delay.assert_not_called()

    async def test_qa_never_cites_another_users_meetings(self):
        with patch("app.services.qa.answer_from_context", return_value="คำตอบ"):
            r = await self.client.post(
                f"/collections/{self.bob.collection.id}/ask",
                json={"question": "งบประมาณการตลาด"}, headers=self.bob.headers,
            )
        ids = {c["meeting_id"] for c in r.json()["citations"]}
        self.assertTrue(ids)
        self.assertEqual(ids, {str(self.bob.meeting.id)})


class Collections(DbCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.w = await build_workspace(self, "me@x.com", "ฉัน")

    async def test_create_and_counts(self):
        r = await self.client.post("/collections", json={"name": "ใหม่"}, headers=self.w.headers)
        self.assertEqual(r.status_code, 201)
        listing = {c["name"]: c for c in (await self.client.get("/collections", headers=self.w.headers)).json()}
        self.assertEqual(listing[self.w.collection.name]["meeting_count"], 1)
        self.assertEqual(listing[self.w.collection.name]["open_action_count"], 1)
        self.assertEqual(listing["ใหม่"]["meeting_count"], 0)

    async def test_unknown_template_is_422(self):
        r = await self.client.post("/collections", json={"name": "x", "default_template": "nope"}, headers=self.w.headers)
        self.assertEqual(r.status_code, 422)

    async def test_delete_cascades(self):
        r = await self.client.delete(f"/collections/{self.w.collection.id}", headers=self.w.headers)
        self.assertEqual(r.status_code, 204)
        self.assertEqual(await self.count(m.Meeting), 0)
        self.assertEqual(await self.count(m.ActionItem), 0)
        self.assertEqual(await self.count(m.TranscriptSegment), 0)

    async def test_action_items_filter(self):
        url = f"/collections/{self.w.collection.id}/action-items"
        self.assertEqual(len((await self.client.get(url, headers=self.w.headers)).json()), 2)
        open_only = (await self.client.get(url, params={"done": "false"}, headers=self.w.headers)).json()
        self.assertEqual([i["text"] for i in open_only], ["ส่งแบบโฆษณา"])

    async def test_ask_is_logged_and_listed(self):
        with patch("app.services.qa.answer_from_context", return_value="ห้าแสนบาท"):
            r = await self.client.post(f"/collections/{self.w.collection.id}/ask",
                                       json={"question": "งบประมาณการตลาดเท่าไร"}, headers=self.w.headers)
        self.assertEqual(r.json()["answer"], "ห้าแสนบาท")
        history = (await self.client.get(f"/collections/{self.w.collection.id}/qa", headers=self.w.headers)).json()
        self.assertEqual(len(history), 1)

    async def test_ask_with_no_match_does_not_call_the_model(self):
        with patch("app.services.qa.answer_from_context") as llm:
            r = await self.client.post(f"/collections/{self.w.collection.id}/ask",
                                       json={"question": "ราคาทุเรียนหมอนทอง"}, headers=self.w.headers)
        llm.assert_not_called()
        self.assertEqual(r.json()["citations"], [])


class Meetings(DbCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.w = await build_workspace(self, "me@x.com", "ฉัน")
        patcher = patch("app.api.meetings.process_meeting_task")
        self.task = patcher.start()
        self.addCleanup(patcher.stop)

    async def upload(self, name="meeting.m4a", content=b"\x00" * 100, **data):
        data.setdefault("collection_id", str(self.w.collection.id))
        return await self.client.post("/meetings", data=data, files={"file": (name, content)}, headers=self.w.headers)

    async def test_upload_creates_meeting_and_queues_it(self):
        r = await self.upload(title="ประชุมใหม่", template="marketing")
        self.assertEqual(r.status_code, 202)
        body = r.json()
        self.assertEqual((body["status"], body["source_kind"], body["template"]), ("processing", "audio", "marketing"))
        self.task.delay.assert_called_once_with(body["id"])
        self.assertIsNotNone((await self.fetch(m.Meeting, body["id"])).processing_started_at)

    async def test_upload_uses_collection_default_template(self):
        async with self.sessionmaker() as s:
            (await s.get(m.Collection, self.w.collection.id)).default_template = "finance"
            await s.commit()
        self.assertEqual((await self.upload()).json()["template"], "finance")

    async def test_bad_files_are_rejected(self):
        self.assertEqual((await self.upload(name="x.exe")).status_code, 415)
        self.assertEqual((await self.upload(content=b"")).status_code, 422)
        self.assertEqual((await self.upload(template="nope")).status_code, 422)
        self.task.delay.assert_not_called()

    async def test_oversized_file_is_413(self):
        with patch("app.services.storage.MAX_UPLOAD_BYTES", 10):
            self.assertEqual((await self.upload(content=b"x" * 11)).status_code, 413)

    async def test_retry_only_for_failed(self):
        url = f"/meetings/{self.w.meeting.id}/retry"
        self.assertEqual((await self.client.post(url, headers=self.w.headers)).status_code, 409)
        async with self.sessionmaker() as s:
            (await s.get(m.Meeting, self.w.meeting.id)).status = m.MeetingStatus.FAILED
            await s.commit()
        async with self.sessionmaker() as s:
            (await s.get(m.Meeting, self.w.meeting.id)).processing_attempts = 2
            await s.commit()
        self.assertEqual((await self.client.post(url, headers=self.w.headers)).status_code, 202)
        self.task.delay.assert_called_once()
        retried = await self.fetch(m.Meeting, self.w.meeting.id)
        self.assertEqual(retried.processing_attempts, 0)
        self.assertIsNotNone(retried.processing_started_at)

    async def test_moving_a_meeting_moves_its_action_items(self):
        (other,) = await self.add(m.Collection(user_id=self.w.user.id, name="อีกอัน"))
        r = await self.client.patch(f"/meetings/{self.w.meeting.id}", json={"collection_id": str(other.id)},
                                    headers=self.w.headers)
        self.assertEqual(r.json()["collection_id"], str(other.id))
        self.assertEqual(await self.count(m.ActionItem, collection_id=other.id), 2)

    async def test_rename_speaker_applies_to_all_their_segments(self):
        r = await self.client.patch(f"/meetings/{self.w.meeting.id}/speakers",
                                    json={"speaker_label": "SPEAKER_00", "speaker_name": "คุณภัทร"}, headers=self.w.headers)
        names = {s["speaker_label"]: s["speaker_name"] for s in r.json()}
        self.assertEqual(names, {"SPEAKER_00": "คุณภัทร", "SPEAKER_01": ""})

    async def test_audio_is_streamed_with_range_support(self):
        r = await self.upload(name="talk.mp3", content=bytes(range(256)) * 4)
        url = f"/meetings/{r.json()['id']}/audio"
        full = await self.client.get(url, headers=self.w.headers)
        self.assertEqual((full.status_code, full.headers["content-type"]), (200, "audio/mpeg"))
        part = await self.client.get(url, headers={**self.w.headers, "Range": "bytes=10-19"})
        self.assertEqual(part.status_code, 206)
        self.assertEqual(part.content, bytes(range(10, 20)))

    async def test_transcript_meetings_have_no_audio(self):
        r = await self.upload(name="notes.txt", content=b"hello")
        self.assertEqual((await self.client.get(f"/meetings/{r.json()['id']}/audio", headers=self.w.headers)).status_code, 404)

    async def test_export_docx(self):
        r = await self.client.get(f"/meetings/{self.w.meeting.id}/export", headers=self.w.headers)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b"PK"))

    async def test_export_refused_while_processing(self):
        r = await self.upload()
        self.assertEqual((await self.client.get(f"/meetings/{r.json()['id']}/export", headers=self.w.headers)).status_code, 409)

    async def test_email_content_comes_from_the_meeting(self):
        with patch("app.services.email.send_html") as send:
            r = await self.client.post(f"/meetings/{self.w.meeting.id}/email",
                                       json={"recipients": ["a@x.com", "A@x.com", "b@x.com"]}, headers=self.w.headers)
        self.assertEqual(r.json(), {"sent": ["a@x.com", "b@x.com"], "failed": []})
        html = send.call_args.args[2]
        self.assertIn(self.w.meeting.summary, html)
        self.assertIn("ส่งแบบโฆษณา", html)
        self.assertEqual(send.call_args.kwargs["reply_to"], "me@x.com")

    async def test_email_recipient_cap(self):
        recipients = [f"u{i}@x.com" for i in range(settings.MAX_EMAIL_RECIPIENTS + 1)]
        r = await self.client.post(f"/meetings/{self.w.meeting.id}/email", json={"recipients": recipients},
                                   headers=self.w.headers)
        self.assertEqual(r.status_code, 422)

    async def test_email_daily_quota(self):
        with patch("app.services.ratelimit.consume", return_value=False), patch("app.services.email.send_html") as send:
            r = await self.client.post(f"/meetings/{self.w.meeting.id}/email", json={"recipients": ["a@x.com"]},
                                       headers=self.w.headers)
        self.assertEqual(r.status_code, 429)
        send.assert_not_called()

    async def test_delete_meeting(self):
        r = await self.client.delete(f"/meetings/{self.w.meeting.id}", headers=self.w.headers)
        self.assertEqual(r.status_code, 204)
        self.assertEqual(await self.count(m.ActionItem), 0)


class ActionItems(DbCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.w = await build_workspace(self, "me@x.com", "ฉัน")
        self.url = f"/action-items/{self.w.open_item.id}"

    async def test_mark_done_and_undo(self):
        r = await self.client.patch(self.url, json={"done": True}, headers=self.w.headers)
        self.assertTrue(r.json()["done"])
        self.assertIsNotNone(r.json()["done_at"])
        r = await self.client.patch(self.url, json={"done": False}, headers=self.w.headers)
        self.assertIsNone(r.json()["done_at"])

    async def test_edit_fields_and_clear_due_date(self):
        r = await self.client.patch(self.url, json={"text": "แก้แล้ว", "owner": "กานต์", "due_date": None},
                                    headers=self.w.headers)
        body = r.json()
        self.assertEqual((body["text"], body["owner"], body["due_date"]), ("แก้แล้ว", "กานต์", None))

    async def test_add_manual_item(self):
        r = await self.client.post(f"/meetings/{self.w.meeting.id}/action-items", json={"text": "งานเพิ่ม"},
                                   headers=self.w.headers)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["collection_id"], str(self.w.collection.id))

    async def suggest(self):
        async with self.sessionmaker() as s:
            item = await s.get(m.ActionItem, self.w.open_item.id)
            item.suggested_done_meeting_id = self.w.meeting.id
            item.suggested_done_evidence = "ส่งแล้วครับ"
            await s.commit()

    async def test_accept_suggestion_marks_done_and_clears_it(self):
        await self.suggest()
        r = await self.client.post(f"{self.url}/suggestion/accept", headers=self.w.headers)
        self.assertTrue(r.json()["done"])
        self.assertIsNone(r.json()["suggested_done_meeting_id"])

    async def test_dismiss_suggestion_keeps_item_open(self):
        await self.suggest()
        r = await self.client.post(f"{self.url}/suggestion/dismiss", headers=self.w.headers)
        self.assertFalse(r.json()["done"])
        self.assertEqual(r.json()["suggested_done_evidence"], "")

    async def test_accept_without_suggestion_is_409(self):
        self.assertEqual((await self.client.post(f"{self.url}/suggestion/accept", headers=self.w.headers)).status_code, 409)


class PublicApi(DbCase):
    async def test_templates_are_public(self):
        r = await self.client.get("/public/templates")
        self.assertEqual({t["id"] for t in r.json()}, {"general", "marketing", "finance", "tech_standup"})

    async def test_summarize_text_file_without_login(self):
        from app.services.extraction import ActionItemDraft, SummaryResult

        fake = SummaryResult(summary="สรุป", key_points=["ก"], action_items=[ActionItemDraft(text="งาน")])
        with patch("app.api.public.summarize", return_value=fake):
            r = await self.client.post("/public/summarize", data={"template": "general"},
                                       files={"file": ("n.txt", io.BytesIO("สวัสดีครับ ประชุมเริ่ม".encode()))})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["action_items"], [{"text": "งาน", "owner": "", "due_date": None}])
        self.assertEqual(await self.count(m.Meeting), 0)

    async def test_summarize_quota(self):
        with patch("app.services.ratelimit.consume", return_value=False):
            r = await self.client.post("/public/summarize", files={"file": ("n.txt", b"hi")})
        self.assertEqual(r.status_code, 429)

    async def test_old_open_email_relay_is_gone(self):
        r = await self.client.post("/public/send-email", json={"recipients": ["x@y.com"]})
        self.assertEqual(r.status_code, 404)
