"use client";

/**
 * ค่าที่เก็บในเครื่องผู้ใช้เท่านั้น: ธีม และภาษา
 * ข้อมูลการประชุมทั้งหมดมาจาก backend ผ่าน lib/query.ts — ไม่เก็บใน localStorage
 */

import { useSyncExternalStore } from "react";

export type Lang = "th" | "en";
export type Theme = "light" | "dark";

export interface Prefs {
  lang: Lang;
  theme: Theme;
}

/* app/layout.tsx อ่าน key นี้ก่อน paint แรกเพื่อกันจอขาววาบในธีมมืด — เปลี่ยนชื่อต้องแก้ที่นั่นด้วย */
export const PREFS_KEY = "sara_prefs";

const DEFAULTS: Prefs = { lang: "th", theme: "light" };

let prefs: Prefs = DEFAULTS;
let hydrated = false;
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

function applyTheme(theme: Theme) {
  if (typeof document !== "undefined") document.documentElement.classList.toggle("dark", theme === "dark");
}

function save() {
  try {
    window.localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
  } catch {
    /* private mode หรือโควตาเต็ม — ใช้ค่าในหน่วยความจำต่อไป */
  }
}

export function hydratePrefs() {
  if (hydrated || typeof window === "undefined") return;
  hydrated = true;
  try {
    const raw = window.localStorage.getItem(PREFS_KEY);
    if (raw) prefs = { ...DEFAULTS, ...(JSON.parse(raw) as Partial<Prefs>) };
  } catch {
    prefs = DEFAULTS;
  }
  applyTheme(prefs.theme);
  emit();
}

function update(patch: Partial<Prefs>) {
  prefs = { ...prefs, ...patch };
  save();
  applyTheme(prefs.theme);
  emit();
}

export function setLang(lang: Lang) {
  update({ lang });
}

export function toggleTheme() {
  update({ theme: prefs.theme === "light" ? "dark" : "light" });
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** selector ต้องคืนค่า primitive หรือ reference ที่มีอยู่แล้ว ไม่งั้น useSyncExternalStore จะ render วน */
export function usePrefs<T>(selector: (p: Prefs) => T): T {
  return useSyncExternalStore(
    subscribe,
    () => selector(prefs),
    () => selector(DEFAULTS),
  );
}
