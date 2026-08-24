/**
 * ข้อมูลตั้งต้นสำหรับเดโม — อิงสคริปต์ใน §11 ของ SARA_v2_Requirements.md
 *
 * ครั้งที่ 5/2569 (ประชุมแล้ว/รับรองแล้ว) มี
 *   มติ A จัดซื้อครุภัณฑ์ → ฝ่ายพัสดุ  → เกินกำหนดแล้ว
 *   มติ B ระบบสารบรรณ    → ฝ่าย IT    → เลื่อนมา 3 ครั้ง ติดธง
 *   มติ C คณะทำงานงบประมาณ → "พี่หนึ่ง" → จะถูกปิดในครั้งที่ 6
 * ครั้งที่ 6/2569 ยังไม่อัปโหลด — ผู้ใช้กดอัปโหลดในเดโมเพื่อโชว์ linking engine
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
export const DEMO_SERIES_ID = "ser-exec-2569";
const SER2 = "ser-acad-2569";

/* ── บุคคล ─────────────────────────────────────────────────────────────── */

export const P = {
  // สำนักผู้อำนวยการ
  deptDirectorate: "dep-directorate",
  chair: "per-chair",
  deputy: "per-deputy",

  // ฝ่ายบริหารงานทั่วไป
  deptAdmin: "dep-admin",
  secretary: "per-sec",
  adminOfficer: "per-admin-off",

  // ฝ่ายเทคโนโลยีสารสนเทศ
  deptIt: "dep-it",
  it: "per-it",
  itOfficer: "per-it-off",

  // ฝ่ายพัสดุ
  deptSupply: "dep-supply",
  supply: "per-supply",
  supplyOfficer: "per-supply-off",

  // ฝ่ายการเงินและบัญชี
  deptFinance: "dep-finance",
  finance: "per-finance",
  financeOfficer: "per-fin-off",

  // ฝ่ายวิชาการ
  deptAcademic: "dep-academic",
  academic: "per-academic",
  academicOfficer: "per-acad-off",
} as const;

