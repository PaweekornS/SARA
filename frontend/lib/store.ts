"use client";

/**
 * Store กลางของ frontend — useSyncExternalStore + localStorage
 *
 * ตอนนี้ทำงานบน mock database (lib/seed.ts) เพราะ backend v2 ยังไม่มี
 * ทุก mutation ในไฟล์นี้ mirror endpoint ใน §6 ของ requirement แบบ 1:1
 * เวลาต่อ API จริงให้แก้เฉพาะ lib/api.ts แล้วสลับ NEXT_PUBLIC_USE_MOCK=false
 */

import { useSyncExternalStore } from "react";
import * as http from "./http";
import {
  LINK_LABEL_TH,
  OPEN_STATUSES,
  STATUS_LABEL_TH,
  formatThaiDate,
  overdueDays,
  relevance,
  thaiGrams,
} from "./domain";
import {
  DEMO_SERIES_ID,
  MEETING_6_SCRIPT,
  MEETING_6_SPEAKER_GUESS,
  createSeedDatabase,
  P,
  R,
} from "./seed";
import type {
  AgendaDraft,
  AgendaItem,
  Database,
  Meeting,
  MeetingSeries,
  OutboundAction,
  Person,
  PipelineStage,
  Proposal,
  QaAnswer,
  Resolution,
  ResolutionStatus,
  TranscriptSegment,
  Uuid,
} from "./types";

export type Lang = "th" | "en";
export type Theme = "light" | "dark";

export interface AppState {
  db: Database;
  lang: Lang;
  theme: Theme;
  /** ผู้ใช้ที่ล็อกอินอยู่ (mock) — ใช้เป็น actor ใน audit log */
  actor: string;
  /** สถานะการซิงก์กับ backend — ใช้เฉพาะตอน NEXT_PUBLIC_USE_MOCK=false */
  loading: boolean;
  lastError: string | null;
  activeSeriesId?: string | null;
}

const STORAGE_KEY = "sara_v4_novatech_state";

function freshState(): AppState {
  return {
    db: createSeedDatabase(),
    lang: "th",
    theme: "light",
    actor: "ภัทร (Phat)",
    loading: false,
    lastError: null,
    activeSeriesId: null,
  };
}

/** snapshot ที่ server render เสมอ — กัน hydration mismatch */
const serverState: AppState = freshState();

let state: AppState = serverState;
let hydrated = false;

const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

function persist() {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    /* โควตาเต็ม — ไม่ใช่เรื่องคอขาดบาดตาย ปล่อยผ่าน */
  }
}

function set(updater: (s: AppState) => AppState) {
  state = updater(state);
  persist();
  emit();
}

/** แก้เฉพาะ db แล้ว emit */
function mutate(updater: (db: Database) => Database) {
  set((s) => ({ ...s, db: updater(s.db) }));
}

export function hydrate() {
  if (hydrated || typeof window === "undefined") return;
  hydrated = true;

  // Clear legacy cache keys
  try {
    window.localStorage.removeItem("sara_v2_state");
    window.localStorage.removeItem("sara_v3_state");
  } catch {
    /* ignore */
  }

  if (LIVE) {
    /* ต่อ backend จริง — ข้อมูลมาจากฐานเสมอ ไม่อ่านของเก่าใน localStorage */
    applyTheme(state.theme);
    void loadFromServer();
    return;
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as AppState;
      // Validate schema: must contain new NovaTech series
      const isNovaTech = parsed?.db?.series?.some((s) => s.id === DEMO_SERIES_ID);
      if (isNovaTech && parsed?.db?.resolutions) {
        state = parsed;
      } else {
        state = freshState();
        persist();
      }
    } else {
      state = freshState();
      persist();
    }
  } catch {
    /* ข้อมูลเก่าพัง — เริ่มใหม่จาก seed */
    state = freshState();
    persist();
  }
  applyTheme(state.theme);
  emit();
}

