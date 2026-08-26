/**
 * Domain Logic Unit Tests
 * Run: node --experimental-strip-types --test lib/domain.test.ts
 */

import assert from "node:assert/strict";
import test from "node:test";
import {
  NEXT_STATUSES,
  escapeHtml,
  formatThaiDate,
  formatTimecode,
  isOpen,
  overdueDays,
  relevance,
  seriesStats,
  thaiGrams,
  toThaiNumeral,
} from "./domain.ts";
import { createSeedDatabase, DEMO_SERIES_ID, R } from "./seed.ts";
import type { Resolution } from "./types.ts";

const db = createSeedDatabase();
const res = (id: string) => db.resolutions.find((r) => r.id === id)!;

test("เกินกำหนดนับจากวันปัจจุบันของเดโม และนับเฉพาะมติที่ยังไม่ปิด", () => {
  const overdueRes: Resolution = {
    ...res(R.adBudget),
    status: "in_progress",
    due_date: "2026-07-18",
  };
  assert.equal(overdueDays(overdueRes, "2026-08-11"), 24);

  const closed: Resolution = { ...overdueRes, status: "done" };
  assert.equal(overdueDays(closed), 0, "มติที่ปิดแล้วต้องไม่ถูกนับว่าเกินกำหนด");

  const cancelled: Resolution = { ...overdueRes, status: "cancelled" };
  assert.equal(overdueDays(cancelled), 0, "มติที่ยกเลิกแล้วต้องไม่ถูกนับว่าเกินกำหนด");

  assert.equal(overdueDays({ ...overdueRes, due_date: null }), 0);
  assert.equal(overdueDays({ ...overdueRes, due_date: "2026-12-31" }, "2026-08-11"), 0, "ยังไม่ถึงกำหนด");
});

test("สถานะที่ถือว่ายังค้าง", () => {
  assert.ok(isOpen(res(R.adBudget))); // in_progress
  assert.ok(!isOpen(res(R.payment))); // done
  assert.ok(!isOpen(res(R.landingPage))); // done
});

test("อัตราการปิดมติไม่นับมติที่ยกเลิก/ถูกแทนที่เป็นตัวหาร", () => {
  const s = seriesStats(db, DEMO_SERIES_ID);
  const rs = db.resolutions.filter((r) => r.series_id === DEMO_SERIES_ID);
  const closable = rs.filter((r) => r.status !== "cancelled" && r.status !== "superseded").length;
  const done = rs.filter((r) => r.status === "done").length;

  assert.equal(s.total, rs.length);
  assert.equal(s.closureRate, Math.round((done / closable) * 100));
  assert.ok(s.closureRate <= 100);
});

test("state machine ห้ามข้ามจาก proposed ไป done ตรง ๆ และ superseded เป็นทางตัน", () => {
  assert.ok(!NEXT_STATUSES.proposed.includes("done"), "ต้องรับรองก่อนจึงจะปิดได้");
  assert.deepEqual(NEXT_STATUSES.superseded, []);
  assert.ok(NEXT_STATUSES.confirmed.includes("done"));
  assert.ok(NEXT_STATUSES.blocked.includes("in_progress"));
});

test("การค้นภาษาไทยต้องเจอแม้คำถามเขียนติดกันโดยไม่เว้นวรรค", () => {
  const grams = thaiGrams("เรื่องระบบชำระเงิน Payment Gateway มีผลสรุปว่าอย่างไร");
  const hit = relevance(res(R.payment).text, grams);
  const miss = relevance("ข้อความอื่นที่ไม่เกี่ยวข้องเลย", grams);

  assert.ok(hit >= 0.1, `ต้องจับคู่กับมติเรื่อง Payment Gateway ได้ (ได้ ${hit.toFixed(2)})`);
  assert.ok(hit > miss, "มติที่ตรงเรื่องต้องได้คะแนนสูงกว่าข้อความอื่น");
  assert.equal(relevance("อะไรก็ได้", []), 0);
});

test("เอกสารราชการใช้เลขไทย และข้อความจากผู้ใช้ถูก escape ก่อนลงเอกสาร", () => {
  assert.equal(toThaiNumeral(6), "๖");
  assert.equal(toThaiNumeral("5/2569"), "๕/๒๕๖๙");

  assert.ok(!escapeHtml("<script>alert(1)</script>").includes("<script>"));
  assert.equal(escapeHtml("ก & ข"), "ก &amp; ข");
  assert.equal(escapeHtml("บรรทัด\nใหม่"), "บรรทัด<br/>ใหม่", "ขึ้นบรรทัดใหม่ต้องกลายเป็น <br/> ในเอกสาร");
});

test("วันที่แสดงเป็น พ.ศ. และ timecode ไม่พังเมื่อไม่มีค่า", () => {
  assert.equal(formatThaiDate("2026-07-18"), "18 กรกฎาคม 2569");
  assert.equal(formatThaiDate("2026-07-18", true), "18 ก.ค. 2569");
  assert.equal(formatThaiDate(""), "-");
  assert.equal(formatTimecode(null), "--:--");
  assert.equal(formatTimecode(688_000), "11:28");
  assert.equal(formatTimecode(3_661_000), "1:01:01");
});
