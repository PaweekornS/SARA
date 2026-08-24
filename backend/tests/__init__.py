"""
ตั้งค่าสภาพแวดล้อมของการทดสอบ — ไฟล์นี้ถูก import ก่อนเคสทุกไฟล์เสมอ

ต้องตั้ง env ให้เสร็จ *ก่อน* ที่ app.core.config จะถูก import
เพราะ Settings อ่านค่าครั้งเดียวตอน import แล้วไม่อ่านซ้ำอีก
ค่าใน os.environ มีลำดับสูงกว่าไฟล์ .env ของ pydantic-settings จึงเขียนทับได้

ฐานข้อมูลสำหรับทดสอบ (ค่าเริ่มต้นชี้ไปคอนเทนเนอร์ที่แยกจากของจริง):

    docker run -d --name sara_test_db -e POSTGRES_PASSWORD=postgrespassword \
        -e POSTGRES_DB=sara_test -p 55432:5432 postgres:15-alpine

เปลี่ยนปลายทางได้ด้วย TEST_DATABASE_URL
"""

import logging
import os

#  log ของ httpx/sqlalchemy กลบผลการทดสอบจนอ่านไม่ออก
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("app").setLevel(logging.CRITICAL)
logging.getLogger("asyncio").setLevel(logging.ERROR)

DEFAULT_TEST_DB = "postgresql+asyncpg://postgres:postgrespassword@127.0.0.1:55432/sara_test"

os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DB)

#  ค่าที่ Settings บังคับให้มี แต่การทดสอบไม่ได้เรียกบริการภายนอกจริงสักตัว
os.environ.setdefault("APP_AI4THAI_API_KEY", "test-key-not-used")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("SECRET_KEY", "test-secret-for-magic-link")
os.environ.setdefault("PUBLIC_BASE_URL", "http://testserver")
os.environ.setdefault("UPLOAD_DIR", os.path.join(os.path.dirname(__file__), ".uploads"))
