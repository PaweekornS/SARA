/**
 * SARA Modernized Seed Dataset (v4.0.0-PROD)
 * Persona: NovaTech Studio & SaaS (High-Growth Product Agency)
 * Specification: Mock_Data_Update.md
 */

import type {
  AuditEntry,
  Database,
  Meeting,
  MeetingSeries,
  Organization,
  Person,
  PersonAlias,
  Resolution,
  ResolutionHistory,
  ResolutionLink,
  TranscriptSegment,
} from "./types";

const ORG_ID = "org-1";
export const DEMO_SERIES_ID = "col-app-launch-2026";
export const SER2 = "col-tech-sprints";

/* ── Team Members (NovaTech Studio) ──────────────────────────────────── */

export const P = {
  phat: "per-phat",
  rin: "per-rin",
  karn: "per-karn",
  mint: "per-mint",
  deptProduct: "dep-product",
  deptDesign: "dep-design",
  deptEngineering: "dep-eng",
  deptMarketing: "dep-mkt",
} as const;

const people: Person[] = [
  {
    id: P.phat,
    org_id: ORG_ID,
    full_name: "ภัทร (Phat)",
    position: "Head of Product / Founder",
    department: "Product & Strategy",
    email: "phat@novatech.io",
    is_active: true,
    is_department: false,
  },
  {
    id: P.rin,
    org_id: ORG_ID,
    full_name: "ริน (Rin)",
    position: "Lead Product Designer / Scrum Lead",
    department: "Design & UX",
    email: "rin@novatech.io",
    is_active: true,
    is_department: false,
  },
  {
    id: P.karn,
    org_id: ORG_ID,
    full_name: "กานต์ (Karn)",
    position: "Lead Software Engineer",
    department: "Engineering",
    email: "karn@novatech.io",
    is_active: true,
    is_department: false,
  },
  {
    id: P.mint,
    org_id: ORG_ID,
    full_name: "มิ้น (Mint)",
    position: "Growth & Marketing Lead",
    department: "Growth & Marketing",
    email: "mint@novatech.io",
    is_active: true,
    is_department: false,
  },
  {
    id: P.deptProduct,
    org_id: ORG_ID,
    full_name: "ทีมบริหารผลิตภัณฑ์ (Product Team)",
    position: "ทีมงาน",
    department: "Product & Strategy",
    email: "product@novatech.io",
    is_active: true,
    is_department: true,
  },
  {
    id: P.deptEngineering,
    org_id: ORG_ID,
    full_name: "ทีมพัฒนาและวิศวกรรม (Engineering Team)",
    position: "ทีมงาน",
    department: "Engineering",
    email: "dev@novatech.io",
    is_active: true,
    is_department: true,
  },
];

const aliases: PersonAlias[] = [
  ["al-1", P.phat, "ภัทร", "confirmed_extraction", 0.98],
  ["al-2", P.phat, "Product Lead", "manual", 1],
  ["al-3", P.rin, "ริน", "confirmed_extraction", 0.96],
  ["al-4", P.rin, "Scrum Lead", "manual", 1],
  ["al-5", P.karn, "กานต์", "confirmed_extraction", 0.97],
  ["al-6", P.karn, "Tech Lead", "manual", 1],
  ["al-7", P.mint, "มิ้น", "confirmed_extraction", 0.95],
  ["al-8", P.mint, "Marketing Lead", "manual", 1],
].map(([id, person_id, alias, source, confidence]) => ({
  id: id as string,
  person_id: person_id as string,
  alias: alias as string,
  source: source as PersonAlias["source"],
  confidence: confidence as number,
  created_at: "2026-07-01T09:00:00",
}));

/* ── Workspace Collections ───────────────────────────────────────────── */

const series: MeetingSeries[] = [
  {
    id: DEMO_SERIES_ID,
    org_id: ORG_ID,
    name: "Alpha App Q3 Launch Campaign",
    committee_type: "Product Launch & Growth",
    fiscal_year: 2026,
    agenda_template_id: "tpl-saas-launch",
    cadence: "weekly",
    next_meeting_date: "2026-08-14",
    member_ids: [P.phat, P.rin, P.karn, P.mint],
  },
  {
    id: SER2,
    org_id: ORG_ID,
    name: "Core Backend & AI Microservices",
    committee_type: "Engineering & Tech Standup",
    fiscal_year: 2026,
    agenda_template_id: "tpl-tech-standup",
    cadence: "bi-weekly",
    next_meeting_date: "2026-08-20",
    member_ids: [P.phat, P.karn, P.rin],
  },
];

