"""M4 — รายละเอียดมติ แก้ไข และเปลี่ยนสถานะ"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_actor, current_org
from app.api.serializers import resolution_out
from app.db.models import Organization, Resolution, ResolutionHistory, ResolutionLink
from app.db.session import get_db
from app.schemas import HistoryOut, LinkOut, ResolutionOut, ResolutionPatch, StatusChange
from app.services.resolutions import audit, change_status, get_or_404, patch_resolution

router = APIRouter(prefix="/resolutions", tags=["Resolutions"])


@router.get("/{resolution_id}", response_model=ResolutionOut)
async def get_resolution(resolution_id: UUID, db: AsyncSession = Depends(get_db)):
    resolution = await get_or_404(db, Resolution, resolution_id, "มติ")
    return await resolution_out(db, resolution)


@router.get("/{resolution_id}/links", response_model=list[LinkOut])
async def get_links(resolution_id: UUID, db: AsyncSession = Depends(get_db)):
    """ไทม์ไลน์การถูกอ้างถึงข้ามการประชุม (FR-M6-06) พร้อมหลักฐานคำต่อคำทุกจุด"""
    rows = await db.execute(
        select(ResolutionLink)
        .where(ResolutionLink.resolution_id == resolution_id)
        .order_by(ResolutionLink.created_at)
    )
    return list(rows.scalars().all())


@router.get("/{resolution_id}/history", response_model=list[HistoryOut])
async def get_history(resolution_id: UUID, db: AsyncSession = Depends(get_db)):
    rows = await db.execute(
        select(ResolutionHistory)
        .where(ResolutionHistory.resolution_id == resolution_id)
        .order_by(ResolutionHistory.changed_at.desc())
    )
    return list(rows.scalars().all())


@router.patch("/{resolution_id}", response_model=ResolutionOut)
async def patch(
    resolution_id: UUID,
    payload: ResolutionPatch,
    db: AsyncSession = Depends(get_db),
    actor: str = Depends(current_actor),
):
    """FR-M4-08 แก้ไขข้อความ/ผู้รับผิดชอบ/กำหนดเสร็จได้ พร้อมเก็บประวัติการแก้"""
    resolution = await get_or_404(db, Resolution, resolution_id, "มติ")
    await patch_resolution(
        db,
        resolution,
        actor=actor,
        text=payload.text,
        category=payload.category,
        due_date=payload.due_date,
        new_assignees=payload.assignee_ids,
        reason=payload.reason,
    )
    await db.commit()
    await db.refresh(resolution)
    return await resolution_out(db, resolution)


@router.post("/{resolution_id}/status", response_model=ResolutionOut)
async def set_status(
    resolution_id: UUID,
    payload: StatusChange,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(current_org),
    actor: str = Depends(current_actor),
):
    """
    เปลี่ยนสถานะมติ — ตรวจ state machine ตาม §4.1 และบังคับให้มีเหตุผลเมื่อปิด/ยกเลิก
    endpoint นี้ถือว่ามีมนุษย์เป็นผู้สั่งเสมอ (system_initiated=False)
    """
    resolution = await get_or_404(db, Resolution, resolution_id, "มติ")
    old_status = resolution.status

    await change_status(
        db,
        resolution,
        payload.status,
        reason=payload.reason,
        actor=actor,
        meeting_id=payload.meeting_id,
        evidence=payload.evidence,
        evidence_start_ms=payload.evidence_start_ms,
        segment_id=payload.segment_id,
    )
    await audit(
        db, org.id, actor, "change_resolution_status", "resolution", resolution.id,
        f"{old_status} → {payload.status}",
    )
    await db.commit()
    await db.refresh(resolution)
    return await resolution_out(db, resolution)
