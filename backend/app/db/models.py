"""
SARA schema — ผู้ช่วยสรุปการประชุมส่วนบุคคล

    User ─┬─ Collection ── (หลาย) Meeting
          └─ Meeting ─┬─ TranscriptSegment
                      └─ ActionItem

ข้อมูลทุกแถวต้องสืบกลับไปหา user_id ได้ เพราะ API กรองสิทธิ์ด้วย user_id อย่างเดียว
Meeting และ ActionItem จึงเก็บ user_id ซ้ำไว้ตรง ๆ เพื่อให้ query สิทธิ์ไม่ต้อง join

สถานะเก็บเป็น String ไม่ใช่ Enum ของ DB เพื่อให้ค่าตรงกับฝั่ง frontend
และไม่ต้องทำ migration ทุกครั้งที่เพิ่มสถานะใหม่
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.session import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MeetingStatus:
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


# ── ผู้ใช้ ──────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "app_user"  # "user" เป็นคำสงวนของ PostgreSQL

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email = Column(String, nullable=False, unique=True, index=True)
    name = Column(String, default="")
    picture = Column(String, default="")
    provider = Column(String, default="google")  # google | demo
    google_sub = Column(String, nullable=True, unique=True)
    created_at = Column(DateTime, default=_now)
    last_login_at = Column(DateTime, default=_now)


class Collection(Base):
    """โฟลเดอร์ของผู้ใช้ เช่น "ทีม Marketing" — ถาม-ตอบและติดตามงานค้างทำในขอบเขตนี้"""

    __tablename__ = "collection"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    default_template = Column(String, default="general")
    created_at = Column(DateTime, default=_now)


# ── การประชุม ───────────────────────────────────────────────────────────

class Meeting(Base):
    __tablename__ = "meeting"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True)
    collection_id = Column(UUID(as_uuid=True), ForeignKey("collection.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, default="")
    meeting_date = Column(Date, nullable=True)
    template = Column(String, default="general")
    source_kind = Column(String, default="audio")  # audio | transcript
    source_filename = Column(String, default="")
    file_uri = Column(String, nullable=True)
    status = Column(String, default=MeetingStatus.PROCESSING, index=True)
    # [{stage, state, detail, error}] ให้หน้าจอแสดงความคืบหน้าทีละขั้น
    pipeline = Column(JSONB, default=list)
    # ใช้หาการประชุมที่ค้าง processing นานผิดปกติ และกันงานที่ทำ worker ล่มซ้ำ ๆ วนไม่จบ
    processing_started_at = Column(DateTime, nullable=True)
    processing_attempts = Column(Integer, default=0)
    summary = Column(Text, default="")
    key_points = Column(JSONB, default=list)
    # ฟิลด์เฉพาะของแต่ละ template เช่น kpis, blockers, budget_allocation
    details = Column(JSONB, default=dict)
    created_at = Column(DateTime, default=_now)


class TranscriptSegment(Base):
    __tablename__ = "transcript_segment"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meeting.id", ondelete="CASCADE"), nullable=False, index=True)
    speaker_label = Column(String, default="SPEAKER_00")
    # ชื่อที่ผู้ใช้ตั้งให้ speaker_label นี้ในการประชุมนี้ (ไม่มีทะเบียนบุคคลกลาง)
    speaker_name = Column(String, default="")
    start_ms = Column(Integer, default=0)
    end_ms = Column(Integer, default=0)
    text = Column(Text, nullable=False)
    confidence = Column(Float, default=1.0)


class ActionItem(Base):
    __tablename__ = "action_item"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meeting.id", ondelete="CASCADE"), nullable=False, index=True)
    collection_id = Column(UUID(as_uuid=True), ForeignKey("collection.id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    owner = Column(String, default="")
    due_date = Column(Date, nullable=True)
    done = Column(Boolean, default=False, index=True)
    done_at = Column(DateTime, nullable=True)
    source_segment_id = Column(UUID(as_uuid=True), ForeignKey("transcript_segment.id", ondelete="SET NULL"), nullable=True)
    # ข้อเสนอจากการประชุมครั้งถัดมาว่างานนี้น่าจะเสร็จแล้ว — ผู้ใช้เป็นคนกดยืนยันเอง
    suggested_done_meeting_id = Column(UUID(as_uuid=True), ForeignKey("meeting.id", ondelete="SET NULL"), nullable=True)
    suggested_done_evidence = Column(Text, default="")
    created_at = Column(DateTime, default=_now)


class QaLog(Base):
    """ประวัติถาม-ตอบของ collection ให้ผู้ใช้ย้อนดูได้"""

    __tablename__ = "qa_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True)
    collection_id = Column(UUID(as_uuid=True), ForeignKey("collection.id", ondelete="CASCADE"), nullable=False, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, default="")
    citations = Column(JSONB, default=list)
    asked_at = Column(DateTime, default=_now)
