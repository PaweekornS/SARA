"""
โทเคนสำหรับ magic link (FR-M7-08)

ผู้รับผิดชอบมติต้องแจ้งสถานะกลับได้โดยไม่ต้องล็อกอิน
โทเคนจึงเซ็นด้วย HMAC-SHA256 (stdlib) ผูกกับ resolution + person + วันหมดอายุ
แก้ค่าใดค่าหนึ่งในลิงก์แล้วลายเซ็นจะไม่ผ่านทันที

ขอบเขตของโทเคนนี้คือ "อัปเดตสถานะมติข้อเดียว" เท่านั้น ไม่ใช่การล็อกอินเข้าระบบ
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from uuid import UUID

from app.core.config import settings


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: bytes) -> str:
    return _b64e(hmac.new(settings.SECRET_KEY.encode(), payload, hashlib.sha256).digest())


def make_magic_token(resolution_id: UUID, person_id: UUID, ttl_days: int | None = None) -> str:
    ttl = ttl_days if ttl_days is not None else settings.MAGIC_LINK_TTL_DAYS
    payload = json.dumps(
        {
            "r": str(resolution_id),
            "p": str(person_id),
            "exp": int(time.time()) + ttl * 86400,
        },
        separators=(",", ":"),
    ).encode()
    return f"{_b64e(payload)}.{_sign(payload)}"


def read_magic_token(token: str) -> dict | None:
    """คืน payload ถ้าลายเซ็นถูกและยังไม่หมดอายุ ไม่งั้นคืน None"""
    try:
        body, signature = token.split(".", 1)
        payload = _b64d(body)
    except (ValueError, TypeError):
        return None

    if not hmac.compare_digest(_sign(payload), signature):
        return None

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None

    if int(data.get("exp", 0)) < time.time():
        return None
    return data


def magic_link_url(resolution_id: UUID, person_id: UUID) -> str:
    #  router ทุกตัวถูก mount ใต้ API_V1_STR — ลิงก์ต้องมี prefix นี้ ไม่งั้นอีเมลพาไป 404
    token = make_magic_token(resolution_id, person_id)
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    return f"{base}{settings.API_V1_STR}/public/resolutions/{token}"
