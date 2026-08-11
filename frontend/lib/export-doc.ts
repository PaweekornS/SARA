"use client";

/**
 * สร้างเอกสาร .doc ที่เปิดแก้ต่อใน Word ได้ (FR-M5-04, FR-M5-05)
 *
 * ponytail: ฝั่ง client ใช้ HTML-for-Word (Word เปิด/แก้ไข/save as .docx ได้ทันที)
 * แทนที่จะลาก library OOXML เข้ามาทั้งก้อน — ของจริงตาม §M5 หมายเหตุ implementation
 * ให้ backend เรนเดอร์ด้วย python-docx จากไฟล์ .docx ต้นแบบขององค์กร
 * แล้วเปลี่ยนปุ่มดาวน์โหลดให้ชี้ /agenda/{id}/export?format=docx
 */

import {
  STATUS_LABEL_TH,
  assigneeNames,
  escapeHtml as esc,
  formatThaiDate,
  overdueDays,
  toThaiNumeral,
} from "./domain";
import type { AgendaDraft, Database, Meeting, Uuid } from "./types";

/* หน้าตัวอย่างเอกสารบนจอใช้เลขไทยชุดเดียวกับไฟล์ที่ export ออกไป */
export { toThaiNumeral };

const SECTION_TITLES: Record<number, string> = {
  1: "ระเบียบวาระที่ ๑ เรื่องที่ประธานแจ้งให้ที่ประชุมทราบ",
  2: "ระเบียบวาระที่ ๒ เรื่องรับรองรายงานการประชุม",
  3: "ระเบียบวาระที่ ๓ เรื่องสืบเนื่องจากการประชุมครั้งก่อน",
  4: "ระเบียบวาระที่ ๔ เรื่องเสนอเพื่อพิจารณา",
  5: "ระเบียบวาระที่ ๕ เรื่องอื่น ๆ",
};

/** ระเบียบสารบรรณ: TH Sarabun New 16 pt */
const DOC_HEAD = `<!DOCTYPE html>
<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word">
<head><meta charset="utf-8"/>
<!--[if gte mso 9]><xml><w:WordDocument><w:View>Print</w:View><w:Zoom>100</w:Zoom></w:WordDocument></xml><![endif]-->
<style>
@page { size: A4; margin: 2.54cm 2cm 2cm 3cm; }
body { font-family: "TH Sarabun New", "Sarabun", serif; font-size: 16pt; line-height: 1.25; }
h1, h2, h3 { font-family: "TH Sarabun New", "Sarabun", serif; font-weight: bold; }
h1 { font-size: 20pt; text-align: center; margin: 0 0 4pt; }
h2 { font-size: 18pt; text-align: center; font-weight: normal; margin: 0 0 18pt; }
h3 { font-size: 16pt; margin: 16pt 0 6pt; }
p { margin: 0 0 6pt; text-indent: 0; }
.indent { margin-left: 1.27cm; }
.meta { font-size: 16pt; }
table { border-collapse: collapse; width: 100%; font-size: 15pt; }
td, th { border: 1px solid #000; padding: 4pt 6pt; vertical-align: top; }
th { background: #eee; }
.sign { margin-top: 36pt; width: 100%; }
.sign td { border: none; text-align: center; }
.flag { font-weight: bold; }
</style></head><body>`;

const DOC_FOOT = `</body></html>`;