const people: Person[] = [
  // ── 1. สำนักผู้อำนวยการ ────────────────────────────────────────────────
  {
    id: P.deptDirectorate,
    org_id: ORG_ID,
    full_name: "สำนักผู้อำนวยการ",
    position: "หน่วยงาน",
    department: "สำนักผู้อำนวยการ",
    email: "test01@gmail.com",
    is_active: true,
    is_department: true,
  },
  {
    id: P.chair,
    org_id: ORG_ID,
    full_name: "นายธนกฤต อารีวงศ์",
    position: "ผู้อำนวยการ (ประธานที่ประชุม)",
    department: "สำนักผู้อำนวยการ",
    email: "test01@gmail.com",
    is_active: true,
    is_department: false,
  },
  {
    id: P.deputy,
    org_id: ORG_ID,
    full_name: "นายสุรชัย ทองอินทร์",
    position: "รองผู้อำนวยการ",
    department: "สำนักผู้อำนวยการ",
    email: "test02@gmail.com",
    is_active: true,
    is_department: false,
  },

  // ── 2. ฝ่ายบริหารงานทั่วไป ───────────────────────────────────────────
  {
    id: P.deptAdmin,
    org_id: ORG_ID,
    full_name: "ฝ่ายบริหารงานทั่วไป",
    position: "หน่วยงาน",
    department: "ฝ่ายบริหารงานทั่วไป",
    email: "test01@gmail.com",
    is_active: true,
    is_department: true,
  },
  {
    id: P.secretary,
    org_id: ORG_ID,
    full_name: "นางสาวปรียานุช วัฒนสิน",
    position: "หัวหน้าฝ่ายบริหารงานทั่วไป (เลขานุการที่ประชุม)",
    department: "ฝ่ายบริหารงานทั่วไป",
    email: "test01@gmail.com",
    is_active: true,
    is_department: false,
  },
  {
    id: P.adminOfficer,
    org_id: ORG_ID,
    full_name: "นายณัฐวุฒิ สิทธิชัย",
    position: "เจ้าหน้าที่บริหารงานทั่วไปปฏิบัติการ",
    department: "ฝ่ายบริหารงานทั่วไป",
    email: "test02@gmail.com",
    is_active: true,
    is_department: false,
  },

  // ── 3. ฝ่ายเทคโนโลยีสารสนเทศ ──────────────────────────────────────────
  {
    id: P.deptIt,
    org_id: ORG_ID,
    full_name: "ฝ่ายเทคโนโลยีสารสนเทศ",
    position: "หน่วยงาน",
    department: "ฝ่ายเทคโนโลยีสารสนเทศ",
    email: "test02@gmail.com",
    is_active: true,
    is_department: true,
  },
  {
    id: P.it,
    org_id: ORG_ID,
    full_name: "นายวีระพงษ์ ศรีสมบูรณ์",
    position: "หัวหน้าฝ่ายเทคโนโลยีสารสนเทศ",
    department: "ฝ่ายเทคโนโลยีสารสนเทศ",
    email: "test02@gmail.com",
    is_active: true,
    is_department: false,
  },
  {
    id: P.itOfficer,
    org_id: ORG_ID,
    full_name: "นายชานนท์ วงศ์สุวรรณ",
    position: "นักวิชาการคอมพิวเตอร์ชำนาญการ",
    department: "ฝ่ายเทคโนโลยีสารสนเทศ",
    email: "test01@gmail.com",
    is_active: true,
    is_department: false,
  },

  // ── 4. ฝ่ายพัสดุ ─────────────────────────────────────────────────────
  {
    id: P.deptSupply,
    org_id: ORG_ID,
    full_name: "ฝ่ายพัสดุ",
    position: "หน่วยงาน",
    department: "ฝ่ายพัสดุ",
    email: "test01@gmail.com",
    is_active: true,
    is_department: true,
  },
  {
    id: P.supply,
    org_id: ORG_ID,
    full_name: "นางกาญจนา พูลสวัสดิ์",
    position: "หัวหน้าฝ่ายพัสดุ",
    department: "ฝ่ายพัสดุ",
    email: "test01@gmail.com",
    is_active: true,
    is_department: false,
  },
  {
    id: P.supplyOfficer,
    org_id: ORG_ID,
    full_name: "นายเอกชัย ภักดี",
    position: "เจ้าหน้าที่พัสดุชำนาญการ",
    department: "ฝ่ายพัสดุ",
    email: "test02@gmail.com",
    is_active: true,
    is_department: false,
  },

  // ── 5. ฝ่ายการเงินและบัญชี ───────────────────────────────────────────
  {
    id: P.deptFinance,
    org_id: ORG_ID,
    full_name: "ฝ่ายการเงินและบัญชี",
    position: "หน่วยงาน",
    department: "ฝ่ายการเงินและบัญชี",
    email: "test02@gmail.com",
    is_active: true,
    is_department: true,
  },
  {
    id: P.finance,
    org_id: ORG_ID,
    full_name: "นางสาวศิริพร เจริญผล",
    position: "หัวหน้าฝ่ายการเงินและบัญชี",
    department: "ฝ่ายการเงินและบัญชี",
    email: "test02@gmail.com",
    is_active: true,
    is_department: false,
  },
  {
    id: P.financeOfficer,
    org_id: ORG_ID,
    full_name: "นางสาวกมลวรรณ สุขสม",
    position: "นักวิชาการเงินและบัญชีปฏิบัติการ",
    department: "ฝ่ายการเงินและบัญชี",
    email: "test01@gmail.com",
    is_active: true,
    is_department: false,
  },

  // ── 6. ฝ่ายวิชาการ ───────────────────────────────────────────────────
  {
    id: P.deptAcademic,
    org_id: ORG_ID,
    full_name: "ฝ่ายวิชาการ",
    position: "หน่วยงาน",
    department: "ฝ่ายวิชาการ",
    email: "test01@gmail.com",
    is_active: true,
    is_department: true,
  },
  {
    id: P.academic,
    org_id: ORG_ID,
    full_name: "นายกิตติศักดิ์ แสนสุข",
    position: "หัวหน้าฝ่ายวิชาการ",
    department: "ฝ่ายวิชาการ",
    email: "test01@gmail.com",
    is_active: true,
    is_department: false,
  },
  {
    id: P.academicOfficer,
    org_id: ORG_ID,
    full_name: "นางสาวนภัสสร รุ่งเรือง",
    position: "นักวิชาการแผนและนโยบายชำนาญการ",
    department: "ฝ่ายวิชาการ",
    email: "test02@gmail.com",
    is_active: true,
    is_department: false,
  },
];

const aliases: PersonAlias[] = [
  ["al-1", P.deputy, "พี่หนึ่ง", "confirmed_extraction", 0.94],
  ["al-2", P.deputy, "ท่านรอง", "manual", 1],
  ["al-3", P.secretary, "พี่แนน", "confirmed_extraction", 0.88],
  ["al-4", P.it, "ผอ.ไอที", "manual", 1],
  ["al-5", P.supply, "พี่กาญ", "confirmed_extraction", 0.91],
  ["al-6", P.chair, "ท่านประธาน", "manual", 1],
  ["al-7", P.deptSupply, "พัสดุ", "manual", 1],
].map(([id, person_id, alias, source, confidence]) => ({
  id: id as string,
  person_id: person_id as string,
  alias: alias as string,
  source: source as PersonAlias["source"],
  confidence: confidence as number,
  created_at: "2026-01-22T10:00:00",
}));

/* ── ชุดการประชุม ──────────────────────────────────────────────────────── */