export function resetDemo() {
  clearTimers();
  state = freshState();
  persist();
  applyTheme(state.theme);
  emit();
  if (LIVE) {
    void http.resetDemoBackend().then(() => loadFromServer(true)).catch(() => {});
  }
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/**
 * ⚠ selector ต้องคืนค่าที่เทียบด้วย === ได้ (primitive หรือ reference ที่มีอยู่แล้วใน state)
 * ห้ามคืน object/array ที่สร้างใหม่ทุกครั้ง ไม่งั้น useSyncExternalStore จะวนไม่รู้จบ
 * ถ้าต้องคำนวณอะไรก็ตาม ให้ใช้ useApp() แล้วคำนวณตอน render
 */
export function useStore<T>(selector: (s: AppState) => T): T {
  return useSyncExternalStore(
    subscribe,
    () => selector(state),
    () => selector(serverState),
  );
}

export function useApp(): AppState {
  return useStore((s) => s);
}

export function getState() {
  return state;
}

/* ── การซิงก์กับ backend ─────────────────────────────────────────────── */

export const LIVE = !http.USE_MOCK;

export function setError(message: string | null) {
  set((s) => ({ ...s, lastError: message }));
}

/** ดึงข้อมูลทั้งก้อนจาก /bootstrap มาแทนที่ของเดิม */
export async function loadFromServer(silent = false): Promise<void> {
  if (!LIVE) return;
  if (!silent) set((s) => ({ ...s, loading: true }));
  try {
    const db = await http.fetchBootstrap();
    const isNovaTech = db?.org?.name === "NovaTech Studio (Demo Workspace)" || db?.series?.some((s) => s.name?.includes("Alpha App"));
    if (!isNovaTech) {
      try {
        await http.resetDemoBackend();
        const freshDb = await http.fetchBootstrap();
        set((s) => ({ ...s, db: freshDb, loading: false, lastError: null }));
        return;
      } catch {
        // Fallback to fresh seed state if backend reset fails
        set((s) => ({ ...s, db: freshState().db, loading: false, lastError: null }));
        return;
      }
    }
    set((s) => ({ ...s, db, loading: false, lastError: null }));
  } catch (err) {
    set((s) => ({
      ...s,
      loading: false,
      lastError: `เชื่อมต่อ backend ไม่ได้: ${err instanceof Error ? err.message : String(err)}`,
    }));
  }
}

/**
 * ส่งการเปลี่ยนแปลงขึ้น server แล้วดึงข้อมูลจริงกลับมาทับ
 *
 * หน้าจออัปเดตทันทีจาก mutation ในเครื่อง (optimistic) แล้วค่อยถูกแทนที่ด้วยของจริง
 * ถ้า server ปฏิเสธ ผู้ใช้จะเห็นข้อความจริงจาก backend และข้อมูลถูกดึงกลับมาให้ตรงกับฐาน
 */
function sync(run: () => Promise<unknown>): void {
  if (!LIVE) return;
  run()
    .then(() => loadFromServer())
    .catch(async (err) => {
      setError(err instanceof Error ? err.message : String(err));
      await loadFromServer();
    });
}

/* ── preferences ─────────────────────────────────────────────────────── */

function applyTheme(theme: Theme) {
  if (typeof document === "undefined") return;
  document.documentElement.classList.toggle("dark", theme === "dark");
}

export function setLang(lang: Lang) {
  set((s) => ({ ...s, lang }));
}

export function toggleTheme() {
  const theme: Theme = state.theme === "light" ? "dark" : "light";
  applyTheme(theme);
  set((s) => ({ ...s, theme }));
}

export function setActiveSeriesId(id: string) {
  if (state.activeSeriesId !== id) {
    set((s) => ({ ...s, activeSeriesId: id }));
  }
}

/* ── helpers ─────────────────────────────────────────────────────────── */

let seq = 0;
export function uid(prefix: string) {
  seq += 1;
  return `${prefix}-${Date.now().toString(36)}-${seq}`;
}

function nowIso() {
  return new Date().toISOString().slice(0, 19);
}

function audit(db: Database, action: string, entity_type: string, entity_id: string, metadata: string): Database {
  return {
    ...db,
    audit: [
      {
        id: uid("au"),
        org_id: db.org.id,
        actor: state.actor,
        action,
        entity_type,
        entity_id,
        metadata,
        created_at: nowIso(),
      },
      ...db.audit,
    ],
  };
}

/* ── M1 · Meeting Series ─────────────────────────────────────────────── */

export function createSeries(input: Partial<MeetingSeries> & { name: string }) {
  const id = uid("ser");
  const full: MeetingSeries = {
    id,
    org_id: state.db.org.id,
    committee_type: "general",
    fiscal_year: new Date().getFullYear() + 543,
    agenda_template_id: "tmpl-general",
    cadence: "adhoc",
    next_meeting_date: null,
    member_ids: [],
    ...input,
  };
  mutate((db) =>
    audit(
      { ...db, series: [...db.series, full] },
      "create_series",
      "meeting_series",
      id,
      input.name,
    ),
  );
  sync(() => http.createSeries({ ...full }, state.actor));
  return id;
}

export function updateSeries(id: Uuid, patch: Partial<MeetingSeries>) {
  mutate((db) => ({
    ...db,
    series: db.series.map((s) => (s.id === id ? { ...s, ...patch } : s)),
  }));
  sync(() => http.updateSeries(id, patch, state.actor));
}

export function deleteSeries(id: Uuid) {
  mutate((db) => ({
    ...db,
    series: db.series.filter((s) => s.id !== id),
    meetings: db.meetings.filter((m) => m.series_id !== id),
    resolutions: db.resolutions.filter((r) => r.series_id !== id),
  }));
  sync(() => http.deleteSeries(id, state.actor));
}

/* ── M2 · Ingestion & pipeline ───────────────────────────────────────── */

const timers = new Map<Uuid, ReturnType<typeof setTimeout>[]>();

function clearTimers() {
  timers.forEach((list) => list.forEach(clearTimeout));
  timers.clear();
}

const STAGE_ORDER: PipelineStage[] = ["upload", "asr", "extract", "done"];

const STAGE_DETAIL: Record<PipelineStage, string> = {
  upload: "รับไฟล์และตรวจความสมบูรณ์",
  asr: "ถอดเสียงด้วย AI4Thai Partii ASR",
  extract: "สรุปเนื้อหาการประชุมและสกัดมติ",
  done: "พร้อมให้ตรวจทาน",
};

function emptyPipeline(): Meeting["pipeline"] {
  return STAGE_ORDER.map((stage) => ({ stage, state: "pending" as const, detail: STAGE_DETAIL[stage] }));
}

export interface UploadInput {
  series_id: Uuid;
  sequence_no: number;
  meeting_date: string;
  file_name: string;
  source_kind: "audio" | "transcript";
  /** เดโมความล้มเหลวของ ASR — FR-M2-04 ต้องหยุด pipeline ไม่ใส่ข้อมูลปลอม */
  simulate_asr_failure?: boolean;
}

/** POST /meetings + POST /meetings/{id}/upload */
export function uploadMeeting(input: UploadInput): Uuid {
  const id = uid("mtg");
  const meeting: Meeting = {
    id,
    series_id: input.series_id,
    sequence_no: input.sequence_no,
    fiscal_year: 2569,
    meeting_date: input.meeting_date,
    title: `การประชุมครั้งที่ ${input.sequence_no}/2569`,
    audio_uri: `minio://sara/uploads/${input.file_name}`,
    source_kind: input.source_kind,
    status: "processing",
    pipeline: emptyPipeline(),
    created_at: nowIso(),
  };
  mutate((db) => audit({ ...db, meetings: [...db.meetings, meeting] }, "upload_meeting", "meeting", id, input.file_name));
  runPipeline(id, input.simulate_asr_failure ?? false);
  return id;
}

/**
 * โหมดต่อ backend จริง — สร้าง meeting แล้วอัปโหลดไฟล์เข้าคิวประมวลผล
 * คืน id ที่ backend สร้างให้ (คนละตัวกับ id ของ mock) แล้ว poll สถานะจนกว่างานจะจบ
 */
export async function uploadMeetingLive(input: UploadInput & { file?: File }): Promise<Uuid> {
  const id = await http.uploadMeeting(
    {
      series_id: input.series_id,
      sequence_no: input.sequence_no,
      meeting_date: input.meeting_date,
      source_kind: input.source_kind,
      simulate_asr_failure: input.simulate_asr_failure,
      file: input.file,
    },
    state.actor,
  );
  await loadFromServer();
  pollMeeting(id);
  return id;
}

/** ระหว่างประมวลผล ให้ดึงสถานะมาอัปเดตหน้าจอทุก 3 วินาทีจนกว่าจะเสร็จหรือพัง */
export function pollMeeting(meetingId: Uuid): void {
  const timer = setInterval(async () => {
    try {
      const { status } = await http.meetingStatus(meetingId);
      await loadFromServer(true);
      if (status !== "processing") clearInterval(timer);
    } catch {
      clearInterval(timer);
    }
  }, 3000);
  //  กันลูปค้างถ้า worker ตายกลางทาง
  setTimeout(() => clearInterval(timer), 10 * 60 * 1000);
}

/** FR-M2-05 retry ด้วยมือ */
export function retryMeeting(meetingId: Uuid) {
  mutate((db) => ({
    ...db,
    meetings: db.meetings.map((m) =>
      m.id === meetingId ? { ...m, status: "processing", pipeline: emptyPipeline() } : m,
    ),
  }));
  if (LIVE) {
    sync(() => http.retryMeeting(meetingId, state.actor));
    return;
  }
  runPipeline(meetingId, false);
}

/** อัปโหลดไฟล์ใหม่สำหรับ meeting เดิมที่ล้มเหลว (Re-upload Retry) */
export async function reuploadMeeting(
  meetingId: Uuid,
  file: File,
  simulate_asr_failure: boolean = false,
) {
  mutate((db) => ({
    ...db,
    meetings: db.meetings.map((m) =>
      m.id === meetingId
        ? {
            ...m,
            status: "processing",
            pipeline: emptyPipeline(),
            audio_uri: `minio://sara/uploads/${file.name}`,
            source_kind: /\.(txt|docx?)$/i.test(file.name) ? "transcript" : "audio",
          }
        : m,
    ),
  }));
  if (LIVE) {
    await http.reuploadMeeting(meetingId, file, simulate_asr_failure, state.actor);
    await loadFromServer();
    pollMeeting(meetingId);
    return;
  }
  runPipeline(meetingId, simulate_asr_failure);
}

function setStage(meetingId: Uuid, stage: PipelineStage, patch: Partial<Meeting["pipeline"][number]>) {
  mutate((db) => ({
    ...db,
    meetings: db.meetings.map((m) =>
      m.id === meetingId
        ? { ...m, pipeline: m.pipeline.map((p) => (p.stage === stage ? { ...p, ...patch } : p)) }
        : m,
    ),
  }));
}

const STAGE_MS: Record<PipelineStage, number> = {
  upload: 900,
  asr: 3200,
  extract: 2600,
  done: 300,
};

function runPipeline(meetingId: Uuid, failAsr: boolean) {
  const list: ReturnType<typeof setTimeout>[] = [];
  timers.set(meetingId, list);
  let t = 0;

  const schedule = (fn: () => void, delay: number) => {
    t += delay;
    list.push(setTimeout(fn, t));
  };

  for (const stage of STAGE_ORDER) {
    schedule(() => setStage(meetingId, stage, { state: "running" }), 120);

    if (stage === "asr" && failAsr) {
      schedule(() => {
        setStage(meetingId, "asr", {
          state: "failed",
          error:
            "ASR API ไม่ตอบสนอง (HTTP 504 หลัง retry 3 ครั้ง) — หยุด pipeline ไม่มีการสร้าง transcript ทดแทน",
        });
        mutate((db) => ({
          ...db,
          meetings: db.meetings.map((m) => (m.id === meetingId ? { ...m, status: "failed" } : m)),
        }));
      }, STAGE_MS.asr);
      return; // FR-M2-04: หยุดตรงนี้ ห้ามเดินต่อด้วยข้อมูลปลอม
    }

    schedule(() => {
      setStage(meetingId, stage, { state: "ok" });
      if (stage === "asr") ingestTranscript(meetingId);
      if (stage === "extract") runExtraction(meetingId);
      if (stage === "done") {
        mutate((db) => ({
          ...db,
          meetings: db.meetings.map((m) => (m.id === meetingId ? { ...m, status: "draft" } : m)),
        }));
      }
    }, STAGE_MS[stage]);
  }
}

function ingestTranscript(meetingId: Uuid) {
  const segments: TranscriptSegment[] = MEETING_6_SCRIPT.map((s, i) => {
    const guess = MEETING_6_SPEAKER_GUESS[s.speaker_label];
    return {
      id: `${meetingId}-s${i + 1}`,
      meeting_id: meetingId,
      speaker_label: s.speaker_label,
      person_id: guess && guess.confidence >= 0.85 ? guess.person_id : null,
      start_ms: s.start_ms,
      end_ms: s.start_ms + Math.max(5000, s.text.length * 130),
      text: s.text,
      confidence: s.confidence,
    };
  });
  mutate((db) => ({ ...db, segments: [...db.segments, ...segments] }));
}

/* ── M4 · Extraction + cross-meeting linking engine (mock) ───────────── */

function runExtraction(meetingId: Uuid) {
  const db = state.db;
  const meeting = db.meetings.find((m) => m.id === meetingId);
  if (!meeting) return;
  const segs = db.segments.filter((s) => s.meeting_id === meetingId);
  const find = (needle: string) => segs.find((s) => s.text.includes(needle));

  const proposals: Proposal[] = [];

  /* 1) จับคู่คำพูดใหม่กับการเพิ่มงบโฆษณา */
  const adSeg = find("เพิ่มงบ TikTok Ads อีก 20%");
  if (adSeg) {
    proposals.push({
      id: uid("prp"),
      meeting_id: meetingId,
      kind: "status_change",
      resolution_id: R.adBudget,
      proposed_status: "in_progress",
      title: "อนุมัติเพิ่มงบประมาณ TikTok Ads 20% สำหรับแคมเปญสัปดาห์ถัดไป",
      evidence_text: adSeg.text,
      evidence_start_ms: adSeg.start_ms,
      segment_id: adSeg.id,
      confidence: 0.95,
      decision: "pending",
    });
  }

  /* 2) Action item ใหม่: ปล่อย Hotfix บน iOS */
  const hotfixSeg = find("ปล่อย Hotfix ภายใน 22:00 น.");
  if (hotfixSeg) {
    proposals.push({
      id: uid("prp"),
      meeting_id: meetingId,
      kind: "new_resolution",
      resolution_id: null,
      title: "มอบหมายให้กานต์ (Lead Engineer) ปล่อย Hotfix แก้ไขปัญหา Push Notification บนระบบ iOS ภายใน 22:00 น. คืนนี้",
      evidence_text: hotfixSeg.text,
      evidence_start_ms: hotfixSeg.start_ms,
      segment_id: hotfixSeg.id,
      confidence: 0.97,
      decision: "pending",
    });
  }

  /* 4) ผู้พูดที่ระบบไม่มั่นใจ → ห้ามเดา ต้องถาม (FR-M3-03) */
  for (const [label, guess] of Object.entries(MEETING_6_SPEAKER_GUESS)) {
    if (guess.confidence >= 0.85) continue;
    const sample = segs.find((s) => s.speaker_label === label);
    if (!sample) continue;
    proposals.push({
      id: uid("prp"),
      meeting_id: meetingId,
      kind: "speaker_identity",
      resolution_id: null,
      speaker_label: label,
      candidate_person_ids: guess.candidates,
      title: `ระบุตัวผู้พูด ${label}`,
      evidence_text: sample.text,
      evidence_start_ms: sample.start_ms,
      segment_id: sample.id,
      confidence: guess.confidence,
      decision: "pending",
    });
  }

  /* บันทึกการอ้างถึง (referenced) ทุกมติที่ถูกพูดถึงในครั้งนี้ */
  const referenced = [
    { rid: R.adBudget, seg: adSeg },
  ].filter((x) => x.seg);

  mutate((db2) => ({
    ...db2,
    proposals: [...db2.proposals, ...proposals],
    links: [
      ...db2.links,
      ...referenced.map((x) => ({
        id: uid("lk"),
        resolution_id: x.rid,
        meeting_id: meetingId,
        link_type: "referenced" as const,
        segment_id: x.seg!.id,
        evidence_text: x.seg!.text,
        evidence_start_ms: x.seg!.start_ms,
        confidence: 0.9,
        created_at: nowIso(),
      })),
    ],
  }));
}

/* ── M3 · Person registry ────────────────────────────────────────────── */

export function upsertPerson(person: Partial<Person> & { id?: Uuid }) {
  mutate((db) => {
    if (person.id && db.people.some((p) => p.id === person.id)) {
      return {
        ...db,
        people: db.people.map((p) => (p.id === person.id ? { ...p, ...person } : p)),
      };
    }
    const id = person.id ?? uid("per");
    const created: Person = {
      id,
      org_id: db.org.id,
      full_name: person.full_name ?? "",
      position: person.position ?? "",
      department: person.department ?? "",
      email: person.email ?? "",
      is_active: person.is_active ?? true,
      is_department: person.is_department ?? false,
    };
    return audit({ ...db, people: [...db.people, created] }, "create_person", "person", id, created.full_name);
  });
  const { id: personId, ...rest } = person;
  sync(() => http.upsertPerson(rest, personId, state.actor));
}

export function deletePerson(id: Uuid) {
  mutate((db) => ({
    ...db,
    people: db.people.filter((p) => p.id !== id),
    aliases: db.aliases.filter((a) => a.person_id !== id),
  }));
  sync(() => http.deletePerson(id, state.actor));
}

/** FR-M3-04 ยืนยันครั้งแรก → จำถาวร */
export function addAlias(person_id: Uuid, alias: string, source: "manual" | "confirmed_extraction" = "manual", confidence = 1) {
  if (!alias.trim()) return;
  mutate((db) =>
    db.aliases.some((a) => a.person_id === person_id && a.alias === alias)
      ? db
      : audit(
          {
            ...db,
            aliases: [
              ...db.aliases,
              { id: uid("al"), person_id, alias: alias.trim(), source, confidence, created_at: nowIso() },
            ],
          },
          "add_alias",
          "person",
          person_id,
          alias,
        ),
  );
  sync(() => http.addAlias(person_id, alias.trim(), state.actor));
}

export function removeAlias(id: Uuid) {
  mutate((db) => ({ ...db, aliases: db.aliases.filter((a) => a.id !== id) }));
  sync(() => http.removeAlias(id, state.actor));
}

/** PATCH /meetings/{id}/speakers */
export function assignSpeaker(
  meetingId: Uuid,
  speaker_label: string,
  person_id: Uuid | null,
  save_alias?: string,
) {
  mutate((db) => ({
    ...db,
    segments: db.segments.map((s) =>
      s.meeting_id === meetingId && s.speaker_label === speaker_label ? { ...s, person_id } : s,
    ),
  }));
  sync(() => http.assignSpeaker(meetingId, speaker_label, person_id, save_alias, state.actor));
}

/* ── M4 · Resolution lifecycle ───────────────────────────────────────── */

/** POST /resolutions/{id}/status — ทุกครั้งต้องมีเหตุผลและบันทึกประวัติ */
export function changeResolutionStatus(
  id: Uuid,
  status: ResolutionStatus,
  reason: string,
  opts: {
    meeting_id?: Uuid | null;
    evidence?: string;
    evidence_start_ms?: number | null;
    segment_id?: Uuid | null;
    by?: string;
  } = {},
) {
  mutate((db) => {
    const target = db.resolutions.find((r) => r.id === id);
    if (!target) return db;
    const closing = status === "done";

    /* ลิงก์ที่มาจากการยืนยันของคนแทนที่ลิงก์ "ถูกอ้างถึง" ที่ระบบสร้างไว้เองในการประชุมเดียวกัน
       ไม่งั้นไทม์ไลน์จะมีหลักฐานท่อนเดียวกันโผล่ซ้ำสองบรรทัด */
    const baseLinks = opts.meeting_id
      ? db.links.filter(
          (l) => !(l.resolution_id === id && l.meeting_id === opts.meeting_id && l.link_type === "referenced"),
        )
      : db.links;
    return audit(
      {
        ...db,
        resolutions: db.resolutions.map((r) =>
          r.id === id
            ? {
                ...r,
                status,
                updated_at: nowIso(),
                closed_meeting_id: closing ? opts.meeting_id ?? r.closed_meeting_id : null,
                closed_at: closing ? nowIso() : null,
              }
            : r,
        ),
        history: [
          {
            id: uid("h"),
            resolution_id: id,
            field: "status",
            old_value: target.status,
            new_value: status,
            changed_by: opts.by ?? state.actor,
            changed_at: nowIso(),
            reason,
            source_meeting_id: opts.meeting_id ?? null,
          },
          ...db.history,
        ],
        links: opts.meeting_id
          ? [
              ...baseLinks,
              {
                id: uid("lk"),
                resolution_id: id,
                meeting_id: opts.meeting_id,
                link_type: closing ? ("closed" as const) : ("progress_reported" as const),
                segment_id: opts.segment_id ?? null,
                evidence_text: opts.evidence ?? reason,
                evidence_start_ms: opts.evidence_start_ms ?? null,
                confidence: 1,
                created_at: nowIso(),
              },
            ]
          : baseLinks,
      },
      "change_resolution_status",
      "resolution",
      id,
      `${target.status} → ${status}`,
    );
  });
  sync(() => http.setResolutionStatus(id, status, reason, opts.meeting_id ?? null, state.actor));
}

/** PATCH /resolutions/{id} — เก็บประวัติทุกฟิลด์ที่แก้ (FR-M4-08) */
export function updateResolution(id: Uuid, patch: Partial<Resolution>, reason = "แก้ไขด้วยผู้ใช้") {
  mutate((db) => {
    const target = db.resolutions.find((r) => r.id === id);
    if (!target) return db;

    const changes = Object.entries(patch).filter(
      ([k, v]) => JSON.stringify((target as unknown as Record<string, unknown>)[k]) !== JSON.stringify(v),
    );

    /* FR-M4-09 เลื่อนกำหนดนับเป็น postpone */
    const postponed =
      patch.due_date !== undefined && target.due_date && patch.due_date && patch.due_date > target.due_date;

    return {
      ...db,
      resolutions: db.resolutions.map((r) =>
        r.id === id
          ? {
              ...r,
              ...patch,
              postpone_count: postponed ? r.postpone_count + 1 : r.postpone_count,
              updated_at: nowIso(),
            }
          : r,
      ),
      history: [
        ...changes.map(([field, value]) => ({
          id: uid("h"),
          resolution_id: id,
          field,
          old_value: String((target as unknown as Record<string, unknown>)[field] ?? ""),
          new_value: String(value ?? ""),
          changed_by: state.actor,
          changed_at: nowIso(),
          reason,
        })),
        ...db.history,
      ],
    };
  });
  sync(() =>
    http.patchResolution(
      id,
      {
        ...(patch.text !== undefined ? { text: patch.text } : {}),
        ...(patch.due_date !== undefined ? { due_date: patch.due_date } : {}),
        ...(patch.assignee_ids !== undefined ? { assignee_ids: patch.assignee_ids } : {}),
        reason,
      },
      state.actor,
    ),
  );
}

/** FR-M4-07 มติใหม่แทนมติเก่า */
export function supersedeResolution(oldId: Uuid, newId: Uuid, reason: string) {
  mutate((db) => ({
    ...db,
    resolutions: db.resolutions.map((r) =>
      r.id === oldId ? { ...r, status: "superseded", superseded_by_id: newId, updated_at: nowIso() } : r,
    ),
    history: [
      {
        id: uid("h"),
        resolution_id: oldId,
        field: "status",
        old_value: "confirmed",
        new_value: "superseded",
        changed_by: state.actor,
        changed_at: nowIso(),
        reason,
      },
      ...db.history,
    ],
  }));
}

/* ── M9 · Review & approval ──────────────────────────────────────────── */

export function decideProposal(
  proposalId: Uuid,
  decision: "accepted" | "rejected",
  overrides: { text?: string; assignee_ids?: Uuid[]; due_date?: string | null; person_id?: Uuid | null; save_alias?: string } = {},
) {
  const proposal = state.db.proposals.find((p) => p.id === proposalId);
  if (!proposal) return;

  if (decision === "rejected") {
    mutate((db) => ({
      ...db,
      proposals: db.proposals.map((p) => (p.id === proposalId ? { ...p, decision } : p)),
    }));
    sync(() => http.decideProposal(proposal.meeting_id, proposalId, { decision }, state.actor));
    return;
  }

  if (proposal.kind === "status_change" && proposal.resolution_id && proposal.proposed_status) {
    changeResolutionStatus(proposal.resolution_id, proposal.proposed_status, "ยืนยันจากรายงานในที่ประชุม", {
      meeting_id: proposal.meeting_id,
      evidence: proposal.evidence_text,
      evidence_start_ms: proposal.evidence_start_ms,
      segment_id: proposal.segment_id,
    });
  }

  if (proposal.kind === "new_resolution") {
    const meeting = state.db.meetings.find((m) => m.id === proposal.meeting_id);
    const id = uid("res");
    const seriesRes = state.db.resolutions.filter((r) => r.series_id === meeting?.series_id);
    const itemNo = seriesRes.filter((r) => r.origin_meeting_id === proposal.meeting_id).length + 1;
    const created: Resolution = {
      id,
      series_id: meeting?.series_id ?? DEMO_SERIES_ID,
      ref_no: `มติ ${meeting?.sequence_no ?? "?"}/2569 ข้อ 4.${itemNo}`,
      origin_meeting_id: proposal.meeting_id,
      origin_segment_id: proposal.segment_id,
      origin_agenda_item: `วาระที่ 4.${itemNo}`,
      text: overrides.text ?? proposal.title,
      category: "other",
      status: "proposed",
      proposer_person_id: P.phat,
      assignee_ids: overrides.assignee_ids ?? [],
      due_date: overrides.due_date ?? null,
      original_due_date: overrides.due_date ?? null,
      postpone_count: 0,
      closed_meeting_id: null,
      closed_at: null,
      superseded_by_id: null,
      created_at: nowIso(),
      updated_at: nowIso(),
      extraction_confidence: proposal.confidence,
    };
    mutate((db) => ({
      ...db,
      resolutions: [...db.resolutions, created],
      links: [
        ...db.links,
        {
          id: uid("lk"),
          resolution_id: id,
          meeting_id: proposal.meeting_id,
          link_type: "created",
          segment_id: proposal.segment_id,
          evidence_text: proposal.evidence_text,
          evidence_start_ms: proposal.evidence_start_ms,
          confidence: proposal.confidence,
          created_at: nowIso(),
        },
      ],
    }));
  }

  if (proposal.kind === "speaker_identity" && proposal.speaker_label) {
    const personId = overrides.person_id ?? null;
    if (personId) {
      assignSpeaker(proposal.meeting_id, proposal.speaker_label, personId);
      if (overrides.save_alias) addAlias(personId, overrides.save_alias, "confirmed_extraction", proposal.confidence);
    }
  }

  mutate((db) => ({
    ...db,
    proposals: db.proposals.map((p) => (p.id === proposalId ? { ...p, decision } : p)),
  }));

  sync(() =>
    http.decideProposal(
      proposal.meeting_id,
      proposalId,
      {
        decision,
        text: overrides.text,
        assignee_ids: overrides.assignee_ids,
        due_date: overrides.due_date,
        person_id: overrides.person_id,
        save_alias: overrides.save_alias,
      },
      state.actor,
    ),
  );
}

export function setMeetingStatus(meetingId: Uuid, status: Meeting["status"]) {
  mutate((db) => {
    const meeting = db.meetings.find((m) => m.id === meetingId);
    const series = meeting ? db.series.find((s) => s.id === meeting.series_id) : null;
    const recipient = db.people.find((p) => !p.is_department && p.email);

    const existingSummaryAction = db.actions.find(
      (a) => a.meeting_id === meetingId && a.action_type === "send_meeting_summary_email"
    );

    const newActions = [...db.actions];
    if (status === "approved" && meeting && !existingSummaryAction) {
      const meetingRes = db.resolutions.filter((r) => r.origin_meeting_id === meetingId);
      const summaryText = meeting.summary || "สรุปสาระสำคัญจากการประชุม";
      const bodyText = `สรุปสาระสำคัญจากการประชุม${series?.name ?? ""} ครั้งที่ ${meeting.sequence_no}/${meeting.fiscal_year}\nเมื่อวันที่ ${formatThaiDate(meeting.meeting_date)}:\n\n${summaryText}`;

      newActions.unshift({
        id: uid("act"),
        series_id: meeting.series_id,
        meeting_id: meeting.id,
        resolution_id: null,
        action_type: "send_meeting_summary_email",
        recipient_person_id: recipient?.id ?? null,
        subject: `สรุปสาระสำคัญและมติการประชุม${series?.name ?? ""} ครั้งที่ ${meeting.sequence_no}/${meeting.fiscal_year}`,
        body: bodyText,
        scheduled_for: nowIso(),
        status: "pending_approval",
        approved_by: null,
        sent_at: null,
        error: null,
        created_at: nowIso(),
      });
    }

    return audit(
      {
        ...db,
        meetings: db.meetings.map((m) =>
          m.id === meetingId
            ? {
                ...m,
                status,
                approved_at: status === "approved" ? nowIso() : m.approved_at,
                approved_by: status === "approved" ? state.actor : m.approved_by,
              }
            : m,
        ),
        /* รับรองรายงาน → proposed เปลี่ยนเป็น confirmed อัตโนมัติ (ข้อเดียวที่ระบบทำเองได้) */
        resolutions:
          status === "approved"
            ? db.resolutions.map((r) =>
                r.origin_meeting_id === meetingId && r.status === "proposed"
                  ? { ...r, status: "confirmed" as const, updated_at: nowIso() }
                  : r,
              )
            : db.resolutions,
        actions: newActions,
      },
      `meeting_${status}`,
      "meeting",
      meetingId,
      status,
    );
  });
  if (status === "approved") sync(() => http.approveMeeting(meetingId, state.actor));
}

/* ── M5 · Agenda generation ──────────────────────────────────────────── */

/** POST /series/{id}/agenda/generate */
export function generateAgenda(series_id: Uuid): Uuid {
  const db = state.db;
  const ser = db.series.find((s) => s.id === series_id);
  const held = db.meetings.filter((m) => m.series_id === series_id);
  const lastSeq = held.reduce((max, m) => Math.max(max, m.sequence_no), 0);
  const lastMeeting = held.find((m) => m.sequence_no === lastSeq);
  const draftId = uid("agd");
  const items: AgendaItem[] = [];
  let order = 0;

  const push = (section_no: AgendaItem["section_no"], item_no: number, title: string, body: string, resolution_id: Uuid | null = null) => {
    items.push({ id: uid("agi"), agenda_draft_id: draftId, section_no, item_no, title, body, resolution_id, sort_order: order++ });
  };

  push(1, 1, "เรื่องที่ประธานแจ้งให้ที่ประชุมทราบ", "");
  push(
    2,
    1,
    `รับรองรายงานการประชุมครั้งที่ ${lastSeq}/2569`,
    lastMeeting
      ? `เมื่อวันที่ ${formatThaiDate(lastMeeting.meeting_date)} ฝ่ายเลขานุการได้จัดทำรายงานการประชุมเสร็จเรียบร้อยแล้ว จึงเสนอที่ประชุมเพื่อพิจารณารับรอง`
      : "",
  );

  /* วาระ 3 เรื่องสืบเนื่อง — จากมติค้างของ series (FR-M5-01, 03) */
  const open = db.resolutions
    .filter((r) => r.series_id === series_id && OPEN_STATUSES.includes(r.status))
    .sort((a, b) => overdueDays(b) - overdueDays(a));

  open.forEach((r, i) => {
    const assignees = r.assignee_ids.map((id) => db.people.find((p) => p.id === id)?.full_name).filter(Boolean).join(", ");
    const od = overdueDays(r);
    /* หัวข้อวาระเขียนเป็น "เรื่อง ..." ตามรูปแบบราชการ
       เก็บข้อความเต็มไว้เสมอ ห้ามตัดด้วย "…" เพราะจะติดไปในเอกสารราชการที่ export
       ถ้ายาวเกินในหน้าจอ ให้ตัดด้วย CSS ที่ชั้นแสดงผลแทน */
    const topic = r.text.replace(/^(ที่ประชุมมีมติให้|มอบหมายให้|อนุมัติให้|อนุมัติ|ให้)\s*/, "");
    push(
      3,
      i + 1,
      `เรื่อง ${topic}`,
      [
        `มติเดิม: “${r.text}”`,
        `ที่มา: การประชุมครั้งที่ ${db.meetings.find((m) => m.id === r.origin_meeting_id)?.sequence_no ?? "-"}/2569 ${r.origin_agenda_item ?? ""} (${r.ref_no})`,
        `ผู้รับผิดชอบ: ${assignees || "-"}`,
        `กำหนดแล้วเสร็จ: ${r.due_date ? formatThaiDate(r.due_date) : "ไม่ระบุ"}`,
        `สถานะปัจจุบัน: ${STATUS_LABEL_TH[r.status]}${od > 0 ? ` · เกินกำหนดแล้ว ${od} วัน` : ""}`,
        r.postpone_count >= 3 ? `⚑ มติข้อนี้ถูกเลื่อนกำหนดมาแล้ว ${r.postpone_count} ครั้ง` : "",
        "จึงเสนอที่ประชุมเพื่อทราบและพิจารณาเร่งรัดการดำเนินการ",
      ]
        .filter(Boolean)
        .join("\n"),
      r.id,
    );
  });

  push(4, 1, "เรื่องเสนอเพื่อพิจารณา", "(ฝ่ายเลขานุการเพิ่มเติมตามที่ได้รับแจ้ง)");
  push(5, 1, "เรื่องอื่น ๆ", "");

  const draft: AgendaDraft = {
    id: draftId,
    series_id,
    target_meeting_date: ser?.next_meeting_date ?? "",
    target_sequence_no: lastSeq + 1,
    status: "draft",
    created_at: nowIso(),
    items,
  };
  mutate((db2) => audit({ ...db2, agendas: [draft, ...db2.agendas.filter((a) => a.series_id !== series_id)] }, "generate_agenda", "agenda_draft", draftId, `ครั้งที่ ${lastSeq + 1}/2569`));
  sync(() => http.generateAgenda(series_id, state.actor));
  return draftId;
}

export function updateAgendaItems(draftId: Uuid, items: AgendaItem[]) {
  mutate((db) => ({
    ...db,
    agendas: db.agendas.map((a) => (a.id === draftId ? { ...a, items } : a)),
  }));
  sync(() => http.patchAgendaItems(draftId, items, state.actor));
}

export function moveAgendaItem(draftId: Uuid, itemId: Uuid, dir: -1 | 1) {
  const draft = state.db.agendas.find((a) => a.id === draftId);
  if (!draft) return;
  const item = draft.items.find((i) => i.id === itemId);
  if (!item) return;
  const siblings = draft.items.filter((i) => i.section_no === item.section_no).sort((a, b) => a.sort_order - b.sort_order);
  const idx = siblings.findIndex((i) => i.id === itemId);
  const swap = siblings[idx + dir];
  if (!swap) return;
  const items = draft.items.map((i) =>
    i.id === item.id ? { ...i, sort_order: swap.sort_order } : i.id === swap.id ? { ...i, sort_order: item.sort_order } : i,
  );
  updateAgendaItems(draftId, items);
}

export function removeAgendaItem(draftId: Uuid, itemId: Uuid) {
  const draft = state.db.agendas.find((a) => a.id === draftId);
  if (!draft) return;
  updateAgendaItems(draftId, draft.items.filter((i) => i.id !== itemId));
}

export function addAgendaItem(draftId: Uuid, section_no: AgendaItem["section_no"]) {
  const draft = state.db.agendas.find((a) => a.id === draftId);
  if (!draft) return;
  const item: AgendaItem = {
    id: uid("agi"),
    agenda_draft_id: draftId,
    section_no,
    item_no: draft.items.filter((i) => i.section_no === section_no).length + 1,
    title: "เรื่องใหม่",
    body: "",
    resolution_id: null,
    sort_order: Math.max(0, ...draft.items.map((i) => i.sort_order)) + 1,
  };
  updateAgendaItems(draftId, [...draft.items, item]);
}

export function editAgendaItem(draftId: Uuid, itemId: Uuid, patch: Partial<AgendaItem>) {
  const draft = state.db.agendas.find((a) => a.id === draftId);
  if (!draft) return;
  updateAgendaItems(draftId, draft.items.map((i) => (i.id === itemId ? { ...i, ...patch } : i)));
}

/* ── M7 · Outbound actions ───────────────────────────────────────────── */

export function queueAction(action: Omit<OutboundAction, "id" | "created_at" | "status" | "approved_by" | "sent_at" | "error">) {
  const id = uid("act");
  mutate((db) => ({
    ...db,
    actions: [
      { ...action, id, status: "pending_approval", approved_by: null, sent_at: null, error: null, created_at: nowIso() },
      ...db.actions,
    ],
  }));
  return id;
}

/** POST /actions/{id}/approve → ส่งจริง */
export function approveAction(id: Uuid) {
  mutate((db) =>
    audit(
      {
        ...db,
        actions: db.actions.map((a) =>
          a.id === id ? { ...a, status: "sent", approved_by: state.actor, sent_at: nowIso() } : a,
        ),
      },
      "approve_outbound_action",
      "outbound_action",
      id,
      "อนุมัติและส่งออก",
    ),
  );
  sync(() => http.approveAction(id, state.actor));
}

export function cancelAction(id: Uuid) {
  mutate((db) => ({
    ...db,
    actions: db.actions.map((a) => (a.id === id ? { ...a, status: "cancelled" } : a)),
  }));
  sync(() => http.cancelAction(id, state.actor));
}

/* ── M8 · Cross-meeting Q&A (mock retrieval) ─────────────────────────── */

export function askSeries(series_id: Uuid, question: string): QaAnswer {
  const db = state.db;
  const grams = [...new Set(thaiGrams(question))];

  const scored = db.resolutions
    .filter((r) => r.series_id === series_id)
    .map((r) => ({ r, score: relevance(`${r.text} ${r.ref_no}`, grams) }))
    .filter((x) => x.score >= 0.1)
    .sort((a, b) => b.score - a.score);

  const meetingOf = (id: Uuid) => db.meetings.find((m) => m.id === id);
  let answer: QaAnswer;

  if (scored.length > 0) {
    const top = scored[0].r;
    const relLinks = db.links
      .filter((l) => l.resolution_id === top.id)
      .sort((a, b) => a.created_at.localeCompare(b.created_at));
    answer = {
      id: uid("qa"),
      question,
      source: "resolution_table",
      answer:
        `พบมติที่เกี่ยวข้อง ${scored.length} ข้อในชุดการประชุมนี้ เรื่องที่ตรงที่สุดคือ ${top.ref_no}\n\n` +
        `“${top.text}”\n\n` +
        `สถานะปัจจุบัน: ${STATUS_LABEL_TH[top.status]}` +
        (top.due_date ? ` · กำหนดแล้วเสร็จ ${formatThaiDate(top.due_date)}` : "") +
        (overdueDays(top) > 0 ? ` · เกินกำหนดแล้ว ${overdueDays(top)} วัน` : "") +
        (top.postpone_count >= 3 ? ` · เลื่อนกำหนดมาแล้ว ${top.postpone_count} ครั้ง` : "") +
        (scored.length > 1
          ? `\n\nมติอื่นที่เกี่ยวข้อง: ${scored
              .slice(1, 4)
              .map((s) => `${s.r.ref_no} (${STATUS_LABEL_TH[s.r.status]})`)
              .join(" · ")}`
          : ""),
      citations: relLinks.map((l) => ({
        meeting_id: l.meeting_id,
        segment_id: l.segment_id,
        resolution_id: l.resolution_id,
        start_ms: l.evidence_start_ms,
        quote: l.evidence_text,
      })),
      timeline: relLinks.map((l) => ({
        meeting_id: l.meeting_id,
        date: meetingOf(l.meeting_id)?.meeting_date ?? "",
        label: `ครั้งที่ ${meetingOf(l.meeting_id)?.sequence_no ?? "?"}/2569 · ${LINK_LABEL_TH[l.link_type]}`,
        detail: l.evidence_text,
      })),
      asked_at: nowIso(),
    };
  } else {
    const hits = db.segments
      .filter((s) => db.meetings.find((m) => m.id === s.meeting_id)?.series_id === series_id)
      .map((s) => ({ s, score: relevance(s.text, grams) }))
      .filter((x) => x.score >= 0.08)
      .sort((a, b) => b.score - a.score)
      .slice(0, 4)
      .map((x) => x.s);
    answer = {
      id: uid("qa"),
      question,
      source: "semantic_search",
      answer:
        hits.length > 0
          ? `ไม่พบมติที่ตรงกับคำถามในทะเบียนมติ จึงค้นจากคำต่อคำในบันทึกการประชุม พบข้อความที่เกี่ยวข้อง ${hits.length} จุด ตามที่อ้างอิงด้านล่าง`
          : "ไม่พบข้อมูลที่เกี่ยวข้องในชุดการประชุมนี้ ระบบจะไม่คาดเดาคำตอบเมื่อไม่มีหลักฐานอ้างอิง",
      citations: hits.map((s) => ({
        meeting_id: s.meeting_id,
        segment_id: s.id,
        resolution_id: null,
        start_ms: s.start_ms,
        quote: s.text,
      })),
      timeline: [],
      asked_at: nowIso(),
    };
  }

  mutate((db2) => ({
    ...db2,
    qa: { ...db2.qa, [series_id]: [...(db2.qa[series_id] ?? []), answer] },
  }));
  return answer;
}

/** เก็บคำตอบที่ได้จาก backend ลง state เพื่อให้หน้าถาม-ตอบแสดงประวัติได้เหมือนกัน */
export function appendQa(series_id: Uuid, answer: QaAnswer) {
  mutate((db) => ({
    ...db,
    qa: { ...db.qa, [series_id]: [...(db.qa[series_id] ?? []), answer] },
  }));
}

export function clearQa(series_id: Uuid) {
  mutate((db) => ({ ...db, qa: { ...db.qa, [series_id]: [] } }));
}

/* ── ตรรกะโดเมนล้วน อยู่ใน lib/domain.ts เพื่อให้ทดสอบได้โดยไม่ต้องมี React ───
   re-export ไว้ที่นี่ให้หน้าจอ import จากที่เดียว                              */
export {
  LINK_LABEL_TH,
  NEXT_STATUSES,
  OPEN_STATUSES,
  STATUS_LABEL_TH,
  TODAY,
  assigneeNames,
  daysUntil,
  formatEnDate,
  formatThaiDate,
  formatTimecode,
  isOpen,
  overdueDays,
  personName,
  relevance,
  seriesStats,
  shortText,
  thaiGrams,
  type SeriesStats,
} from "./domain";
