"""
โครงร่างที่เคสระดับ API และ worker ใช้ร่วมกัน

ทำไมต้องใช้ PostgreSQL จริงแทน SQLite:
    ตารางใช้ชนิด JSONB และ UUID ของ PostgreSQL โดยตรง (app/db/models.py)
    การทดสอบบน SQLite จึงต้องแก้ชนิดข้อมูลจนไม่เหลือความหมายของการทดสอบ
    สู้ต่อฐานจริงที่แยกออกมาต่างหากตรง ๆ ดีกว่า

ทำไมสร้าง engine ใหม่ทุกเคส:
    IsolatedAsyncioTestCase สร้าง event loop ใหม่ต่อหนึ่งเคส
    ส่วน asyncpg ผูก connection ไว้กับ loop ที่สร้างมัน — ใช้ engine ข้าม loop แล้วพัง
    (บทเรียนเดียวกับ session_scope() ใน app/workers/tasks.py)
"""

from __future__ import annotations

import tests  # noqa: F401  — ต้องมาก่อน import app เพื่อตั้ง env ของการทดสอบให้ทัน

import asyncio
import unittest
from datetime import date, datetime, timedelta
from uuid import UUID

from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db import models as m
from app.db.session import Base, get_db
from app.main import app

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
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


def ensure_schema() -> None:
    """สร้างตารางครั้งเดียวต่อการรันหนึ่งครั้ง"""
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


class DbCase(unittest.IsolatedAsyncioTestCase):
    """เคสที่ต้องใช้ฐานข้อมูล — ข้อมูลถูกล้างใหม่ก่อนทุกเคส"""

    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        ensure_schema()

    async def asyncSetUp(self) -> None:
        self.engine = create_async_engine(settings.DATABASE_URL)
        self.sessionmaker = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

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

    # ── ตัวช่วย ────────────────────────────────────────────────────────

    async def session(self) -> AsyncSession:
        return self.sessionmaker()

    async def fetch(self, model, entity_id):
        """อ่านค่าจากฐานข้อมูลตรง ๆ เพื่อยืนยันว่า API เขียนลงจริง ไม่ใช่แค่ตอบกลับสวย"""
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


class Fixture:
    """ข้อมูลตั้งต้นขนาดเล็กสำหรับเคส — เล็กกว่า app/seed.py แต่มีครบทุกความสัมพันธ์ที่ต้องทดสอบ"""

    def __init__(self) -> None:
        self.org: m.Organization
        self.chair: m.Person
        self.supply: m.Person
        self.it: m.Person
        self.dept: m.Person
        self.series: m.MeetingSeries
        self.other_series: m.MeetingSeries
        self.meeting1: m.Meeting
        self.meeting2: m.Meeting
        self.segment: m.TranscriptSegment
        self.open_res: m.Resolution
        self.blocked_res: m.Resolution
        self.done_res: m.Resolution
        self.cancelled_res: m.Resolution
        self.overdue_by: int


