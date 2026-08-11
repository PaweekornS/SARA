"use client";

/**
 * จุดเดียวที่รู้ว่าข้อมูลมาจากไหน — ทุก endpoint mirror §6 ของ requirement
 *
 * ตอนนี้ NEXT_PUBLIC_USE_MOCK ไม่ได้ตั้งเป็น "false" → เดินสาย mock ใน lib/store.ts
 * เมื่อ backend v2 พร้อม: ตั้ง NEXT_PUBLIC_USE_MOCK=false + NEXT_PUBLIC_API_URL
 * แล้วแก้เฉพาะไฟล์นี้ ไม่ต้องแตะหน้าจอสักหน้า
 */

import * as store from "./store";
import type { AgendaItem, QaAnswer, Resolution, ResolutionStatus, Uuid } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";
export const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK !== "false";

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) throw new Error(`${init?.method ?? "GET"} ${path} → ${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

/* ── meetings ────────────────────────────────────────────────────────── */

export async function uploadMeeting(input: store.UploadInput & { file?: File }): Promise<Uuid> {
  if (USE_MOCK) return store.uploadMeeting(input);

  const form = new FormData();
  if (input.file) form.append("file", input.file);
  form.append("series_id", input.series_id);
  form.append("sequence_no", String(input.sequence_no));
  form.append("meeting_date", input.meeting_date);
  const created = await http<{ meeting_id: string }>("/meetings", {
    method: "POST",
    body: JSON.stringify({
      series_id: input.series_id,
      sequence_no: input.sequence_no,
      meeting_date: input.meeting_date,
    }),
  });
  const res = await fetch(`${BASE}/meetings/${created.meeting_id}/upload`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`upload failed: ${res.status}`);
  return created.meeting_id;
}

export async function retryMeeting(id: Uuid) {
  if (USE_MOCK) return store.retryMeeting(id);
  await http(`/meetings/${id}/upload`, { method: "POST" });
}

export async function patchSpeakers(meetingId: Uuid, speaker_label: string, person_id: Uuid | null) {
  if (USE_MOCK) return store.assignSpeaker(meetingId, speaker_label, person_id);
  await http(`/meetings/${meetingId}/speakers`, {
    method: "PATCH",
    body: JSON.stringify({ speaker_label, person_id }),
  });
}

export async function approveMeeting(id: Uuid) {
  if (USE_MOCK) return store.setMeetingStatus(id, "approved");
  await http(`/meetings/${id}/approve`, { method: "POST" });
}

/* ── resolutions ─────────────────────────────────────────────────────── */

export async function patchResolution(id: Uuid, patch: Partial<Resolution>, reason: string) {
  if (USE_MOCK) return store.updateResolution(id, patch, reason);
  await http(`/resolutions/${id}`, { method: "PATCH", body: JSON.stringify({ ...patch, reason }) });
}

export async function setResolutionStatus(
  id: Uuid,
  status: ResolutionStatus,
  reason: string,
  meeting_id: Uuid | null = null,
) {
  if (USE_MOCK) return store.changeResolutionStatus(id, status, reason, { meeting_id });
  await http(`/resolutions/${id}/status`, { method: "POST", body: JSON.stringify({ status, reason, meeting_id }) });
}

/* ── agenda ──────────────────────────────────────────────────────────── */

export async function generateAgenda(series_id: Uuid): Promise<Uuid> {
  if (USE_MOCK) return store.generateAgenda(series_id);
  const r = await http<{ agenda_id: string }>(`/series/${series_id}/agenda/generate`, { method: "POST" });
  return r.agenda_id;
}

export async function patchAgendaItems(agenda_id: Uuid, items: AgendaItem[]) {
  if (USE_MOCK) return store.updateAgendaItems(agenda_id, items);
  await http(`/agenda/${agenda_id}/items`, { method: "PATCH", body: JSON.stringify({ items }) });
}

/* ── actions ─────────────────────────────────────────────────────────── */

export async function approveAction(id: Uuid) {
  if (USE_MOCK) return store.approveAction(id);
  await http(`/actions/${id}/approve`, { method: "POST" });
}

/* ── Q&A ─────────────────────────────────────────────────────────────── */

export async function askSeries(series_id: Uuid, question: string): Promise<QaAnswer> {
  if (USE_MOCK) {
    /* หน่วงเล็กน้อยให้ UI แสดงสถานะกำลังค้นได้เหมือนของจริง */
    await new Promise((r) => setTimeout(r, 700));
    return store.askSeries(series_id, question);
  }
  return http<QaAnswer>(`/series/${series_id}/ask`, { method: "POST", body: JSON.stringify({ question }) });
}
