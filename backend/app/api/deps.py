"""
Dependency ที่ router ใช้ร่วมกัน

หลักการกันข้อมูลรั่วข้ามผู้ใช้: ทุก endpoint ที่รับ {id} ต้องดึงผ่าน owned_or_404()
ซึ่งกรองด้วย user_id ไปพร้อมกัน — ของคนอื่นตอบ 404 เหมือนไม่มีอยู่ ไม่ใช่ 403
เพื่อไม่ให้เดา id แล้วรู้ว่ามีข้อมูลอยู่จริง
"""

from __future__ import annotations

from typing import TypeVar
from uuid import UUID

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import read_access_token
from app.db.models import User
from app.db.session import get_db

SESSION_COOKIE = "access_token"

Model = TypeVar("Model")


def _bearer(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


async def optional_user(
    access_token: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    token = _bearer(authorization) or access_token
    if not token:
        return None
    user_id = read_access_token(token)
    if user_id is None:
        return None
    try:
        return await db.get(User, UUID(user_id))
    except ValueError:
        return None


async def current_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="กรุณาเข้าสู่ระบบ",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def owned_or_404(db: AsyncSession, model: type[Model], entity_id: UUID, user: User, label: str) -> Model:
    row = (
        await db.execute(select(model).where(model.id == entity_id, model.user_id == user.id))
    ).scalars().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ไม่พบ{label}")
    return row