/* ── Meeting Sessions ────────────────────────────────────────────────── */

const donePipeline: Meeting["pipeline"] = [
  { stage: "upload", state: "ok" },
  { stage: "asr", state: "ok", detail: "AI4Thai Partii · WER 7.2%" },
  { stage: "extract", state: "ok" },
  { stage: "done", state: "ok" },
];

function heldMeeting(
  id: string,
  seq: number,
  date: string,
  title: string,
  series_id = DEMO_SERIES_ID,
): Meeting {
  return {
    id,
    series_id,
    sequence_no: seq,
    fiscal_year: 2026,
    meeting_date: date,
    title,
    audio_uri: `minio://sara/meetings/${id}.m4a`,
    source_kind: "audio",
    status: "distributed",
    pipeline: donePipeline,
    created_at: `${date}T10:00:00`,
    approved_at: `${date}T11:30:00`,
    approved_by: "ภัทร (Phat)",
  };
}

export const M = {
  m1: "mtg-1",
  m2: "mtg-2",
  m3: "mtg-3",
} as const;

const meetings: Meeting[] = [
  heldMeeting(M.m1, 1, "2026-07-10", "Kickoff: Scope & Budget Allocation"),
  heldMeeting(M.m2, 2, "2026-07-24", "Sprint Review: Beta Readiness & Ad Visuals"),
  heldMeeting(M.m3, 3, "2026-08-07", "Pre-Launch Sync: Blocker Clearance & Pricing"),
  heldMeeting("mtg-tech-1", 1, "2026-07-15", "Sprint 14: AI Gateway & Rate Limiting", SER2),
];

/* ── Transcripts for Meeting #3 ──────────────────────────────────────── */

function seg(
  id: string,
  meeting_id: string,
  speaker_label: string,
  person_id: string | null,
  start_ms: number,
  text: string,
  confidence = 0.96,
): TranscriptSegment {
  return {
    id,
    meeting_id,
    speaker_label,
    person_id,
    start_ms,
    end_ms: start_ms + Math.max(3500, text.length * 100),
    text,
    confidence,
  };
}

const segments: TranscriptSegment[] = [
  seg("s3-01", M.m3, "SPEAKER_01", P.phat, 12_000, "สวัสดีทุกคน วันนี้มาเช็คความพร้อมก่อนเปิด Beta สัปดาห์หน้า เรื่องแรก Payment Gateway ที่ติดสัปดาห์ที่แล้วเป็นยังไงบ้าง กานต์?"),
  seg("s3-02", M.m3, "SPEAKER_03", P.karn, 24_000, "แก้เรียบร้อยแล้วครับ ผู้ให้บริการปลดล็อก Production Key ให้แล้ว เมื่อวานทีมเทสระบบตัดบัตรเครดิตและ PromptPay ผ่านฉลุย ไม่มีปัญหาแล้วครับ", 0.98),
  seg("s3-03", M.m3, "SPEAKER_01", P.phat, 70_000, "ยอดเยี่ยมมาก ถือว่า Blocker ตัวนี้เคลียร์แล้วนะ ถัดมาเรื่องแคมเปญการตลาด มิ้น เตรียม Key Visual ทันไหม?"),
  seg("s3-04", M.m3, "SPEAKER_04", P.mint, 95_000, "สำหรับ Key Visual ชุดแรกพร้อมยิง Ads บน TikTok และ Meta วันจันทร์นี้ค่ะ แต่มีเรื่องขออนุมัติงบเพิ่ม 50,000 บาท สำหรับจ้าง Tech Influencer 2 ช่อง มารีวิวช่วง Early Access ค่ะ", 0.95),
  seg("s3-05", M.m3, "SPEAKER_01", P.phat, 135_000, "งบรวม 500,000 บาทเดิมยังเหลือไหม? ถ้ายังอยู่ใน Cap 5 แสน เกลี่ยจากงบ Google Search Ads มาได้เลย ผมอนุมัติ", 0.97),
  seg("s3-06", M.m3, "SPEAKER_04", P.mint, 160_000, "โอเคค่ะ งั้นสรุปเกลี่ยงบ 50,000 บาทมาจ่าย Influencer โดยคุมยอดรวมไม่เกิน 500k บาท และจะส่งรายงาน Conversion ให้ดูทุกเย็นวันศุกร์ค่ะ", 0.96),
  seg("s3-07", M.m3, "SPEAKER_02", P.rin, 195_000, "หน้า Landing Page สมัคร Early Access ทำเสร็จแล้วนะคะ พร้อมเปิดให้ลงทะเบียนศุกร์นี้ที่ราคา 299 บาท/เดือน ตามมติใหม่", 0.97),
  seg("s3-08", M.m3, "SPEAKER_01", P.phat, 245_000, "ดีมาก สรุป Action Item: มิ้นยิง Ads วันจันทร์, รินเปิดหน้าเว็บวันศุกร์, กานต์สแตนด์บาย Monitor Server ปิดประชุมครับ", 0.98),
];

