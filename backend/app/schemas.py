"""รูปร่างข้อมูลขาเข้า-ขาออกของ API"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Auth ────────────────────────────────────────────────────────────────

class GoogleLoginIn(BaseModel):
    id_token: str


class DemoLoginIn(BaseModel):
    name: str = Field(default="ผู้ใช้ทดลอง", max_length=80)


class UserOut(OrmModel):
    id: UUID
    email: str
    name: str
    picture: str = ""
    provider: str


class AuthOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ── Collection ──────────────────────────────────────────────────────────

class CollectionIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    default_template: str = "general"


class CollectionPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    default_template: str | None = None


class CollectionOut(OrmModel):
    id: UUID
    name: str
    description: str
    default_template: str
    created_at: datetime
    meeting_count: int = 0
    open_action_count: int = 0


# ── Meeting ─────────────────────────────────────────────────────────────

class MeetingPatch(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    meeting_date: date | None = None
    collection_id: UUID | None = None


class MeetingOut(OrmModel):
    id: UUID
    collection_id: UUID
    title: str
    meeting_date: date | None
    template: str
    source_kind: str
    source_filename: str
    status: str
    pipeline: list[dict]
    summary: str
    key_points: list[str]
    details: dict
    created_at: datetime


class SegmentOut(OrmModel):
    id: UUID
    speaker_label: str
    speaker_name: str
    start_ms: int
    end_ms: int
    text: str
    confidence: float


class SpeakerRename(BaseModel):
    speaker_label: str
    speaker_name: str = Field(max_length=80)


# ── Action item ─────────────────────────────────────────────────────────

class ActionItemIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    owner: str = Field(default="", max_length=120)
    due_date: date | None = None


class ActionItemPatch(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=2000)
    owner: str | None = Field(default=None, max_length=120)
    due_date: date | None = None
    done: bool | None = None


class ActionItemOut(OrmModel):
    id: UUID
    meeting_id: UUID
    collection_id: UUID
    text: str
    owner: str
    due_date: date | None
    done: bool
    done_at: datetime | None
    source_segment_id: UUID | None
    suggested_done_meeting_id: UUID | None
    suggested_done_evidence: str
    created_at: datetime


# ── ถาม-ตอบ ─────────────────────────────────────────────────────────────

class Question(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class QaOut(OrmModel):
    id: UUID
    question: str
    answer: str
    citations: list[dict]
    asked_at: datetime


# ── อีเมล ───────────────────────────────────────────────────────────────

class EmailIn(BaseModel):
    recipients: list[EmailStr] = Field(min_length=1)
    subject: str | None = Field(default=None, max_length=200)
    include_action_items: bool = True


class EmailOut(BaseModel):
    sent: list[str]
    failed: list[str]
