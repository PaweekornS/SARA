"""
Pydantic DTO — ชื่อฟิลด์ตรงกับ frontend/lib/types.ts แบบ 1:1
ตั้งใจไม่แปลงเป็น camelCase เพื่อให้ตาราง SQL, API และหน้าจอใช้คำเดียวกันทั้งระบบ
"""

from datetime import date, datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

#  TimelineEntry มีฟิลด์ชื่อ "date" ซึ่งบังชื่อ type date ในขอบเขตของคลาส
#  จน pydantic ตีความ annotation เพี้ยนไปเป็น None เท่านั้น — ใช้ชื่อสำรองแทน
DateOnly = date


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── องค์กร / บุคคล ──────────────────────────────────────────────────────

class OrganizationOut(ORMModel):
    id: UUID
    name: str


class PersonIn(BaseModel):
    full_name: str
    position: str = ""
    department: str = ""
    email: str = ""
    is_active: bool = True
    is_department: bool = False


class PersonOut(ORMModel):
    id: UUID
    org_id: UUID
    full_name: str
    position: str = ""
    department: str = ""
    email: str = ""
    is_active: bool = True
    is_department: bool = False


class AliasIn(BaseModel):
    person_id: UUID
    alias: str
    source: str = "manual"
    confidence: float = 1.0


class AliasOut(ORMModel):
    id: UUID
    person_id: UUID
    alias: str
    source: str
    confidence: float
    created_at: datetime


# ── ชุดการประชุม ────────────────────────────────────────────────────────

class SeriesIn(BaseModel):
    name: str
    committee_type: str = ""
    fiscal_year: int
    agenda_template_id: str = "tpl-official-th"
    cadence: str = "monthly"
    next_meeting_date: Optional[date] = None
    member_ids: list[UUID] = Field(default_factory=list)


class SeriesPatch(BaseModel):
    name: Optional[str] = None
    committee_type: Optional[str] = None
    fiscal_year: Optional[int] = None
    cadence: Optional[str] = None
    next_meeting_date: Optional[date] = None
    member_ids: Optional[list[UUID]] = None


class SeriesOut(ORMModel):
    id: UUID
    org_id: UUID
    name: str
    committee_type: str = ""
    fiscal_year: int
    agenda_template_id: str
    cadence: str
    next_meeting_date: Optional[date] = None
    member_ids: list[UUID] = Field(default_factory=list)


# ── การประชุม ───────────────────────────────────────────────────────────

class PipelineStep(BaseModel):
    stage: Literal["upload", "asr", "diarize", "extract", "done"]
    state: Literal["pending", "running", "ok", "failed"]
    detail: Optional[str] = None
    error: Optional[str] = None


class MeetingIn(BaseModel):
    series_id: UUID
    sequence_no: int
    meeting_date: date
    title: str = ""
    source_kind: str = "audio"


class MeetingOut(ORMModel):
    id: UUID
    series_id: UUID
    sequence_no: int
    fiscal_year: int
    meeting_date: date
    title: str = ""
    audio_uri: Optional[str] = None
    source_kind: str
    status: str
    pipeline: list[PipelineStep] = Field(default_factory=list)
    created_at: datetime
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None


class SegmentOut(ORMModel):
    id: UUID
    meeting_id: UUID
    speaker_label: str
    person_id: Optional[UUID] = None
    start_ms: int
    end_ms: int
    text: str
    confidence: float


class SpeakerPatch(BaseModel):
    speaker_label: str
    person_id: Optional[UUID] = None
    #  FR-M3-04 ยืนยันครั้งแรก → ระบบจำเป็น alias ถาวร
    save_alias: Optional[str] = None


# ── มติ ─────────────────────────────────────────────────────────────────

class ResolutionOut(ORMModel):
    id: UUID
    series_id: UUID
    ref_no: str
    origin_meeting_id: Optional[UUID] = None
    origin_segment_id: Optional[UUID] = None
    origin_agenda_item: Optional[str] = None
    text: str
    category: str
    status: str
    proposer_person_id: Optional[UUID] = None
    assignee_ids: list[UUID] = Field(default_factory=list)
    due_date: Optional[date] = None
    original_due_date: Optional[date] = None
    postpone_count: int
    closed_meeting_id: Optional[UUID] = None
    closed_at: Optional[datetime] = None
    superseded_by_id: Optional[UUID] = None
    extraction_confidence: float
    created_at: datetime
    updated_at: datetime


class ResolutionPatch(BaseModel):
    text: Optional[str] = None
    category: Optional[str] = None
    due_date: Optional[date] = None
    assignee_ids: Optional[list[UUID]] = None
    reason: str = "แก้ไขด้วยผู้ใช้"


class StatusChange(BaseModel):
    status: str
    reason: str = ""
    meeting_id: Optional[UUID] = None
    evidence: Optional[str] = None
    evidence_start_ms: Optional[int] = None
    segment_id: Optional[UUID] = None


class LinkOut(ORMModel):
    id: UUID
    resolution_id: UUID
    meeting_id: UUID
    link_type: str
    segment_id: Optional[UUID] = None
    evidence_text: str
    evidence_start_ms: Optional[int] = None
    confidence: float
    created_at: datetime


