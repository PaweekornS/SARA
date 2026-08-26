"""
โครงร่างที่เคสระดับ API และ worker ใช้ร่วมกัน — Persona: NovaTech Studio & SaaS

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
    """ข้อมูลตั้งต้นขนาดเล็กสำหรับเคส — Persona: NovaTech Studio"""

    def __init__(self) -> None:
        self.org: m.Organization
        self.phat: m.Person
        self.rin: m.Person
        self.karn: m.Person
        self.mint: m.Person
        self.dept: m.Person
        # Aliases for backward compatibility in existing test suites
        self.chair: m.Person
        self.supply: m.Person
        self.it: m.Person
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
    สร้างชุดข้อมูล NovaTech Studio:
      * มติค้างที่เกินกำหนด · มติที่เลื่อนซ้ำ · มติที่ปิดแล้ว · มติที่ยกเลิก
      * คอลเลกชันที่สองไว้ตรวจว่าข้อมูลไม่รั่วข้ามชุด
      * ผู้รับผิดชอบที่เป็นหน่วยงาน/ทีมงาน ไม่ใช่บุคคล
    """
    f = Fixture()
    today = date.today()
    f.overdue_by = 26
    due_overdue = today - timedelta(days=f.overdue_by)
    due_future = today + timedelta(days=18)

    async with sessionmaker() as s:
        f.org = m.Organization(name="NovaTech Studio (Demo Workspace)")
        s.add(f.org)
        await s.flush()

        f.phat = m.Person(
            org_id=f.org.id, full_name="ภัทร (Phat)", position="Head of Product / Founder",
            department="Product & Strategy", email="phat@novatech.io",
        )
        f.mint = m.Person(
            org_id=f.org.id, full_name="มิ้น (Mint)", position="Growth & Marketing Lead",
            department="Growth & Marketing", email="mint@novatech.io",
        )
        f.karn = m.Person(
            org_id=f.org.id, full_name="กานต์ (Karn)", position="Lead Software Engineer",
            department="Engineering", email="",  # ไม่มีอีเมล ใช้ทดสอบ validation ส่งออก
        )
        f.rin = m.Person(
            org_id=f.org.id, full_name="ริน (Rin)", position="Lead Product Designer / Scrum Lead",
            department="Design & UX", email="rin@novatech.io",
        )
        f.dept = m.Person(
            org_id=f.org.id, full_name="ทีมพัฒนาและวิศวกรรม", position="ทีมงาน",
            department="Engineering", email="dev@novatech.io", is_department=True,
        )
        # Compatibility aliases
        f.chair = f.phat
        f.supply = f.mint
        f.it = f.karn

        s.add_all([f.phat, f.mint, f.karn, f.rin, f.dept])
        await s.flush()

        s.add(m.PersonAlias(person_id=f.phat.id, alias="ท่านประธาน", source="manual", confidence=1.0))
        s.add(m.PersonAlias(person_id=f.phat.id, alias="Product Lead", source="manual", confidence=1.0))
        s.add(m.PersonAlias(person_id=f.karn.id, alias="Tech Lead", source="manual", confidence=1.0))
        s.add(m.PersonAlias(person_id=f.mint.id, alias="Marketing Lead", source="manual", confidence=1.0))

        f.series = m.MeetingSeries(
            org_id=f.org.id, name="Alpha App Q3 Launch Campaign",
            committee_type="Product Launch & Growth", fiscal_year=2026, cadence="weekly",
            next_meeting_date=date(2026, 8, 14), member_ids=[str(f.phat.id), str(f.mint.id), str(f.karn.id), str(f.rin.id)],
        )
        f.other_series = m.MeetingSeries(
            org_id=f.org.id, name="Core Backend & AI Microservices",
            committee_type="Engineering & Tech Standup", fiscal_year=2026, cadence="bi-weekly",
        )
        s.add_all([f.series, f.other_series])
        await s.flush()

        done_pipeline = [
            {"stage": stage, "state": "ok", "detail": ""}
            for stage in ("upload", "asr", "extract", "done")
        ]
        f.meeting1 = m.Meeting(
            series_id=f.series.id, sequence_no=1, fiscal_year=2026, meeting_date=date(2026, 7, 10),
            title="Kickoff: Scope & Budget Allocation", source_kind="audio",
            status=m.MeetingStatus.DISTRIBUTED, pipeline=done_pipeline,
            approved_at=datetime(2026, 7, 10, 11, 30), approved_by="ภัทร (Phat)",
        )
        f.meeting2 = m.Meeting(
            series_id=f.series.id, sequence_no=2, fiscal_year=2026, meeting_date=date(2026, 7, 24),
            title="Sprint Review: Beta Readiness & Ad Visuals", source_kind="audio",
            status=m.MeetingStatus.DISTRIBUTED, pipeline=done_pipeline,
            approved_at=datetime(2026, 7, 24, 11, 30), approved_by="ภัทร (Phat)",
        )
        s.add_all([f.meeting1, f.meeting2])
        await s.flush()

        f.segment = m.TranscriptSegment(
            meeting_id=f.meeting2.id, speaker_label="SPEAKER_01", person_id=f.phat.id,
            start_ms=135_000, end_ms=150_000,
            text="งบรวม 500,000 บาทเดิมยังเหลือไหม ถ้ายังอยู่ใน Cap 5 แสน เกลี่ยจากงบ Google Search Ads มาได้เลย ผมอนุมัติ",
            confidence=0.97,
        )
        s.add(f.segment)
        await s.flush()

        f.open_res = m.Resolution(
            series_id=f.series.id, ref_no="Action #2 (Growth & Marketing)", origin_meeting_id=f.meeting2.id,
            origin_segment_id=f.segment.id, origin_agenda_item="วาระการตลาด",
            text="คุมงบยิงโฆษณา Alpha Launch รวมไม่เกิน 500,000 บาท โดยเกลี่ยงบ 50,000 บาทสำหรับ Tech Influencer 2 ช่อง",
            category="budget", status=m.ResolutionStatus.CONFIRMED,
            proposer_person_id=f.phat.id, due_date=due_overdue,
            original_due_date=due_overdue, extraction_confidence=0.97,
            created_at=datetime(2026, 7, 24, 11, 0),
        )
        f.blocked_res = m.Resolution(
            series_id=f.series.id, ref_no="Action #1 (Tech Architecture)", origin_meeting_id=f.meeting1.id,
            text="เชื่อมต่อ Payment Gateway ทั้งระบบบัตรเครดิตและ PromptPay ให้พร้อมรับชำระเงินจริงในรอบ Beta Launch",
            category="operations", status=m.ResolutionStatus.BLOCKED,
            due_date=due_future, original_due_date=date(2026, 7, 28), postpone_count=3,
            extraction_confidence=0.93, created_at=datetime(2026, 7, 10, 10, 30),
        )
        f.done_res = m.Resolution(
            series_id=f.series.id, ref_no="Action #3 (Product & Design)", origin_meeting_id=f.meeting1.id,
            text="เปิดหน้า Landing Page สำหรับลงทะเบียน Early-bird Subscription ราคาพิเศษ 299 บาท/เดือน ภายในวันศุกร์นี้",
            category="operations", status=m.ResolutionStatus.DONE, due_date=due_overdue,
            original_due_date=due_overdue, closed_meeting_id=f.meeting2.id,
            closed_at=datetime(2026, 7, 24, 11, 30), created_at=datetime(2026, 7, 10, 11, 0),
        )
        f.cancelled_res = m.Resolution(
            series_id=f.series.id, ref_no="Action #0 (Legacy)", origin_meeting_id=f.meeting1.id,
            text="ยกเลิกการซื้อสื่อโฆษณาผ่านบิลบอร์ดริมทางด่วน",
            category="marketing", status=m.ResolutionStatus.CANCELLED, due_date=due_overdue,
            original_due_date=due_overdue, created_at=datetime(2026, 7, 10, 11, 15),
        )
        s.add_all([f.open_res, f.blocked_res, f.done_res, f.cancelled_res])
        await s.flush()

        s.add_all(
            [
                m.ResolutionAssignee(resolution_id=f.open_res.id, person_id=f.dept.id, department_name="Growth & Marketing"),
                m.ResolutionAssignee(resolution_id=f.open_res.id, person_id=f.mint.id, department_name="Growth & Marketing"),
                m.ResolutionAssignee(resolution_id=f.blocked_res.id, person_id=f.karn.id, department_name="Engineering"),
            ]
        )
        s.add_all(
            [
                m.ResolutionLink(
                    resolution_id=f.open_res.id, meeting_id=f.meeting2.id, link_type=m.LinkType.CREATED,
                    segment_id=f.segment.id, evidence_text=f.segment.text,
                    evidence_start_ms=135_000, confidence=0.97,
                    created_at=datetime(2026, 7, 24, 11, 0),
                ),
                m.ResolutionLink(
                    resolution_id=f.blocked_res.id, meeting_id=f.meeting1.id, link_type=m.LinkType.CREATED,
                    evidence_text="วางแผนเชื่อมต่อ Payment Gateway เพื่อรองรับรอบ Beta",
                    evidence_start_ms=0, confidence=0.95,
                    created_at=datetime(2026, 7, 10, 10, 0),
                ),
                m.ResolutionLink(
                    resolution_id=f.blocked_res.id, meeting_id=f.meeting2.id,
                    link_type=m.LinkType.PROGRESS_REPORTED,
                    evidence_text="ติดปัญหา Production Key จากผู้ให้บริการ (Blocked)",
                    evidence_start_ms=120_000, confidence=0.92,
                    created_at=datetime(2026, 7, 24, 10, 30),
                ),
            ]
        )
        await s.commit()

    return f
