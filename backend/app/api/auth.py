"""เข้าสู่ระบบด้วย Google — ผู้ใช้ใหม่ได้ collection แรกให้อัตโนมัติ"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SESSION_COOKIE, current_user
from app.core.config import settings
from app.core.security import (
    InvalidGoogleToken,
    create_access_token,
    verify_google_token,
)
from app.db.models import Collection, User, _now
from app.db.session import get_db
from app.schemas import AuthOut, DemoLoginIn, GoogleLoginIn, UserOut

router = APIRouter(prefix="/auth", tags=["Authentication"])

FIRST_COLLECTION_NAME = "การประชุมของฉัน"
DEMO_EMAIL = "demo@sara.local"


async def _upsert_user(db: AsyncSession, *, email: str, name: str, picture: str, provider: str,
                       google_sub: str | None) -> User:
    user = None
    if google_sub:
        user = (await db.execute(select(User).where(User.google_sub == google_sub))).scalars().first()
    if user is None:
        user = (await db.execute(select(User).where(User.email == email))).scalars().first()

    if user is None:
        user = User(email=email, name=name, picture=picture, provider=provider, google_sub=google_sub)
        db.add(user)
        await db.flush()
        db.add(Collection(user_id=user.id, name=FIRST_COLLECTION_NAME))
    else:
        user.name = name or user.name
        user.picture = picture or user.picture
        user.google_sub = google_sub or user.google_sub
        user.last_login_at = _now()

    await db.commit()
    await db.refresh(user)
    return user


def _issue_session(response: Response, user: User) -> AuthOut:
    token = create_access_token(str(user.id))
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.SESSION_COOKIE_SECURE,
        max_age=settings.SESSION_EXPIRE_HOURS * 3600,
    )
    return AuthOut(access_token=token, user=UserOut.model_validate(user))


@router.post("/google", response_model=AuthOut)
async def google_login(payload: GoogleLoginIn, response: Response, db: AsyncSession = Depends(get_db)):
    try:
        info = verify_google_token(payload.id_token)
    except InvalidGoogleToken as err:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"ยืนยันตัวตนกับ Google ไม่สำเร็จ: {err}")

    email = info["email"].lower()
    user = await _upsert_user(
        db,
        email=email,
        name=info.get("name") or email.split("@")[0],
        picture=info.get("picture", ""),
        provider="google",
        google_sub=info["sub"],
    )
    return _issue_session(response, user)


@router.post("/demo", response_model=AuthOut)
async def demo_login(payload: DemoLoginIn, response: Response, db: AsyncSession = Depends(get_db)):
    """ใช้ตอนพัฒนาเท่านั้น — ปิดเมื่อ ENV=prod เว้นแต่ตั้ง ALLOW_DEMO_LOGIN=true"""
    if not settings.demo_login_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")

    #  บัญชี demo มีบัญชีเดียวที่อีเมลตายตัว ห้ามรับอีเมลจากผู้ใช้
    #  ไม่อย่างนั้นใครก็สวมรอยบัญชี Google ของคนอื่นได้ผ่านทางนี้
    user = await _upsert_user(
        db,
        email=DEMO_EMAIL,
        name=payload.name,
        picture="",
        provider="demo",
        google_sub=None,
    )
    return _issue_session(response, user)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)):
    return user


@router.post("/logout", status_code=204)
async def logout(response: Response):
    response.delete_cookie(key=SESSION_COOKIE, samesite="lax", secure=settings.SESSION_COOKIE_SECURE)
    response.status_code = 204
    return response
