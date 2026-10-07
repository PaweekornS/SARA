"""แก้ไข / ติ๊กเสร็จ / ลบ action item และตอบรับข้อเสนอว่างานเสร็จแล้ว"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, owned_or_404
from app.db.models import ActionItem, User, _now
from app.db.session import get_db
from app.schemas import ActionItemOut, ActionItemPatch

router = APIRouter(prefix="/action-items", tags=["Action items"], dependencies=[Depends(current_user)])


def _set_done(item: ActionItem, done: bool) -> None:
    if item.done == done:
        return
    item.done = done
    item.done_at = _now() if done else None
    #  ผู้ใช้ตัดสินใจเองแล้ว ข้อเสนอเดิมจึงไม่ต้องแสดงอีก
    item.suggested_done_meeting_id = None
    item.suggested_done_evidence = ""


@router.patch("/{item_id}", response_model=ActionItemOut)
async def patch_item(item_id: UUID, payload: ActionItemPatch, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    item = await owned_or_404(db, ActionItem, item_id, user, "งาน")
    changes = payload.model_dump(exclude_unset=True)
    if "done" in changes:
        done = changes.pop("done")
        if done is not None:
            _set_done(item, done)
    if changes.get("text") is None:
        changes.pop("text", None)
    for key, value in changes.items():
        setattr(item, key, "" if key == "owner" and value is None else value)
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
async def delete_item(item_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    item = await owned_or_404(db, ActionItem, item_id, user, "งาน")
    await db.delete(item)
    await db.commit()


@router.post("/{item_id}/suggestion/accept", response_model=ActionItemOut)
async def accept_suggestion(item_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    item = await owned_or_404(db, ActionItem, item_id, user, "งาน")
    if item.suggested_done_meeting_id is None:
        raise HTTPException(status_code=409, detail="งานนี้ไม่มีข้อเสนอให้ยืนยัน")
    _set_done(item, True)
    await db.commit()
    await db.refresh(item)
    return item


@router.post("/{item_id}/suggestion/dismiss", response_model=ActionItemOut)
async def dismiss_suggestion(item_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    item = await owned_or_404(db, ActionItem, item_id, user, "งาน")
    item.suggested_done_meeting_id = None
    item.suggested_done_evidence = ""
    await db.commit()
    await db.refresh(item)
    return item