/* ── Resolutions & Action Items ──────────────────────────────────────── */

function res(r: Partial<Resolution> & Pick<Resolution, "id" | "ref_no" | "text" | "origin_meeting_id" | "status">): Resolution {
  return {
    series_id: DEMO_SERIES_ID,
    origin_segment_id: null,
    category: "operations",
    proposer_person_id: P.phat,
    assignee_ids: [],
    due_date: null,
    original_due_date: null,
    postpone_count: 0,
    closed_meeting_id: null,
    closed_at: null,
    superseded_by_id: null,
    created_at: "2026-07-10T10:00:00",
    updated_at: "2026-08-07T11:00:00",
    extraction_confidence: 0.95,
    ...r,
  } as Resolution;
}

export const R = {
  payment: "act-payment",
  adBudget: "act-ad-budget",
  landingPage: "act-landing-page",
  hotfixIos: "act-hotfix-ios",
} as const;

const resolutions: Resolution[] = [
  /* ── 1. Payment Gateway (Cleared in M3) ── */
  res({
    id: R.payment,
    ref_no: "Action #1 (Tech Architecture)",
    text: "เชื่อมต่อและทดสอบ Payment Gateway ทั้งระบบบัตรเครดิตและ PromptPay ให้พร้อมรับชำระเงินจริงในรอบ Beta Launch",
    category: "operations",
    status: "done",
    origin_meeting_id: M.m1,
    origin_segment_id: "s3-02",
    assignee_ids: [P.karn],
    due_date: "2026-08-05",
    original_due_date: "2026-07-28",
    postpone_count: 1,
    closed_meeting_id: M.m3,
    closed_at: "2026-08-07T10:30:00",
    extraction_confidence: 0.98,
  }),
  /* ── 2. Ad Budget & Influencer Reallocation ── */
  res({
    id: R.adBudget,
    ref_no: "Action #2 (Growth & Marketing)",
    text: "คุมงบยิงโฆษณา Alpha Launch รวมไม่เกิน 500,000 บาท โดยเกลี่ยงบ 50,000 บาทสำหรับ Tech Influencer 2 ช่อง และส่งรายงาน Conversion ทุกวันศุกร์",
    category: "budget",
    status: "in_progress",
    origin_meeting_id: M.m3,
    origin_segment_id: "s3-06",
    assignee_ids: [P.mint],
    due_date: "2026-08-31",
    original_due_date: "2026-08-31",
    extraction_confidence: 0.96,
  }),
  /* ── 3. Early Access Landing Page ── */
  res({
    id: R.landingPage,
    ref_no: "Action #3 (Product & Design)",
    text: "เปิดหน้า Landing Page สำหรับลงทะเบียน Early-bird Subscription ราคาพิเศษ 299 บาท/เดือน ภายในวันศุกร์นี้",
    category: "operations",
    status: "done",
    origin_meeting_id: M.m3,
    origin_segment_id: "s3-07",
    assignee_ids: [P.rin],
    due_date: "2026-08-14",
    original_due_date: "2026-08-14",
    closed_meeting_id: M.m3,
    closed_at: "2026-08-07T11:00:00",
    extraction_confidence: 0.97,
  }),
  /* ── 4. Tech Infrastructure Standup Item ── */
  res({
    id: "act-ai-gateway",
    ref_no: "Action #4 (AI Infra)",
    text: "พัฒนาระบบ AI Gateway และ Cache Proxy สำหรับจัดการ Rate Limiting ของโมเดล LLM ให้เสร็จใน Sprint 14",
    category: "operations",
    status: "done",
    origin_meeting_id: "mtg-tech-1",
    assignee_ids: [P.karn],
    due_date: "2026-07-30",
    original_due_date: "2026-07-30",
    closed_meeting_id: "mtg-tech-1",
    closed_at: "2026-07-30T17:00:00",
    created_at: "2026-07-15T10:00:00",
  }),
];

