"""
SARA v2 schema — ตรงกับ §5 ของ business-docs/SARA_v2_Requirements.md

จุดที่ห้ามออกแบบผิด (§5.2):
  * resolution.series_id ไม่ใช่ meeting_id — มติอยู่ระดับ Series นี่คือสิ่งที่ทำให้ระบบ "จำ" ได้
  * resolution_link เป็น many-to-many ระหว่าง Resolution กับ Meeting
  * evidence_text + segment_id ใน link คือสิ่งที่ทำให้ตรวจสอบย้อนกลับได้ ห้ามตัดทิ้ง

สถานะทั้งหมดเก็บเป็น String ไม่ใช่ Enum ของ DB เพื่อให้ค่าตรงกับฝั่ง frontend เป๊ะ ๆ
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
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.session import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── ค่าคงที่ของสถานะ ────────────────────────────────────────────────────

class MeetingStatus:
    DRAFT = "draft"
    PROCESSING = "processing"
    FAILED = "failed"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    DISTRIBUTED = "distributed"


class ResolutionStatus:
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"

    OPEN = (CONFIRMED, IN_PROGRESS, BLOCKED)

    #  §4.1 state machine — ระบบเปลี่ยนเองได้เฉพาะ proposed → confirmed
    TRANSITIONS = {
        PROPOSED: (CONFIRMED, CANCELLED),
        CONFIRMED: (IN_PROGRESS, BLOCKED, DONE, CANCELLED, SUPERSEDED),
        IN_PROGRESS: (BLOCKED, DONE, CANCELLED),
        BLOCKED: (IN_PROGRESS, DONE, CANCELLED),
        DONE: (IN_PROGRESS,),
        CANCELLED: (CONFIRMED,),
        SUPERSEDED: (),
    }


class LinkType:
    CREATED = "created"
    REFERENCED = "referenced"
    PROGRESS_REPORTED = "progress_reported"
    CLOSED = "closed"
    SUPERSEDED = "superseded"


class ActionStatus:
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ── องค์กรและบุคคล ──────────────────────────────────────────────────────

class Organization(Base):
    __tablename__ = "organization"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=_now)


class Person(Base):
    __tablename__ = "person"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name = Column(String, nullable=False)
    position = Column(String, default="")
    department = Column(String, default="")
    email = Column(String, default="")
    is_active = Column(Boolean, default=True)
    # FR-M3-05 ผู้รับผิดชอบที่เป็น "หน่วยงาน" ไม่ใช่บุคคล เช่น "ฝ่ายพัสดุ"
    is_department = Column(Boolean, default=False)

    aliases = relationship("PersonAlias", back_populates="person", cascade="all, delete-orphan")


class PersonAlias(Base):
    """ชื่อเล่น/คำเรียกที่ map ไปหา Person — หัวใจของ entity resolution ชื่อคนไทย"""

    __tablename__ = "person_alias"
    __table_args__ = (UniqueConstraint("person_id", "alias", name="uq_person_alias"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    person_id = Column(UUID(as_uuid=True), ForeignKey("person.id", ondelete="CASCADE"), nullable=False, index=True)
    alias = Column(String, nullable=False, index=True)
    source = Column(String, default="manual")  # manual | confirmed_extraction | imported
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=_now)

    person = relationship("Person", back_populates="aliases")


# ── ชุดการประชุมและการประชุม ────────────────────────────────────────────

class MeetingSeries(Base):
    __tablename__ = "meeting_series"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    committee_type = Column(String, default="")
    fiscal_year = Column(Integer, nullable=False)
    agenda_template_id = Column(String, default="tpl-official-th")
    cadence = Column(String, default="monthly")  # monthly | quarterly | biannual | adhoc
    next_meeting_date = Column(Date, nullable=True)
    member_ids = Column(JSONB, default=list)
    created_at = Column(DateTime, default=_now)

    meetings = relationship("Meeting", back_populates="series", cascade="all, delete-orphan")
    resolutions = relationship("Resolution", back_populates="series", cascade="all, delete-orphan")


class Meeting(Base):
    __tablename__ = "meeting"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    series_id = Column(UUID(as_uuid=True), ForeignKey("meeting_series.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence_no = Column(Integer, nullable=False)
    fiscal_year = Column(Integer, nullable=False)
    meeting_date = Column(Date, nullable=False)
    title = Column(String, default="")
    summary = Column(Text, default="")
    audio_uri = Column(String, nullable=True)
    source_kind = Column(String, default="audio")  # audio | transcript
    status = Column(String, default=MeetingStatus.PROCESSING, index=True)
    # FR-M2-03 สถานะเป็นขั้น: upload → asr → diarize → extract → done
    pipeline = Column(JSONB, default=list)
    created_at = Column(DateTime, default=_now)
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(String, nullable=True)

    series = relationship("MeetingSeries", back_populates="meetings")
    segments = relationship("TranscriptSegment", back_populates="meeting", cascade="all, delete-orphan")


class TranscriptSegment(Base):
    """ท่อนคำพูด 1 ท่อน — เก็บ timestamp ไว้เพื่ออ้างอิงหลักฐานของมติได้ (FR-M2-08)"""

    __tablename__ = "transcript_segment"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meeting.id", ondelete="CASCADE"), nullable=False, index=True)
    speaker_label = Column(String, default="SPEAKER_00")
    person_id = Column(UUID(as_uuid=True), ForeignKey("person.id", ondelete="SET NULL"), nullable=True)
    start_ms = Column(Integer, default=0)
    end_ms = Column(Integer, default=0)
    text = Column(Text, nullable=False)
    confidence = Column(Float, default=1.0)

    meeting = relationship("Meeting", back_populates="segments")


# ── มติ — entity แกนกลางของ v2 ──────────────────────────────────────────

class Resolution(Base):
    __tablename__ = "resolution"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    # ⚠ ผูกกับ series ไม่ใช่ meeting
    series_id = Column(UUID(as_uuid=True), ForeignKey("meeting_series.id", ondelete="CASCADE"), nullable=False, index=True)
    ref_no = Column(String, default="")
    origin_meeting_id = Column(UUID(as_uuid=True), ForeignKey("meeting.id", ondelete="SET NULL"), nullable=True)
    origin_segment_id = Column(UUID(as_uuid=True), ForeignKey("transcript_segment.id", ondelete="SET NULL"), nullable=True)
    origin_agenda_item = Column(String, nullable=True)
    text = Column(Text, nullable=False)
    category = Column(String, default="other")
    status = Column(String, default=ResolutionStatus.PROPOSED, index=True)
    proposer_person_id = Column(UUID(as_uuid=True), ForeignKey("person.id", ondelete="SET NULL"), nullable=True)
    due_date = Column(Date, nullable=True)
    original_due_date = Column(Date, nullable=True)
    postpone_count = Column(Integer, default=0)
    closed_meeting_id = Column(UUID(as_uuid=True), ForeignKey("meeting.id", ondelete="SET NULL"), nullable=True)
    closed_at = Column(DateTime, nullable=True)
    superseded_by_id = Column(UUID(as_uuid=True), ForeignKey("resolution.id", ondelete="SET NULL"), nullable=True)
    extraction_confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    series = relationship("MeetingSeries", back_populates="resolutions")
    assignees = relationship("ResolutionAssignee", back_populates="resolution", cascade="all, delete-orphan")
    links = relationship("ResolutionLink", back_populates="resolution", cascade="all, delete-orphan")
    history = relationship("ResolutionHistory", back_populates="resolution", cascade="all, delete-orphan")


class ResolutionAssignee(Base):
    __tablename__ = "resolution_assignee"
    __table_args__ = (UniqueConstraint("resolution_id", "person_id", name="uq_resolution_assignee"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    resolution_id = Column(UUID(as_uuid=True), ForeignKey("resolution.id", ondelete="CASCADE"), nullable=False, index=True)
    person_id = Column(UUID(as_uuid=True), ForeignKey("person.id", ondelete="CASCADE"), nullable=False)
    department_name = Column(String, nullable=True)

    resolution = relationship("Resolution", back_populates="assignees")


class ResolutionLink(Base):
    """ความสัมพันธ์ระหว่าง Resolution กับ Meeting — มติหนึ่งข้อถูกพูดถึงได้หลายครั้งข้ามหลายการประชุม"""

    __tablename__ = "resolution_link"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    resolution_id = Column(UUID(as_uuid=True), ForeignKey("resolution.id", ondelete="CASCADE"), nullable=False, index=True)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meeting.id", ondelete="CASCADE"), nullable=False, index=True)
    link_type = Column(String, nullable=False)
    segment_id = Column(UUID(as_uuid=True), ForeignKey("transcript_segment.id", ondelete="SET NULL"), nullable=True)
    # หลักฐานคำต่อคำ — ห้ามตัดทิ้งเพื่อประหยัดเวลา (§5.2)
    evidence_text = Column(Text, default="")
    evidence_start_ms = Column(Integer, nullable=True)
    confidence = Column(Float, default=1.0)
    created_at = Column(DateTime, default=_now)

    resolution = relationship("Resolution", back_populates="links")


class ResolutionHistory(Base):
    __tablename__ = "resolution_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    resolution_id = Column(UUID(as_uuid=True), ForeignKey("resolution.id", ondelete="CASCADE"), nullable=False, index=True)
    field = Column(String, nullable=False)
    old_value = Column(Text, default="")
    new_value = Column(Text, default="")
    changed_by = Column(String, default="")
    changed_at = Column(DateTime, default=_now)
    reason = Column(Text, default="")
    source_meeting_id = Column(UUID(as_uuid=True), ForeignKey("meeting.id", ondelete="SET NULL"), nullable=True)

    resolution = relationship("Resolution", back_populates="history")


class Proposal(Base):
    """
    สิ่งที่ระบบ "เสนอ" หลังประมวลผล รอมนุษย์ยืนยัน (FR-M4-05, 06 · FR-M3-03)
    ไม่มีในตาราง §5 แต่จำเป็น เพราะ requirement บังคับว่าระบบปิดมติเองไม่ได้
    ต้องมีที่เก็บข้อเสนอที่ยังไม่ถูกตัดสิน
    """

    __tablename__ = "proposal"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meeting.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String, nullable=False)  # status_change | new_resolution | speaker_identity | supersede
    resolution_id = Column(UUID(as_uuid=True), ForeignKey("resolution.id", ondelete="CASCADE"), nullable=True)
    proposed_status = Column(String, nullable=True)
    speaker_label = Column(String, nullable=True)
    candidate_person_ids = Column(JSONB, default=list)
    title = Column(Text, default="")
    evidence_text = Column(Text, default="")
    evidence_start_ms = Column(Integer, nullable=True)
    segment_id = Column(UUID(as_uuid=True), ForeignKey("transcript_segment.id", ondelete="SET NULL"), nullable=True)
    confidence = Column(Float, default=0.0)
    decision = Column(String, default="pending")  # pending | accepted | rejected
    created_at = Column(DateTime, default=_now)


# ── ระเบียบวาระ ─────────────────────────────────────────────────────────

class AgendaDraft(Base):
    __tablename__ = "agenda_draft"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    series_id = Column(UUID(as_uuid=True), ForeignKey("meeting_series.id", ondelete="CASCADE"), nullable=False, index=True)
    target_meeting_date = Column(Date, nullable=True)
    target_sequence_no = Column(Integer, default=1)
    status = Column(String, default="draft")  # draft | finalized
    created_at = Column(DateTime, default=_now)

    items = relationship(
        "AgendaItem",
        back_populates="draft",
        cascade="all, delete-orphan",
        order_by="AgendaItem.sort_order",
    )


class AgendaItem(Base):
    __tablename__ = "agenda_item"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    agenda_draft_id = Column(UUID(as_uuid=True), ForeignKey("agenda_draft.id", ondelete="CASCADE"), nullable=False, index=True)
    section_no = Column(Integer, nullable=False)
    item_no = Column(Integer, default=1)
    title = Column(Text, default="")
    body = Column(Text, default="")
    resolution_id = Column(UUID(as_uuid=True), ForeignKey("resolution.id", ondelete="SET NULL"), nullable=True)
    sort_order = Column(Integer, default=0)

    draft = relationship("AgendaDraft", back_populates="items")


# ── การส่งออกและ audit ──────────────────────────────────────────────────

class OutboundAction(Base):
    __tablename__ = "outbound_action"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    series_id = Column(UUID(as_uuid=True), ForeignKey("meeting_series.id", ondelete="CASCADE"), nullable=True, index=True)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meeting.id", ondelete="CASCADE"), nullable=True)
    resolution_id = Column(UUID(as_uuid=True), ForeignKey("resolution.id", ondelete="CASCADE"), nullable=True)
    action_type = Column(String, nullable=False)
    recipient_person_id = Column(UUID(as_uuid=True), ForeignKey("person.id", ondelete="SET NULL"), nullable=True)
    subject = Column(String, default="")
    body = Column(Text, default="")
    payload = Column(JSONB, default=dict)
    scheduled_for = Column(DateTime, nullable=True)
    # FR-M7-07 default = ต้องอนุมัติก่อนส่งเสมอ
    status = Column(String, default=ActionStatus.PENDING_APPROVAL, index=True)
    approved_by = Column(String, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_now)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organization.id", ondelete="CASCADE"), nullable=True, index=True)
    actor = Column(String, default="")
    action = Column(String, nullable=False)
    entity_type = Column(String, default="")
    entity_id = Column(String, default="")
    meta = Column(Text, default="")
    created_at = Column(DateTime, default=_now)


class QaLog(Base):
    """เก็บคำถาม-คำตอบข้าม meeting ไว้ให้ย้อนดูได้ และใช้วัดคุณภาพภายหลัง"""

    __tablename__ = "qa_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    series_id = Column(UUID(as_uuid=True), ForeignKey("meeting_series.id", ondelete="CASCADE"), nullable=False, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, default="")
    source = Column(String, default="resolution_table")
    citations = Column(JSONB, default=list)
    timeline = Column(JSONB, default=list)
    asked_at = Column(DateTime, default=_now)
