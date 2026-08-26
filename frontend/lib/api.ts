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

export async function reuploadMeeting(id: Uuid, file: File, simulate_asr_failure: boolean = false) {
  return store.reuploadMeeting(id, file, simulate_asr_failure);
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

/** v3.0.0 Public Stateless API Helper */
export async function summarizePublicFile(
  file: File,
  template: string = "general",
  recipients?: string[],
  email_subject?: string,
) {
  return http.summarizePublicFile(file, template, recipients, email_subject);
}

export async function loginGoogle(id_token: string, client_id?: string) {
  return http.authGoogle(id_token, client_id);
}

export async function loginDemo(name?: string, email?: string) {
  return http.authDemo(name, email);
}

export async function fetchCurrentUser() {
  return http.getAuthMe();
}

/** Series / Collection Management */
export function createSeries(input: Parameters<typeof store.createSeries>[0]) {
  return store.createSeries(input);
}

export function updateSeries(id: Uuid, patch: Parameters<typeof store.updateSeries>[1]) {
  return store.updateSeries(id, patch);
}

export function deleteSeries(id: Uuid) {
  return store.deleteSeries(id);
}

export async function sendDirectEmail(payload: {
  recipients: string[];
  subject: string;
  summary_text: string;
  template_name?: string;
  items?: any[];
}) {
  if (store.LIVE) {
    return http.sendDirectEmail(payload);
  }
  // If in mock mode without backend, simulate with timeout
  try {
    return await http.sendDirectEmail(payload);
  } catch {
    await new Promise((r) => setTimeout(r, 600));
    return { status: "success", dispatched_count: payload.recipients.length };
  }
}