async def build_fixture(sessionmaker) -> Fixture:
    """
    สร้างชุดข้อมูลที่ครอบคลุมกรณีสำคัญ:
      * มติค้างที่เกินกำหนด · มติที่เลื่อนซ้ำ 3 ครั้ง · มติที่ปิดแล้ว · มติที่ยกเลิก
      * ชุดการประชุมที่สองไว้ตรวจว่าข้อมูลไม่รั่วข้ามชุด
      * ผู้รับผิดชอบที่เป็นหน่วยงาน ไม่ใช่บุคคล
    """
    f = Fixture()
    #  กำหนดเสร็จตั้งเทียบกับวันนี้เสมอ ไม่งั้นเคสจะพังเองเมื่อเวลาผ่านไป
    today = date.today()
    f.overdue_by = 26
    due_overdue = today - timedelta(days=f.overdue_by)
    due_future = today + timedelta(days=18)

    async with sessionmaker() as s:
        f.org = m.Organization(name="สำนักงานทดสอบระบบ")
        s.add(f.org)
        await s.flush()

        f.chair = m.Person(
            org_id=f.org.id, full_name="นายธนกฤต อารีวงศ์", position="ผู้อำนวยการ",
            department="สำนักผู้อำนวยการ", email="chair@test.go.th",
        )
        f.supply = m.Person(
            org_id=f.org.id, full_name="นางกาญจนา พูลสวัสดิ์", position="หัวหน้าฝ่ายพัสดุ",
            department="ฝ่ายพัสดุ", email="supply@test.go.th",
        )
        f.it = m.Person(
            org_id=f.org.id, full_name="นายวีระพงษ์ ศรีสมบูรณ์", position="หัวหน้าฝ่ายไอที",
            department="ฝ่ายไอที", email="",  # ตั้งใจไม่มีอีเมล ใช้ทดสอบเส้นทางส่งไม่ได้
        )
        f.dept = m.Person(
            org_id=f.org.id, full_name="ฝ่ายพัสดุ", position="หน่วยงาน",
            department="ฝ่ายพัสดุ", email="dept@test.go.th", is_department=True,
        )
        s.add_all([f.chair, f.supply, f.it, f.dept])
        await s.flush()

        s.add(m.PersonAlias(person_id=f.chair.id, alias="ท่านประธาน", source="manual", confidence=1.0))

        f.series = m.MeetingSeries(
            org_id=f.org.id, name="คณะกรรมการบริหาร ปีงบประมาณ 2569",
            committee_type="คณะกรรมการบริหาร", fiscal_year=2569, cadence="monthly",
            next_meeting_date=date(2026, 9, 20), member_ids=[str(f.chair.id), str(f.supply.id)],
        )
        f.other_series = m.MeetingSeries(
            org_id=f.org.id, name="คณะกรรมการวิชาการ ปีงบประมาณ 2569",
            committee_type="คณะกรรมการวิชาการ", fiscal_year=2569, cadence="quarterly",
        )
        s.add_all([f.series, f.other_series])
        await s.flush()

        done_pipeline = [
            {"stage": stage, "state": "ok", "detail": ""}
            for stage in ("upload", "asr", "extract", "done")
        ]
        f.meeting1 = m.Meeting(
            series_id=f.series.id, sequence_no=1, fiscal_year=2569, meeting_date=date(2026, 5, 20),
            title="การประชุมครั้งที่ 1/2569", source_kind="audio",
            status=m.MeetingStatus.DISTRIBUTED, pipeline=done_pipeline,
            approved_at=datetime(2026, 5, 20, 16, 0), approved_by="ฝ่ายเลขานุการ",
        )
        f.meeting2 = m.Meeting(
            series_id=f.series.id, sequence_no=2, fiscal_year=2569, meeting_date=date(2026, 6, 18),
            title="การประชุมครั้งที่ 2/2569", source_kind="audio",
            status=m.MeetingStatus.DISTRIBUTED, pipeline=done_pipeline,
            approved_at=datetime(2026, 6, 18, 16, 0), approved_by="ฝ่ายเลขานุการ",
        )
        s.add_all([f.meeting1, f.meeting2])
        await s.flush()

        f.segment = m.TranscriptSegment(
            meeting_id=f.meeting2.id, speaker_label="SPEAKER_00", person_id=f.chair.id,
            start_ms=688_000, end_ms=700_000,
            text="ที่ประชุมมีมติมอบหมายให้ฝ่ายพัสดุจัดทำร่างขอบเขตของงาน สำหรับการจัดซื้อครุภัณฑ์คอมพิวเตอร์ทดแทน",
            confidence=0.97,
        )
        s.add(f.segment)
        await s.flush()

        f.open_res = m.Resolution(
            series_id=f.series.id, ref_no="มติ 2/2569 ข้อ 4.1", origin_meeting_id=f.meeting2.id,
            origin_segment_id=f.segment.id, origin_agenda_item="วาระที่ 4.1",
            text="มอบหมายให้ฝ่ายพัสดุจัดทำร่างขอบเขตของงาน (TOR) สำหรับการจัดซื้อครุภัณฑ์คอมพิวเตอร์ทดแทน จำนวน 42 เครื่อง",
            category="procurement", status=m.ResolutionStatus.CONFIRMED,
            proposer_person_id=f.chair.id, due_date=due_overdue,
            original_due_date=due_overdue, extraction_confidence=0.97,
            created_at=datetime(2026, 6, 18, 14, 0),
        )
        f.blocked_res = m.Resolution(
            series_id=f.series.id, ref_no="มติ 1/2569 ข้อ 4.2", origin_meeting_id=f.meeting1.id,
            text="ให้ฝ่ายเทคโนโลยีสารสนเทศเร่งรัดผู้รับจ้างให้ส่งมอบระบบสารบรรณอิเล็กทรอนิกส์ให้ครบทุกโมดูล",
            category="operations", status=m.ResolutionStatus.BLOCKED,
            due_date=due_future, original_due_date=date(2026, 3, 31), postpone_count=3,
            extraction_confidence=0.93, created_at=datetime(2026, 5, 20, 14, 0),
        )
        f.done_res = m.Resolution(
            series_id=f.series.id, ref_no="มติ 1/2569 ข้อ 4.1", origin_meeting_id=f.meeting1.id,
            text="ให้ทุกฝ่ายจัดทำแผนปฏิบัติการประจำปีงบประมาณ 2569",
            category="policy", status=m.ResolutionStatus.DONE, due_date=due_overdue,
            original_due_date=due_overdue, closed_meeting_id=f.meeting2.id,
            closed_at=datetime(2026, 6, 18, 15, 0), created_at=datetime(2026, 5, 20, 14, 0),
        )
        f.cancelled_res = m.Resolution(
            series_id=f.series.id, ref_no="มติ 1/2569 ข้อ 5.1", origin_meeting_id=f.meeting1.id,
            text="ให้จัดกิจกรรมสัมมนาประจำปีนอกสถานที่",
            category="operations", status=m.ResolutionStatus.CANCELLED, due_date=due_overdue,
            original_due_date=due_overdue, created_at=datetime(2026, 5, 20, 15, 0),
        )
        s.add_all([f.open_res, f.blocked_res, f.done_res, f.cancelled_res])
        await s.flush()

        s.add_all(
            [
                m.ResolutionAssignee(resolution_id=f.open_res.id, person_id=f.dept.id, department_name="ฝ่ายพัสดุ"),
                m.ResolutionAssignee(resolution_id=f.open_res.id, person_id=f.supply.id, department_name="ฝ่ายพัสดุ"),
                m.ResolutionAssignee(resolution_id=f.blocked_res.id, person_id=f.it.id, department_name="ฝ่ายไอที"),
            ]
        )
        s.add_all(
            [
                m.ResolutionLink(
                    resolution_id=f.open_res.id, meeting_id=f.meeting2.id, link_type=m.LinkType.CREATED,
                    segment_id=f.segment.id, evidence_text=f.segment.text,
                    evidence_start_ms=688_000, confidence=0.97,
                    created_at=datetime(2026, 6, 18, 14, 0),
                ),
                m.ResolutionLink(
                    resolution_id=f.blocked_res.id, meeting_id=f.meeting1.id, link_type=m.LinkType.CREATED,
                    evidence_text="ที่ประชุมมีมติให้ปรับปรุงระบบสารบรรณอิเล็กทรอนิกส์",
                    evidence_start_ms=120_000, confidence=0.94,
                    created_at=datetime(2026, 5, 20, 14, 0),
                ),
                m.ResolutionLink(
                    resolution_id=f.blocked_res.id, meeting_id=f.meeting2.id,
                    link_type=m.LinkType.PROGRESS_REPORTED,
                    evidence_text="ผู้รับจ้างส่งมอบโมดูลไม่ครบ ทำให้ยังทดสอบระบบไม่ได้",
                    evidence_start_ms=1_040_000, confidence=0.93,
                    created_at=datetime(2026, 6, 18, 15, 10),
                ),
            ]
        )
        await s.commit()

    return f
