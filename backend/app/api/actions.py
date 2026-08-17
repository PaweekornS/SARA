"""
M7 — คิวการส่งออก

จุดยืนของ v2: human-in-the-loop เป็นค่าเริ่มต้น (FR-M7-07)
ไม่มี endpoint ไหนที่ส่งอีเมลออกได้โดยไม่ผ่านการอนุมัติ
ตัวส่งจริงคือ MCP tool ที่ถูกเรียกจาก /approve เท่านั้น
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_actor, current_org
from app.db.models import ActionStatus, Organization, OutboundAction, Person
from app.db.session import get_db
from app.schemas import ActionOut
from app.services.resolutions import audit, get_or_404, utcnow
from app.workers.tasks import _send_action, send_outbound_action_task

# ── Global Variables & Constants ─────────────────────────────────────────────

router = APIRouter(prefix="/actions", tags=["Outbound actions"])


# ── Functions & Route Handlers ───────────────────────────────────────────────

def _dispatch_action(action_id: UUID, bg_tasks: BackgroundTasks):
    """ส่งออกผ่าน Celery คิว หรือส่งตรงผ่าน FastAPI BackgroundTasks"""
    try:
        send_outbound_action_task.delay(str(action_id))
    except Exception:
        # Fallback หากไม่ได้รัน Celery Broker ให้ใช้ FastAPI BackgroundTasks ส่งสดทันที
        bg_tasks.add_task(_send_action, action_id, None)


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
    bg_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(current_org),
    actor: str = Depends(current_actor),
):
    """อนุมัติแล้วส่งจริงผ่าน Direct SMTP/Email Engine — บันทึกทุกครั้งว่าใครอนุมัติ (FR-M7-09)"""
    action = await get_or_404(db, OutboundAction, action_id, "รายการส่งออก")
    if action.status != ActionStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=409,
            detail=f"อนุมัติไม่ได้ — รายการอยู่ในสถานะ {action.status}",
        )

    action.status = ActionStatus.APPROVED
    action.approved_by = actor
    action.approved_at = utcnow()
    await audit(db, org.id, actor, "approve_action", "outbound_action", action.id, action.action_type)
    await db.commit()
    await db.refresh(action)

    _dispatch_action(action.id, bg_tasks)
    return action


@router.post("/{action_id}/cancel", response_model=ActionOut)
async def cancel(
    action_id: UUID,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(current_org),
    actor: str = Depends(current_actor),
):
    """ยกเลิกก่อนส่ง"""
    action = await get_or_404(db, OutboundAction, action_id, "รายการส่งออก")
    if action.status not in (ActionStatus.PENDING_APPROVAL, ActionStatus.FAILED):
        raise HTTPException(status_code=409, detail=f"ยกเลิกไม่ได้ — รายการอยู่ในสถานะ {action.status}")

    action.status = ActionStatus.CANCELLED
    await audit(db, org.id, actor, "cancel_action", "outbound_action", action.id, action.action_type)
    await db.commit()
    await db.refresh(action)
    return action


@router.post("/{action_id}/retry", response_model=ActionOut)
async def retry(
    action_id: UUID,
    bg_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(current_org),
    actor: str = Depends(current_actor),
):
    """retry เมื่อส่งไม่สำเร็จ"""
    action = await get_or_404(db, OutboundAction, action_id, "รายการส่งออก")
    if action.status != ActionStatus.FAILED:
        raise HTTPException(status_code=409, detail=f"retry ได้เฉพาะรายการที่ failed (ปัจจุบัน {action.status})")

    action.status = ActionStatus.APPROVED
    action.error_message = None
    await audit(db, org.id, actor, "retry_action", "outbound_action", action.id, action.action_type)
    await db.commit()
    await db.refresh(action)

    _dispatch_action(action.id, bg_tasks)
    return action
