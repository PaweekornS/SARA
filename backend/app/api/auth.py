"""
SARA Authentication Router (v3.0.0-PROD)

Provides Google OAuth 2.0 OpenID Connect authentication,
session JWT generation, user identity queries, and guest/demo login.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Cookie, Header, HTTPException, Response, status
from pydantic import BaseModel, EmailStr

from app.core.security import create_access_token, verify_access_token, verify_google_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── Pydantic Request & Response Models ───────────────────────────────────────

class GoogleAuthRequest(BaseModel):
    id_token: str
    client_id: Optional[str] = None


class UserProfile(BaseModel):
    id: str
    email: str
    name: str
    picture: Optional[str] = None
    provider: str = "google"


class AuthResponse(BaseModel):
    status: str
    access_token: str
    token_type: str = "bearer"
    user: UserProfile


class DemoAuthRequest(BaseModel):
    name: Optional[str] = "ผู้ใช้งานทดสอบ (Demo User)"
    email: Optional[EmailStr] = "demo.user@sara-ai.local"


# ── Route Handlers ───────────────────────────────────────────────────────────

@router.post("/google", response_model=AuthResponse)
async def google_login(payload: GoogleAuthRequest, response: Response):
    """
    Verify Google ID Token, provision/retrieve user session, and issue secure JWT cookie.
    """
    try:
        id_info = verify_google_token(payload.id_token, payload.client_id)
        email = id_info.get("email", "unknown@google.com")
        name = id_info.get("name", email.split("@")[0])
        user_id = id_info.get("sub", email)
        picture = id_info.get("picture", "")

        user_data = {
            "id": str(user_id),
            "email": email,
            "name": name,
            "picture": picture,
            "provider": "google",
        }

        token = create_access_token(data=user_data)

        # Set secure HttpOnly cookie for Web UI clients
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            samesite="lax",
            secure=False,  # Can be configured via settings
            max_age=72 * 3600,
        )

        return AuthResponse(
            status="success",
            access_token=token,
            user=UserProfile(**user_data),
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"การยืนยัน Google Token ไม่สำเร็จ: {err}",
        )
    except Exception as err:
        logger.exception("Google auth error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"เกิดข้อผิดพลาดในการเข้าสู่ระบบ: {err}",
        )


@router.post("/demo", response_model=AuthResponse)
async def demo_login(payload: DemoAuthRequest = DemoAuthRequest(), response: Response = None):
    """
    One-click demo/guest login for evaluating SARA without configuring Google OAuth keys.
    """
    user_data = {
        "id": "demo-user-id",
        "email": str(payload.email),
        "name": payload.name or "Demo User",
        "picture": "",
        "provider": "demo",
    }

    token = create_access_token(data=user_data)
    if response:
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            samesite="lax",
            secure=False,
            max_age=72 * 3600,
        )

    return AuthResponse(
        status="success",
        access_token=token,
        user=UserProfile(**user_data),
    )


@router.get("/me", response_model=UserProfile)
async def get_current_user(
    access_token: Optional[str] = Cookie(None),
    authorization: Optional[str] = Header(None),
):
    """
    Return currently authenticated user profile from Cookie or Bearer header.
    """
    token = None
    if access_token:
        token = access_token
    elif authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]

    if not token:
        # Default guest identity for public / zero-friction use
        return UserProfile(
            id="public-guest",
            email="guest@sara-ai.local",
            name="ผู้ใช้งานทั่วไป (Guest)",
            picture="",
            provider="guest",
        )

    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session หมดอายุหรือไม่ถูกต้อง")

    return UserProfile(
        id=str(payload.get("id", "user")),
        email=payload.get("email", ""),
        name=payload.get("name", "User"),
        picture=payload.get("picture", ""),
        provider=payload.get("provider", "jwt"),
    )


@router.post("/logout")
async def logout(response: Response):
    """Clear session cookie."""
    response.delete_cookie(key="access_token")
    return {"status": "success", "message": "ออกจากระบบเรียบร้อย"}
