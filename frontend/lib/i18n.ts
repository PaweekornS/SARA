"use client";

/** i18n แบบบาง ๆ — ไทยเป็นหลัก อังกฤษเป็นตัวสำรอง (เนื้อหาการประชุมแสดงตามที่โมเดลสรุปมา) */

import { usePrefs, type Lang } from "./store";

const dict = {
  appName: ["SARA", "SARA"],
  cancel: ["ยกเลิก", "Cancel"],
  save: ["บันทึก", "Save"],
  close: ["ปิด", "Close"],
  delete: ["ลบ", "Delete"],
  add: ["เพิ่ม", "Add"],
  edit: ["แก้ไข", "Edit"],
  retry: ["ลองใหม่", "Retry"],
  theme: ["สลับธีม", "Toggle theme"],
  loading: ["กำลังโหลด…", "Loading…"],
  logout: ["ออกจากระบบ", "Sign out"],
} as const;

export type TKey = keyof typeof dict;

export function t(key: TKey, lang: Lang): string {
  return dict[key][lang === "th" ? 0 : 1];
}

export function useT() {
  const lang = usePrefs((p) => p.lang);
  return Object.assign((key: TKey) => t(key, lang), {
    lang,
    /** เลือกข้อความตามภาษา สำหรับข้อความเฉพาะจุดที่ไม่คุ้มใส่ dict */
    pick: (th: string, en: string) => (lang === "th" ? th : en),
  });
}
