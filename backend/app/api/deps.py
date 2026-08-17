"""
Dependency ที่ router ใช้ร่วมกัน

⚠ ยังไม่มีระบบล็อกอิน (M10 ถูกลดเป็น Should สำหรับรอบนี้)
   ตอนนี้ผู้กระทำมาจากหัวข้อ X-Actor ซึ่ง "ไม่ใช่การยืนยันตัวตน" ใครก็ปลอมได้
   ก่อนใช้งานจริงต้องเปลี่ยนมาอ่านจาก session/JWT และบังคับ auth ทุก endpoint
   ดู FR-M10-01 ถึง 03 ซึ่งเป็น Must แบบไม่มีข้อยกเว้นสำหรับการใช้งานจริง
"""

from __future__ import annotations

from urllib.parse import unquote

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Organization
from app.db.session import get_db


async def current_actor(
    x_actor: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="x-api-key"),
    authorization: str | None = Header(default=None),
) -> str:
    """
    ตรวจสอบสิทธิ์ผ่าน API Key (หากมีการกำหนด API_KEY ในคอนฟิก)
    และอ่านชื่อผู้กระทำจาก X-Actor header เพื่อสร้าง Audit Trail ที่น่าเชื่อถือ
    """
    if settings.API_KEY:
        auth_token = None
        if authorization and authorization.lower().startswith("bearer "):
            auth_token = authorization[7:].strip()
        provided_key = x_api_key or auth_token
        if provided_key != settings.API_KEY:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API Key ไม่ถูกต้องหรือไม่ได้ระบุสิทธิ์ในการใช้งาน",
            )

    if not x_actor:
        return settings.DEFAULT_ACTOR
    return (unquote(x_actor) or settings.DEFAULT_ACTOR).strip()



async def current_org(db: AsyncSession = Depends(get_db)) -> Organization:
    """ระบบยังเป็น single-tenant — ใช้ organization แถวแรกที่มี"""
    org = (await db.execute(select(Organization).order_by(Organization.created_at))).scalars().first()
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ยังไม่มีข้อมูลองค์กรในระบบ — รัน `python -m app.seed` เพื่อสร้างข้อมูลตั้งต้น",
        )
    return org