const series: MeetingSeries[] = [
  {
    id: DEMO_SERIES_ID,
    org_id: ORG_ID,
    name: "คณะกรรมการบริหาร ปีงบประมาณ 2569",
    committee_type: "คณะกรรมการบริหาร",
    fiscal_year: 2569,
    agenda_template_id: "tpl-official-th",
    cadence: "monthly",
    next_meeting_date: "2026-08-20",
    member_ids: [P.chair, P.deputy, P.secretary, P.it, P.supply, P.finance, P.academic],
  },
  {
    id: SER2,
    org_id: ORG_ID,
    name: "คณะกรรมการวิชาการ ปีงบประมาณ 2569",
    committee_type: "คณะกรรมการวิชาการ",
    fiscal_year: 2569,
    agenda_template_id: "tpl-official-th",
    cadence: "quarterly",
    next_meeting_date: "2026-09-10",
    member_ids: [P.chair, P.academic, P.secretary],
  },
];

/* ── การประชุม ────────────────────────────────────────────────────────── */

const donePipeline: Meeting["pipeline"] = [
  { stage: "upload", state: "ok" },
  { stage: "asr", state: "ok", detail: "AI4Thai Partii · WER 8.4%" },
  { stage: "extract", state: "ok" },
  { stage: "done", state: "ok" },
];

function heldMeeting(
  id: string,
  seq: number,
  date: string,
  series_id = DEMO_SERIES_ID,
): Meeting {
  return {
    id,
    series_id,
    sequence_no: seq,
    fiscal_year: 2569,
    meeting_date: date,
    title: `การประชุมครั้งที่ ${seq}/2569`,
    audio_uri: `minio://sara/meetings/${id}.m4a`,
    source_kind: "audio",
    status: "distributed",
    pipeline: donePipeline,
    created_at: `${date}T09:00:00`,
    approved_at: `${date}T16:20:00`,
    approved_by: "นางสาวปรียานุช วัฒนสิน",
  };
}

export const M = {
  m2: "mtg-2",
  m3: "mtg-3",
  m4: "mtg-4",
  m5: "mtg-5",
} as const;

const meetings: Meeting[] = [
  heldMeeting("mtg-1", 1, "2026-01-22"),
  heldMeeting(M.m2, 2, "2026-03-12"),
  heldMeeting(M.m3, 3, "2026-04-23"),
  heldMeeting(M.m4, 4, "2026-05-21"),
  { ...heldMeeting(M.m5, 5, "2026-06-18"), status: "distributed" },
  heldMeeting("mtg-a1", 1, "2026-02-05", SER2),
];

/* ── Transcript ครั้งที่ 5/2569 ────────────────────────────────────────── */

function seg(
  id: string,
  meeting_id: string,
  speaker_label: string,
  person_id: string | null,
  start_ms: number,
  text: string,
  confidence = 0.95,
): TranscriptSegment {
  return {
    id,
    meeting_id,
    speaker_label,
    person_id,
    start_ms,
    end_ms: start_ms + Math.max(4000, text.length * 120),
    text,
    confidence,
  };
}

const segments: TranscriptSegment[] = [
  seg("s5-01", M.m5, "SPEAKER_00", P.chair, 12_000, "เรียนคณะกรรมการทุกท่าน วันนี้เป็นการประชุมครั้งที่ 5 ประจำปีงบประมาณ 2569 ขอเปิดการประชุมครับ"),
  seg("s5-02", M.m5, "SPEAKER_02", P.secretary, 96_000, "วาระที่ 2 ขอให้ที่ประชุมพิจารณารับรองรายงานการประชุมครั้งที่ 4/2569 ค่ะ"),
  seg("s5-03", M.m5, "SPEAKER_00", P.chair, 141_000, "ถ้าไม่มีการแก้ไข ถือว่าที่ประชุมรับรองรายงานการประชุมครั้งที่ 4 นะครับ"),
  seg("s5-04", M.m5, "SPEAKER_03", P.supply, 620_000, "เรื่องครุภัณฑ์คอมพิวเตอร์ที่จะทดแทนของเดิม ตอนนี้ฝ่ายพัสดุประเมินไว้ 42 เครื่อง กรอบวงเงินประมาณ 1.26 ล้านบาทค่ะ"),
  seg("s5-05", M.m5, "SPEAKER_00", P.chair, 688_000, "งั้นที่ประชุมมีมติมอบหมายให้ฝ่ายพัสดุจัดทำร่างขอบเขตของงาน หรือ TOR สำหรับการจัดซื้อครุภัณฑ์คอมพิวเตอร์ทดแทน จำนวน 42 เครื่อง ให้แล้วเสร็จภายใน 30 วัน แล้วเสนอที่ประชุมพิจารณาครับ", 0.97),
  seg("s5-06", M.m5, "SPEAKER_01", P.it, 1_040_000, "เรื่องระบบสารบรรณอิเล็กทรอนิกส์ ต้องขออภัยที่ประชุม ผู้รับจ้างส่งมอบโมดูลไม่ครบ ทำให้ยังทดสอบระบบไม่ได้ครับ", 0.93),
  seg("s5-07", M.m5, "SPEAKER_00", P.chair, 1_112_000, "อันนี้เลื่อนมาสามรอบแล้วนะครับ ที่ประชุมขอให้ฝ่ายเทคโนโลยีสารสนเทศเร่งรัดผู้รับจ้าง และรายงานความคืบหน้าเป็นลายลักษณ์อักษรภายในวันที่ 31 สิงหาคม 2569", 0.95),
  seg("s5-08", M.m5, "SPEAKER_02", P.secretary, 1_530_000, "วาระที่ 4.3 เรื่องการจัดทำคำของบประมาณประจำปี 2570 ค่ะ ต้องเริ่มภายในเดือนกรกฎาคม"),
  seg("s5-09", M.m5, "SPEAKER_00", P.chair, 1_588_000, "ขอให้พี่หนึ่งรับไปดูแลนะครับ ที่ประชุมมีมติให้แต่งตั้งคณะทำงานจัดทำคำของบประมาณประจำปี 2570 โดยมอบหมายรองผู้อำนวยการเป็นประธานคณะทำงาน ให้แล้วเสร็จภายในวันที่ 31 กรกฎาคม 2569", 0.96),
  seg("s5-10", M.m5, "SPEAKER_04", P.deputy, 1_664_000, "รับทราบครับ ผมจะประสานฝ่ายการเงินเรื่องกรอบวงเงินก่อนครับ"),
  seg("s5-11", M.m5, "SPEAKER_00", P.chair, 2_402_000, "ไม่มีเรื่องอื่นแล้วนะครับ ปิดประชุมครับ"),
];

