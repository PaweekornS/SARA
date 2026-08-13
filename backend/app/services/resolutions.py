"""
ตรรกะวงจรชีวิตของมติ (M4) — ทุกการเปลี่ยนแปลงต้องทิ้งร่องรอยไว้เสมอ

กติกาจาก §4.1:
  * ระบบเปลี่ยนสถานะเองได้เฉพาะ proposed → confirmed (ตอนรับรองรายงานการประชุม)
  * การเปลี่ยนไป done / cancelled ต้องมีคนกดยืนยันเสมอ
  * ทุกการเปลี่ยนสถานะบันทึก: ใครเปลี่ยน เมื่อไหร่ meeting ไหนเป็นต้นเหตุ หลักฐานอะไร
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status as http_status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AuditLog,
    LinkType,
    Person,
    Resolution,
    ResolutionAssignee,
    ResolutionHistory,
    ResolutionLink,
    ResolutionStatus,
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def get_or_404(db: AsyncSession, model, entity_id: UUID, label: str):
    obj = await db.get(model, entity_id)
    if obj is None:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=f"ไม่พบ{label}")
    return obj


async def assignee_ids(db: AsyncSession, resolution_id: UUID) -> list[UUID]:
    rows = await db.execute(
        select(ResolutionAssignee.person_id).where(ResolutionAssignee.resolution_id == resolution_id)
    )
    return list(rows.scalars().all())


async def set_assignees(db: AsyncSession, resolution: Resolution, person_ids: list[UUID]) -> None:
    existing = await db.execute(
        select(ResolutionAssignee).where(ResolutionAssignee.resolution_id == resolution.id)
    )
    for row in existing.scalars().all():
        await db.delete(row)
    for pid in dict.fromkeys(person_ids):
        person = await db.get(Person, pid)
        db.add(
            ResolutionAssignee(
                resolution_id=resolution.id,
                person_id=pid,
                department_name=person.department if person else None,
            )
        )


async def audit(
    db: AsyncSession,
    org_id: UUID | None,
    actor: str,
    action: str,
    entity_type: str,
    entity_id,
    meta: str = "",
) -> None:
    db.add(
        AuditLog(
            org_id=org_id,
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            meta=meta,
        )
    )


async def record_history(
    db: AsyncSession,
    resolution: Resolution,
    field: str,
    old_value,
    new_value,
    actor: str,
    reason: str,
    source_meeting_id: UUID | None = None,
) -> None:
    db.add(
        ResolutionHistory(
            resolution_id=resolution.id,
            field=field,
            old_value="" if old_value is None else str(old_value),
            new_value="" if new_value is None else str(new_value),
            changed_by=actor,
            reason=reason,
            source_meeting_id=source_meeting_id,
        )
    )


async def change_status(
    db: AsyncSession,
    resolution: Resolution,
    new_status: str,
    reason: str,
    actor: str,
    meeting_id: UUID | None = None,
    evidence: str | None = None,
    evidence_start_ms: int | None = None,
    segment_id: UUID | None = None,
    system_initiated: bool = False,
) -> Resolution:
    old_status = resolution.status
    if new_status == old_status:
        return resolution

    allowed = ResolutionStatus.TRANSITIONS.get(old_status, ())
    if new_status not in allowed:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail=f"เปลี่ยนสถานะจาก {old_status} ไป {new_status} ไม่ได้ตาม state machine",
        )

    #  FR-M4-06 การปิดมติอัตโนมัติต้องผ่านการยืนยันจากมนุษย์เสมอ
    if system_initiated and new_status in (ResolutionStatus.DONE, ResolutionStatus.CANCELLED):
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="ระบบปิดหรือยกเลิกมติเองไม่ได้ ต้องมีผู้ใช้ยืนยัน",
        )

    if new_status in (ResolutionStatus.DONE, ResolutionStatus.CANCELLED) and not reason.strip():
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="การปิดหรือยกเลิกมติต้องระบุเหตุผลกำกับเสมอ",
        )

    resolution.status = new_status
    resolution.updated_at = utcnow()
    if new_status == ResolutionStatus.DONE:
        resolution.closed_at = utcnow()
        resolution.closed_meeting_id = meeting_id or resolution.closed_meeting_id
    else:
        resolution.closed_at = None
        resolution.closed_meeting_id = None

    await record_history(
        db, resolution, "status", old_status, new_status, actor, reason or new_status, meeting_id
    )

    if meeting_id:
        #  ลิงก์ที่มาจากการยืนยันของคนแทนที่ลิงก์ referenced ที่ระบบสร้างไว้เองในการประชุมเดียวกัน
        #  ไม่งั้นไทม์ไลน์จะมีหลักฐานท่อนเดียวกันโผล่ซ้ำสองบรรทัด
        dupes = await db.execute(
            select(ResolutionLink).where(
                ResolutionLink.resolution_id == resolution.id,
                ResolutionLink.meeting_id == meeting_id,
                ResolutionLink.link_type == LinkType.REFERENCED,
            )
        )
        for row in dupes.scalars().all():
            await db.delete(row)

        db.add(
            ResolutionLink(
                resolution_id=resolution.id,
                meeting_id=meeting_id,
                link_type=LinkType.CLOSED if new_status == ResolutionStatus.DONE else LinkType.PROGRESS_REPORTED,
                segment_id=segment_id,
                evidence_text=evidence or reason,
                evidence_start_ms=evidence_start_ms,
                confidence=1.0,
            )
        )

    return resolution


async def patch_resolution(
    db: AsyncSession,
    resolution: Resolution,
    actor: str,
    text: str | None = None,
    category: str | None = None,
    due_date: date | None = None,
    new_assignees: list[UUID] | None = None,
    reason: str = "แก้ไขด้วยผู้ใช้",
) -> Resolution:
    """FR-M4-08 แก้ไขได้ด้วยมือ พร้อมเก็บประวัติการแก้ทุกฟิลด์"""
    if text is not None and text != resolution.text:
        await record_history(db, resolution, "text", resolution.text, text, actor, reason)
        resolution.text = text

    if category is not None and category != resolution.category:
        await record_history(db, resolution, "category", resolution.category, category, actor, reason)
        resolution.category = category

    if due_date is not None and due_date != resolution.due_date:
        #  FR-M4-09 เลื่อนกำหนดออกไปนับเป็นการเลื่อนซ้ำ 1 ครั้ง เพื่อให้ติดธงได้เมื่อเกิน 3
        if resolution.due_date and due_date > resolution.due_date:
            resolution.postpone_count = (resolution.postpone_count or 0) + 1
        await record_history(db, resolution, "due_date", resolution.due_date, due_date, actor, reason)
        resolution.due_date = due_date
        if resolution.original_due_date is None:
            resolution.original_due_date = due_date

    if new_assignees is not None:
        current = await assignee_ids(db, resolution.id)
        if sorted(map(str, current)) != sorted(map(str, new_assignees)):
            await record_history(
                db, resolution, "assignee_ids", ",".join(map(str, current)),
                ",".join(map(str, new_assignees)), actor, reason,
            )
            await set_assignees(db, resolution, new_assignees)

    resolution.updated_at = utcnow()
    return resolution


async def supersede(
    db: AsyncSession, old: Resolution, new: Resolution, actor: str, reason: str
) -> None:
    """FR-M4-07 มติใหม่มาแทนมติเก่า พร้อมลิงก์อ้างอิงถึงกัน"""
    await record_history(db, old, "status", old.status, ResolutionStatus.SUPERSEDED, actor, reason)
    old.status = ResolutionStatus.SUPERSEDED
    old.superseded_by_id = new.id
    old.updated_at = utcnow()
    if new.origin_meeting_id:
        db.add(
            ResolutionLink(
                resolution_id=old.id,
                meeting_id=new.origin_meeting_id,
                link_type=LinkType.SUPERSEDED,
                evidence_text=reason,
                confidence=1.0,
            )
        )


def overdue_days(resolution: Resolution, today: date | None = None) -> int:
    """มติที่ปิด/ยกเลิก/ถูกแทนที่แล้ว ไม่นับว่าเกินกำหนด ต่อให้เลยวันมาแล้ว"""
    if not resolution.due_date or resolution.status not in ResolutionStatus.OPEN:
        return 0
    delta = (today or date.today()) - resolution.due_date
    return max(0, delta.days)


def next_ref_no(sequence_no: int, fiscal_year: int, item_no: int) -> str:
    return f"มติ {sequence_no}/{fiscal_year} ข้อ 4.{item_no}"
