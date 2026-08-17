"use client";

/**
 * M7 — คิวการส่งออกทั้งหมด
 * จุดยืนของ v2: human-in-the-loop เป็นค่าเริ่มต้น ส่งข้อมูลประชุมผิดคน = data breach
 */

import { useState } from "react";
import { AlarmClock, Ban, CalendarClock, Check, Mail, Send, Ticket } from "lucide-react";
import { PageBody, PageHeader } from "@/components/app-shell";
import { Badge, Button, Card, CardHead, EmptyState, Segmented, cn } from "@/components/ui";
import { useT } from "@/lib/i18n";
import * as api from "@/lib/api";
import { cancelAction, formatThaiDate, useApp } from "@/lib/store";
import type { ActionType, OutboundAction } from "@/lib/types";

const ACTION_META: Record<ActionType, { th: string; en: string; icon: React.ReactNode }> = {
  send_meeting_summary_email: { th: "สรุปสาระสำคัญและมติการประชุม", en: "Meeting summary email", icon: <Mail size={15} /> },
  send_resolution_reminder: { th: "แจ้งเตือนมติเกินกำหนดส่ง", en: "Overdue resolution reminder", icon: <AlarmClock size={15} /> },
  send_agenda_preview: { th: "ส่งสรุปเรื่องค้างให้ประธาน", en: "Agenda preview to chair", icon: <CalendarClock size={15} /> },
  create_jira_issue: { th: "สร้าง issue ในระบบติดตามงาน", en: "Create tracker issue", icon: <Ticket size={15} /> },
};

type Tab = "pending" | "sent" | "all";

export default function ActionsPage() {
  const t = useT();
  const { db } = useApp();
  const [tab, setTab] = useState<Tab>("pending");

  const pending = db.actions.filter((a) => a.status === "pending_approval");
  const sent = db.actions.filter((a) => a.status === "sent");
  const rows = tab === "pending" ? pending : tab === "sent" ? sent : db.actions;

  return (
    <>
      <PageHeader
        title={t("navActions")}
        desc={t.pick(
          "ทุกอีเมลที่ระบบจะส่งออกต้องผ่านสายตาคนก่อนเสมอ ตั้งให้ส่งอัตโนมัติได้ แต่ค่าเริ่มต้นคือต้องอนุมัติ",
          "Every outbound message is reviewed by a human first. Automation is a setting, not the default.",
        )}
        tabs={
          <Segmented
            value={tab}
            onChange={setTab}
            options={[
              { value: "pending", label: t("pendingApproval"), count: pending.length },
              { value: "sent", label: t("sent"), count: sent.length },
              { value: "all", label: t.pick("บันทึกทั้งหมด", "All log"), count: db.actions.length },
            ]}
          />
        }
      />

      <PageBody className="space-y-4">
        {rows.length === 0 ? (
          <Card className="border-dashed">
            <EmptyState
              icon={<Send size={20} />}
              title={t.pick("ไม่มีรายการในคิวนี้", "Nothing here")}
              desc={t.pick("รายการเตือนมติจะถูกสร้างอัตโนมัติตามกำหนดที่ตั้งไว้", "Reminders are queued automatically by the scheduler.")}
            />
          </Card>
        ) : (
          rows.map((a) => <ActionCard key={a.id} action={a} />)
        )}
      </PageBody>
    </>
  );
}

function ActionCard({ action }: { action: OutboundAction }) {
  const t = useT();
  const { db } = useApp();
  const [expanded, setExpanded] = useState(action.status === "pending_approval");
  const meta = ACTION_META[action.action_type];
  const resolution = db.resolutions.find((r) => r.id === action.resolution_id);
  const recipient = db.people.find((p) => p.id === action.recipient_person_id);

  const statusBadge = {
    pending_approval: <Badge tone="warn">{t("pendingApproval")}</Badge>,
    approved: <Badge tone="brand">{t.pick("อนุมัติแล้ว", "Approved")}</Badge>,
    sent: <Badge tone="ok">✓ {t("sent")}</Badge>,
    failed: <Badge tone="danger">{t.pick("ส่งไม่สำเร็จ", "Failed")}</Badge>,
    cancelled: <Badge>{t.pick("ยกเลิกแล้ว", "Cancelled")}</Badge>,
  }[action.status];

  return (
    <Card className="overflow-hidden">
      <CardHead
        title={
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-ink-3">{meta.icon}</span>
            {action.subject}
          </span>
        }
        desc={
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span>{t.lang === "th" ? meta.th : meta.en}</span>
            <span className="text-ink-4">·</span>
            <span>
              {t("recipient")}: {recipient ? `${recipient.full_name} <${recipient.email}>` : "-"}
            </span>
            {action.scheduled_for && (
              <>
                <span className="text-ink-4">·</span>
                <span className="tnum">
                  {t("scheduledFor")} {formatThaiDate(action.scheduled_for.slice(0, 10), true)}{" "}
                  {action.scheduled_for.slice(11, 16)} น.
                </span>
              </>
            )}
            {action.sent_at && (
              <>
                <span className="text-ink-4">·</span>
                <span className="tnum">
                  {t("sent")} {action.sent_at.replace("T", " ").slice(0, 16)} · {action.approved_by}
                </span>
              </>
            )}
          </span>
        }
        right={statusBadge}
      />

      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full border-b border-line px-5 py-2 text-left text-[12px] font-medium text-ink-3 hover:bg-surface-2 cursor-pointer"
      >
        {expanded ? t.pick("ซ่อนเนื้อหาที่จะส่ง", "Hide message") : t.pick("ดูเนื้อหาที่จะส่งทั้งหมด", "Preview message")}
      </button>

      {expanded && (
        <div className="space-y-3 px-5 py-4">
          {resolution && (
            <div className="rounded-[var(--radius)] border border-line bg-surface-2 px-3.5 py-3">
              <p className="font-mono text-[11.5px] text-brand">{resolution.ref_no}</p>
              <p className="mt-1 text-[13px] leading-relaxed text-ink-2">{resolution.text}</p>
            </div>
          )}
          <pre className="whitespace-pre-wrap rounded-[var(--radius)] bg-sunken px-4 py-3.5 font-sans text-[13px] leading-relaxed text-ink-2">
            {action.body}
          </pre>
          {action.status === "pending_approval" && (
            <p className="text-[12px] leading-relaxed text-ink-3">
              {t.pick(
                "ผู้รับสามารถกดลิงก์ในอีเมลเพื่อแจ้งสถานะกลับได้โดยไม่ต้องล็อกอิน ระบบจะบันทึกเป็นการรายงานความคืบหน้าของมติข้อนี้",
                "The recipient can update status via a magic link without logging in.",
              )}
            </p>
          )}
        </div>
      )}

      {action.status === "pending_approval" && (
        <div className={cn("flex flex-wrap gap-2 border-t border-line px-5 py-3.5")}>
          <Button variant="primary" size="sm" icon={<Check size={14} />} onClick={() => api.approveAction(action.id)}>
            {t("approveAndSend")}
          </Button>
          <Button size="sm" icon={<Ban size={14} />} onClick={() => cancelAction(action.id)}>
            {t.pick("ไม่ส่ง", "Cancel")}
          </Button>
        </div>
      )}
    </Card>
  );
}