/* ── มติ ──────────────────────────────────────────────────────────────── */

function res(r: Partial<Resolution> & Pick<Resolution, "id" | "ref_no" | "text" | "origin_meeting_id" | "status">): Resolution {
  return {
    series_id: DEMO_SERIES_ID,
    origin_segment_id: null,
    category: "other",
    proposer_person_id: P.chair,
    assignee_ids: [],
    due_date: null,
    original_due_date: null,
    postpone_count: 0,
    closed_meeting_id: null,
    closed_at: null,
    superseded_by_id: null,
    created_at: "2026-06-18T14:00:00",
    updated_at: "2026-06-18T14:00:00",
    extraction_confidence: 0.9,
    ...r,
  } as Resolution;
}

export const R = {
  a: "res-a-tor",
  b: "res-b-edoc",
  c: "res-c-budget",
} as const;

const resolutions: Resolution[] = [
  /* ── มติ A · เกินกำหนด และครั้งที่ 6 จะไม่มีใครพูดถึง ── */
  res({
    id: R.a,
    ref_no: "มติ 5/2569 ข้อ 4.1",
    text: "มอบหมายให้ฝ่ายพัสดุจัดทำร่างขอบเขตของงาน (TOR) สำหรับการจัดซื้อครุภัณฑ์คอมพิวเตอร์ทดแทน จำนวน 42 เครื่อง กรอบวงเงิน 1,260,000 บาท ให้แล้วเสร็จภายใน 30 วัน และเสนอที่ประชุมพิจารณา",
    category: "procurement",
    status: "confirmed",
    origin_meeting_id: M.m5,
    origin_segment_id: "s5-05",
    origin_agenda_item: "วาระที่ 4.1",
    assignee_ids: [P.deptSupply, P.supply],
    due_date: "2026-07-18",
    original_due_date: "2026-07-18",
    extraction_confidence: 0.97,
  }),
  /* ── มติ B · เลื่อนซ้ำ 3 ครั้ง ── */
  res({
    id: R.b,
    ref_no: "มติ 2/2569 ข้อ 4.2",
    text: "ให้ฝ่ายเทคโนโลยีสารสนเทศเร่งรัดผู้รับจ้างให้ส่งมอบและติดตั้งระบบสารบรรณอิเล็กทรอนิกส์ให้ครบทุกโมดูล พร้อมรายงานความคืบหน้าเป็นลายลักษณ์อักษรต่อที่ประชุม",
    category: "operations",
    status: "blocked",
    origin_meeting_id: M.m2,
    origin_agenda_item: "วาระที่ 4.2",
    assignee_ids: [P.it, P.deptIt],
    due_date: "2026-08-31",
    original_due_date: "2026-03-31",
    postpone_count: 3,
    created_at: "2026-03-12T14:00:00",
    updated_at: "2026-06-18T15:10:00",
    extraction_confidence: 0.93,
  }),
  /* ── มติ C · จะถูกปิดในครั้งที่ 6 ── */
  res({
    id: R.c,
    ref_no: "มติ 5/2569 ข้อ 4.3",
    text: "ให้แต่งตั้งคณะทำงานจัดทำคำของบประมาณประจำปีงบประมาณ 2570 โดยมอบหมายรองผู้อำนวยการเป็นประธานคณะทำงาน ให้แล้วเสร็จภายในวันที่ 31 กรกฎาคม 2569",
    category: "budget",
    status: "in_progress",
    origin_meeting_id: M.m5,
    origin_segment_id: "s5-09",
    origin_agenda_item: "วาระที่ 4.3",
    assignee_ids: [P.deputy],
    due_date: "2026-07-31",
    original_due_date: "2026-07-31",
    extraction_confidence: 0.96,
  }),
  /* ── มติเก่าที่ปิดแล้ว เพื่อให้สถิติแดชบอร์ดสมจริง ── */
  res({
    id: "res-d",
    ref_no: "มติ 1/2569 ข้อ 4.1",
    text: "ให้ทุกฝ่ายจัดทำแผนปฏิบัติการประจำปีงบประมาณ 2569 ส่งฝ่ายบริหารงานทั่วไปภายในวันที่ 15 กุมภาพันธ์ 2569",
    category: "policy",
    status: "done",
    origin_meeting_id: "mtg-1",
    assignee_ids: [P.secretary],
    due_date: "2026-02-15",
    original_due_date: "2026-02-15",
    closed_meeting_id: M.m2,
    closed_at: "2026-03-12T15:00:00",
    created_at: "2026-01-22T14:00:00",
  }),
  res({
    id: "res-e",
    ref_no: "มติ 2/2569 ข้อ 4.1",
    text: "อนุมัติปรับปรุงห้องประชุมใหญ่ ชั้น 3 วงเงินไม่เกิน 480,000 บาท โดยให้ฝ่ายพัสดุดำเนินการตามระเบียบพัสดุ",
    category: "budget",
    status: "done",
    origin_meeting_id: M.m2,
    assignee_ids: [P.deptSupply],
    due_date: "2026-05-31",
    original_due_date: "2026-04-30",
    postpone_count: 1,
    closed_meeting_id: M.m5,
    closed_at: "2026-06-18T15:30:00",
    created_at: "2026-03-12T14:20:00",
  }),
  res({
    id: "res-f",
    ref_no: "มติ 3/2569 ข้อ 4.1",
    text: "ให้ฝ่ายการเงินและบัญชีรายงานผลการใช้จ่ายงบประมาณรายไตรมาสต่อที่ประชุมทุกครั้ง",
    category: "budget",
    status: "done",
    origin_meeting_id: M.m3,
    assignee_ids: [P.finance],
    due_date: "2026-05-15",
    original_due_date: "2026-05-15",
    closed_meeting_id: M.m4,
    closed_at: "2026-05-21T15:00:00",
    created_at: "2026-04-23T14:10:00",
  }),
  res({
    id: "res-g",
    ref_no: "มติ 3/2569 ข้อ 4.2",
    text: "ให้ฝ่ายวิชาการจัดทำหลักสูตรอบรมภายในสำหรับเจ้าหน้าที่ใหม่ ปีละไม่น้อยกว่า 2 รุ่น",
    category: "operations",
    status: "done",
    origin_meeting_id: M.m3,
    assignee_ids: [P.academic],
    due_date: "2026-06-15",
    original_due_date: "2026-06-15",
    closed_meeting_id: M.m5,
    closed_at: "2026-06-18T15:35:00",
    created_at: "2026-04-23T14:30:00",
  }),
  res({
    id: "res-h",
    ref_no: "มติ 4/2569 ข้อ 4.1",
    text: "ให้ทบทวนระเบียบการเบิกจ่ายค่าใช้จ่ายในการเดินทางไปราชการ ให้สอดคล้องกับระเบียบกระทรวงการคลังฉบับใหม่",
    category: "policy",
    status: "in_progress",
    origin_meeting_id: M.m4,
    assignee_ids: [P.finance],
    due_date: "2026-08-29",
    original_due_date: "2026-07-31",
    postpone_count: 1,
    created_at: "2026-05-21T14:15:00",
  }),
  res({
    id: "res-i",
    ref_no: "มติ 4/2569 ข้อ 4.2",
    text: "ให้ฝ่ายเทคโนโลยีสารสนเทศจัดหาระบบสำรองข้อมูลนอกสถานที่ (offsite backup) ภายในไตรมาส 4",
    category: "operations",
    status: "confirmed",
    origin_meeting_id: M.m4,
    assignee_ids: [P.it],
    due_date: "2026-09-30",
    original_due_date: "2026-09-30",
    created_at: "2026-05-21T14:40:00",
  }),
  res({
    id: "res-j",
    ref_no: "มติ 2/2569 ข้อ 4.3",
    text: "ให้จัดซื้อเครื่องปรับอากาศทดแทนของเดิม จำนวน 8 เครื่อง โดยวิธีเฉพาะเจาะจง",
    category: "procurement",
    status: "superseded",
    origin_meeting_id: M.m2,
    assignee_ids: [P.deptSupply],
    due_date: "2026-05-31",
    original_due_date: "2026-05-31",
    superseded_by_id: "res-k",
    created_at: "2026-03-12T14:50:00",
  }),
  res({
    id: "res-k",
    ref_no: "มติ 4/2569 ข้อ 4.3",
    text: "ให้จัดซื้อเครื่องปรับอากาศทดแทน จำนวน 12 เครื่อง โดยวิธีประกวดราคาอิเล็กทรอนิกส์ (e-bidding) แทนมติเดิมตามข้อเสนอของฝ่ายพัสดุ",
    category: "procurement",
    status: "done",
    origin_meeting_id: M.m4,
    assignee_ids: [P.deptSupply],
    due_date: "2026-06-30",
    original_due_date: "2026-06-30",
    closed_meeting_id: M.m5,
    closed_at: "2026-06-18T15:40:00",
    created_at: "2026-05-21T15:00:00",
  }),
  res({
    id: "res-l",
    ref_no: "มติ 1/2569 ข้อ 5.1",
    text: "ให้จัดกิจกรรมสัมมนาประจำปีนอกสถานที่ในไตรมาส 3",
    category: "operations",
    status: "cancelled",
    origin_meeting_id: "mtg-1",
    assignee_ids: [P.secretary],
    due_date: "2026-06-30",
    original_due_date: "2026-06-30",
    created_at: "2026-01-22T15:00:00",
  }),
];

