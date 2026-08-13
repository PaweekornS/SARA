"use client";

/**
 * หน้าบ้านของงานที่เป็น async — หน้าจอเรียกผ่านไฟล์นี้ที่เดียว
 *
 * งานที่เปลี่ยน state แบบทันที (แก้มติ ลบคน จัดวาระ) เรียก mutation ใน store ได้ตรง ๆ
 * เพราะ store จัดการซิงก์ขึ้น backend ให้เองแล้ว ดู push() ใน lib/store.ts
 *
 * สลับระหว่าง mock กับของจริงที่ตัวแปรเดียว: NEXT_PUBLIC_USE_MOCK
 */

import * as http from "./http";
import * as store from "./store";
import type { QaAnswer, Uuid } from "./types";

export const USE_MOCK = http.USE_MOCK;

/** M2 — อัปโหลดการประชุมครั้งใหม่ คืน id ของ meeting ที่จะใช้เปิดหน้าตรวจทาน */
export async function uploadMeeting(input: store.UploadInput & { file?: File }): Promise<Uuid> {
  if (store.LIVE) return store.uploadMeetingLive(input);
  return store.uploadMeeting(input);
}

export async function retryMeeting(id: Uuid) {
  store.retryMeeting(id);
}

export async function approveMeeting(id: Uuid) {
  store.setMeetingStatus(id, "approved");
}

export async function generateAgenda(seriesId: Uuid): Promise<Uuid> {
  return store.generateAgenda(seriesId);
}

export async function approveAction(id: Uuid) {
  store.approveAction(id);
}

/** M8 — ถาม-ตอบข้ามการประชุม */
export async function askSeries(seriesId: Uuid, question: string): Promise<QaAnswer> {
  if (!store.LIVE) {
    /* หน่วงเล็กน้อยให้ UI แสดงสถานะกำลังค้นได้เหมือนของจริง */
    await new Promise((resolve) => setTimeout(resolve, 700));
    return store.askSeries(seriesId, question);
  }

  const answer = await http.askSeries(seriesId, question);
  store.appendQa(seriesId, answer);
  return answer;
}

/** ลิงก์ดาวน์โหลดเอกสาร — โหมด mock สร้างไฟล์ในเครื่อง โหมดจริงให้ backend เรนเดอร์ */
export function agendaExportUrl(agendaId: Uuid): string | null {
  return store.LIVE ? http.agendaExportUrl(agendaId) : null;
}

export function minutesExportUrl(meetingId: Uuid): string | null {
  return store.LIVE ? http.minutesExportUrl(meetingId) : null;
}
