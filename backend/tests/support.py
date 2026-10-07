"""
โครงร่างที่เคสระดับ API และ worker ใช้ร่วมกัน

ทำไมต้องใช้ PostgreSQL จริงแทน SQLite:
    ตารางใช้ชนิด JSONB และ UUID ของ PostgreSQL โดยตรง (app/db/models.py)
    การทดสอบบน SQLite จึงต้องแก้ชนิดข้อมูลจนไม่เหลือความหมายของการทดสอบ

ทำไมสร้าง engine ใหม่ทุกเคส:
    IsolatedAsyncioTestCase สร้าง event loop ใหม่ต่อหนึ่งเคส
    ส่วน asyncpg ผูก connection ไว้กับ loop ที่สร้างมัน — ใช้ engine ข้าม loop แล้วพัง
"""

from __future__ import annotations

import asyncio
import unittest
from datetime import date
from uuid import UUID

from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import tests  # noqa: F401  — ต้องมาก่อน import app เพื่อตั้ง env ของการทดสอบให้ทัน
from app.core.config import settings
from app.core.security import create_access_token
from app.db import models as m
from app.db.session import Base, get_db
from app.main import app
from app.services import vector_store

SETUP_HINT = (
    "ต่อฐานข้อมูลสำหรับทดสอบไม่ได้ที่ %s\n"
    "  เริ่มฐานทดสอบด้วย:\n"
    "    docker run -d --name sara_test_db -e POSTGRES_PASSWORD=postgrespassword \\\n"
    "        -e POSTGRES_DB=sara_test -p 55432:5432 postgres:15-alpine\n"
    "  หรือชี้ไปฐานอื่นด้วย TEST_DATABASE_URL"
)

_schema_ready = False


async def _create_schema() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


def ensure_schema() -> None:
    """สร้างตารางใหม่ครั้งเดียวต่อการรันหนึ่งครั้ง"""
    global _schema_ready
    if _schema_ready:
        return
    try:
        asyncio.run(_create_schema())
    except Exception as err:  # noqa: BLE001
        raise RuntimeError(SETUP_HINT % settings.DATABASE_URL) from err
    _schema_ready = True


#  ล้างทุกตารางในคำสั่งเดียว CASCADE จัดการลำดับ foreign key ให้เอง
_TRUNCATE = "TRUNCATE TABLE {} RESTART IDENTITY CASCADE".format(
    ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
)


def fresh_vector_store() -> None:
    from qdrant_client import QdrantClient

    from tests.fakes import HashEmbedder

    vector_store.configure(QdrantClient(":memory:"), HashEmbedder())


def index_workspace(w: Workspace) -> None:
    chunks = vector_store.build_chunks(w.meeting.id, w.meeting.summary, w.segments)
    vector_store.index_meeting(w.user.id, w.collection.id, w.meeting.id, chunks)


def auth_headers(user: m.User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


class DbCase(unittest.IsolatedAsyncioTestCase):
    """เคสที่ต้องใช้ฐานข้อมูล — ข้อมูลถูกล้างใหม่ก่อนทุกเคส"""

    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        ensure_schema()

    async def asyncSetUp(self) -> None:
        fresh_vector_store()
        self.engine = create_async_engine(settings.DATABASE_URL)
        self.sessionmaker = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

        async with self.engine.begin() as conn:
            await conn.execute(text(_TRUNCATE))

        async def override_get_db():
            async with self.sessionmaker() as session:
                yield session

        app.dependency_overrides[get_db] = override_get_db
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")

    async def asyncTearDown(self) -> None:
        app.dependency_overrides.clear()
        await self.client.aclose()
        await self.engine.dispose()

    async def fetch(self, model, entity_id):
        """อ่านจากฐานข้อมูลตรง ๆ เพื่อยืนยันว่า API เขียนลงจริง ไม่ใช่แค่ตอบกลับสวย"""
        async with self.sessionmaker() as session:
            return await session.get(model, UUID(str(entity_id)))

    async def count(self, model, **where) -> int:
        from sqlalchemy import func, select

        stmt = select(func.count()).select_from(model)
        for key, value in where.items():
            stmt = stmt.where(getattr(model, key) == value)
        async with self.sessionmaker() as session:
            return (await session.execute(stmt)).scalar_one()

    async def add(self, *rows):
        async with self.sessionmaker() as session:
            session.add_all(rows)
            await session.commit()
            for row in rows:
                await session.refresh(row)
        return rows


class Workspace:
    """ข้อมูลของผู้ใช้หนึ่งคน: collection 1 อัน, การประชุมที่เสร็จแล้ว 1 ครั้ง, segment 2 ท่อน, งาน 2 ข้อ"""

    user: m.User
    collection: m.Collection
    meeting: m.Meeting
    segments: list[m.TranscriptSegment]
    open_item: m.ActionItem
    done_item: m.ActionItem
    headers: dict[str, str]


async def build_workspace(case: DbCase, email: str, name: str) -> Workspace:
    w = Workspace()
    (w.user,) = await case.add(m.User(email=email, name=name, provider="google", google_sub=f"sub-{email}"))
    (w.collection,) = await case.add(m.Collection(user_id=w.user.id, name=f"งานของ{name}"))
    (w.meeting,) = await case.add(
        m.Meeting(
            user_id=w.user.id, collection_id=w.collection.id, title=f"ประชุมทีมของ{name}",
            meeting_date=date(2026, 9, 1), template="general", source_kind="transcript",
            status=m.MeetingStatus.READY, pipeline=[], summary=f"สรุปงบประมาณการตลาดของ{name}",
            key_points=["งบประมาณ"], details={"decisions": ["อนุมัติงบ"]},
        )
    )
    w.segments = list(
        await case.add(
            m.TranscriptSegment(meeting_id=w.meeting.id, speaker_label="SPEAKER_00", start_ms=0, end_ms=5000,
                                text="เราอนุมัติงบประมาณการตลาดห้าแสนบาท"),
            m.TranscriptSegment(meeting_id=w.meeting.id, speaker_label="SPEAKER_01", start_ms=5000, end_ms=9000,
                                text="ฝั่งดีไซน์จะส่งแบบโฆษณาวันศุกร์"),
        )
    )
    w.open_item, w.done_item = await case.add(
        m.ActionItem(user_id=w.user.id, meeting_id=w.meeting.id, collection_id=w.collection.id,
                     text="ส่งแบบโฆษณา", owner="มิ้น", due_date=date(2026, 9, 5)),
        m.ActionItem(user_id=w.user.id, meeting_id=w.meeting.id, collection_id=w.collection.id,
                     text="สรุปงบประมาณ", done=True),
    )
    w.headers = auth_headers(w.user)
    return w
