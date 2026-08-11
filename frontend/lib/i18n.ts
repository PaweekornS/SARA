"use client";

/**
 * i18n แบบบาง ๆ — ไทยเป็นหลัก อังกฤษเป็นตัวสำรองสำหรับกรรมการต่างชาติ
 * เนื้อหาที่เป็นเอกสารราชการ (มติ/วาระ) คงเป็นภาษาไทยเสมอ แปลเฉพาะ UI chrome
 */

import { useStore, type Lang } from "./store";

const dict = {
  /* chrome */
  appName: ["SARA", "SARA"],
  appTagline: ["ระบบสารบรรณการประชุมอัตโนมัติ", "Automated meeting records system"],
  search: ["ค้นหา", "Search"],
  cancel: ["ยกเลิก", "Cancel"],
  save: ["บันทึก", "Save"],
  close: ["ปิด", "Close"],
  confirm: ["ยืนยัน", "Confirm"],
  edit: ["แก้ไข", "Edit"],
  delete: ["ลบ", "Delete"],
  add: ["เพิ่ม", "Add"],
  all: ["ทั้งหมด", "All"],
  none: ["ไม่มี", "None"],
  back: ["ย้อนกลับ", "Back"],
  reason: ["เหตุผล", "Reason"],
  optional: ["ไม่บังคับ", "optional"],
  resetDemo: ["รีเซ็ตข้อมูลเดโม", "Reset demo data"],
  theme: ["สลับธีม", "Toggle theme"],

  /* nav */
  navSeries: ["ชุดการประชุม", "Meeting series"],
  navDashboard: ["ภาพรวมมติ", "Resolution dashboard"],
  navResolutions: ["ทะเบียนมติ", "Resolutions"],
  navMeetings: ["การประชุม", "Meetings"],
  navAgenda: ["ร่างระเบียบวาระ", "Agenda draft"],
  navAsk: ["ถาม-ตอบข้ามครั้ง", "Cross-meeting Q&A"],
  navPeople: ["ทะเบียนบุคคล", "People registry"],
  navActions: ["คิวส่งออก", "Outbound queue"],
  navAudit: ["บันทึกการใช้งาน", "Audit log"],

  /* dashboard */
  statTotal: ["มติทั้งหมด", "Total resolutions"],
  statOpen: ["ค้างดำเนินการ", "Open"],
  statDone: ["ดำเนินการแล้วเสร็จ", "Completed"],
  statOverdue: ["เกินกำหนด", "Overdue"],
  closureRate: ["อัตราการปิดมติ", "Closure rate"],
  avgDaysToClose: ["เวลาเฉลี่ยจากมติถึงปิด", "Avg. days to close"],
  overdueList: ["มติค้าง เรียงตามจำนวนวันที่เกินกำหนด", "Open resolutions by days overdue"],
  flaggedList: ["มติที่ถูกเลื่อนซ้ำเกิน 3 ครั้ง", "Postponed more than 3 times"],
  byAssignee: ["ภาระมติค้าง แยกตามผู้รับผิดชอบ", "Open load by assignee"],
  noOverdue: ["ไม่มีมติเกินกำหนด", "No overdue resolutions"],

  /* resolutions */
  status: ["สถานะ", "Status"],
  assignee: ["ผู้รับผิดชอบ", "Assignee"],
  dueDate: ["กำหนดแล้วเสร็จ", "Due date"],
  origin: ["ที่มา", "Origin"],
  overdueBy: ["เกินกำหนด", "Overdue by"],
  days: ["วัน", "days"],
  daysLeft: ["เหลืออีก", "in"],
  timeline: ["ไทม์ไลน์การถูกอ้างถึง", "Reference timeline"],
  history: ["ประวัติการแก้ไข", "Change history"],
  evidence: ["หลักฐานอ้างอิง", "Evidence"],
  changeStatus: ["เปลี่ยนสถานะ", "Change status"],
  postponedTimes: ["เลื่อนกำหนดมาแล้ว", "Postponed"],
  times: ["ครั้ง", "times"],
  noResolutions: ["ไม่พบมติตามเงื่อนไขที่เลือก", "No resolutions match these filters"],

  /* meetings */
  uploadMeeting: ["อัปโหลดการประชุมครั้งใหม่", "Upload new meeting"],
  processing: ["กำลังประมวลผล", "Processing"],
  review: ["ตรวจทาน", "Review"],
  approve: ["รับรองรายงาน", "Approve minutes"],
  approved: ["รับรองแล้ว", "Approved"],
  retry: ["ลองใหม่", "Retry"],
  transcript: ["บันทึกคำต่อคำ", "Transcript"],
  speakers: ["ผู้พูด", "Speakers"],
  pendingReview: ["รอการตรวจทาน", "Awaiting review"],

  /* review */
  proposalsTitle: ["สิ่งที่ระบบเสนอ รอการยืนยันจากท่าน", "System proposals awaiting your confirmation"],
  accept: ["ยอมรับ", "Accept"],
  reject: ["ปฏิเสธ", "Reject"],
  lowConfidence: ["ระบบไม่มั่นใจ", "Low confidence"],
  confidence: ["ความมั่นใจ", "Confidence"],

  /* agenda */
  generateAgenda: ["สร้างร่างระเบียบวาระครั้งถัดไป", "Generate next agenda"],
  exportDocx: ["ส่งออก .docx", "Export .docx"],
  exportPdf: ["พิมพ์ / PDF", "Print / PDF"],

  /* actions */
  pendingApproval: ["รออนุมัติก่อนส่ง", "Awaiting approval"],
  sent: ["ส่งแล้ว", "Sent"],
  approveAndSend: ["อนุมัติและส่ง", "Approve & send"],
  scheduledFor: ["ตั้งเวลาส่ง", "Scheduled"],
  recipient: ["ผู้รับ", "Recipient"],

  /* qa */
  askPlaceholder: ["ถามได้ทุกเรื่องในชุดการประชุมนี้ เช่น เรื่องระบบสารบรรณเคยมีมติว่าอะไรบ้าง", "Ask anything across this series"],
  answerSource: ["แหล่งที่มาของคำตอบ", "Answer source"],
  fromResolutions: ["ทะเบียนมติ", "Resolution table"],
  fromTranscript: ["ค้นจากบันทึกคำต่อคำ", "Transcript search"],
} as const;

export type TKey = keyof typeof dict;

export function t(key: TKey, lang: Lang): string {
  return dict[key][lang === "th" ? 0 : 1];
}

export function useT() {
  const lang = useStore((s) => s.lang);
  return Object.assign((key: TKey) => t(key, lang), {
    lang,
    /** เลือกข้อความตามภาษา สำหรับข้อความเฉพาะจุดที่ไม่คุ้มใส่ dict */
    pick: (th: string, en: string) => (lang === "th" ? th : en),
  });
}
