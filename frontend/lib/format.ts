/** รูปแบบวันที่/เวลาที่หน้าจอใช้ — ไม่มี dependency เพื่อให้ทดสอบด้วย node --test ได้ตรง ๆ */

const THAI_MONTHS = [
  "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
  "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
];
const THAI_MONTHS_SHORT = [
  "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
  "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.",
];

/** รับ "YYYY-MM-DD" หรือ ISO datetime — วันที่ล้วนอ่านเป็นวันที่ท้องถิ่น ไม่ให้เลื่อนวันเพราะ timezone */
function parse(value: string): Date | null {
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  const d = dateOnly ? new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3])) : new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatThaiDate(value: string | null | undefined, short = false): string {
  if (!value) return "-";
  const d = parse(value);
  if (!d) return value;
  const month = (short ? THAI_MONTHS_SHORT : THAI_MONTHS)[d.getMonth()];
  return `${d.getDate()} ${month} ${d.getFullYear() + 543}`;
}

export function formatTimecode(ms: number | null | undefined): string {
  if (ms == null) return "--:--";
  const total = Math.floor(ms / 1000);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

export function todayIso(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** จำนวนวันจากวันนี้ถึงกำหนด (ติดลบ = เลยกำหนดแล้ว) */
export function daysUntil(value: string, today: string = todayIso()): number {
  const a = parse(today);
  const b = parse(value);
  if (!a || !b) return 0;
  return Math.round((b.getTime() - a.getTime()) / 86_400_000);
}

/** ชื่อที่แสดงของผู้พูด — ใช้ชื่อที่ผู้ใช้ตั้งถ้ามี */
export function speakerLabel(segment: { speaker_label: string; speaker_name: string }): string {
  return segment.speaker_name || segment.speaker_label.replace(/^SPEAKER_0*(\d+)$/, (_, n) => `ผู้พูด ${Number(n) + 1}`);
}
