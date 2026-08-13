/**
 * ตรวจตรรกะที่พังแล้วเจ็บจริง — เกินกำหนด / อัตราการปิด / state machine / การค้นภาษาไทย
 *   npm run check
 */

import assert from "node:assert/strict";
import test from "node:test";
import {
  NEXT_STATUSES,
  activeSegmentIndex,
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
  assert.equal(overdueDays(res(R.a)), 24); // due 2026-07-18 · today 2026-08-11
  assert.equal(overdueDays(res(R.c)), 11); // due 2026-07-31

  const closed: Resolution = { ...res(R.a), status: "done" };
  assert.equal(overdueDays(closed), 0, "มติที่ปิดแล้วต้องไม่ถูกนับว่าเกินกำหนด");

  const cancelled: Resolution = { ...res(R.a), status: "cancelled" };
  assert.equal(overdueDays(cancelled), 0, "มติที่ยกเลิกแล้วต้องไม่ถูกนับว่าเกินกำหนด");

  assert.equal(overdueDays({ ...res(R.a), due_date: null }), 0);
  assert.equal(overdueDays({ ...res(R.a), due_date: "2026-12-31" }), 0, "ยังไม่ถึงกำหนด");
});

test("สถานะที่ถือว่ายังค้าง", () => {
  assert.ok(isOpen(res(R.a))); // confirmed
  assert.ok(isOpen(res(R.b))); // blocked
  assert.ok(isOpen(res(R.c))); // in_progress
  assert.ok(!isOpen(res("res-d"))); // done
  assert.ok(!isOpen(res("res-j"))); // superseded
});

test("อัตราการปิดมติไม่นับมติที่ยกเลิก/ถูกแทนที่เป็นตัวหาร", () => {
  const s = seriesStats(db, DEMO_SERIES_ID);
  const rs = db.resolutions.filter((r) => r.series_id === DEMO_SERIES_ID);
  const closable = rs.filter((r) => r.status !== "cancelled" && r.status !== "superseded").length;
  const done = rs.filter((r) => r.status === "done").length;

  assert.equal(s.total, rs.length);
  assert.equal(s.closureRate, Math.round((done / closable) * 100));
  assert.ok(s.closureRate <= 100);
  assert.equal(s.flagged, 1, "มติ B เลื่อนมา 3 ครั้งและยังไม่ปิด ต้องติดธง 1 ข้อ");
  assert.equal(s.overdue, 2, "มติ A และ C เกินกำหนด");
});

test("state machine ห้ามข้ามจาก proposed ไป done ตรง ๆ และ superseded เป็นทางตัน", () => {
  assert.ok(!NEXT_STATUSES.proposed.includes("done"), "ต้องรับรองก่อนจึงจะปิดได้");
  assert.deepEqual(NEXT_STATUSES.superseded, []);
  assert.ok(NEXT_STATUSES.confirmed.includes("done"));
  assert.ok(NEXT_STATUSES.blocked.includes("in_progress"));
});

test("การค้นภาษาไทยต้องเจอแม้คำถามเขียนติดกันโดยไม่เว้นวรรค", () => {
  const grams = thaiGrams("เรื่องระบบสารบรรณอิเล็กทรอนิกส์ เคยมีมติว่าอะไรบ้าง");
  const hit = relevance(res(R.b).text, grams);
  const miss = relevance(res(R.a).text, grams);

  assert.ok(hit >= 0.1, `ต้องจับคู่กับมติเรื่องระบบสารบรรณได้ (ได้ ${hit.toFixed(2)})`);
  assert.ok(hit > miss, "มติที่ตรงเรื่องต้องได้คะแนนสูงกว่ามติเรื่องจัดซื้อ");
  assert.equal(relevance("อะไรก็ได้", []), 0);
});

test("เอกสารราชการใช้เลขไทย และข้อความจากผู้ใช้ถูก escape ก่อนลงเอกสาร", () => {
  assert.equal(toThaiNumeral(6), "๖");
  assert.equal(toThaiNumeral("5/2569"), "๕/๒๕๖๙");
  assert.equal(toThaiNumeral("18 กรกฎาคม 2569"), "๑๘ กรกฎาคม ๒๕๖๙");

  assert.ok(!escapeHtml("<script>alert(1)</script>").includes("<script>"));
  assert.equal(escapeHtml("ก & ข"), "ก &amp; ข");
  assert.equal(escapeHtml("บรรทัด\nใหม่"), "บรรทัด<br/>ใหม่", "ขึ้นบรรทัดใหม่ต้องกลายเป็น <br/> ในเอกสาร");
});

test("วันที่แสดงเป็น พ.ศ. และ timecode ไม่พังเมื่อไม่มีค่า", () => {
  assert.equal(formatThaiDate("2026-07-18"), "18 กรกฎาคม 2569");
  assert.equal(formatThaiDate("2026-07-18", true), "18 กรก. 2569");
  assert.equal(formatThaiDate(""), "-");
  assert.equal(formatTimecode(null), "--:--");
  assert.equal(formatTimecode(688_000), "11:28");
  assert.equal(formatTimecode(3_661_000), "1:01:01");
});

test("หัวอ่านชี้ท่อนที่ถูก และไม่หลุดตอนเงียบระหว่างท่อน", () => {
  const segments = [{ start_ms: 0 }, { start_ms: 18_000 }, { start_ms: 35_000 }];

  assert.equal(activeSegmentIndex(segments, 0), 0);
  assert.equal(activeSegmentIndex(segments, 17_999), 0);
  assert.equal(activeSegmentIndex(segments, 18_000), 1, "ตรงวินาทีที่เริ่ม ต้องเป็นท่อนใหม่ ไม่ใช่ท่อนก่อน");
  assert.equal(activeSegmentIndex(segments, 34_000), 1, "ช่วงเงียบต้องคาที่ท่อนล่าสุด ไม่ใช่ -1");
  assert.equal(activeSegmentIndex(segments, 900_000), 2, "เลยท่อนสุดท้ายต้องคาท่อนสุดท้าย");
  assert.equal(activeSegmentIndex(segments, -1), -1, "ยังไม่เริ่มเล่นต้องไม่เน้นบรรทัดใด");
  assert.equal(activeSegmentIndex([], 5_000), -1);
});
