import { test } from "node:test";
import assert from "node:assert/strict";
import { daysUntil, formatThaiDate, formatTimecode, speakerLabel } from "./format.ts";

test("วันที่แสดงเป็น พ.ศ. และไม่เลื่อนวันเพราะ timezone", () => {
  assert.equal(formatThaiDate("2026-01-01"), "1 มกราคม 2569");
  assert.equal(formatThaiDate("2026-07-18", true), "18 ก.ค. 2569");
});

test("ค่าว่างหรือผิดรูปไม่ทำให้พัง", () => {
  assert.equal(formatThaiDate(null), "-");
  assert.equal(formatThaiDate("ไม่ใช่วันที่"), "ไม่ใช่วันที่");
});

test("timecode", () => {
  assert.equal(formatTimecode(65_000), "01:05");
  assert.equal(formatTimecode(3_725_000), "1:02:05");
  assert.equal(formatTimecode(null), "--:--");
});

test("daysUntil นับข้ามเดือนและติดลบเมื่อเลยกำหนด", () => {
  assert.equal(daysUntil("2026-03-01", "2026-02-27"), 2);
  assert.equal(daysUntil("2026-02-20", "2026-02-27"), -7);
});

test("ชื่อผู้พูด: ใช้ชื่อที่ตั้งไว้ก่อน ไม่งั้นแปลง label ให้อ่านง่าย", () => {
  assert.equal(speakerLabel({ speaker_label: "SPEAKER_00", speaker_name: "" }), "ผู้พูด 1");
  assert.equal(speakerLabel({ speaker_label: "SPEAKER_02", speaker_name: "คุณมิ้น" }), "คุณมิ้น");
  assert.equal(speakerLabel({ speaker_label: "Speaker 3", speaker_name: "" }), "Speaker 3");
});
