"""
ข้อมูลตัวอย่างสำหรับพัฒนา — บัญชี demo ที่มี collection และการประชุมที่สรุปเสร็จแล้ว 2 ครั้ง

    python -m app.seed

รันซ้ำได้ ถ้ามีบัญชี demo อยู่แล้วจะไม่ทำอะไร ไม่รันบน ENV=prod
"""

from __future__ import annotations

import asyncio
from datetime import date

from sqlalchemy import select

from app.api.auth import DEMO_EMAIL
from app.core.config import settings
from app.db.models import (
    ActionItem,
    Collection,
    Meeting,
    MeetingStatus,
    TranscriptSegment,
    User,
)
from app.db.session import AsyncSessionLocal
from app.workers.tasks import INITIAL_PIPELINE

DONE_PIPELINE = [{**step, "state": "ok"} for step in INITIAL_PIPELINE]

KICKOFF = [
    ("SPEAKER_00", "เริ่มประชุมเรื่องเปิดตัวแอปเวอร์ชันใหม่ครับ เป้าคือปล่อยเบต้าภายในสิ้นเดือน"),
    ("SPEAKER_01", "ฝั่งการตลาดขอทำ landing page ใหม่ จะส่ง draft ให้ดูวันศุกร์นี้"),
    ("SPEAKER_02", "ฝั่ง dev ยังติดเรื่อง rate limit ของ API ต้องแก้ก่อนเปิดเบต้า"),
    ("SPEAKER_00", "โอเค งั้นกานต์รับเรื่อง rate limit ส่วนมิ้นรับ landing page นะครับ"),
]

FOLLOWUP = [
    ("SPEAKER_00", "อัปเดตจากรอบที่แล้วครับ"),
    ("SPEAKER_02", "rate limit แก้เสร็จแล้ว deploy ขึ้น staging เรียบร้อย"),
    ("SPEAKER_01", "landing page ยังไม่เสร็จ ติดรอรูปจากดีไซเนอร์ ขอเลื่อนไปสัปดาห์หน้า"),
    ("SPEAKER_00", "งั้นรอบนี้เพิ่มงานเตรียม FAQ สำหรับผู้ใช้เบต้าด้วย"),
]


def _segments(meeting: Meeting, lines: list[tuple[str, str]]) -> list[TranscriptSegment]:
    return [
        TranscriptSegment(
            meeting_id=meeting.id, speaker_label=label, start_ms=i * 15000, end_ms=(i + 1) * 15000, text=text
        )
        for i, (label, text) in enumerate(lines)
    ]


async def seed() -> None:
    async with AsyncSessionLocal() as s:
        if (await s.execute(select(User).where(User.email == DEMO_EMAIL))).scalars().first():
            print("มีบัญชี demo อยู่แล้ว ข้าม")
            return

        user = User(email=DEMO_EMAIL, name="ผู้ใช้ทดลอง", provider="demo")
        s.add(user)
        await s.flush()

        collection = Collection(user_id=user.id, name="โปรเจกต์เปิดตัวแอป", description="ประชุมทีมทุกสัปดาห์")
        s.add(collection)
        await s.flush()

        kickoff = Meeting(
            user_id=user.id, collection_id=collection.id, title="Kickoff: เปิดตัวเบต้า",
            meeting_date=date(2026, 9, 1), template="general", source_kind="transcript",
            status=MeetingStatus.READY, pipeline=DONE_PIPELINE,
            summary="ทีมตั้งเป้าเปิดเบต้าภายในสิ้นเดือน การตลาดทำ landing page ใหม่ ส่วน dev ต้องแก้ rate limit ก่อน",
            key_points=["เปิดเบต้าภายในสิ้นเดือน", "rate limit เป็นตัวบล็อกหลัก"],
            details={"decisions": ["แบ่งงาน rate limit ให้ dev และ landing page ให้การตลาด"]},
        )
        followup = Meeting(
            user_id=user.id, collection_id=collection.id, title="ติดตามความคืบหน้าเบต้า",
            meeting_date=date(2026, 9, 8), template="general", source_kind="transcript",
            status=MeetingStatus.READY, pipeline=DONE_PIPELINE,
            summary="rate limit แก้เสร็จและขึ้น staging แล้ว landing page เลื่อนไปสัปดาห์หน้า เพิ่มงานเตรียม FAQ",
            key_points=["rate limit เสร็จแล้ว", "landing page เลื่อน"],
            details={},
        )
        s.add_all([kickoff, followup])
        await s.flush()

        s.add_all(_segments(kickoff, KICKOFF))
        followup_segments = _segments(followup, FOLLOWUP)
        s.add_all(followup_segments)
        await s.flush()

        s.add_all([
            ActionItem(
                user_id=user.id, meeting_id=kickoff.id, collection_id=collection.id,
                text="แก้ปัญหา rate limit ของ API ก่อนเปิดเบต้า", owner="กานต์",
                suggested_done_meeting_id=followup.id,
                suggested_done_evidence=followup_segments[1].text,
            ),
            ActionItem(
                user_id=user.id, meeting_id=kickoff.id, collection_id=collection.id,
                text="ส่ง draft landing page ใหม่", owner="มิ้น", due_date=date(2026, 9, 5),
            ),
            ActionItem(
                user_id=user.id, meeting_id=followup.id, collection_id=collection.id,
                text="เตรียม FAQ สำหรับผู้ใช้เบต้า",
            ),
        ])
        await s.commit()
        print(f"สร้างบัญชี demo ({DEMO_EMAIL}) พร้อมข้อมูลตัวอย่างแล้ว")


if __name__ == "__main__":
    if settings.is_prod:
        raise SystemExit("ไม่รัน seed บน ENV=prod")
    asyncio.run(seed())
