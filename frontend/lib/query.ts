"use client";

/**
 * cache ข้อมูลจาก backend แบบเล็ก ๆ (แนวเดียวกับ SWR)
 *
 * - หลาย component ที่ใช้ key เดียวกันได้ข้อมูลก้อนเดียวกัน และยิง request ครั้งเดียว
 * - หลังแก้ข้อมูล เรียก invalidate("collections") แล้วทุกหน้าที่ใช้ key ขึ้นต้นด้วยคำนั้นจะโหลดใหม่เอง
 * - pollMs ใช้กับการประชุมที่กำลังประมวลผล
 */

import { useCallback, useEffect, useSyncExternalStore } from "react";

interface Entry<T = unknown> {
  data?: T;
  error?: Error;
  loading: boolean;
  promise?: Promise<void>;
  fetcher?: () => Promise<T>;
}

const cache = new Map<string, Entry>();
const listeners = new Set<() => void>();
let version = 0;

function emit() {
  version += 1;
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function load<T>(key: string, fetcher: () => Promise<T>): Promise<void> {
  const entry = (cache.get(key) as Entry<T> | undefined) ?? { loading: false };
  entry.fetcher = fetcher;
  if (entry.promise) return entry.promise;

  entry.loading = true;
  entry.promise = fetcher()
    .then((data) => {
      entry.data = data;
      entry.error = undefined;
    })
    .catch((err: unknown) => {
      entry.error = err instanceof Error ? err : new Error(String(err));
    })
    .finally(() => {
      entry.loading = false;
      entry.promise = undefined;
      emit();
    });
  cache.set(key, entry as Entry);
  emit();
  return entry.promise;
}

/** โหลดใหม่ทุก key ที่ขึ้นต้นด้วย prefix (ข้อมูลเดิมยังแสดงอยู่ระหว่างโหลด) */
export function invalidate(...prefixes: string[]) {
  for (const [key, entry] of cache) {
    if (prefixes.some((p) => key === p || key.startsWith(`${p}:`)) && entry.fetcher) {
      void load(key, entry.fetcher);
    }
  }
}

/** แทนค่าใน cache ทันทีโดยไม่ยิง request (ใช้หลัง mutation ที่ตอบข้อมูลใหม่กลับมา) */
export function setCached<T>(key: string, updater: (current: T | undefined) => T) {
  const entry = (cache.get(key) as Entry<T> | undefined) ?? { loading: false };
  entry.data = updater(entry.data);
  cache.set(key, entry as Entry);
  emit();
}

/** ล้างทั้งหมด — ใช้ตอน logout ไม่ให้ข้อมูลของคนก่อนหน้าค้างอยู่ */
export function clearCache() {
  cache.clear();
  emit();
}

export interface QueryResult<T> {
  data: T | undefined;
  error: Error | undefined;
  loading: boolean;
  reload: () => Promise<void>;
}

export function useQuery<T>(key: string | null, fetcher: () => Promise<T>, opts: { pollMs?: number } = {}): QueryResult<T> {
  useSyncExternalStore(subscribe, () => version, () => 0);

  const entry = key ? (cache.get(key) as Entry<T> | undefined) : undefined;

  useEffect(() => {
    if (!key) return;
    const current = cache.get(key);
    if (!current || (current.data === undefined && !current.loading && !current.error)) void load(key, fetcher);
    // fetcher เปลี่ยน reference ทุก render — ใช้ key เป็นตัวตัดสินว่าต้องโหลดใหม่หรือไม่
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    if (!key || !opts.pollMs) return;
    const timer = window.setInterval(() => void load(key, fetcher), opts.pollMs);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, opts.pollMs]);

  const reload = useCallback(() => (key ? load(key, fetcher) : Promise.resolve()), [key, fetcher]);

  return {
    data: entry?.data,
    error: entry?.error,
    loading: Boolean(key) && (entry?.loading ?? true),
    reload,
  };
}