class HistoryOut(ORMModel):
    id: UUID
    resolution_id: UUID
    field: str
    old_value: str
    new_value: str
    changed_by: str
    changed_at: datetime
    reason: str
    source_meeting_id: Optional[UUID] = None


class ProposalOut(ORMModel):
    id: UUID
    meeting_id: UUID
    kind: str
    resolution_id: Optional[UUID] = None
    proposed_status: Optional[str] = None
    speaker_label: Optional[str] = None
    candidate_person_ids: list[UUID] = Field(default_factory=list)
    title: str
    evidence_text: str
    evidence_start_ms: Optional[int] = None
    segment_id: Optional[UUID] = None
    confidence: float
    decision: str


class ProposalDecision(BaseModel):
    decision: Literal["accepted", "rejected"]
    text: Optional[str] = None
    assignee_ids: Optional[list[UUID]] = None
    due_date: Optional[date] = None
    person_id: Optional[UUID] = None
    save_alias: Optional[str] = None


# ── ระเบียบวาระ ─────────────────────────────────────────────────────────

class AgendaItemOut(ORMModel):
    id: UUID
    agenda_draft_id: UUID
    section_no: int
    item_no: int
    title: str
    body: str
    resolution_id: Optional[UUID] = None
    sort_order: int


class AgendaItemIn(BaseModel):
    id: Optional[UUID] = None
    section_no: int
    item_no: int = 1
    title: str = ""
    body: str = ""
    resolution_id: Optional[UUID] = None
    sort_order: int = 0


class AgendaItemsPatch(BaseModel):
    items: list[AgendaItemIn]


class AgendaOut(ORMModel):
    id: UUID
    series_id: UUID
    target_meeting_date: Optional[date] = None
    target_sequence_no: int
    status: str
    created_at: datetime
    items: list[AgendaItemOut] = Field(default_factory=list)


# ── การส่งออก ───────────────────────────────────────────────────────────

class ActionOut(ORMModel):
    id: UUID
    series_id: Optional[UUID] = None
    meeting_id: Optional[UUID] = None
    resolution_id: Optional[UUID] = None
    action_type: str
    recipient_person_id: Optional[UUID] = None
    subject: str
    body: str
    scheduled_for: Optional[datetime] = None
    status: str
    approved_by: Optional[str] = None
    sent_at: Optional[datetime] = None
    error: Optional[str] = None
    created_at: datetime


class AuditOut(ORMModel):
    id: UUID
    org_id: Optional[UUID] = None
    actor: str
    action: str
    entity_type: str
    entity_id: str
    metadata: str = Field(validation_alias="meta", serialization_alias="metadata")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# ── Q&A ─────────────────────────────────────────────────────────────────

class Citation(BaseModel):
    meeting_id: Optional[UUID] = None
    segment_id: Optional[UUID] = None
    resolution_id: Optional[UUID] = None
    start_ms: Optional[int] = None
    quote: str


class TimelineEntry(BaseModel):
    meeting_id: Optional[UUID] = None
    date: Optional[DateOnly] = None
    label: str
    detail: str


class Question(BaseModel):
    question: str


class QaAnswerOut(ORMModel):
    id: UUID
    question: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    timeline: list[TimelineEntry] = Field(default_factory=list)
    source: str
    asked_at: datetime


# ── สรุปสำหรับแดชบอร์ด ──────────────────────────────────────────────────

class SeriesStats(BaseModel):
    total: int
    open: int
    done: int
    overdue: int
    flagged: int
    closure_rate: int
    avg_days_to_close: int


class AssigneeLoad(BaseModel):
    person_id: UUID
    name: str
    open: int
    overdue: int


class DashboardOut(BaseModel):
    stats: SeriesStats
    status_counts: dict[str, int]
    overdue: list[ResolutionOut]
    flagged: list[ResolutionOut]
    load: list[AssigneeLoad]


# ── ก้อนข้อมูลทั้งองค์กรสำหรับ frontend ─────────────────────────────────

class Bootstrap(BaseModel):
    """
    ชุดข้อมูลทั้งหมดของ org ในรูปเดียวกับ Database ใน frontend/lib/types.ts
    ระบบขนาด pilot มีข้อมูลไม่กี่พันแถว การส่งทีเดียวจึงถูกกว่าการทำ pagination
    ทุกหน้าจอ — ถ้าโตกว่านี้ค่อยแตกเป็น endpoint ย่อยตาม §6
    """

    org: OrganizationOut
    people: list[PersonOut]
    aliases: list[AliasOut]
    series: list[SeriesOut]
    meetings: list[MeetingOut]
    segments: list[SegmentOut]
    resolutions: list[ResolutionOut]
    links: list[LinkOut]
    history: list[HistoryOut]
    proposals: list[ProposalOut]
    agendas: list[AgendaOut]
    actions: list[ActionOut]
    audit: list[AuditOut]
    qa: dict[str, list[QaAnswerOut]] = Field(default_factory=dict)


class UploadAccepted(BaseModel):
    meeting_id: UUID
    status: str
    message: str


class Ack(BaseModel):
    ok: bool = True
    detail: str = ""
    data: Optional[Any] = None
