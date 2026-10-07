"use client";

/**
 * ตัวเรียก backend — ทุก endpoint อยู่ที่นี่ที่เดียว
 *
 * เรียกผ่าน path แบบ relative (/api/...) เสมอ: บนเซิร์ฟเวอร์ reverse proxy ส่งต่อให้ backend
 * ส่วนบนเครื่องตัวเอง next.config.ts rewrite /api ไปที่ backend — cookie ของ session จึงเป็น same-origin
 */

import type {
  ActionItem,
  Collection,
  EmailResult,
  Meeting,
  QaEntry,
  Segment,
  TemplateId,
  TemplateInfo,
  User,
  Uuid,
} from "./types";

export const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "/api").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

function goToLogin() {
  if (typeof window === "undefined" || window.location.pathname.startsWith("/login")) return;
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  window.location.assign(`/login?next=${next}`);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const isForm = init.body instanceof FormData;
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "same-origin",
    headers: { ...(isForm || !init.body ? {} : { "Content-Type": "application/json" }), ...(init.headers ?? {}) },
  });

  if (response.status === 401 && !path.startsWith("/auth/")) {
    goToLogin();
  }
  if (!response.ok) {
    /* FastAPI ตอบ error เป็น {detail: "..."} หรือ {detail: [{msg}]} ตอน validation ไม่ผ่าน */
    let detail = `${response.status} ${response.statusText}`;
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") detail = data.detail;
      else if (Array.isArray(data?.detail) && data.detail[0]?.msg) detail = data.detail[0].msg;
    } catch {
      /* ไม่ใช่ JSON ใช้ status ตามเดิม */
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) return undefined as T;
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

const json = (body: unknown) => JSON.stringify(body);

/* ── auth ────────────────────────────────────────────────────────────── */

export const auth = {
  me: () => request<User>("/auth/me"),
  google: (id_token: string) => request<{ user: User }>("/auth/google", { method: "POST", body: json({ id_token }) }),
  demo: (name?: string) => request<{ user: User }>("/auth/demo", { method: "POST", body: json(name ? { name } : {}) }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
};

/* ── templates ───────────────────────────────────────────────────────── */

export const templates = () => request<TemplateInfo[]>("/public/templates");

/* ── collections ─────────────────────────────────────────────────────── */

export const collections = {
  list: () => request<Collection[]>("/collections"),
  get: (id: Uuid) => request<Collection>(`/collections/${id}`),
  create: (input: { name: string; description?: string; default_template?: TemplateId }) =>
    request<Collection>("/collections", { method: "POST", body: json(input) }),
  update: (id: Uuid, patch: Partial<Pick<Collection, "name" | "description" | "default_template">>) =>
    request<Collection>(`/collections/${id}`, { method: "PATCH", body: json(patch) }),
  remove: (id: Uuid) => request<void>(`/collections/${id}`, { method: "DELETE" }),
  meetings: (id: Uuid) => request<Meeting[]>(`/collections/${id}/meetings`),
  actionItems: (id: Uuid, done?: boolean) =>
    request<ActionItem[]>(`/collections/${id}/action-items${done === undefined ? "" : `?done=${done}`}`),
  ask: (id: Uuid, question: string) =>
    request<QaEntry>(`/collections/${id}/ask`, { method: "POST", body: json({ question }) }),
  qaHistory: (id: Uuid) => request<QaEntry[]>(`/collections/${id}/qa`),
  clearQa: (id: Uuid) => request<void>(`/collections/${id}/qa`, { method: "DELETE" }),
};

/* ── meetings ────────────────────────────────────────────────────────── */

export const meetings = {
  upload: (input: { file: File; collection_id: Uuid; title?: string; meeting_date?: string; template?: TemplateId }) => {
    const form = new FormData();
    form.append("file", input.file);
    form.append("collection_id", input.collection_id);
    if (input.title) form.append("title", input.title);
    if (input.meeting_date) form.append("meeting_date", input.meeting_date);
    if (input.template) form.append("template", input.template);
    return request<Meeting>("/meetings", { method: "POST", body: form });
  },
  get: (id: Uuid) => request<Meeting>(`/meetings/${id}`),
  update: (id: Uuid, patch: { title?: string; meeting_date?: string | null; collection_id?: Uuid }) =>
    request<Meeting>(`/meetings/${id}`, { method: "PATCH", body: json(patch) }),
  remove: (id: Uuid) => request<void>(`/meetings/${id}`, { method: "DELETE" }),
  retry: (id: Uuid) => request<Meeting>(`/meetings/${id}/retry`, { method: "POST" }),
  segments: (id: Uuid) => request<Segment[]>(`/meetings/${id}/segments`),
  renameSpeaker: (id: Uuid, speaker_label: string, speaker_name: string) =>
    request<Segment[]>(`/meetings/${id}/speakers`, { method: "PATCH", body: json({ speaker_label, speaker_name }) }),
  actionItems: (id: Uuid) => request<ActionItem[]>(`/meetings/${id}/action-items`),
  addActionItem: (id: Uuid, input: { text: string; owner?: string; due_date?: string | null }) =>
    request<ActionItem>(`/meetings/${id}/action-items`, { method: "POST", body: json(input) }),
  email: (id: Uuid, input: { recipients: string[]; subject?: string; include_action_items?: boolean }) =>
    request<EmailResult>(`/meetings/${id}/email`, { method: "POST", body: json(input) }),
  audioUrl: (id: Uuid) => `${API_BASE}/meetings/${id}/audio`,
  exportUrl: (id: Uuid) => `${API_BASE}/meetings/${id}/export`,
};

/* ── action items ────────────────────────────────────────────────────── */

export const actionItems = {
  update: (id: Uuid, patch: Partial<Pick<ActionItem, "text" | "owner" | "due_date" | "done">>) =>
    request<ActionItem>(`/action-items/${id}`, { method: "PATCH", body: json(patch) }),
  remove: (id: Uuid) => request<void>(`/action-items/${id}`, { method: "DELETE" }),
  acceptSuggestion: (id: Uuid) => request<ActionItem>(`/action-items/${id}/suggestion/accept`, { method: "POST" }),
  dismissSuggestion: (id: Uuid) => request<ActionItem>(`/action-items/${id}/suggestion/dismiss`, { method: "POST" }),
};
