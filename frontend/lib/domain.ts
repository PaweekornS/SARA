/**
 * ตรรกะโดเมนล้วน ๆ — ไม่มี React ไม่มี state ทดสอบได้ตรง ๆ ด้วย node
 *   node --experimental-strip-types --test lib/domain.test.ts
 */

import type { Database, Person, Resolution, ResolutionStatus, Uuid } from "./types";

export const STATUS_LABEL_TH: Record<ResolutionStatus, string> = {
  proposed: "รอรับรอง",
  confirmed: "รับรองแล้ว",
  in_progress: "กำลังดำเนินการ",
  blocked: "ติดปัญหา",
  done: "ดำเนินการแล้วเสร็จ",
  cancelled: "ยกเลิก",
  superseded: "ถูกแทนที่",
};

export const LINK_LABEL_TH: Record<string, string> = {
  created: "เกิดมติ",
  referenced: "ถูกอ้างถึง",
  progress_reported: "รายงานความคืบหน้า",
  closed: "ปิดมติ",
  superseded: "ถูกแทนที่",
};

/** state machine ตาม §4.1 — ระบบเปลี่ยนเองได้แค่ proposed → confirmed ที่เหลือคนต้องกด */
export const NEXT_STATUSES: Record<ResolutionStatus, ResolutionStatus[]> = {
  proposed: ["confirmed", "cancelled"],
  confirmed: ["in_progress", "blocked", "done", "cancelled", "superseded"],
  in_progress: ["blocked", "done", "cancelled"],
  blocked: ["in_progress", "done", "cancelled"],
  done: ["in_progress"],
  cancelled: ["confirmed"],
  superseded: [],
};

export const OPEN_STATUSES: ResolutionStatus[] = ["confirmed", "in_progress", "blocked"];

/** วันปัจจุบันของเดโม — ตรึงไว้ให้ตัวเลข "เกินกำหนด" คงที่ตอนนำเสนอ */
export const TODAY = "2026-08-11";

export function isOpen(r: Resolution) {
  return OPEN_STATUSES.includes(r.status);
}

/** มติที่ปิด/ยกเลิก/ถูกแทนที่แล้ว ไม่นับว่าเกินกำหนด ต่อให้เลยวันมาแล้วก็ตาม */
export function overdueDays(r: Resolution, today = TODAY): number {
  if (!r.due_date || !isOpen(r)) return 0;
  const diff = Date.parse(today) - Date.parse(r.due_date);
  return diff <= 0 ? 0 : Math.floor(diff / 86_400_000);
}

export function daysUntil(date: string, today = TODAY): number {
  return Math.round((Date.parse(date) - Date.parse(today)) / 86_400_000);
}

const THAI_MONTHS = [
  "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
  "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
];

const THAI_MONTHS_SHORT = [
  "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
  "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.",
];

/** พ.ศ. = ค.ศ. + 543 ตามระเบียบสารบรรณ */
export function formatThaiDate(iso: string, short = false) {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const month = short ? THAI_MONTHS_SHORT[d.getMonth()] : THAI_MONTHS[d.getMonth()];
  return `${d.getDate()} ${month} ${d.getFullYear() + 543}`;
}

export function formatEnDate(iso: string) {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export function formatTimecode(ms: number | null) {
  if (ms == null) return "--:--";
  const total = Math.floor(ms / 1000);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

export function shortText(text: string, max: number) {
  return text.length <= max ? text : `${text.slice(0, max).trimEnd()}…`;
}

const THAI_DIGITS = ["๐", "๑", "๒", "๓", "๔", "๕", "๖", "๗", "๘", "๙"];

/** เลขไทยสำหรับหัวข้อวาระและเลขครั้งที่ ตามระเบียบสารบรรณ */
export function toThaiNumeral(n: number | string) {
  return String(n).replace(/\d/g, (d) => THAI_DIGITS[Number(d)]);
}

/** ข้อความจากผู้ใช้ทุกชิ้นต้องผ่านตัวนี้ก่อนลงเอกสาร ไม่งั้นเอกสารพังหรือถูกฝังสคริปต์ */
export function escapeHtml(s: string) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\n/g, "<br/>");
}

/* ── การค้นแบบทนภาษาไทย ──────────────────────────────────────────────
   ภาษาไทยไม่เว้นวรรคระหว่างคำ การตัดด้วยช่องว่างจึงพลาดเกือบทุกครั้ง
   จึงเทียบด้วย n-gram ระดับตัวอักษรแทน — หยาบแต่ใช้ได้จริงโดยไม่ต้องมี tokenizer
   ของจริงให้เปลี่ยนไปใช้ embedding + pgvector ตามคำถามข้อ 3 ใน §14
   ------------------------------------------------------------------- */

const NGRAM = 5;

function normalize(text: string) {
  return text.replace(/[\s.,!?"'()“”]/g, "");
}

export function thaiGrams(text: string): string[] {
  const clean = normalize(text);
  const grams: string[] = [];
  for (let i = 0; i + NGRAM <= clean.length; i++) grams.push(clean.slice(i, i + NGRAM));
  return [...new Set(grams)];
}

/** สัดส่วน n-gram ของคำถามที่พบในข้อความ 0..1 */
export function relevance(haystack: string, questionGrams: string[]): number {
  if (questionGrams.length === 0) return 0;
  const hay = normalize(haystack);
  return questionGrams.filter((g) => hay.includes(g)).length / questionGrams.length;
}

/* ── สถิติระดับชุดการประชุม ──────────────────────────────────────────── */

export interface SeriesStats {
  total: number;
  open: number;
  done: number;
  overdue: number;
  flagged: number;
  closureRate: number;
  avgDaysToClose: number;
}

export function seriesStats(db: Database, series_id: Uuid, today = TODAY): SeriesStats {
  const rs = db.resolutions.filter((r) => r.series_id === series_id);
  const done = rs.filter((r) => r.status === "done");
  /* มติที่ยกเลิก/ถูกแทนที่ ไม่ควรถูกนับเป็นตัวหารของอัตราการปิด เพราะไม่เคยต้องปิด */
  const closable = rs.filter((r) => r.status !== "cancelled" && r.status !== "superseded");
  const durations = done
    .filter((r) => r.closed_at)
    .map((r) => (Date.parse(r.closed_at!) - Date.parse(r.created_at)) / 86_400_000);
  return {
    total: rs.length,
    open: rs.filter(isOpen).length,
    done: done.length,
    overdue: rs.filter((r) => overdueDays(r, today) > 0).length,
    flagged: rs.filter((r) => r.postpone_count >= 3 && isOpen(r)).length,
    closureRate: closable.length === 0 ? 0 : Math.round((done.length / closable.length) * 100),
    avgDaysToClose:
      durations.length === 0 ? 0 : Math.round(durations.reduce((a, b) => a + b, 0) / durations.length),
  };
}

export function personName(db: Database, id: Uuid | null | undefined) {
  if (!id) return "-";
  return db.people.find((p) => p.id === id)?.full_name ?? "-";
}

/** ถ้ามอบทั้งหน่วยงานและบุคคล ให้ขึ้นหน่วยงานก่อน อ่านแล้วรู้ทันทีว่าใครรับผิดชอบจริง */
export function assigneeNames(db: Database, r: Resolution): Person[] {
  const list = r.assignee_ids.map((id) => db.people.find((p) => p.id === id)).filter(Boolean) as Person[];
  return list.sort((a, b) => Number(b.is_department) - Number(a.is_department));
}
