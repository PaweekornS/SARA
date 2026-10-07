"use client";

/** รายการงานที่ต้องทำ — ติ๊กเสร็จ แก้ไข ลบ และตอบรับข้อเสนอว่า "น่าจะเสร็จแล้ว" */

import { useState } from "react";
import Link from "next/link";
import { CalendarClock, Check, CheckCircle2, Pencil, Plus, Sparkles, Trash2, User, X } from "lucide-react";
import * as api from "@/lib/api";
import { daysUntil, formatThaiDate } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { invalidate } from "@/lib/query";
import type { ActionItem } from "@/lib/types";
import { Button, EmptyState, Field, Input, Modal, cn } from "./ui";

function refresh(item: Pick<ActionItem, "meeting_id">) {
  invalidate("collections", `meetings:${item.meeting_id}`);
}

export function ActionItemList({
  items,
  meetingLink,
  emptyText,
}: {
  items: ActionItem[];
  /** แสดงลิงก์ไปการประชุมต้นทาง (ใช้ในหน้ารวมของ collection) */
  meetingLink?: (item: ActionItem) => { href: string; label: string } | null;
  emptyText?: string;
}) {
  const t = useT();
  const [editing, setEditing] = useState<ActionItem | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async (item: ActionItem, op: () => Promise<unknown>) => {
    setError(null);
    try {
      await op();
      refresh(item);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  if (items.length === 0) {
    return (
      <EmptyState
        icon={<CheckCircle2 size={22} className="text-brand" />}
        title={emptyText ?? t.pick("ไม่มีงานที่ต้องทำ", "No action items")}
      />
    );
  }

  return (
    <div className="space-y-2">
      {error && <p className="rounded-[var(--radius)] bg-[var(--danger-bg)] px-3 py-2 text-[12.5px] text-[var(--danger)]">{error}</p>}
      {items.map((item) => {
        const link = meetingLink?.(item);
        const dueIn = item.due_date && !item.done ? daysUntil(item.due_date) : null;
        return (
          <div
            key={item.id}
            className={cn(
              "group rounded-[var(--radius)] border bg-[var(--bg-surface)] p-3 transition-colors",
              item.suggested_done_meeting_id ? "border-brand/40" : "border-line",
            )}
          >
            <div className="flex items-start gap-3">
              <button
                onClick={() => run(item, () => api.actionItems.update(item.id, { done: !item.done }))}
                className={cn(
                  "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border transition-colors cursor-pointer",
                  item.done ? "border-[var(--ok)] bg-[var(--ok)] text-white" : "border-[var(--line-strong)] hover:border-brand",
                )}
                aria-label={item.done ? t.pick("ยกเลิกว่าเสร็จ", "Mark not done") : t.pick("ทำเครื่องหมายว่าเสร็จ", "Mark done")}
              >
                {item.done && <Check size={13} strokeWidth={3} />}
              </button>

              <div className="min-w-0 flex-1">
                <p className={cn("text-[13.5px] leading-relaxed", item.done ? "text-ink-4 line-through" : "text-ink")}>{item.text}</p>
                <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11.5px] text-ink-3">
                  {item.owner && (
                    <span className="flex items-center gap-1">
                      <User size={11} /> {item.owner}
                    </span>
                  )}
                  {item.due_date && (
                    <span className={cn("flex items-center gap-1", dueIn !== null && dueIn < 0 && "font-medium text-[var(--danger)]")}>
                      <CalendarClock size={11} /> {formatThaiDate(item.due_date, true)}
                      {dueIn !== null && dueIn < 0 && ` (${t.pick(`เลย ${-dueIn} วัน`, `${-dueIn}d overdue`)})`}
                    </span>
                  )}
                  {link && (
                    <Link href={link.href} className="truncate hover:text-brand hover:underline">
                      {link.label}
                    </Link>
                  )}
                </div>
              </div>

              <div className="flex shrink-0 gap-0.5 opacity-60 transition-opacity group-hover:opacity-100">
                <button onClick={() => setEditing(item)} className="rounded p-1.5 text-ink-3 hover:bg-sunken hover:text-ink cursor-pointer" aria-label={t("edit")}>
                  <Pencil size={13} />
                </button>
                <button
                  onClick={() => run(item, () => api.actionItems.remove(item.id))}
                  className="rounded p-1.5 text-ink-3 hover:bg-sunken hover:text-[var(--danger)] cursor-pointer"
                  aria-label={t("delete")}
                >
                  <Trash2 size={13} />
                </button>
              </div>
            </div>

            {item.suggested_done_meeting_id && !item.done && (
              <div className="mt-2.5 flex flex-wrap items-center gap-2 rounded-[var(--radius)] bg-[var(--brand-soft)] px-3 py-2 text-[12.5px]">
                <Sparkles size={13} className="shrink-0 text-brand" />
                <span className="min-w-0 flex-1 text-ink-2">
                  <span className="font-medium text-brand">{t.pick("น่าจะเสร็จแล้ว", "Likely done")}</span>
                  {item.suggested_done_evidence && <span className="italic"> — “{item.suggested_done_evidence}”</span>}
                </span>
                <Button size="sm" variant="primary" icon={<Check size={13} />} onClick={() => run(item, () => api.actionItems.acceptSuggestion(item.id))}>
                  {t.pick("ยืนยันว่าเสร็จ", "Confirm")}
                </Button>
                <Button size="sm" variant="ghost" icon={<X size={13} />} onClick={() => run(item, () => api.actionItems.dismissSuggestion(item.id))}>
                  {t.pick("ยังไม่เสร็จ", "Not yet")}
                </Button>
              </div>
            )}
          </div>
        );
      })}

      <ActionItemEditor item={editing} onClose={() => setEditing(null)} />
    </div>
  );
}

/** แก้ไขงานที่มีอยู่ (ส่ง item) หรือเพิ่มงานใหม่ในการประชุม (ส่ง meetingId) */
export function ActionItemEditor({
  item,
  meetingId,
  open,
  onClose,
}: {
  item?: ActionItem | null;
  meetingId?: string;
  open?: boolean;
  onClose: () => void;
}) {
  const t = useT();
  const isOpen = Boolean(item) || Boolean(open);
  const [text, setText] = useState("");
  const [owner, setOwner] = useState("");
  const [due, setDue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  //  เปิดใหม่ (หรือเปลี่ยนไปแก้งานอื่น) → เติมค่าของงานนั้นลงฟอร์ม
  const openKey = isOpen ? (item?.id ?? "new") : null;
  const [lastKey, setLastKey] = useState<string | null>(null);
  if (openKey !== lastKey) {
    setLastKey(openKey);
    if (openKey) {
      setText(item?.text ?? "");
      setOwner(item?.owner ?? "");
      setDue(item?.due_date ?? "");
      setError(null);
    }
  }

  const save = async () => {
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const payload = { text: text.trim(), owner: owner.trim(), due_date: due || null };
      if (item) {
        await api.actionItems.update(item.id, payload);
        refresh(item);
      } else if (meetingId) {
        await api.meetings.addActionItem(meetingId, payload);
        refresh({ meeting_id: meetingId });
      }
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      title={item ? t.pick("แก้ไขงาน", "Edit action item") : t.pick("เพิ่มงาน", "Add action item")}
      footer={
        <>
          <Button onClick={onClose}>{t("cancel")}</Button>
          <Button variant="primary" disabled={!text.trim() || busy} onClick={save} icon={item ? undefined : <Plus size={14} />}>
            {t("save")}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label={t.pick("งานที่ต้องทำ", "Task")} required>
          <Input value={text} onChange={(e) => setText(e.target.value)} autoFocus maxLength={2000} />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t.pick("ผู้รับผิดชอบ", "Owner")}>
            <Input value={owner} onChange={(e) => setOwner(e.target.value)} maxLength={120} />
          </Field>
          <Field label={t.pick("กำหนดเสร็จ", "Due date")}>
            <Input type="date" value={due} onChange={(e) => setDue(e.target.value)} />
          </Field>
        </div>
        {error && <p className="text-[12.5px] text-[var(--danger)]">{error}</p>}
      </div>
    </Modal>
  );
}
