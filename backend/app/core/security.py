"""
Session JWT และการตรวจ Google ID token

⚠ ห้ามเพิ่มทางลัดที่ข้ามการตรวจลายเซ็นของ Google (mock token, ถอด payload เอง ฯลฯ)
   ถ้าต้องการ login ตอนพัฒนา ให้ใช้ /auth/demo ซึ่งถูกปิดอัตโนมัติเมื่อ ENV=prod
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import settings

JWT_ALGORITHM = "HS256"
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


class InvalidGoogleToken(ValueError):
    pass


def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(hours=settings.SESSION_EXPIRE_HOURS),
    }
    return jwt.encode(payload, settings.APP_SECRET_KEY, algorithm=JWT_ALGORITHM)


def read_access_token(token: str) -> str | None:
    """คืน user id ถ้า token ถูกต้องและยังไม่หมดอายุ"""
    try:
        payload = jwt.decode(
            token, settings.APP_SECRET_KEY, algorithms=[JWT_ALGORITHM], options={"require": ["sub", "exp"]}
        )
    except jwt.PyJWTError:
        return None
    return str(payload["sub"])


def verify_google_token(token: str) -> dict:
    """ตรวจลายเซ็น, audience (GOOGLE_CLIENT_ID ของเราเท่านั้น), issuer และอีเมลที่ยืนยันแล้ว"""
    if not settings.GOOGLE_CLIENT_ID:
        raise InvalidGoogleToken("เซิร์ฟเวอร์ยังไม่ได้ตั้ง GOOGLE_CLIENT_ID")
    if not token or not token.strip():
        raise InvalidGoogleToken("ไม่ได้ส่ง Google ID token มา")

    try:
        info = google_id_token.verify_oauth2_token(
            token, google_requests.Request(), settings.GOOGLE_CLIENT_ID
        )
    except ValueError as err:
        raise InvalidGoogleToken(str(err)) from err

    if info.get("iss") not in GOOGLE_ISSUERS:
        raise InvalidGoogleToken("issuer ไม่ใช่ Google")
    if not info.get("email") or not info.get("email_verified"):
        raise InvalidGoogleToken("บัญชี Google นี้ยังไม่ได้ยืนยันอีเมล")
    return info