export function downloadDoc(filename: string, html: string) {
  const blob = new Blob(["﻿", html], { type: "application/msword;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename.endsWith(".doc") ? filename : `${filename}.doc`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function signatureBlock() {
  return `<table class="sign"><tr>
<td>(ลงชื่อ) .................................................. ผู้จดรายงานการประชุม<br/><br/>(..................................................)</td>
<td>(ลงชื่อ) .................................................. ผู้ตรวจรายงานการประชุม<br/><br/>(..................................................)</td>
</tr></table>`;
}

/* ── ร่างระเบียบวาระ ─────────────────────────────────────────────────── */

export function buildAgendaHtml(db: Database, draft: AgendaDraft): string {
  const ser = db.series.find((s) => s.id === draft.series_id);
  const parts: string[] = [DOC_HEAD];

  parts.push(`<h1>ระเบียบวาระการประชุม${esc(ser?.name ?? "")}</h1>`);
  parts.push(
    `<h2>ครั้งที่ ${toThaiNumeral(draft.target_sequence_no)}/${toThaiNumeral(ser?.fiscal_year ?? 2569)}` +
      (draft.target_meeting_date ? `<br/>วันที่ ${toThaiNumeral(formatThaiDate(draft.target_meeting_date))}` : "") +
      `</h2>`,
  );

  for (const section of [1, 2, 3, 4, 5] as const) {
    const items = draft.items.filter((i) => i.section_no === section).sort((a, b) => a.sort_order - b.sort_order);
    parts.push(`<h3>${SECTION_TITLES[section]}</h3>`);
    if (items.length === 0) {
      parts.push(`<p class="indent">(ไม่มี)</p>`);
      continue;
    }
    items.forEach((item, idx) => {
      const heading =
        section === 3
          ? `${toThaiNumeral(section)}.${toThaiNumeral(idx + 1)} ${esc(item.title)}`
          : items.length > 1
            ? `${toThaiNumeral(section)}.${toThaiNumeral(idx + 1)} ${esc(item.title)}`
            : esc(item.title);
      parts.push(`<p class="indent"><b>${heading}</b></p>`);
      if (item.body) parts.push(`<p class="indent">${esc(item.body)}</p>`);
    });
  }

  /* ตารางสรุปมติค้าง แนบท้ายวาระ ให้ประธานเห็นภาพรวมในหน้าเดียว */
  const open = draft.items
    .filter((i) => i.section_no === 3 && i.resolution_id)
    .map((i) => db.resolutions.find((r) => r.id === i.resolution_id))
    .filter(Boolean);

  if (open.length > 0) {
    parts.push(`<h3>เอกสารแนบ ๑ สรุปสถานะมติค้างดำเนินการ</h3>`);
    parts.push(
      `<table><tr><th style="width:6%">ลำดับ</th><th style="width:34%">มติ</th><th style="width:16%">ที่มา</th>` +
        `<th style="width:18%">ผู้รับผิดชอบ</th><th style="width:14%">กำหนด</th><th style="width:12%">สถานะ</th></tr>`,
    );
    open.forEach((r, i) => {
      const od = overdueDays(r!);
      parts.push(
        `<tr><td>${toThaiNumeral(i + 1)}</td><td>${esc(r!.text)}</td><td>${esc(r!.ref_no)}</td>` +
          `<td>${esc(assigneeNames(db, r!).map((p) => p.full_name).join(", ") || "-")}</td>` +
          `<td>${r!.due_date ? toThaiNumeral(formatThaiDate(r!.due_date)) : "-"}</td>` +
          `<td>${STATUS_LABEL_TH[r!.status]}${od > 0 ? `<br/><span class="flag">เกิน ${toThaiNumeral(od)} วัน</span>` : ""}</td></tr>`,
      );
    });
    parts.push(`</table>`);
  }

  parts.push(signatureBlock(), DOC_FOOT);
  return parts.join("\n");
}

/* ── รายงานการประชุมฉบับเต็ม ─────────────────────────────────────────── */

export function buildMinutesHtml(db: Database, meeting: Meeting): string {
  const ser = db.series.find((s) => s.id === meeting.series_id);
  const segs = db.segments.filter((s) => s.meeting_id === meeting.id).sort((a, b) => a.start_ms - b.start_ms);
  const resolutions = db.resolutions.filter((r) => r.origin_meeting_id === meeting.id);
  const attendees = new Set<Uuid>();
  segs.forEach((s) => s.person_id && attendees.add(s.person_id));

  const parts: string[] = [DOC_HEAD];
  parts.push(`<h1>รายงานการประชุม${esc(ser?.name ?? "")}</h1>`);
  parts.push(
    `<h2>ครั้งที่ ${toThaiNumeral(meeting.sequence_no)}/${toThaiNumeral(meeting.fiscal_year)}<br/>` +
      `เมื่อวันที่ ${toThaiNumeral(formatThaiDate(meeting.meeting_date))}</h2>`,
  );

  parts.push(`<p class="meta"><b>ผู้มาประชุม</b></p>`);
  const list = [...attendees].map((id) => db.people.find((p) => p.id === id)).filter(Boolean);
  (list.length > 0 ? list : db.people.filter((p) => ser?.member_ids.includes(p.id))).forEach((p, i) => {
    parts.push(`<p class="indent">${toThaiNumeral(i + 1)}. ${esc(p!.full_name)} ${esc(p!.position)}</p>`);
  });

  parts.push(`<p class="meta"><b>เริ่มประชุมเวลา</b> ๐๙.๐๐ น.</p>`);

  parts.push(`<h3>${SECTION_TITLES[1]}</h3>`);
  parts.push(`<p class="indent">ประธานกล่าวเปิดการประชุมและแจ้งให้ที่ประชุมทราบตามระเบียบวาระ</p>`);

  parts.push(`<h3>${SECTION_TITLES[2]}</h3>`);
  parts.push(
    `<p class="indent">ที่ประชุมพิจารณารายงานการประชุมครั้งที่ ${toThaiNumeral(meeting.sequence_no - 1)}/${toThaiNumeral(meeting.fiscal_year)} แล้ว มีมติรับรองรายงานการประชุม</p>`,
  );

  parts.push(`<h3>${SECTION_TITLES[4]}</h3>`);
  resolutions.forEach((r, i) => {
    parts.push(`<p class="indent"><b>${toThaiNumeral(4)}.${toThaiNumeral(i + 1)} ${esc(r.text.slice(0, 60))}</b></p>`);
    parts.push(`<p class="indent"><b>มติที่ประชุม</b> ${esc(r.text)}</p>`);
    const who = assigneeNames(db, r).map((p) => p.full_name).join(", ");
    if (who) parts.push(`<p class="indent">ผู้รับผิดชอบ ${esc(who)}${r.due_date ? ` กำหนดแล้วเสร็จภายในวันที่ ${toThaiNumeral(formatThaiDate(r.due_date))}` : ""}</p>`);
  });

  parts.push(`<h3>${SECTION_TITLES[5]}</h3>`);
  parts.push(`<p class="indent">ไม่มี</p>`);
  parts.push(`<p class="meta"><b>เลิกประชุมเวลา</b> ๑๒.๐๐ น.</p>`);

  /* บันทึกคำต่อคำแนบท้าย — เป็นหลักฐานให้ตรวจย้อนกลับได้ */
  parts.push(`<h3>เอกสารแนบ ๑ บันทึกถ้อยคำการประชุม</h3>`);
  parts.push(`<table><tr><th style="width:12%">เวลา</th><th style="width:22%">ผู้พูด</th><th>ข้อความ</th></tr>`);
  segs.forEach((s) => {
    const name = s.person_id ? db.people.find((p) => p.id === s.person_id)?.full_name : s.speaker_label;
    const mm = Math.floor(s.start_ms / 60000);
    const ss = Math.floor((s.start_ms % 60000) / 1000);
    parts.push(
      `<tr><td>${toThaiNumeral(String(mm).padStart(2, "0"))}:${toThaiNumeral(String(ss).padStart(2, "0"))}</td>` +
        `<td>${esc(name ?? "-")}</td><td>${esc(s.text)}</td></tr>`,
    );
  });
  parts.push(`</table>`);

  parts.push(signatureBlock(), DOC_FOOT);
  return parts.join("\n");
}
