"""
M7 — คิวการส่งออก

จุดยืนของ v2: human-in-the-loop เป็นค่าเริ่มต้น (FR-M7-07)
ไม่มี endpoint ไหนที่ส่งอีเมลออกได้โดยไม่ผ่านการอนุมัติ
ตัวส่งจริงคือ MCP tool ที่ถูกเรียกจาก /approve เท่านั้น
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_actor, current_org
from app.db.models import ActionStatus, Organization, OutboundAction, Person
from app.db.session import get_db
from app.schemas import ActionOut
from app.services.resolutions import audit, get_or_404, utcnow
from app.workers.tasks import send_outbound_action_task

router = APIRouter(prefix="/actions", tags=["Outbound actions"])


@router.get("", response_model=list[ActionOut])
async def list_actions(status: str | None = None, db: AsyncSession = Depends(get_db)):
    stmt = select(OutboundAction).order_by(OutboundAction.created_at.desc())
    if status:
        stmt = stmt.where(OutboundAction.status == status)
    return list((await db.execute(stmt)).scalars().all())


@router.get("/pending", response_model=list[ActionOut])
async def pending(db: AsyncSession = Depends(get_db)):
    rows = await db.execute(
        select(OutboundAction)
        .where(OutboundAction.status == ActionStatus.PENDING_APPROVAL)
        .order_by(OutboundAction.created_at)
    )
    return list(rows.scalars().all())


@router.post("/{action_id}/approve", response_model=ActionOut)
async def approve(
    action_id: UUID,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(current_org),
    actor: str = Depends(current_actor),
):
    """อนุมัติแล้วส่งจริงผ่าน MCP — บันทึกทุกครั้งว่าใครอนุมัติ (FR-M7-09)"""
    action = await get_or_404(db, OutboundAction, action_id, "รายการส่งออก")
    if action.status != ActionStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=409, detail=f"รายการนี้อยู่ในสถานะ {action.status} แล้ว")

    recipient = await db.get(Person, action.recipient_person_id) if action.recipient_person_id else None
    if recipient is None or not recipient.email:
        raise HTTPException(
            status_code=422,
            detail="ผู้รับยังไม่มีอีเมลในทะเบียนบุคคล จึงส่งออกไม่ได้",
        )

    action.status = ActionStatus.APPROVED
    action.approved_by = actor
    await audit(db, org.id, actor, "approve_outbound_action", "outbound_action", action.id, action.subject)
    await db.commit()

    #  ส่งจริงในเบื้องหลัง เพื่อไม่ให้ผู้ใช้ต้องรอ SMTP
    send_outbound_action_task.delay(str(action.id))

    await db.refresh(action)
    return action


@router.post("/{action_id}/cancel", response_model=ActionOut)
async def cancel(
    action_id: UUID,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(current_org),
    actor: str = Depends(current_actor),
):
    action = await get_or_404(db, OutboundAction, action_id, "รายการส่งออก")
    if action.status == ActionStatus.SENT:
        raise HTTPException(status_code=409, detail="รายการนี้ส่งออกไปแล้ว ยกเลิกไม่ได้")
    action.status = ActionStatus.CANCELLED
    await audit(db, org.id, actor, "cancel_outbound_action", "outbound_action", action.id, action.subject)
    await db.commit()
    await db.refresh(action)
    return action


@router.post("/{action_id}/retry", response_model=ActionOut)
async def retry(action_id: UUID, db: AsyncSession = Depends(get_db)):
    action = await get_or_404(db, OutboundAction, action_id, "รายการส่งออก")
    if action.status != ActionStatus.FAILED:
        raise HTTPException(status_code=409, detail="ลองส่งใหม่ได้เฉพาะรายการที่ส่งไม่สำเร็จ")
    action.status = ActionStatus.APPROVED
    action.error = None
    await db.commit()
    send_outbound_action_task.delay(str(action.id))
    await db.refresh(action)
    return action


@router.get("/{action_id}", response_model=ActionOut)
async def get_action(action_id: UUID, db: AsyncSession = Depends(get_db)):
    return await get_or_404(db, OutboundAction, action_id, "รายการส่งออก")


def mark_sent(action: OutboundAction) -> None:
    action.status = ActionStatus.SENT
    action.sent_at = utcnow()
    action.error = None