/* ── การอ้างถึงมติข้ามการประชุม ───────────────────────────────────────── */

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
    confidence: 0.92,
    created_at,
    ...opts,
  };
}

const links: ResolutionLink[] = [
  link("lk-a1", R.a, M.m5, "created", "ที่ประชุมมีมติมอบหมายให้ฝ่ายพัสดุจัดทำร่างขอบเขตของงาน หรือ TOR สำหรับการจัดซื้อครุภัณฑ์คอมพิวเตอร์ทดแทน จำนวน 42 เครื่อง", "2026-06-18T14:00:00", { segment_id: "s5-05", evidence_start_ms: 688_000, confidence: 0.97 }),
  link("lk-b1", R.b, M.m2, "created", "ที่ประชุมมีมติให้ฝ่ายเทคโนโลยีสารสนเทศดำเนินการปรับปรุงระบบสารบรรณอิเล็กทรอนิกส์", "2026-03-12T14:00:00", { evidence_start_ms: 1_204_000, confidence: 0.94 }),
  link("lk-b2", R.b, M.m3, "progress_reported", "ขณะนี้อยู่ระหว่างรอผู้รับจ้างส่งมอบโมดูลที่ 2 ขอเลื่อนกำหนดเป็นสิ้นเดือนพฤษภาคม", "2026-04-23T14:20:00", { evidence_start_ms: 948_000, confidence: 0.89 }),
  link("lk-b3", R.b, M.m4, "progress_reported", "ผู้รับจ้างยังส่งมอบไม่ครบ ขอเลื่อนอีกครั้งเป็นสิ้นเดือนมิถุนายน", "2026-05-21T14:25:00", { evidence_start_ms: 1_017_000, confidence: 0.9 }),
  link("lk-b4", R.b, M.m5, "progress_reported", "ผู้รับจ้างส่งมอบโมดูลไม่ครบ ทำให้ยังทดสอบระบบไม่ได้ครับ", "2026-06-18T15:10:00", { segment_id: "s5-06", evidence_start_ms: 1_040_000, confidence: 0.93 }),
  link("lk-c1", R.c, M.m5, "created", "ที่ประชุมมีมติให้แต่งตั้งคณะทำงานจัดทำคำของบประมาณประจำปี 2570", "2026-06-18T14:00:00", { segment_id: "s5-09", evidence_start_ms: 1_588_000, confidence: 0.96 }),
  link("lk-e1", "res-e", M.m5, "closed", "เรื่องปรับปรุงห้องประชุมใหญ่ ดำเนินการแล้วเสร็จและตรวจรับเรียบร้อยแล้ว", "2026-06-18T15:30:00", { evidence_start_ms: 1_842_000 }),
  link("lk-j1", "res-j", M.m4, "superseded", "ขอปรับจำนวนเป็น 12 เครื่องและเปลี่ยนวิธีจัดซื้อเป็น e-bidding", "2026-05-21T15:00:00", { evidence_start_ms: 1_530_000 }),
];

