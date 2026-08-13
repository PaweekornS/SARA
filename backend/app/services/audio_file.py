"""M2 — หาไฟล์เสียงต้นฉบับของการประชุมอย่างปลอดภัย

แยกเป็นฟังก์ชันบริสุทธิ์ ไม่พึ่ง settings หรือ DB เพื่อให้ทดสอบได้ด้วย unittest
แนวเดียวกับ tests/test_domain.py
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

# เดาชนิดไฟล์จากนามสกุล ถ้าเดาไม่ได้ปล่อยเป็นสตรีมไบต์ทั่วไป
DEFAULT_MEDIA_TYPE = "application/octet-stream"


def resolve_audio_path(audio_uri: str | None, upload_dir: str) -> Path | None:
    """คืน path จริงของไฟล์เสียง หรือ None ถ้าชี้ออกนอก upload_dir หรือไม่มีไฟล์

    ต้องตรวจว่า path อยู่ใน upload_dir จริง กัน `..` ชี้ออกไปอ่านไฟล์อื่นในเครื่อง
    ตอนอัปโหลดระบบสร้างชื่อไฟล์เอง แต่ค่า audio_uri ใน DB แก้ได้ จึงไม่ควรเชื่อ
    """
    if not audio_uri:
        return None

    root = Path(upload_dir).resolve()
    try:
        path = Path(audio_uri).resolve()
    except OSError:
        # ชื่อไฟล์ที่ OS ปฏิเสธ เช่นยาวเกินหรือมีอักขระต้องห้าม
        return None

    if not path.is_relative_to(root):
        return None
    if not path.is_file():
        return None
    return path


def audio_media_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or DEFAULT_MEDIA_TYPE
