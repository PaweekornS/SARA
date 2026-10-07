/**
 * รูปร่างข้อมูลจาก backend — ตรงกับ backend/app/schemas.py ทีละฟิลด์
 * ถ้าแก้ schema ฝั่ง backend ต้องแก้ไฟล์นี้ตาม
 */

export type Uuid = string;

export type TemplateId = "general" | "marketing" | "finance" | "tech_standup";

export interface TemplateInfo {
  id: TemplateId;
  name: string;
  description: string;
  detail_labels: Record<string, string>;
}

export interface User {
  id: Uuid;
  email: string;
  name: string;
  picture: string;
  provider: string;
}

export interface Collection {
  id: Uuid;
  name: string;
  description: string;
  default_template: TemplateId;
  created_at: string;
  meeting_count: number;
  open_action_count: number;
}

export type MeetingStatus = "processing" | "ready" | "failed";
export type PipelineStage = "upload" | "asr" | "summarize" | "index" | "followup" | "done";
export type StageState = "pending" | "running" | "ok" | "failed" | "skipped";

export interface PipelineStep {
  stage: PipelineStage;
  state: StageState;
  detail?: string;
  error?: string;
}

export interface Meeting {
  id: Uuid;
  collection_id: Uuid;
  title: string;
  meeting_date: string | null;
  template: TemplateId;
  source_kind: "audio" | "transcript";
  source_filename: string;
  status: MeetingStatus;
  pipeline: PipelineStep[];
  summary: string;
  key_points: string[];
  /** ฟิลด์เฉพาะของ template เช่น kpis, blockers — ชื่อหัวข้อดูจาก TemplateInfo.detail_labels */
  details: Record<string, unknown>;
  created_at: string;
}

export interface Segment {
  id: Uuid;
  speaker_label: string;
  speaker_name: string;
  start_ms: number;
  end_ms: number;
  text: string;
  confidence: number;
}

export interface ActionItem {
  id: Uuid;
  meeting_id: Uuid;
  collection_id: Uuid;
  text: string;
  owner: string;
  due_date: string | null;
  done: boolean;
  done_at: string | null;
  source_segment_id: Uuid | null;
  /** มีค่าเมื่อการประชุมครั้งหลังพูดถึงว่างานนี้น่าจะเสร็จแล้ว — รอผู้ใช้ยืนยัน */
  suggested_done_meeting_id: Uuid | null;
  suggested_done_evidence: string;
  created_at: string;
}

export interface Citation {
  kind: "summary" | "action_item" | "transcript";
  source: "vector" | "lexical";
  meeting_id: Uuid;
  meeting_label: string;
  segment_id: Uuid | null;
  start_ms: number | null;
  quote: string;
}

export interface QaEntry {
  id: Uuid;
  question: string;
  answer: string;
  citations: Citation[];
  asked_at: string;
}

export interface EmailResult {
  sent: string[];
  failed: string[];
}
