/**
 * SARA v2 domain model — โครงสร้างตรงกับ §5 Data model ใน SARA_v2_Requirements.md
 * ตั้งใจให้ชื่อฟิลด์ตรงกับ SQL schema เพื่อให้สลับจาก mock ไป API จริงได้โดยไม่ต้อง map
 */

export type Uuid = string;

/* ── Organization / Person ────────────────────────────────────────────── */

export interface Organization {
  id: Uuid;
  name: string;
}

export interface PersonAlias {
  id: Uuid;
  person_id: Uuid;
  alias: string;
  source: "manual" | "confirmed_extraction" | "imported";
  confidence: number;
  created_at: string;
}

export interface Person {
  id: Uuid;
  org_id: Uuid;
  full_name: string;
  position: string;
  department: string;
  email: string;
  is_active: boolean;
  /** FR-M3-05: ผู้รับผิดชอบที่เป็น "หน่วยงาน" ไม่ใช่บุคคล */
  is_department: boolean;
}

/* ── Meeting series / Meeting ─────────────────────────────────────────── */

export type Cadence = "monthly" | "quarterly" | "biannual" | "adhoc";

export interface MeetingSeries {
  id: Uuid;
  org_id: Uuid;
  name: string;
  committee_type: string;
  fiscal_year: number;
  agenda_template_id: string;
  cadence: Cadence;
  next_meeting_date: string | null;
  /** FR-M1-04 กรรมการประจำ series */
  member_ids: Uuid[];
}

export type MeetingStatus =
  | "draft"
  | "processing"
  | "failed"
  | "reviewed"
  | "approved"
  | "distributed";

/** FR-M2-03 ขั้นตอนของ background job */
export type PipelineStage = "upload" | "asr" | "diarize" | "extract" | "done";
export type StageState = "pending" | "running" | "ok" | "failed";

export interface PipelineStep {
  stage: PipelineStage;
  state: StageState;
  detail?: string;
  /** ข้อความ error จริง — FR-M2-04 ห้ามกลบด้วยข้อมูลปลอม */
  error?: string;
}

export interface Meeting {
  id: Uuid;
  series_id: Uuid;
  sequence_no: number;
  fiscal_year: number;
  meeting_date: string;
  title: string;
  audio_uri: string | null;
  source_kind: "audio" | "transcript";
  status: MeetingStatus;
  pipeline: PipelineStep[];
  created_at: string;
  approved_at?: string | null;
  approved_by?: string | null;
}

export interface TranscriptSegment {
  id: Uuid;
  meeting_id: Uuid;
  speaker_label: string;
  person_id: Uuid | null;
  start_ms: number;
  end_ms: number;
  text: string;
  confidence: number;
}

/* ── Resolution — entity แกนกลางของ v2 ────────────────────────────────── */

export type ResolutionStatus =
  | "proposed"
  | "confirmed"
  | "in_progress"
  | "blocked"
  | "done"
  | "cancelled"
  | "superseded";

export type ResolutionCategory =
  | "procurement"
  | "policy"
  | "personnel"
  | "budget"
  | "operations"
  | "other";

export interface Resolution {
  id: Uuid;
  /** ⚠ series_id ไม่ใช่ meeting_id — มติอยู่ระดับ Series (§5.2) */
  series_id: Uuid;
  ref_no: string;
  origin_meeting_id: Uuid;
  origin_segment_id: Uuid | null;
  origin_agenda_item?: string;
  text: string;
  category: ResolutionCategory;
  status: ResolutionStatus;
  proposer_person_id: Uuid | null;
  assignee_ids: Uuid[];
  due_date: string | null;
  original_due_date: string | null;
  postpone_count: number;
  closed_meeting_id: Uuid | null;
  closed_at: string | null;
  superseded_by_id: Uuid | null;
  created_at: string;
  updated_at: string;
  /** FR-M9-05 จุดที่ AI ไม่มั่นใจ ให้คนตรวจโฟกัสถูกที่ */
  extraction_confidence: number;
}

export type LinkType =
  | "created"
  | "referenced"
  | "progress_reported"
  | "closed"
  | "superseded";

