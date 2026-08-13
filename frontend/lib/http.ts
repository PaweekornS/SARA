"use client";

/**
 * ชั้นเรียก HTTP ล้วน ๆ — ไม่รู้จัก state ของแอป
 *
 * ทุกฟังก์ชันในนี้ map กับ endpoint ใน §6 ของ requirement แบบ 1:1
 * ไฟล์นี้ไม่ import store เพื่อไม่ให้เกิด import cycle (store เป็นฝ่าย import ไฟล์นี้)
 */

import type { AgendaItem, Database, QaAnswer, Resolution, ResolutionStatus, Uuid } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

/** ค่าเริ่มต้นคือ mock เพื่อให้เปิดดูหน้าจอได้โดยไม่ต้องมี backend */
export const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK !== "false";

/** ชื่อผู้กระทำเป็นภาษาไทย แต่ HTTP header รับได้เฉพาะ latin-1 จึงต้อง encode ก่อนส่ง */
function actorHeader(actor: string): Record<string, string> {
  return { "X-Actor": encodeURIComponent(actor) };
}

async function request<T>(path: string, init: RequestInit & { actor?: string } = {}): Promise<T> {
  const { actor = "", ...rest } = init;
  const response = await fetch(`${BASE}${path}`, {
    ...rest,
    headers: {
      ...(rest.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...actorHeader(actor),
      ...(rest.headers ?? {}),
    },
  });

  if (!response.ok) {
    /* FastAPI ตอบ error เป็น {detail: "..."} — ดึงข้อความจริงมาแสดงให้ผู้ใช้เห็น */
    let detail = `${response.status} ${response.statusText}`;
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch {
      /* ไม่ใช่ JSON ก็ใช้ status ตามเดิม */
    }
    throw new Error(detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/* ── โหลดข้อมูลทั้งก้อน ──────────────────────────────────────────────── */

export function fetchBootstrap(): Promise<Database> {
  return request<Database>("/bootstrap");
}

/* ── M1 ชุดการประชุม ─────────────────────────────────────────────────── */

export function createSeries(payload: Record<string, unknown>, actor: string) {
  return request("/series", { method: "POST", body: JSON.stringify(payload), actor });
}

export function updateSeries(id: Uuid, patch: Record<string, unknown>, actor: string) {
  return request(`/series/${id}`, { method: "PATCH", body: JSON.stringify(patch), actor });
}

export function deleteSeries(id: Uuid, actor: string) {
  return request(`/series/${id}`, { method: "DELETE", actor });
}

/* ── M2 การประชุม ────────────────────────────────────────────────────── */

export async function uploadMeeting(
  input: {
    series_id: Uuid;
    sequence_no: number;
    meeting_date: string;
    source_kind: "audio" | "transcript";
    simulate_asr_failure?: boolean;
    file?: File;
  },
  actor: string,
): Promise<Uuid> {
  const meeting = await request<{ id: Uuid }>("/meetings", {
    method: "POST",
    actor,
    body: JSON.stringify({
      series_id: input.series_id,
      sequence_no: input.sequence_no,
      meeting_date: input.meeting_date,
      source_kind: input.source_kind,
    }),
  });

  if (input.file) {
    const form = new FormData();
    form.append("file", input.file);
    form.append("simulate_asr_failure", String(Boolean(input.simulate_asr_failure)));
    await request(`/meetings/${meeting.id}/upload`, { method: "POST", body: form, actor });
  }
  return meeting.id;
}

export function retryMeeting(id: Uuid, actor: string) {
  return request(`/meetings/${id}/retry`, { method: "POST", actor });
}

export function assignSpeaker(
  meetingId: Uuid,
  speaker_label: string,
  person_id: Uuid | null,
  save_alias: string | undefined,
  actor: string,
) {
  return request(`/meetings/${meetingId}/speakers`, {
    method: "PATCH",
    body: JSON.stringify({ speaker_label, person_id, save_alias }),
    actor,
  });
}

export function decideProposal(
  meetingId: Uuid,
  proposalId: Uuid,
  payload: Record<string, unknown>,
  actor: string,
) {
  return request(`/meetings/${meetingId}/proposals/${proposalId}`, {
    method: "POST",
    body: JSON.stringify(payload),
    actor,
  });
}

export function approveMeeting(id: Uuid, actor: string) {
  return request(`/meetings/${id}/approve`, { method: "POST", actor });
}

export function meetingStatus(id: Uuid) {
  return request<{ status: string }>(`/meetings/${id}/status`);
}

/* ── M3 ทะเบียนบุคคล ─────────────────────────────────────────────────── */

export function upsertPerson(payload: Record<string, unknown>, id: Uuid | undefined, actor: string) {
  return id
    ? request(`/people/${id}`, { method: "PATCH", body: JSON.stringify(payload), actor })
    : request("/people", { method: "POST", body: JSON.stringify(payload), actor });
}

export function deletePerson(id: Uuid, actor: string) {
  return request(`/people/${id}`, { method: "DELETE", actor });
}

export function addAlias(person_id: Uuid, alias: string, actor: string) {
  return request("/people/aliases", {
    method: "POST",
    body: JSON.stringify({ person_id, alias, source: "manual", confidence: 1 }),
    actor,
  });
}

export function removeAlias(id: Uuid, actor: string) {
  return request(`/people/aliases/${id}`, { method: "DELETE", actor });
}

/* ── M4 มติ ──────────────────────────────────────────────────────────── */

export function patchResolution(id: Uuid, patch: Partial<Resolution> & { reason: string }, actor: string) {
  return request(`/resolutions/${id}`, { method: "PATCH", body: JSON.stringify(patch), actor });
}

export function setResolutionStatus(
  id: Uuid,
  status: ResolutionStatus,
  reason: string,
  meeting_id: Uuid | null,
  actor: string,
) {
  return request(`/resolutions/${id}/status`, {
    method: "POST",
    body: JSON.stringify({ status, reason, meeting_id }),
    actor,
  });
}

/* ── M5 ระเบียบวาระ ──────────────────────────────────────────────────── */

export function generateAgenda(seriesId: Uuid, actor: string) {
  return request<{ id: Uuid }>(`/series/${seriesId}/agenda/generate`, { method: "POST", actor });
}

export function patchAgendaItems(agendaId: Uuid, items: AgendaItem[], actor: string) {
  return request(`/agenda/${agendaId}/items`, {
    method: "PATCH",
    body: JSON.stringify({ items }),
    actor,
  });
}

export function agendaExportUrl(agendaId: Uuid) {
  return `${BASE}/agenda/${agendaId}/export?format=docx`;
}

export function minutesExportUrl(meetingId: Uuid) {
  return `${BASE}/meetings/${meetingId}/export?format=docx`;
}

/** ไฟล์เสียงต้นฉบับ — backend ตอบ Range ได้ จึง seek ไปวินาทีที่อ้างอิงได้เลย */
export function meetingAudioUrl(meetingId: Uuid) {
  return `${BASE}/meetings/${meetingId}/audio`;
}

/* ── M7 คิวส่งออก ────────────────────────────────────────────────────── */

export function approveAction(id: Uuid, actor: string) {
  return request(`/actions/${id}/approve`, { method: "POST", actor });
}

export function cancelAction(id: Uuid, actor: string) {
  return request(`/actions/${id}/cancel`, { method: "POST", actor });
}

/* ── M8 ถาม-ตอบ ──────────────────────────────────────────────────────── */

export function askSeries(seriesId: Uuid, question: string): Promise<QaAnswer> {
  return request<QaAnswer>(`/series/${seriesId}/ask`, {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}