const history: ResolutionHistory[] = [
  { id: "h-b1", resolution_id: R.b, field: "due_date", old_value: "2026-03-31", new_value: "2026-05-15", changed_by: "นางสาวปรียานุช วัฒนสิน", changed_at: "2026-04-23T14:20:00", reason: "ที่ประชุมครั้งที่ 3/2569 อนุมัติให้ขยายเวลา", source_meeting_id: M.m3 },
  { id: "h-b2", resolution_id: R.b, field: "due_date", old_value: "2026-05-15", new_value: "2026-06-30", changed_by: "นางสาวปรียานุช วัฒนสิน", changed_at: "2026-05-21T14:25:00", reason: "ผู้รับจ้างส่งมอบล่าช้า", source_meeting_id: M.m4 },
  { id: "h-b3", resolution_id: R.b, field: "due_date", old_value: "2026-06-30", new_value: "2026-08-31", changed_by: "นางสาวปรียานุช วัฒนสิน", changed_at: "2026-06-18T15:10:00", reason: "ที่ประชุมครั้งที่ 5/2569 ให้เร่งรัดผู้รับจ้าง", source_meeting_id: M.m5 },
  { id: "h-b4", resolution_id: R.b, field: "status", old_value: "in_progress", new_value: "blocked", changed_by: "นางสาวปรียานุช วัฒนสิน", changed_at: "2026-06-18T15:12:00", reason: "ติดปัญหาผู้รับจ้างส่งมอบไม่ครบ", source_meeting_id: M.m5 },
  { id: "h-c1", resolution_id: R.c, field: "status", old_value: "confirmed", new_value: "in_progress", changed_by: "ระบบ (รับรองรายงานการประชุม)", changed_at: "2026-07-02T09:00:00", reason: "ผู้รับผิดชอบแจ้งเริ่มดำเนินการผ่าน magic link" },
];

