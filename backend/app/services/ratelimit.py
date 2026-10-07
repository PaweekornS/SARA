"""
โควตาแบบ fixed window เก็บใน Redis — ใช้ร่วมกันได้ทุก worker และไม่หายเมื่อ restart

ถ้า Redis ล่ม ระบบยอมให้ผ่าน (fail open) แล้ว log เตือน
เพราะโควตามีไว้กันการใช้ผิดวัตถุประสงค์ ไม่ใช่ตัวกันความปลอดภัยหลัก
"""

from __future__ import annotations

import logging
import time

import redis
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None


def _redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2, socket_connect_timeout=2)
    return _client


def consume(key: str, cost: int, limit: int, window_seconds: int) -> bool:
    """หักโควตา `cost` หน่วย คืน False ถ้าเกิน `limit` ในช่วงเวลานี้ (และไม่หักให้)"""
    bucket = f"ratelimit:{key}:{int(time.time()) // window_seconds}"
    try:
        client = _redis()
        used = client.incrby(bucket, cost)
        if used == cost:
            client.expire(bucket, window_seconds)
        if used > limit:
            client.decrby(bucket, cost)
            return False
        return True
    except redis.RedisError as err:
        logger.warning("ตรวจโควตาไม่ได้เพราะ Redis มีปัญหา ปล่อยผ่าน: %s", err)
        return True


def enforce(key: str, cost: int, limit: int, window_seconds: int, message: str) -> None:
    if not consume(key, cost, limit, window_seconds):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=message)
