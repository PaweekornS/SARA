"""Collection ของผู้ใช้ — รายการ, การประชุมข้างใน, งานค้าง และถาม-ตอบ"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user, owned_or_404
from app.db.models import ActionItem, Collection, Meeting, QaLog, User
from app.db.session import get_db
from app.schemas import (
    ActionItemOut,
    CollectionIn,
    CollectionOut,
    CollectionPatch,
    MeetingOut,
    QaOut,
    Question,
)
from app.services import qa as qa_service
from app.services import vector_store
from app.services.ratelimit import enforce
from app.services.storage import remove_files
from app.services.templates import is_known_template

router = APIRouter(prefix="/collections", tags=["Collections"], dependencies=[Depends(current_user)])

QA_PER_HOUR = 60


async def _with_counts(db: AsyncSession, collections: list[Collection]) -> list[CollectionOut]:
    ids = [c.id for c in collections]
    if not ids:
        return []
    meeting_counts = dict(
        (await db.execute(
            select(Meeting.collection_id, func.count()).where(Meeting.collection_id.in_(ids)).group_by(Meeting.collection_id)
        )).all()
    )
    open_counts = dict(
        (await db.execute(
            select(ActionItem.collection_id, func.count())
            .where(ActionItem.collection_id.in_(ids), ActionItem.done.is_(False))
            .group_by(ActionItem.collection_id)
        )).all()
    )
    return [
        CollectionOut.model_validate(c).model_copy(
            update={"meeting_count": meeting_counts.get(c.id, 0), "open_action_count": open_counts.get(c.id, 0)}
        )
        for c in collections
    ]


def _check_template(template: str | None) -> None:
    if template is not None and not is_known_template(template):
        raise HTTPException(status_code=422, detail=f"ไม่รู้จักรูปแบบสรุป {template}")


@router.get("", response_model=list[CollectionOut])
async def list_collections(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(Collection).where(Collection.user_id == user.id).order_by(Collection.created_at))
    ).scalars().all()
    return await _with_counts(db, list(rows))


@router.post("", response_model=CollectionOut, status_code=201)
async def create_collection(payload: CollectionIn, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    _check_template(payload.default_template)
    collection = Collection(user_id=user.id, **payload.model_dump())
    db.add(collection)
    await db.commit()
    await db.refresh(collection)
    return CollectionOut.model_validate(collection)


@router.get("/{collection_id}", response_model=CollectionOut)
async def get_collection(collection_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    collection = await owned_or_404(db, Collection, collection_id, user, "collection")
    return (await _with_counts(db, [collection]))[0]


@router.patch("/{collection_id}", response_model=CollectionOut)
async def patch_collection(
    collection_id: UUID, payload: CollectionPatch, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    collection = await owned_or_404(db, Collection, collection_id, user, "collection")
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    _check_template(changes.get("default_template"))
    for key, value in changes.items():
        setattr(collection, key, value)
    await db.commit()
    return (await _with_counts(db, [collection]))[0]


@router.delete("/{collection_id}", status_code=204)
async def delete_collection(
    collection_id: UUID, background: BackgroundTasks, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    collection = await owned_or_404(db, Collection, collection_id, user, "collection")
    meetings = (await db.execute(select(Meeting).where(Meeting.collection_id == collection.id))).scalars().all()
    await db.delete(collection)
    await db.commit()
    remove_files(meetings)
    background.add_task(vector_store.delete_meetings, [m.id for m in meetings])


@router.get("/{collection_id}/meetings", response_model=list[MeetingOut])
async def list_meetings(collection_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await owned_or_404(db, Collection, collection_id, user, "collection")
    rows = await db.execute(
        select(Meeting)
        .where(Meeting.collection_id == collection_id)
        .order_by(Meeting.meeting_date.desc().nulls_last(), Meeting.created_at.desc())
    )
    return rows.scalars().all()


@router.get("/{collection_id}/action-items", response_model=list[ActionItemOut])
async def list_action_items(
    collection_id: UUID,
    done: bool | None = None,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
):
    await owned_or_404(db, Collection, collection_id, user, "collection")
    stmt = select(ActionItem).where(ActionItem.collection_id == collection_id)
    if done is not None:
        stmt = stmt.where(ActionItem.done.is_(done))
    stmt = stmt.order_by(ActionItem.done, ActionItem.due_date.asc().nulls_last(), ActionItem.created_at)
    return (await db.execute(stmt)).scalars().all()


@router.post("/{collection_id}/ask", response_model=QaOut)
async def ask(collection_id: UUID, payload: Question, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await owned_or_404(db, Collection, collection_id, user, "collection")
    enforce(f"qa:{user.id}", 1, QA_PER_HOUR, 3600, "ถามได้ไม่เกิน 60 คำถามต่อชั่วโมง")

    result = await qa_service.answer_question(db, user.id, collection_id, payload.question)
    log = QaLog(
        user_id=user.id,
        collection_id=collection_id,
        question=payload.question,
        answer=result.answer,
        citations=result.citations,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


@router.get("/{collection_id}/qa", response_model=list[QaOut])
async def qa_history(collection_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await owned_or_404(db, Collection, collection_id, user, "collection")
    rows = await db.execute(
        select(QaLog).where(QaLog.collection_id == collection_id).order_by(QaLog.asked_at.desc()).limit(50)
    )
    return rows.scalars().all()


@router.delete("/{collection_id}/qa", status_code=204)
async def clear_qa(collection_id: UUID, user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await owned_or_404(db, Collection, collection_id, user, "collection")
    await db.execute(delete(QaLog).where(QaLog.collection_id == collection_id))
    await db.commit()
