"""
ข้อมูลตั้งต้นสำหรับเดโม — Persona: NovaTech Studio & SaaS (High-Growth Product Agency)
ตรงกับข้อกำหนดใน Mock_Data_Update.md และ frontend/lib/seed.ts

    python -m app.seed          สร้างข้อมูลถ้ายังไม่มี
    python -m app.seed --reset  ล้างของเดิมแล้วสร้างใหม่

Collection: Alpha App Q3 Launch Campaign (col-app-launch-2026)
Team: ภัทร (Phat), ริน (Rin), กานต์ (Karn), มิ้น (Mint)
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    ActionStatus,
    AgendaDraft,
    AuditLog,
    LinkType,
    Meeting,
    MeetingSeries,
    MeetingStatus,
    Organization,
    OutboundAction,
    Person,
    PersonAlias,
    Proposal,
    QaLog,
    Resolution,
    ResolutionAssignee,
    ResolutionHistory,
    ResolutionLink,
    ResolutionStatus,
    TranscriptSegment,
)
from app.db.session import AsyncSessionLocal, engine

DONE_PIPELINE = [
    {"stage": "upload", "state": "ok", "detail": "รับไฟล์และตรวจความสมบูรณ์"},
    {"stage": "asr", "state": "ok", "detail": "ถอดเสียงด้วย AI4Thai ASR"},
    {"stage": "extract", "state": "ok", "detail": "สรุปเนื้อหาและสกัดมติ"},
    {"stage": "done", "state": "ok", "detail": "พร้อมให้ตรวจทาน"},
]

LEAD_ACTOR = "ภัทร (Phat)"


async def seed(session: AsyncSession) -> None:
    org = Organization(name="NovaTech Studio (Demo Workspace)")
    session.add(org)
    await session.flush()

    # ── บุคคล ───────────────────────────────────────────────────────────
    def person(full_name, position, department, email, is_department=False) -> Person:
        row = Person(
            org_id=org.id,
            full_name=full_name,
            position=position,
            department=department,
            email=email,
            is_department=is_department,
        )
        session.add(row)
        return row

    # ── หน่วยงาน / ฝ่าย (Department Entities) ───────────────────────────
    dept_product = person("ทีมบริหารผลิตภัณฑ์ (Product Team)", "ทีมงาน", "Product & Strategy", "product@novatech.io", True)
    dept_eng = person("ทีมพัฒนาและวิศวกรรม (Engineering Team)", "ทีมงาน", "Engineering", "dev@novatech.io", True)
    dept_design = person("ทีมออกแบบและประสบการณ์ผู้ใช้ (Design Team)", "ทีมงาน", "Design & UX", "design@novatech.io", True)
    dept_growth = person("ทีมการตลาดและการเติบโต (Growth Team)", "ทีมงาน", "Growth & Marketing", "growth@novatech.io", True)

    # ── บุคลากรหลักในทีม (NovaTech Studio Core Members) ─────────────────
    phat = person("ภัทร (Phat)", "Head of Product / Founder", "Product & Strategy", "phat@novatech.io")
    rin = person("ริน (Rin)", "Lead Product Designer / Scrum Lead", "Design & UX", "rin@novatech.io")
    karn = person("กานต์ (Karn)", "Lead Software Engineer", "Engineering", "karn@novatech.io")
    mint = person("มิ้น (Mint)", "Growth & Marketing Lead", "Growth & Marketing", "mint@novatech.io")
    await session.flush()

    # ── ฉายาและชื่อเรียก (Aliases) ──────────────────────────────────────
    for person_row, alias, source, confidence in [
        (phat, "ภัทร", "confirmed_extraction", 0.98),
        (phat, "Product Lead", "manual", 1.0),
        (phat, "ท่านประธาน", "manual", 1.0),
        (rin, "ริน", "confirmed_extraction", 0.96),
        (rin, "Scrum Lead", "manual", 1.0),
        (rin, "Designer", "manual", 1.0),
        (karn, "กานต์", "confirmed_extraction", 0.97),
        (karn, "Tech Lead", "manual", 1.0),
        (karn, "Lead Dev", "manual", 1.0),
        (mint, "มิ้น", "confirmed_extraction", 0.95),
        (mint, "Marketing Lead", "manual", 1.0),
        (mint, "Growth", "manual", 1.0),
        (dept_eng, "ทีม Dev", "manual", 1.0),
        (dept_growth, "ทีมการตลาด", "manual", 1.0),
    ]:
        session.add(
            PersonAlias(person_id=person_row.id, alias=alias, source=source, confidence=confidence)
        )

    # ── คอลเลกชัน / ชุดการประชุม (Workspace Collections) ────────────────
    launch_series = MeetingSeries(
        org_id=org.id,
        name="Alpha App Q3 Launch Campaign",
        committee_type="Product Launch & Growth",
        fiscal_year=2026,
        cadence="weekly",
        next_meeting_date=date(2026, 8, 14),
        member_ids=[str(p.id) for p in (phat, rin, karn, mint)],
    )
    tech_series = MeetingSeries(
        org_id=org.id,
        name="Core Backend & AI Microservices",
        committee_type="Engineering & Tech Standup",
        fiscal_year=2026,
        cadence="bi-weekly",
        next_meeting_date=date(2026, 8, 20),
        member_ids=[str(p.id) for p in (phat, karn, rin)],
    )
    session.add_all([launch_series, tech_series])
    await session.flush()

    # ── การประชุม (Meeting Sessions) ────────────────────────────────────
    def meeting(series, seq, day: date, title: str) -> Meeting:
        row = Meeting(
            series_id=series.id,
            sequence_no=seq,
            fiscal_year=2026,
            meeting_date=day,
            title=title,
            audio_uri=None,
            source_kind="audio",
            status=MeetingStatus.DISTRIBUTED,
            pipeline=[dict(s) for s in DONE_PIPELINE],
            approved_at=datetime(day.year, day.month, day.day, 11, 30),
            approved_by=LEAD_ACTOR,
        )
        session.add(row)
        return row

    m1 = meeting(launch_series, 1, date(2026, 7, 10), "Kickoff: Scope & Budget Allocation")
    m2 = meeting(launch_series, 2, date(2026, 7, 24), "Sprint Review: Beta Readiness & Ad Visuals")
    m3 = meeting(launch_series, 3, date(2026, 8, 7), "Pre-Launch Sync: Blocker Clearance & Pricing")
    meeting(tech_series, 1, date(2026, 7, 15), "Sprint 14: AI Gateway & Rate Limiting")
    await session.flush()

    # ── บันทึกคำต่อคำของการประชุม Pre-Launch Sync (Meeting #3) ───────────
    script = [
        ("SPEAKER_01", phat, 12_000, "สวัสดีทุกคน วันนี้มาเช็คความพร้อมก่อนเปิด Beta สัปดาห์หน้า เรื่องแรก Payment Gateway ที่ติดสัปดาห์ที่แล้วเป็นยังไงบ้าง กานต์?", 0.98),
        ("SPEAKER_03", karn, 24_000, "แก้เรียบร้อยแล้วครับ ผู้ให้บริการปลดล็อก Production Key ให้แล้ว เมื่อวานทีมเทสระบบตัดบัตรเครดิตและ PromptPay ผ่านฉลุย ไม่มีปัญหาแล้วครับ", 0.98),
        ("SPEAKER_01", phat, 70_000, "ยอดเยี่ยมมาก ถือว่า Blocker ตัวนี้เคลียร์แล้วนะ ถัดมาเรื่องแคมเปญการตลาด มิ้น เตรียม Key Visual ทันไหม?", 0.97),
        ("SPEAKER_04", mint, 95_000, "สำหรับ Key Visual ชุดแรกพร้อมยิง Ads บน TikTok และ Meta วันจันทร์นี้ค่ะ แต่มีเรื่องขออนุมัติงบเพิ่ม 50,000 บาท สำหรับจ้าง Tech Influencer 2 ช่อง มารีวิวช่วง Early Access ค่ะ", 0.95),
        ("SPEAKER_01", phat, 135_000, "งบรวม 500,000 บาทเดิมยังเหลือไหม? ถ้ายังอยู่ใน Cap 5 แสน เกลี่ยจากงบ Google Search Ads มาได้เลย ผมอนุมัติ", 0.97),
        ("SPEAKER_04", mint, 160_000, "โอเคค่ะ งั้นสรุปเกลี่ยงบ 50,000 บาทมาจ่าย Influencer โดยคุมยอดรวมไม่เกิน 500k บาท และจะส่งรายงาน Conversion ให้ดูทุกเย็นวันศุกร์ค่ะ", 0.96),
        ("SPEAKER_02", rin, 195_000, "หน้า Landing Page สมัคร Early Access ทำเสร็จแล้วนะคะ พร้อมเปิดให้ลงทะเบียนศุกร์นี้ที่ราคา 299 บาท/เดือน ตามมติใหม่", 0.97),
        ("SPEAKER_01", phat, 245_000, "ดีมาก สรุป Action Item: มิ้นยิง Ads วันจันทร์, รินเปิดหน้าเว็บวันศุกร์, กานต์สแตนด์บาย Monitor Server ปิดประชุมครับ", 0.98),
    ]
    segments: dict[int, TranscriptSegment] = {}
    for label, who, start, text, confidence in script:
        row = TranscriptSegment(
            meeting_id=m3.id,
            speaker_label=label,
            person_id=who.id,
            start_ms=start,
            end_ms=start + max(4000, len(text) * 120),
            text=text,
            confidence=confidence,
        )
        session.add(row)
        segments[start] = row
    await session.flush()

    # ── ข้อสรุปและมติการดำเนินงาน (Resolutions & Action Items) ─────────
    def resolution(**kwargs) -> Resolution:
        row = Resolution(series_id=launch_series.id, **kwargs)
        session.add(row)
        return row

    res_payment = resolution(
        ref_no="Action #1 (Tech Architecture)",
        origin_meeting_id=m1.id,
        origin_segment_id=segments[24_000].id,
        origin_agenda_item="วาระที่ 1 (Infrastructure)",
        text="เชื่อมต่อและทดสอบ Payment Gateway ทั้งระบบบัตรเครดิตและ PromptPay ให้พร้อมรับชำระเงินจริงในรอบ Beta Launch",
        category="operations",
        status=ResolutionStatus.DONE,
        proposer_person_id=phat.id,
        due_date=date(2026, 8, 5),
        original_due_date=date(2026, 7, 28),
        postpone_count=1,
        closed_meeting_id=m3.id,
        closed_at=datetime(2026, 8, 7, 10, 30),
        extraction_confidence=0.98,
    )
    res_ad_budget = resolution(
        ref_no="Action #2 (Growth & Marketing)",
        origin_meeting_id=m3.id,
        origin_segment_id=segments[160_000].id,
        origin_agenda_item="วาระที่ 2 (Marketing Launch)",
        text="คุมงบยิงโฆษณา Alpha Launch รวมไม่เกิน 500,000 บาท โดยเกลี่ยงบ 50,000 บาทสำหรับ Tech Influencer 2 ช่อง และส่งรายงาน Conversion ทุกวันศุกร์",
        category="budget",
        status=ResolutionStatus.IN_PROGRESS,
        proposer_person_id=phat.id,
        due_date=date(2026, 8, 31),
        original_due_date=date(2026, 8, 31),
        postpone_count=0,
        extraction_confidence=0.96,
    )
    res_landing_page = resolution(
        ref_no="Action #3 (Product & Design)",
        origin_meeting_id=m3.id,
        origin_segment_id=segments[195_000].id,
        origin_agenda_item="วาระที่ 3 (Product Delivery)",
        text="เปิดหน้า Landing Page สำหรับลงทะเบียน Early-bird Subscription ราคาพิเศษ 299 บาท/เดือน ภายในวันศุกร์นี้",
        category="operations",
        status=ResolutionStatus.DONE,
        proposer_person_id=phat.id,
        due_date=date(2026, 8, 14),
        original_due_date=date(2026, 8, 14),
        postpone_count=0,
        closed_meeting_id=m3.id,
        closed_at=datetime(2026, 8, 7, 11, 0),
        extraction_confidence=0.97,
    )
    await session.flush()

    for resolution_row, people in [
        (res_payment, [karn, dept_eng]),
        (res_ad_budget, [mint, dept_growth]),
        (res_landing_page, [rin, dept_design]),
    ]:
        for who in people:
            session.add(
                ResolutionAssignee(
                    resolution_id=resolution_row.id, person_id=who.id, department_name=who.department
                )
            )

    # ── การเชื่อมโยงข้ามการประชุม (Cross-Meeting Citations & Links) ────
    for resolution_row, meeting_row, link_type, evidence, start_ms, confidence, created in [
        (res_payment, m1, LinkType.CREATED, "วางแผนเชื่อมต่อ Payment Gateway เพื่อรองรับรอบ Beta", 0, 0.95, datetime(2026, 7, 10, 10, 0)),
        (res_payment, m2, LinkType.PROGRESS_REPORTED, "ติดปัญหา Production Key จากผู้ให้บริการ (Blocked)", 120_000, 0.92, datetime(2026, 7, 24, 10, 30)),
        (res_payment, m3, LinkType.CLOSED, "ผู้ให้บริการปลดล็อก Production Key ให้แล้ว ทดสอบตัดบัตรและ PromptPay ผ่านฉลุย", 24_000, 0.98, datetime(2026, 8, 7, 10, 30)),
        (res_ad_budget, m3, LinkType.CREATED, "อนุมัติเกลี่ยงบ 50,000 บาทสำหรับจ้าง Influencer โดยคุมยอดรวมไม่เกิน 500k", 160_000, 0.96, datetime(2026, 8, 7, 10, 45)),
        (res_landing_page, m3, LinkType.CREATED, "หน้า Landing Page สมัคร Early Access พร้อมเปิดวันศุกร์นี้ที่ราคา 299 บาท/เดือน", 195_000, 0.97, datetime(2026, 8, 7, 11, 0)),
    ]:
        session.add(
            ResolutionLink(
                resolution_id=resolution_row.id,
                meeting_id=meeting_row.id,
                link_type=link_type,
                evidence_text=evidence,
                evidence_start_ms=start_ms,
                confidence=confidence,
                created_at=created,
            )
        )

    # ── ประวัติการเปลี่ยนแปลงสถานะ (Resolution History) ─────────────────
    for field, old, new, reason, when, meeting_row in [
        ("status", "in_progress", "blocked", "รอ Production Key จาก Payment Gateway Provider", datetime(2026, 7, 24, 10, 35), m2),
        ("status", "blocked", "done", "ทดสอบผ่านระบบตัดบัตรเครดิตและ PromptPay แล้ว", datetime(2026, 8, 7, 10, 30), m3),
        ("due_date", "2026-08-15", "2026-08-31", "ขยายเวลารวมช่วง Tech Influencer Review", datetime(2026, 8, 7, 10, 45), m3),
    ]:
        session.add(
            ResolutionHistory(
                resolution_id=res_payment.id if "Payment" in reason or "บัตรเครดิต" in reason else res_ad_budget.id,
                field=field, old_value=old, new_value=new,
                changed_by=LEAD_ACTOR, changed_at=when, reason=reason, source_meeting_id=meeting_row.id,
            )
        )

    # ── คิวส่งออกและอีเมลแจ้งเตือน (Outbound Actions) ─────────────────
    session.add(
        OutboundAction(
            series_id=launch_series.id,
            resolution_id=res_ad_budget.id,
            action_type="send_resolution_reminder",
            recipient_person_id=mint.id,
            subject="แจ้งเตือน Action Item: ส่งรายงาน Conversion & TikTok Ads ทุกเย็นวันศุกร์",
            body=(
                "เรียน คุณมิ้น (Growth Lead)\n\n"
                "ระบบสรุป Action Item จากที่ประชุม Pre-Launch Sync:\n\n"
                f"“{res_ad_budget.text}”\n\n"
                "กำหนดส่ง: 31 สิงหาคม 2569\n\n"
                "สามารถรายงานผลหรืออัปเดตผ่านระบบ SARA ได้ทันที"
            ),
            status=ActionStatus.PENDING_APPROVAL,
        )
    )

    session.add_all(
        [
            AuditLog(org_id=org.id, actor=LEAD_ACTOR, action="meeting_approved", entity_type="meeting",
                     entity_id=str(m3.id), meta="รับรองรายงานการประชุม Pre-Launch Sync"),
            AuditLog(org_id=org.id, actor=LEAD_ACTOR, action="confirm_alias", entity_type="person",
                     entity_id=str(karn.id), meta='ยืนยัน "Tech Lead" → กานต์ (Karn)'),
        ]
    )

    await session.commit()


async def reset(session: AsyncSession) -> None:
    for model in (
        QaLog, AuditLog, OutboundAction, AgendaDraft, Proposal, ResolutionHistory,
        ResolutionLink, ResolutionAssignee, Resolution, TranscriptSegment, Meeting,
        MeetingSeries, PersonAlias, Person, Organization,
    ):
        await session.execute(delete(model))
    await session.commit()


async def main(force_reset: bool) -> None:
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(select(Organization).limit(1))
        except Exception as err:  # noqa: BLE001
            raise SystemExit(
                f"ยังไม่มีตารางในฐานข้อมูล ({err.__class__.__name__}) — รัน `alembic upgrade head` ก่อน"
            ) from err

    async with AsyncSessionLocal() as session:
        if force_reset:
            await reset(session)
        existing = (await session.execute(select(Organization))).scalars().first()
        if existing and not force_reset:
            print("มีข้อมูลอยู่แล้ว — ใช้ --reset ถ้าต้องการล้างแล้วสร้างใหม่")
            return
        await seed(session)
        print("สร้างข้อมูลตั้งต้น NovaTech Studio เรียบร้อย")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main("--reset" in sys.argv))