/* ── Cross-Meeting Links & Citations ──────────────────────────────────── */

function link(
  id: string,
  resolution_id: string,
  meeting_id: string,
  link_type: ResolutionLink["link_type"],
  evidence_text: string,
  created_at: string,
  opts: Partial<ResolutionLink> = {},
): ResolutionLink {
  return {
    id,
    resolution_id,
    meeting_id,
    link_type,
    segment_id: null,
    evidence_text,
    evidence_start_ms: null,
    confidence: 0.95,
    created_at,
    ...opts,
  };
}

const links: ResolutionLink[] = [
  link("lk-1", R.payment, M.m1, "created", "วางแผนเชื่อมต่อ Payment Gateway เพื่อรองรับรอบ Beta", "2026-07-10T10:00:00"),
  link("lk-2", R.payment, M.m2, "progress_reported", "ติดปัญหา Production Key จากผู้ให้บริการ (Blocked)", "2026-07-24T10:30:00", { evidence_start_ms: 120_000 }),
  link("lk-3", R.payment, M.m3, "closed", "ผู้ให้บริการปลดล็อก Production Key ให้แล้ว ทดสอบตัดบัตรและ PromptPay ผ่านฉลุย", "2026-08-07T10:30:00", { segment_id: "s3-02", evidence_start_ms: 24_000, confidence: 0.98 }),
  link("lk-4", R.adBudget, M.m3, "created", "อนุมัติเกลี่ยงบ 50,000 บาทสำหรับจ้าง Influencer โดยคุมยอดรวมไม่เกิน 500k", "2026-08-07T10:45:00", { segment_id: "s3-06", evidence_start_ms: 160_000, confidence: 0.96 }),
  link("lk-5", R.landingPage, M.m3, "created", "หน้า Landing Page สมัคร Early Access พร้อมเปิดวันศุกร์นี้ที่ราคา 299 บาท/เดือน", "2026-08-07T11:00:00", { segment_id: "s3-07", evidence_start_ms: 195_000, confidence: 0.97 }),
];

const history: ResolutionHistory[] = [
  { id: "h-1", resolution_id: R.payment, field: "status", old_value: "in_progress", new_value: "blocked", changed_by: "กานต์ (Karn)", changed_at: "2026-07-24T10:35:00", reason: "รอ Production Key จาก Gateway Provider", source_meeting_id: M.m2 },
  { id: "h-2", resolution_id: R.payment, field: "status", old_value: "blocked", new_value: "done", changed_by: "ภัทร (Phat)", changed_at: "2026-08-07T10:30:00", reason: "ทดสอบผ่านระบบตัดบัตรเครดิตและ PromptPay แล้ว", source_meeting_id: M.m3 },
  { id: "h-3", resolution_id: R.adBudget, field: "due_date", old_value: "2026-08-15", new_value: "2026-08-31", changed_by: "ภัทร (Phat)", changed_at: "2026-08-07T10:45:00", reason: "ขยายเวลารวมช่วง Influencer Review", source_meeting_id: M.m3 },
];

const audit: AuditEntry[] = [
  { id: "au-1", org_id: ORG_ID, actor: "ภัทร (Phat)", action: "approve_meeting", entity_type: "meeting", entity_id: M.m3, metadata: "รับรองรายงานการประชุม Pre-Launch Sync", created_at: "2026-08-07T11:30:00" },
  { id: "au-2", org_id: ORG_ID, actor: "ภัทร (Phat)", action: "confirm_alias", entity_type: "person", entity_id: P.karn, metadata: 'ยืนยัน "Tech Lead" → กานต์ (Karn)', created_at: "2026-08-07T11:05:00" },
];