const audit: AuditEntry[] = [
  { id: "au-1", org_id: ORG_ID, actor: "นางสาวปรียานุช วัฒนสิน", action: "approve_meeting", entity_type: "meeting", entity_id: M.m5, metadata: "รับรองรายงานการประชุมครั้งที่ 5/2569", created_at: "2026-06-18T16:20:00" },
  { id: "au-2", org_id: ORG_ID, actor: "นางสาวปรียานุช วัฒนสิน", action: "confirm_alias", entity_type: "person", entity_id: P.deputy, metadata: 'ยืนยัน "พี่หนึ่ง" → นายสุรชัย ทองอินทร์', created_at: "2026-06-18T15:02:00" },
];

export function createSeedDatabase(): Database {
  const org: Organization = { id: ORG_ID, name: "สำนักงานพัฒนาระบบราชการ (ตัวอย่าง)" };
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
        resolution_id: R.a,
        action_type: "send_resolution_reminder",
        recipient_person_id: P.supply,
        subject: "แจ้งเตือน: มติ 5/2569 ข้อ 4.1 เกินกำหนดแล้ว 24 วัน",
        body:
          "เรียน หัวหน้าฝ่ายพัสดุ\n\nระบบตรวจพบว่ามติต่อไปนี้เกินกำหนดแล้ว\n\n" +
          "“มอบหมายให้ฝ่ายพัสดุจัดทำร่างขอบเขตของงาน (TOR) สำหรับการจัดซื้อครุภัณฑ์คอมพิวเตอร์ทดแทน จำนวน 42 เครื่อง กรอบวงเงิน 1,260,000 บาท ให้แล้วเสร็จภายใน 30 วัน และเสนอที่ประชุมพิจารณา”\n\n" +
          "ที่มา: การประชุมครั้งที่ 5/2569 วาระที่ 4.1 · กำหนดเดิม 18 กรกฎาคม 2569\n\n" +
          "กรุณาแจ้งสถานะกลับผ่านลิงก์ในอีเมลฉบับนี้",
        scheduled_for: "2026-08-12T08:00:00",
        status: "pending_approval",
        approved_by: null,
        sent_at: null,
        error: null,
        created_at: "2026-08-11T08:00:00",
      },
      {
        id: "act-2",
        series_id: DEMO_SERIES_ID,
        meeting_id: null,
        resolution_id: null,
        action_type: "send_agenda_preview",
        recipient_person_id: P.chair,
        subject: "สรุปเรื่องค้างก่อนการประชุมครั้งที่ 6/2569",
        body: "เรียน ท่านประธาน\n\nก่อนการประชุมครั้งที่ 6/2569 มีมติค้างดำเนินการ 4 เรื่อง เกินกำหนด 2 เรื่อง รายละเอียดตามร่างระเบียบวาระที่แนบ",
        scheduled_for: "2026-08-19T08:00:00",
        status: "pending_approval",
        approved_by: null,
        sent_at: null,
        error: null,
        created_at: "2026-08-11T08:05:00",
      },
      {
        id: "act-3",
        series_id: DEMO_SERIES_ID,
        meeting_id: M.m5,
        resolution_id: null,
        action_type: "send_meeting_summary_email",
        recipient_person_id: P.it,
        subject: "รายงานการประชุมครั้งที่ 5/2569 และมติที่เกี่ยวข้องกับท่าน",
        body: "เรียน หัวหน้าฝ่ายเทคโนโลยีสารสนเทศ\n\nแนบรายงานการประชุมครั้งที่ 5/2569 พร้อมมติที่อยู่ในความรับผิดชอบของท่าน 2 เรื่อง",
        scheduled_for: null,
        status: "sent",
        approved_by: "นางสาวปรียานุช วัฒนสิน",
        sent_at: "2026-06-18T16:40:00",
        error: null,
        created_at: "2026-06-18T16:35:00",
      },
    ],
    audit,
    qa: {},
  };
}

