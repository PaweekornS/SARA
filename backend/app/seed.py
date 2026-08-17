"""
ข้อมูลตั้งต้นสำหรับเดโม — ตรงกับสคริปต์ใน §11 และกับ frontend/lib/seed.ts

    python -m app.seed          สร้างข้อมูลถ้ายังไม่มี
    python -m app.seed --reset  ล้างของเดิมแล้วสร้างใหม่

ครั้งที่ 5/2569 (รับรองแล้ว) มีมติ A จัดซื้อครุภัณฑ์ (เกินกำหนด) · B ระบบสารบรรณ (เลื่อน 3 ครั้ง)
· C คณะทำงานงบประมาณ (จะถูกปิดเมื่ออัปโหลดครั้งที่ 6)
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

SECRETARY = "นางสาวปรียานุช วัฒนสิน"


async def seed(session: AsyncSession) -> None:
    org = Organization(name="สำนักงานพัฒนาระบบราชการ (ตัวอย่าง)")
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
    dept_directorate = person("สำนักผู้อำนวยการ", "หน่วยงาน", "สำนักผู้อำนวยการ", "test01@gmail.com", True)
    dept_admin = person("ฝ่ายบริหารงานทั่วไป", "หน่วยงาน", "ฝ่ายบริหารงานทั่วไป", "test01@gmail.com", True)
    dept_it = person("ฝ่ายเทคโนโลยีสารสนเทศ", "หน่วยงาน", "ฝ่ายเทคโนโลยีสารสนเทศ", "test02@gmail.com", True)
    dept_supply = person("ฝ่ายพัสดุ", "หน่วยงาน", "ฝ่ายพัสดุ", "test01@gmail.com", True)
    dept_finance = person("ฝ่ายการเงินและบัญชี", "หน่วยงาน", "ฝ่ายการเงินและบัญชี", "test02@gmail.com", True)
    dept_academic = person("ฝ่ายวิชาการ", "หน่วยงาน", "ฝ่ายวิชาการ", "test01@gmail.com", True)

    # ── บุคลากรในแต่ละฝ่าย (Members per Department) ─────────────────────
    chair = person("นายธนกฤต อารีวงศ์", "ผู้อำนวยการ (ประธานที่ประชุม)", "สำนักผู้อำนวยการ", "test01@gmail.com")
    deputy = person("นายสุรชัย ทองอินทร์", "รองผู้อำนวยการ", "สำนักผู้อำนวยการ", "test02@gmail.com")
    secretary = person(SECRETARY, "หัวหน้าฝ่ายบริหารงานทั่วไป (เลขานุการที่ประชุม)", "ฝ่ายบริหารงานทั่วไป", "test01@gmail.com")
    admin_officer = person("นายณัฐวุฒิ สิทธิชัย", "เจ้าหน้าที่บริหารงานทั่วไปปฏิบัติการ", "ฝ่ายบริหารงานทั่วไป", "test02@gmail.com")
    it = person("นายวีระพงษ์ ศรีสมบูรณ์", "หัวหน้าฝ่ายเทคโนโลยีสารสนเทศ", "ฝ่ายเทคโนโลยีสารสนเทศ", "test02@gmail.com")
    it_officer = person("นายชานนท์ วงศ์สุวรรณ", "นักวิชาการคอมพิวเตอร์ชำนาญการ", "ฝ่ายเทคโนโลยีสารสนเทศ", "test01@gmail.com")
    supply = person("นางกาญจนา พูลสวัสดิ์", "หัวหน้าฝ่ายพัสดุ", "ฝ่ายพัสดุ", "test01@gmail.com")
    supply_officer = person("นายเอกชัย ภักดี", "เจ้าหน้าที่พัสดุชำนาญการ", "ฝ่ายพัสดุ", "test02@gmail.com")
    finance = person("นางสาวศิริพร เจริญผล", "หัวหน้าฝ่ายการเงินและบัญชี", "ฝ่ายการเงินและบัญชี", "test02@gmail.com")
    finance_officer = person("นางสาวกมลวรรณ สุขสม", "นักวิชาการเงินและบัญชีปฏิบัติการ", "ฝ่ายการเงินและบัญชี", "test01@gmail.com")
    academic = person("นายกิตติศักดิ์ แสนสุข", "หัวหน้าฝ่ายวิชาการ", "ฝ่ายวิชาการ", "test01@gmail.com")
    academic_officer = person("นางสาวนภัสสร รุ่งเรือง", "นักวิชาการแผนและนโยบายชำนาญการ", "ฝ่ายวิชาการ", "test02@gmail.com")
    await session.flush()

    for person_row, alias, source, confidence in [
        (deputy, "พี่หนึ่ง", "confirmed_extraction", 0.94),
        (deputy, "ท่านรอง", "manual", 1.0),
        (secretary, "พี่แนน", "confirmed_extraction", 0.88),
        (it, "ผอ.ไอที", "manual", 1.0),
        (supply, "พี่กาญ", "confirmed_extraction", 0.91),
        (chair, "ท่านประธาน", "manual", 1.0),
        (dept_supply, "พัสดุ", "manual", 1.0),
    ]:
        session.add(
            PersonAlias(person_id=person_row.id, alias=alias, source=source, confidence=confidence)
        )

    # ── ชุดการประชุม ────────────────────────────────────────────────────
    exec_series = MeetingSeries(
        org_id=org.id,
        name="คณะกรรมการบริหาร ปีงบประมาณ 2569",
        committee_type="คณะกรรมการบริหาร",
        fiscal_year=2569,
        cadence="monthly",
        next_meeting_date=date(2026, 8, 20),
        member_ids=[str(p.id) for p in (chair, deputy, secretary, it, supply, finance, academic)],
    )
    academic_series = MeetingSeries(
        org_id=org.id,
        name="คณะกรรมการวิชาการ ปีงบประมาณ 2569",
        committee_type="คณะกรรมการวิชาการ",
        fiscal_year=2569,
        cadence="quarterly",
        next_meeting_date=date(2026, 9, 10),
        member_ids=[str(p.id) for p in (chair, academic, secretary)],
    )
    session.add_all([exec_series, academic_series])
    await session.flush()

    # ── การประชุม ───────────────────────────────────────────────────────
    def meeting(series, seq, day: date) -> Meeting:
        row = Meeting(
            series_id=series.id,
            sequence_no=seq,
            fiscal_year=2569,
            meeting_date=day,
            title=f"การประชุมครั้งที่ {seq}/2569",
            audio_uri=None,
            source_kind="audio",
            status=MeetingStatus.DISTRIBUTED,
            pipeline=[dict(s) for s in DONE_PIPELINE],
            approved_at=datetime(day.year, day.month, day.day, 16, 20),
            approved_by=SECRETARY,
        )
        session.add(row)
        return row

    m1 = meeting(exec_series, 1, date(2026, 1, 22))
    m2 = meeting(exec_series, 2, date(2026, 3, 12))
    m3 = meeting(exec_series, 3, date(2026, 4, 23))
    m4 = meeting(exec_series, 4, date(2026, 5, 21))
    m5 = meeting(exec_series, 5, date(2026, 6, 18))
    meeting(academic_series, 1, date(2026, 2, 5))
    await session.flush()

    # ── บันทึกคำต่อคำของครั้งที่ 5 ──────────────────────────────────────
    script = [
        ("SPEAKER_00", chair, 12_000, "เรียนคณะกรรมการทุกท่าน วันนี้เป็นการประชุมครั้งที่ 5 ประจำปีงบประมาณ 2569 ขอเปิดการประชุมครับ", 0.95),
        ("SPEAKER_02", secretary, 96_000, "วาระที่ 2 ขอให้ที่ประชุมพิจารณารับรองรายงานการประชุมครั้งที่ 4/2569 ค่ะ", 0.95),
        ("SPEAKER_00", chair, 141_000, "ถ้าไม่มีการแก้ไข ถือว่าที่ประชุมรับรองรายงานการประชุมครั้งที่ 4 นะครับ", 0.95),
        ("SPEAKER_03", supply, 620_000, "เรื่องครุภัณฑ์คอมพิวเตอร์ที่จะทดแทนของเดิม ตอนนี้ฝ่ายพัสดุประเมินไว้ 42 เครื่อง กรอบวงเงินประมาณ 1.26 ล้านบาทค่ะ", 0.94),
        ("SPEAKER_00", chair, 688_000, "งั้นที่ประชุมมีมติมอบหมายให้ฝ่ายพัสดุจัดทำร่างขอบเขตของงาน หรือ TOR สำหรับการจัดซื้อครุภัณฑ์คอมพิวเตอร์ทดแทน จำนวน 42 เครื่อง ให้แล้วเสร็จภายใน 30 วัน แล้วเสนอที่ประชุมพิจารณาครับ", 0.97),
        ("SPEAKER_01", it, 1_040_000, "เรื่องระบบสารบรรณอิเล็กทรอนิกส์ ต้องขออภัยที่ประชุม ผู้รับจ้างส่งมอบโมดูลไม่ครบ ทำให้ยังทดสอบระบบไม่ได้ครับ", 0.93),
        ("SPEAKER_00", chair, 1_112_000, "อันนี้เลื่อนมาสามรอบแล้วนะครับ ที่ประชุมขอให้ฝ่ายเทคโนโลยีสารสนเทศเร่งรัดผู้รับจ้าง และรายงานความคืบหน้าเป็นลายลักษณ์อักษรภายในวันที่ 31 สิงหาคม 2569", 0.95),
        ("SPEAKER_02", secretary, 1_530_000, "วาระที่ 4.3 เรื่องการจัดทำคำของบประมาณประจำปี 2570 ค่ะ ต้องเริ่มภายในเดือนกรกฎาคม", 0.94),
        ("SPEAKER_00", chair, 1_588_000, "ขอให้พี่หนึ่งรับไปดูแลนะครับ ที่ประชุมมีมติให้แต่งตั้งคณะทำงานจัดทำคำของบประมาณประจำปี 2570 โดยมอบหมายรองผู้อำนวยการเป็นประธานคณะทำงาน ให้แล้วเสร็จภายในวันที่ 31 กรกฎาคม 2569", 0.96),
        ("SPEAKER_04", deputy, 1_664_000, "รับทราบครับ ผมจะประสานฝ่ายการเงินเรื่องกรอบวงเงินก่อนครับ", 0.93),
        ("SPEAKER_00", chair, 2_402_000, "ไม่มีเรื่องอื่นแล้วนะครับ ปิดประชุมครับ", 0.96),
    ]
    segments: dict[int, TranscriptSegment] = {}
    for label, who, start, text, confidence in script:
        row = TranscriptSegment(
            meeting_id=m5.id,
            speaker_label=label,
            person_id=who.id,
            start_ms=start,
            end_ms=start + max(5000, len(text) * 130),
            text=text,
            confidence=confidence,
        )
        session.add(row)
        segments[start] = row
    await session.flush()

    # ── มติ ─────────────────────────────────────────────────────────────
    def resolution(**kwargs) -> Resolution:
        row = Resolution(series_id=exec_series.id, **kwargs)
        session.add(row)
        return row

    res_a = resolution(
        ref_no="มติ 5/2569 ข้อ 4.1",
        origin_meeting_id=m5.id,
        origin_segment_id=segments[688_000].id,
        origin_agenda_item="วาระที่ 4.1",
        text="มอบหมายให้ฝ่ายพัสดุจัดทำร่างขอบเขตของงาน (TOR) สำหรับการจัดซื้อครุภัณฑ์คอมพิวเตอร์ทดแทน จำนวน 42 เครื่อง กรอบวงเงิน 1,260,000 บาท ให้แล้วเสร็จภายใน 30 วัน และเสนอที่ประชุมพิจารณา",
        category="procurement",
        status=ResolutionStatus.CONFIRMED,
        proposer_person_id=chair.id,
        due_date=date(2026, 7, 18),
        original_due_date=date(2026, 7, 18),
        extraction_confidence=0.97,
        created_at=datetime(2026, 6, 18, 14, 0),
    )
    res_b = resolution(
        ref_no="มติ 2/2569 ข้อ 4.2",
        origin_meeting_id=m2.id,
        origin_agenda_item="วาระที่ 4.2",
        text="ให้ฝ่ายเทคโนโลยีสารสนเทศเร่งรัดผู้รับจ้างให้ส่งมอบและติดตั้งระบบสารบรรณอิเล็กทรอนิกส์ให้ครบทุกโมดูล พร้อมรายงานความคืบหน้าเป็นลายลักษณ์อักษรต่อที่ประชุม",
        category="operations",
        status=ResolutionStatus.BLOCKED,
        proposer_person_id=chair.id,
        due_date=date(2026, 8, 31),
        original_due_date=date(2026, 3, 31),
        postpone_count=3,
        extraction_confidence=0.93,
        created_at=datetime(2026, 3, 12, 14, 0),
    )
    res_c = resolution(
        ref_no="มติ 5/2569 ข้อ 4.3",
        origin_meeting_id=m5.id,
        origin_segment_id=segments[1_588_000].id,
        origin_agenda_item="วาระที่ 4.3",
        text="ให้แต่งตั้งคณะทำงานจัดทำคำของบประมาณประจำปีงบประมาณ 2570 โดยมอบหมายรองผู้อำนวยการเป็นประธานคณะทำงาน ให้แล้วเสร็จภายในวันที่ 31 กรกฎาคม 2569",
        category="budget",
        status=ResolutionStatus.IN_PROGRESS,
        proposer_person_id=chair.id,
        due_date=date(2026, 7, 31),
        original_due_date=date(2026, 7, 31),
        extraction_confidence=0.96,
        created_at=datetime(2026, 6, 18, 14, 0),
    )
    res_d = resolution(
        ref_no="มติ 1/2569 ข้อ 4.1", origin_meeting_id=m1.id,
        text="ให้ทุกฝ่ายจัดทำแผนปฏิบัติการประจำปีงบประมาณ 2569 ส่งฝ่ายบริหารงานทั่วไปภายในวันที่ 15 กุมภาพันธ์ 2569",
        category="policy", status=ResolutionStatus.DONE, proposer_person_id=chair.id,
        due_date=date(2026, 2, 15), original_due_date=date(2026, 2, 15),
        closed_meeting_id=m2.id, closed_at=datetime(2026, 3, 12, 15, 0),
        created_at=datetime(2026, 1, 22, 14, 0),
    )
    res_e = resolution(
        ref_no="มติ 2/2569 ข้อ 4.1", origin_meeting_id=m2.id,
        text="อนุมัติปรับปรุงห้องประชุมใหญ่ ชั้น 3 วงเงินไม่เกิน 480,000 บาท โดยให้ฝ่ายพัสดุดำเนินการตามระเบียบพัสดุ",
        category="budget", status=ResolutionStatus.DONE, proposer_person_id=chair.id,
        due_date=date(2026, 5, 31), original_due_date=date(2026, 4, 30), postpone_count=1,
        closed_meeting_id=m5.id, closed_at=datetime(2026, 6, 18, 15, 30),
        created_at=datetime(2026, 3, 12, 14, 20),
    )
    res_f = resolution(
        ref_no="มติ 3/2569 ข้อ 4.1", origin_meeting_id=m3.id,
        text="ให้ฝ่ายการเงินและบัญชีรายงานผลการใช้จ่ายงบประมาณรายไตรมาสต่อที่ประชุมทุกครั้ง",
        category="budget", status=ResolutionStatus.DONE, proposer_person_id=chair.id,
        due_date=date(2026, 5, 15), original_due_date=date(2026, 5, 15),
        closed_meeting_id=m4.id, closed_at=datetime(2026, 5, 21, 15, 0),
        created_at=datetime(2026, 4, 23, 14, 10),
    )
    res_g = resolution(
        ref_no="มติ 3/2569 ข้อ 4.2", origin_meeting_id=m3.id,
        text="ให้ฝ่ายวิชาการจัดทำหลักสูตรอบรมภายในสำหรับเจ้าหน้าที่ใหม่ ปีละไม่น้อยกว่า 2 รุ่น",
        category="operations", status=ResolutionStatus.DONE, proposer_person_id=chair.id,
        due_date=date(2026, 6, 15), original_due_date=date(2026, 6, 15),
        closed_meeting_id=m5.id, closed_at=datetime(2026, 6, 18, 15, 35),
        created_at=datetime(2026, 4, 23, 14, 30),
    )
    res_h = resolution(
        ref_no="มติ 4/2569 ข้อ 4.1", origin_meeting_id=m4.id,
        text="ให้ทบทวนระเบียบการเบิกจ่ายค่าใช้จ่ายในการเดินทางไปราชการ ให้สอดคล้องกับระเบียบกระทรวงการคลังฉบับใหม่",
        category="policy", status=ResolutionStatus.IN_PROGRESS, proposer_person_id=chair.id,
        due_date=date(2026, 8, 29), original_due_date=date(2026, 7, 31), postpone_count=1,
        created_at=datetime(2026, 5, 21, 14, 15),
    )
    res_i = resolution(
        ref_no="มติ 4/2569 ข้อ 4.2", origin_meeting_id=m4.id,
        text="ให้ฝ่ายเทคโนโลยีสารสนเทศจัดหาระบบสำรองข้อมูลนอกสถานที่ (offsite backup) ภายในไตรมาส 4",
        category="operations", status=ResolutionStatus.CONFIRMED, proposer_person_id=chair.id,
        due_date=date(2026, 9, 30), original_due_date=date(2026, 9, 30),
        created_at=datetime(2026, 5, 21, 14, 40),
    )
    res_k = resolution(
        ref_no="มติ 4/2569 ข้อ 4.3", origin_meeting_id=m4.id,
        text="ให้จัดซื้อเครื่องปรับอากาศทดแทน จำนวน 12 เครื่อง โดยวิธีประกวดราคาอิเล็กทรอนิกส์ (e-bidding) แทนมติเดิมตามข้อเสนอของฝ่ายพัสดุ",
        category="procurement", status=ResolutionStatus.DONE, proposer_person_id=chair.id,
        due_date=date(2026, 6, 30), original_due_date=date(2026, 6, 30),
        closed_meeting_id=m5.id, closed_at=datetime(2026, 6, 18, 15, 40),
        created_at=datetime(2026, 5, 21, 15, 0),
    )
    await session.flush()

    res_j = resolution(
        ref_no="มติ 2/2569 ข้อ 4.3", origin_meeting_id=m2.id,
        text="ให้จัดซื้อเครื่องปรับอากาศทดแทนของเดิม จำนวน 8 เครื่อง โดยวิธีเฉพาะเจาะจง",
        category="procurement", status=ResolutionStatus.SUPERSEDED, proposer_person_id=chair.id,
        due_date=date(2026, 5, 31), original_due_date=date(2026, 5, 31),
        superseded_by_id=res_k.id, created_at=datetime(2026, 3, 12, 14, 50),
    )
    res_l = resolution(
        ref_no="มติ 1/2569 ข้อ 5.1", origin_meeting_id=m1.id,
        text="ให้จัดกิจกรรมสัมมนาประจำปีนอกสถานที่ในไตรมาส 3",
        category="operations", status=ResolutionStatus.CANCELLED, proposer_person_id=chair.id,
        due_date=date(2026, 6, 30), original_due_date=date(2026, 6, 30),
        created_at=datetime(2026, 1, 22, 15, 0),
    )
    await session.flush()

    for resolution_row, people in [
        (res_a, [dept_supply, supply]),
        (res_b, [it, dept_it]),
        (res_c, [deputy]),
        (res_d, [secretary]),
        (res_e, [dept_supply]),
        (res_f, [finance]),
        (res_g, [academic]),
        (res_h, [finance]),
        (res_i, [it]),
        (res_j, [dept_supply]),
        (res_k, [dept_supply]),
        (res_l, [secretary]),
    ]:
        for who in people:
            session.add(
                ResolutionAssignee(
                    resolution_id=resolution_row.id, person_id=who.id, department_name=who.department
                )
            )

    # ── การอ้างถึงข้ามการประชุม ────────────────────────────────────────
    for resolution_row, meeting_row, link_type, evidence, start_ms, confidence, created in [
        (res_a, m5, LinkType.CREATED, "ที่ประชุมมีมติมอบหมายให้ฝ่ายพัสดุจัดทำร่างขอบเขตของงาน หรือ TOR สำหรับการจัดซื้อครุภัณฑ์คอมพิวเตอร์ทดแทน จำนวน 42 เครื่อง", 688_000, 0.97, datetime(2026, 6, 18, 14, 0)),
        (res_b, m2, LinkType.CREATED, "ที่ประชุมมีมติให้ฝ่ายเทคโนโลยีสารสนเทศดำเนินการปรับปรุงระบบสารบรรณอิเล็กทรอนิกส์", 1_204_000, 0.94, datetime(2026, 3, 12, 14, 0)),
        (res_b, m3, LinkType.PROGRESS_REPORTED, "ขณะนี้อยู่ระหว่างรอผู้รับจ้างส่งมอบโมดูลที่ 2 ขอเลื่อนกำหนดเป็นสิ้นเดือนพฤษภาคม", 948_000, 0.89, datetime(2026, 4, 23, 14, 20)),
        (res_b, m4, LinkType.PROGRESS_REPORTED, "ผู้รับจ้างยังส่งมอบไม่ครบ ขอเลื่อนอีกครั้งเป็นสิ้นเดือนมิถุนายน", 1_017_000, 0.90, datetime(2026, 5, 21, 14, 25)),
        (res_b, m5, LinkType.PROGRESS_REPORTED, "ผู้รับจ้างส่งมอบโมดูลไม่ครบ ทำให้ยังทดสอบระบบไม่ได้ครับ", 1_040_000, 0.93, datetime(2026, 6, 18, 15, 10)),
        (res_c, m5, LinkType.CREATED, "ที่ประชุมมีมติให้แต่งตั้งคณะทำงานจัดทำคำของบประมาณประจำปี 2570", 1_588_000, 0.96, datetime(2026, 6, 18, 14, 0)),
        (res_e, m5, LinkType.CLOSED, "เรื่องปรับปรุงห้องประชุมใหญ่ ดำเนินการแล้วเสร็จและตรวจรับเรียบร้อยแล้ว", 1_842_000, 1.0, datetime(2026, 6, 18, 15, 30)),
        (res_j, m4, LinkType.SUPERSEDED, "ขอปรับจำนวนเป็น 12 เครื่องและเปลี่ยนวิธีจัดซื้อเป็น e-bidding", 1_530_000, 1.0, datetime(2026, 5, 21, 15, 0)),
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

    for field, old, new, reason, when, meeting_row in [
        ("due_date", "2026-03-31", "2026-05-15", "ที่ประชุมครั้งที่ 3/2569 อนุมัติให้ขยายเวลา", datetime(2026, 4, 23, 14, 20), m3),
        ("due_date", "2026-05-15", "2026-06-30", "ผู้รับจ้างส่งมอบล่าช้า", datetime(2026, 5, 21, 14, 25), m4),
        ("due_date", "2026-06-30", "2026-08-31", "ที่ประชุมครั้งที่ 5/2569 ให้เร่งรัดผู้รับจ้าง", datetime(2026, 6, 18, 15, 10), m5),
        ("status", "in_progress", "blocked", "ติดปัญหาผู้รับจ้างส่งมอบไม่ครบ", datetime(2026, 6, 18, 15, 12), m5),
    ]:
        session.add(
            ResolutionHistory(
                resolution_id=res_b.id, field=field, old_value=old, new_value=new,
                changed_by=SECRETARY, changed_at=when, reason=reason, source_meeting_id=meeting_row.id,
            )
        )

    # ── คิวส่งออกที่รออนุมัติ ───────────────────────────────────────────
    session.add(
        OutboundAction(
            series_id=exec_series.id,
            resolution_id=res_a.id,
            action_type="send_resolution_reminder",
            recipient_person_id=supply.id,
            subject="แจ้งเตือน: มติ 5/2569 ข้อ 4.1 เกินกำหนดแล้ว",
            body=(
                "ระบบขอแจ้งเตือนมติที่อยู่ในความรับผิดชอบของท่าน\n\n"
                f"“{res_a.text}”\n\n"
                "อ้างถึง: มติ 5/2569 ข้อ 4.1 · กำหนดเดิม 18 กรกฎาคม 2569\n\n"
                "กรุณาแจ้งความคืบหน้ากลับผ่านลิงก์ในอีเมล โดยไม่ต้องเข้าสู่ระบบ"
            ),
            status=ActionStatus.PENDING_APPROVAL,
        )
    )

    session.add_all(
        [
            AuditLog(org_id=org.id, actor=SECRETARY, action="meeting_approved", entity_type="meeting",
                     entity_id=str(m5.id), meta="รับรองรายงานการประชุมครั้งที่ 5/2569"),
            AuditLog(org_id=org.id, actor=SECRETARY, action="confirm_alias", entity_type="person",
                     entity_id=str(deputy.id), meta='ยืนยัน "พี่หนึ่ง" → นายสุรชัย ทองอินทร์'),
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
    """
    ไม่สร้างตารางเอง — schema เป็นหน้าที่ของ Alembic เท่านั้น
    ถ้า create_all อยู่ตรงนี้ migration ที่หายไปจะถูกกลบจนไม่มีใครรู้ว่าหลุด
    """
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
        print("สร้างข้อมูลตั้งต้นเรียบร้อย")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main("--reset" in sys.argv))