export function createSeedDatabase(): Database {
  const org: Organization = { id: ORG_ID, name: "NovaTech Studio (Demo Workspace)" };
  return {
    org,
    people,
    aliases,
    series,
    meetings,
    segments,
    resolutions,
    links,
    history,
    proposals: [],
    agendas: [],
    actions: [
      {
        id: "act-1",
        series_id: DEMO_SERIES_ID,
        meeting_id: null,
        resolution_id: R.adBudget,
        action_type: "send_resolution_reminder",
        recipient_person_id: P.mint,
        subject: "แจ้งเตือน Action Item: ส่งรายงาน Conversion & TikTok Ads ทุกเย็นวันศุกร์",
        body:
          "เรียน มิ้น (Growth Lead)\n\nระบบสรุป Action Item จากที่ประชุม Pre-Launch Sync:\n\n" +
          "“คุมงบยิงโฆษณา Alpha Launch รวมไม่เกิน 500,000 บาท โดยเกลี่ยงบ 50,000 บาทสำหรับ Tech Influencer 2 ช่อง และส่งรายงาน Conversion ทุกวันศุกร์”\n\n" +
          "กำหนดส่ง: 31 สิงหาคม 2569\n\nสามารถรายงานผลหรืออัปเดตผ่านระบบ SARA ได้ทันที",
        scheduled_for: "2026-08-14T09:00:00",
        status: "pending_approval",
        approved_by: null,
        sent_at: null,
        error: null,
        created_at: "2026-08-08T09:00:00",
      },
      {
        id: "act-2",
        series_id: DEMO_SERIES_ID,
        meeting_id: M.m3,
        resolution_id: null,
        action_type: "send_meeting_summary_email",
        recipient_person_id: P.phat,
        subject: "สรุปการประชุม Pre-Launch Sync (Meeting #3) และ Action Items",
        body: "เรียน คุณภัทร และทีมงาน NovaTech\n\nแนบสรุปมติและ Action Items จากการประชุม Pre-Launch Sync วันที่ 7 สิงหาคม 2569 บล็อกเกอร์เรื่องระบบชำระเงินได้รับการแก้ไขแล้ว",
        scheduled_for: null,
        status: "sent",
        approved_by: "ภัทร (Phat)",
        sent_at: "2026-08-07T11:45:00",
        error: null,
        created_at: "2026-08-07T11:35:00",
      },
    ],
    audit,
    qa: {},
  };
}

/* ── Interactive Demo Ingest Script (Meeting #4 Ingestion) ──────────── */

export interface ScriptedSegment {
  speaker_label: string;
  start_ms: number;
  text: string;
  confidence: number;
}

export const MEETING_6_SCRIPT: ScriptedSegment[] = [
  { speaker_label: "SPEAKER_01", start_ms: 10_000, text: "สรุปผลหลังเปิด Beta มา 3 วัน ยอดดาวน์โหลดทะลุ 5,000 Users แล้วนะครับ", confidence: 0.98 },
  { speaker_label: "SPEAKER_04", start_ms: 45_000, text: "ใช่ค่ะ ยอดจาก TikTok ดีมาก CAC อยู่ที่ 85 บาท ต่ำกว่าเป้าที่เราตั้งไว้ 120 บาทมากค่ะ", confidence: 0.97 },
  { speaker_label: "SPEAKER_03", start_ms: 90_000, text: "แต่เราพบ Issue เรื่อง Push Notification ส่งช้าไป 5 นาทีบนระบบ iOS ทีมกำลังปล่อย Hotfix คืนนี้ครับ", confidence: 0.96 },
  { speaker_label: "SPEAKER_01", start_ms: 135_000, text: "โอเค ให้กานต์ปล่อย Hotfix ภายใน 22:00 น. คืนนี้ และให้มิ้นเพิ่มงบ TikTok Ads อีก 20% สำหรับสัปดาห์หน้า", confidence: 0.97 },
  { speaker_label: "SPEAKER_02", start_ms: 180_000, text: "รับทราบค่ะ เดี๋ยวรินเตรียม Asset Banner สำหรับโปรโมตสัปดาห์หน้าที่เพิ่มงบด้วยค่ะ", confidence: 0.96 },
];

export const MEETING_6_SPEAKER_GUESS: Record<string, { person_id: string | null; confidence: number; candidates: string[] }> = {
  SPEAKER_01: { person_id: P.phat, confidence: 0.98, candidates: [P.phat] },
  SPEAKER_02: { person_id: P.rin, confidence: 0.96, candidates: [P.rin] },
  SPEAKER_03: { person_id: P.karn, confidence: 0.97, candidates: [P.karn] },
  SPEAKER_04: { person_id: P.mint, confidence: 0.95, candidates: [P.mint] },
};