/* ── สคริปต์ครั้งที่ 6/2569 — ใช้ตอนผู้ใช้อัปโหลดในเดโม ─────────────────
   ตาม §11: รายงานผลมติ C ชัดเจน / ไม่พูดถึงมติ A เลย / มีมติใหม่ 2 ข้อ
   ---------------------------------------------------------------------- */

export interface ScriptedSegment {
  speaker_label: string;
  start_ms: number;
  text: string;
  confidence: number;
}

export const MEETING_6_SCRIPT: ScriptedSegment[] = [
  { speaker_label: "SPEAKER_00", start_ms: 9_000, text: "เรียนคณะกรรมการทุกท่าน วันนี้เป็นการประชุมครั้งที่ 6 ประจำปีงบประมาณ 2569 ขอเปิดการประชุมครับ", confidence: 0.96 },
  { speaker_label: "SPEAKER_02", start_ms: 88_000, text: "วาระที่ 2 ขอให้ที่ประชุมรับรองรายงานการประชุมครั้งที่ 5/2569 ค่ะ", confidence: 0.95 },
  { speaker_label: "SPEAKER_00", start_ms: 133_000, text: "ไม่มีการแก้ไข ถือว่าที่ประชุมรับรองรายงานการประชุมครั้งที่ 5 นะครับ", confidence: 0.96 },
  { speaker_label: "SPEAKER_01", start_ms: 402_000, text: "เรื่องคณะทำงานจัดทำคำของบประมาณที่ค้างจากคราวที่แล้ว ตอนนี้แต่งตั้งเรียบร้อยแล้วครับ ท่านผู้อำนวยการลงนามคำสั่งที่ 118/2569 เมื่อวันที่ 5 สิงหาคม และคณะทำงานประชุมนัดแรกไปแล้วครับ", confidence: 0.94 },
  { speaker_label: "SPEAKER_00", start_ms: 471_000, text: "ดีครับ ถือว่าเรื่องนี้ดำเนินการเสร็จแล้ว ขอบคุณพี่หนึ่งครับ", confidence: 0.93 },
  { speaker_label: "SPEAKER_03", start_ms: 690_000, text: "เรื่องระบบสารบรรณ ผู้รับจ้างเพิ่งส่งมอบโมดูลที่เหลือเมื่อสัปดาห์ที่แล้ว ฝ่ายไอทีกำลังทดสอบอยู่ครับ คาดว่าจะรายงานได้ภายในสิ้นเดือน", confidence: 0.91 },
  { speaker_label: "SPEAKER_02", start_ms: 1_180_000, text: "วาระที่ 4.1 ค่ะ เมื่อระบบสารบรรณใหม่ใช้งานได้ เจ้าหน้าที่ยังใช้ไม่เป็น ควรจัดอบรมก่อนค่ะ", confidence: 0.94 },
  { speaker_label: "SPEAKER_00", start_ms: 1_246_000, text: "ที่ประชุมมีมติให้ฝ่ายเทคโนโลยีสารสนเทศร่วมกับฝ่ายบริหารงานทั่วไป จัดอบรมการใช้งานระบบสารบรรณอิเล็กทรอนิกส์ให้เจ้าหน้าที่ทุกฝ่าย ไม่น้อยกว่า 2 รุ่น ให้แล้วเสร็จภายในวันที่ 30 กันยายน 2569", confidence: 0.95 },
  { speaker_label: "SPEAKER_04", start_ms: 1_690_000, text: "ผมว่าเรื่องนี้น่าจะดีนะครับ แต่ต้องดูงบก่อน เดี๋ยวค่อยว่ากันอีกที", confidence: 0.88 },
  { speaker_label: "SPEAKER_00", start_ms: 1_902_000, text: "อีกเรื่องครับ ที่ประชุมมีมติให้ฝ่ายการเงินและบัญชีจัดทำรายงานผลการใช้จ่ายงบประมาณไตรมาสที่ 4 เสนอที่ประชุมในการประชุมครั้งถัดไป", confidence: 0.92 },
  { speaker_label: "SPEAKER_00", start_ms: 2_310_000, text: "ไม่มีเรื่องอื่นแล้วนะครับ ปิดประชุมครับ", confidence: 0.96 },
];

/** ผู้พูดที่ระบบเดาไว้ — SPEAKER_01 ต้องให้คนยืนยัน (โชว์ entity resolution) */
export const MEETING_6_SPEAKER_GUESS: Record<string, { person_id: string | null; confidence: number; candidates: string[] }> = {
  SPEAKER_00: { person_id: P.chair, confidence: 0.95, candidates: [P.chair] },
  SPEAKER_01: { person_id: null, confidence: 0.58, candidates: [P.deputy, P.academic] },
  SPEAKER_02: { person_id: P.secretary, confidence: 0.91, candidates: [P.secretary] },
  SPEAKER_03: { person_id: P.it, confidence: 0.87, candidates: [P.it] },
  SPEAKER_04: { person_id: null, confidence: 0.44, candidates: [P.finance, P.academic] },
};
