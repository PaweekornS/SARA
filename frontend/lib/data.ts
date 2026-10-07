"use client";

/**
 * hook ดึงข้อมูลแต่ละชนิด — key ของ cache ตั้งเป็นลำดับชั้นเพื่อให้ invalidate ทีละกลุ่มได้
 *   collections · collections:<id> · collections:<id>:meetings · collections:<id>:actions · collections:<id>:qa
 *   meetings:<id> · meetings:<id>:segments · meetings:<id>:actions
 */

import * as api from "./api";
import { useQuery } from "./query";
import type { Meeting } from "./types";

const POLL_MS = 3000;

export const useMe = () => useQuery("me", api.auth.me);

export const useTemplates = () => useQuery("templates", api.templates);

export const useCollections = () => useQuery("collections", api.collections.list);

export const useCollection = (id: string | undefined) =>
  useQuery(id ? `collections:${id}` : null, () => api.collections.get(id!));

export function useCollectionMeetings(id: string | undefined) {
  const result = useQuery(id ? `collections:${id}:meetings` : null, () => api.collections.meetings(id!));
  const processing = result.data?.some((m) => m.status === "processing");
  //  ตราบใดที่ยังมีการประชุมกำลังประมวลผล ให้โหลดรายการใหม่เรื่อย ๆ
  useQuery(processing && id ? `collections:${id}:meetings` : null, () => api.collections.meetings(id!), {
    pollMs: POLL_MS,
  });
  return result;
}

export const useCollectionActions = (id: string | undefined) =>
  useQuery(id ? `collections:${id}:actions` : null, () => api.collections.actionItems(id!));

export const useQaHistory = (id: string | undefined) =>
  useQuery(id ? `collections:${id}:qa` : null, () => api.collections.qaHistory(id!));

export function useMeeting(id: string | undefined) {
  const result = useQuery(id ? `meetings:${id}` : null, () => api.meetings.get(id!));
  const processing = result.data?.status === "processing";
  useQuery(processing && id ? `meetings:${id}` : null, () => api.meetings.get(id!), { pollMs: POLL_MS });
  return result;
}

export const useSegments = (meeting: Meeting | undefined) =>
  useQuery(meeting?.status === "ready" ? `meetings:${meeting.id}:segments` : null, () =>
    api.meetings.segments(meeting!.id),
  );

export const useMeetingActions = (meeting: Meeting | undefined) =>
  useQuery(meeting?.status === "ready" ? `meetings:${meeting.id}:actions` : null, () =>
    api.meetings.actionItems(meeting!.id),
  );