export interface ResolutionLink {
  id: Uuid;
  resolution_id: Uuid;
  meeting_id: Uuid;
  link_type: LinkType;
  segment_id: Uuid | null;
  /** หลักฐานคำต่อคำ — §5.2 ห้ามตัดทิ้ง */
  evidence_text: string;
  evidence_start_ms: number | null;
  confidence: number;
  created_at: string;
}

export interface ResolutionHistory {
  id: Uuid;
  resolution_id: Uuid;
  field: string;
  old_value: string;
  new_value: string;
  changed_by: string;
  changed_at: string;
  reason: string;
  source_meeting_id?: Uuid | null;
}

/* ── ข้อเสนอจากระบบที่รอมนุษย์ยืนยัน (FR-M4-05/06, FR-M3-03) ──────────── */

export type ProposalKind =
  | "status_change"
  | "new_resolution"
  | "speaker_identity"
  | "supersede";

export interface Proposal {
  id: Uuid;
  meeting_id: Uuid;
  kind: ProposalKind;
  resolution_id: Uuid | null;
  /** สถานะที่ระบบ "เสนอ" — ปิดเองไม่ได้เด็ดขาด (FR-M4-06) */
  proposed_status?: ResolutionStatus;
  proposed_person_id?: Uuid | null;
  speaker_label?: string;
  candidate_person_ids?: Uuid[];
  title: string;
  evidence_text: string;
  evidence_start_ms: number | null;
  segment_id: Uuid | null;
  confidence: number;
  decision: "pending" | "accepted" | "rejected";
}

/* ── Agenda ───────────────────────────────────────────────────────────── */

export interface AgendaItem {
  id: Uuid;
  agenda_draft_id: Uuid;
  section_no: 1 | 2 | 3 | 4 | 5;
  item_no: number;
  title: string;
  body: string;
  resolution_id: Uuid | null;
  sort_order: number;
}

export interface AgendaDraft {
  id: Uuid;
  series_id: Uuid;
  target_meeting_date: string;
  target_sequence_no: number;
  status: "draft" | "finalized";
  created_at: string;
  items: AgendaItem[];
}

/* ── Outbound actions (MCP layer) ─────────────────────────────────────── */

export type ActionType =
  | "send_meeting_summary_email"
  | "send_resolution_reminder"
  | "send_agenda_preview"
  | "create_jira_issue";

export interface OutboundAction {
  id: Uuid;
  series_id: Uuid;
  meeting_id: Uuid | null;
  resolution_id: Uuid | null;
  action_type: ActionType;
  recipient_person_id: Uuid | null;
  subject: string;
  body: string;
  /** FR-M7-06 trigger ตามเวลา */
  scheduled_for: string | null;
  status: "pending_approval" | "approved" | "sent" | "failed" | "cancelled";
  approved_by: string | null;
  sent_at: string | null;
  error: string | null;
  created_at: string;
}

/* ── Q&A ──────────────────────────────────────────────────────────────── */

export interface Citation {
  meeting_id: Uuid;
  segment_id: Uuid | null;
  resolution_id: Uuid | null;
  start_ms: number | null;
  quote: string;
}

export interface QaTimelineEntry {
  meeting_id: Uuid;
  date: string;
  label: string;
  detail: string;
}

export interface QaAnswer {
  id: Uuid;
  question: string;
  answer: string;
  /** FR-M8-02 ทุกคำตอบต้องอ้างอิงกลับได้เสมอ */
  citations: Citation[];
  /** FR-M8-03 คำถามเชิงมติ ตอบเป็น timeline */
  timeline: QaTimelineEntry[];
  source: "resolution_table" | "semantic_search";
  asked_at: string;
}

/* ── Audit ────────────────────────────────────────────────────────────── */

export interface AuditEntry {
  id: Uuid;
  org_id: Uuid;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: Uuid;
  metadata: string;
  created_at: string;
}

export interface Database {
  org: Organization;
  people: Person[];
  aliases: PersonAlias[];
  series: MeetingSeries[];
  meetings: Meeting[];
  segments: TranscriptSegment[];
  resolutions: Resolution[];
  links: ResolutionLink[];
  history: ResolutionHistory[];
  proposals: Proposal[];
  agendas: AgendaDraft[];
  actions: OutboundAction[];
  audit: AuditEntry[];
  qa: Record<Uuid, QaAnswer[]>;
}
