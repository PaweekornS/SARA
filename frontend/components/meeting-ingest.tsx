"use client";

/** อัปโหลดการประชุม · สถานะ pipeline · ส่งอีเมลสรุป */

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertOctagon, Check, FileAudio, FileText, Loader2, Mail, MinusCircle, Plus, RotateCw, Sparkles, Upload, X } from "lucide-react";
import * as api from "@/lib/api";
import { useCollection, useTemplates } from "@/lib/data";
import { todayIso } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { invalidate } from "@/lib/query";
import type { Meeting, TemplateId } from "@/lib/types";
import { Badge, Button, Field, Input, Modal, cn } from "./ui";

const MAX_MB = 500;
const AUDIO_RE = /\.(mp3|wav|m4a|aac|ogg|flac)$/i;
const DOC_RE = /\.(txt|docx|pdf|md)$/i;

const TEMPLATE_ICON: Record<TemplateId, string> = {
  general: "📋",
  marketing: "📈",
  finance: "💰",
  tech_standup: "💻",
};

export function UploadMeetingModal({
  open,
  onClose,
  collectionId,
}: {
  open: boolean;
  onClose: () => void;
  collectionId: string;
}) {
  const t = useT();
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const { data: templates = [] } = useTemplates();
  const { data: collection } = useCollection(collectionId);

  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [title, setTitle] = useState("");
  const [date, setDate] = useState(todayIso());
  const [template, setTemplate] = useState<TemplateId>("general");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  //  เปิด modal ใหม่ทุกครั้งเริ่มจากฟอร์มว่าง (ปรับ state ตอน render แทน effect ตามแนวทางของ React)
  const [wasOpen, setWasOpen] = useState(false);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) {
      setFile(null);
      setTitle("");
      setError(null);
      setDate(todayIso());
      setTemplate(collection?.default_template ?? "general");
    }
  }

  const pick = (f: File) => {
    if (!AUDIO_RE.test(f.name) && !DOC_RE.test(f.name)) {
      setError(t.pick("รองรับไฟล์เสียง (mp3, wav, m4a, aac, ogg, flac) และเอกสาร (txt, docx, pdf, md)", "Unsupported file type"));
      return;
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setError(t.pick(`ไฟล์ใหญ่เกิน ${MAX_MB} MB`, `File exceeds ${MAX_MB} MB`));
      return;
    }
    setError(null);
    setFile(f);
    if (!title) setTitle(f.name.replace(/\.[^.]+$/, ""));
  };

  const submit = async () => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const meeting = await api.meetings.upload({
        file,
        collection_id: collectionId,
        title: title.trim(),
        meeting_date: date || undefined,
        template,
      });
      invalidate(`collections:${collectionId}`, "collections");
      onClose();
      router.push(`/collections/${collectionId}/meetings/${meeting.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t.pick("อัปโหลดและประมวลผลการประชุม", "Upload & Summarize Meeting")}
      desc={t.pick(
        "รองรับทั้งไฟล์บันทึกเสียงและเอกสาร พร้อมเลือกรูปแบบการสรุปให้ตรงกับประเภทการประชุม",
        "Supports audio recordings and documents with meeting-type templates.",
      )}
      width="max-w-xl"
      footer={
        <>
          <Button onClick={onClose}>{t("cancel")}</Button>
          <Button
            variant="primary"
            onClick={submit}
            disabled={!file || busy}
            icon={busy ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}
          >
            {busy ? t.pick("กำลังอัปโหลด…", "Uploading…") : t.pick("เริ่มประมวลผล AI", "Start AI Processing")}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            const f = e.dataTransfer.files?.[0];
            if (f) pick(f);
          }}
          onClick={() => inputRef.current?.click()}
          className={cn(
            "flex cursor-pointer flex-col items-center justify-center rounded-[var(--radius)] border-2 border-dashed px-6 py-8 text-center transition-colors",
            dragging ? "border-brand bg-[var(--brand-soft)]" : "border-[var(--line-strong)] hover:border-brand hover:bg-surface-2",
          )}
        >
          <input
            ref={inputRef}
            type="file"
            className="hidden"
            accept=".mp3,.wav,.m4a,.aac,.ogg,.flac,.txt,.docx,.pdf,.md"
            onChange={(e) => e.target.files?.[0] && pick(e.target.files[0])}
          />
          <div className="mb-2.5 flex h-11 w-11 items-center justify-center rounded-full bg-[var(--brand-soft)] text-brand">
            {file ? AUDIO_RE.test(file.name) ? <FileAudio size={20} /> : <FileText size={20} /> : <Upload size={20} />}
          </div>
          {file ? (
            <>
              <p className="text-[14px] font-semibold text-ink">{file.name}</p>
              <p className="tnum mt-0.5 text-[12px] text-ink-3">{(file.size / 1024 / 1024).toFixed(1)} MB</p>
            </>
          ) : (
            <>
              <p className="text-[13.5px] font-medium text-ink">
                {t.pick("ลากไฟล์มาวาง หรือคลิกเพื่อเลือกไฟล์", "Drop a file here or click to browse")}
              </p>
              <p className="mt-1 text-[12px] text-ink-3">
                {t.pick(`เสียง mp3 · wav · m4a หรือเอกสาร txt · docx · pdf (ไม่เกิน ${MAX_MB} MB)`, "Audio mp3/wav/m4a or txt/docx/pdf")}
              </p>
            </>
          )}
        </div>

        {error && <p className="rounded-[var(--radius)] bg-[var(--danger-bg)] px-3 py-2 text-[12.5px] text-[var(--danger)]">{error}</p>}

        <Field label={t.pick("รูปแบบการสรุป", "Summary template")}>
          <div className="grid grid-cols-2 gap-2">
            {templates.map((opt) => (
              <button
                key={opt.id}
                type="button"
                onClick={() => setTemplate(opt.id)}
                className={cn(
                  "flex flex-col items-start rounded-[var(--radius)] border p-2.5 text-left transition-all",
                  template === opt.id
                    ? "border-brand bg-[var(--brand-soft)] text-brand shadow-sm ring-1 ring-brand"
                    : "border-line bg-surface hover:bg-surface-2 text-ink",
                )}
              >
                <div className="flex items-center gap-1.5 font-medium text-[13px]">
                  <span>{TEMPLATE_ICON[opt.id]}</span>
                  <span>{opt.name.split(" (")[0]}</span>
                </div>
                <p className="mt-1 text-[11px] leading-tight text-ink-3 line-clamp-2">{opt.description}</p>
              </button>
            ))}
          </div>
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t.pick("ชื่อการประชุม", "Title")}>
            <Input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} />
          </Field>
          <Field label={t.pick("วันที่ประชุม", "Meeting date")}>
            <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </Field>
        </div>
      </div>
    </Modal>
  );
}

/* ── ส่งอีเมลสรุป ────────────────────────────────────────────────────── */

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MAX_RECIPIENTS = 10;

export function EmailSummaryModal({ open, onClose, meeting }: { open: boolean; onClose: () => void; meeting: Meeting }) {
  const t = useT();
  const [recipients, setRecipients] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);
  const [subject, setSubject] = useState("");
  const [includeItems, setIncludeItems] = useState(true);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [wasOpen, setWasOpen] = useState(false);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) {
      setRecipients([]);
      setInput("");
      setInputError(null);
      setError(null);
      setResult(null);
      setIncludeItems(true);
      setSubject(`สรุปการประชุม: ${meeting.title}`);
    }
  }

  const add = (raw: string = input): string[] | null => {
    const email = raw.trim();
    if (!email) return recipients;
    if (!EMAIL_RE.test(email)) {
      setInputError(t.pick("รูปแบบอีเมลไม่ถูกต้อง (เช่น name@company.com)", "Invalid email (e.g. name@company.com)"));
      return null;
    }
    if (recipients.some((r) => r.toLowerCase() === email.toLowerCase())) {
      setInputError(t.pick("อีเมลนี้ถูกเพิ่มไปแล้ว", "Already added"));
      return null;
    }
    if (recipients.length >= MAX_RECIPIENTS) {
      setInputError(t.pick(`เพิ่มผู้รับได้สูงสุด ${MAX_RECIPIENTS} คน`, `Max ${MAX_RECIPIENTS} recipients`));
      return null;
    }
    const next = [...recipients, email];
    setRecipients(next);
    setInput("");
    setInputError(null);
    return next;
  };

  const send = async () => {
    const list = input.trim() ? add() : recipients;
    if (!list || list.length === 0) {
      setError(t.pick("กรุณาเพิ่มอีเมลผู้รับอย่างน้อย 1 คน", "Add at least one recipient"));
      return;
    }
    setSending(true);
    setError(null);
    try {
      const res = await api.meetings.email(meeting.id, { recipients: list, subject: subject.trim(), include_action_items: includeItems });
      if (res.failed.length > 0) {
        setError(t.pick(`ส่งไม่สำเร็จ: ${res.failed.join(", ")}`, `Failed: ${res.failed.join(", ")}`));
      }
      if (res.sent.length > 0) {
        setResult(t.pick(`ส่งแล้ว ${res.sent.length} ฉบับ`, `Sent to ${res.sent.length}`));
        if (res.failed.length === 0) setTimeout(onClose, 1500);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSending(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t.pick("ส่งสรุปการประชุมทางอีเมล", "Email summary")}
      desc={t.pick("อีเมลมีสรุป ประเด็นสำคัญ และรายการงานจากการประชุมนี้ ผู้รับตอบกลับจะถึงอีเมลของคุณ", "Includes summary, key points and action items. Replies go to your email.")}
      width="max-w-lg"
      footer={
        <>
          <Button onClick={onClose}>{t("cancel")}</Button>
          <Button
            variant="primary"
            onClick={send}
            disabled={(recipients.length === 0 && !input.trim()) || sending}
            icon={sending ? <Loader2 size={14} className="animate-spin" /> : result ? <Check size={14} /> : <Mail size={14} />}
          >
            {result ?? (sending ? t.pick("กำลังส่ง…", "Sending…") : t.pick(`ส่งอีเมล (${recipients.length})`, `Send (${recipients.length})`))}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label={t.pick("หัวข้ออีเมล", "Subject")}>
          <Input value={subject} onChange={(e) => setSubject(e.target.value)} maxLength={200} />
        </Field>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[12.5px] font-medium text-ink-2">{t.pick("ผู้รับ", "Recipients")}</span>
            <span className="text-[11px] text-ink-4">
              {recipients.length} / {MAX_RECIPIENTS}
            </span>
          </div>

          {recipients.length > 0 && (
            <div className="flex flex-wrap gap-1.5 rounded-[var(--radius)] border border-line bg-surface-2 p-2.5">
              {recipients.map((email, i) => (
                <span key={email} className="inline-flex items-center gap-1.5 rounded-full border border-brand/20 bg-[var(--brand-soft)] px-3 py-1 text-[12px] font-medium text-brand">
                  <span className="max-w-[200px] truncate">{email}</span>
                  <button
                    type="button"
                    onClick={() => setRecipients((prev) => prev.filter((_, j) => j !== i))}
                    className="rounded-full p-0.5 hover:bg-brand/20 cursor-pointer"
                    aria-label={t("delete")}
                  >
                    <X size={13} />
                  </button>
                </span>
              ))}
            </div>
          )}

          <div className="flex gap-2">
            <input
              type="email"
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                setInputError(null);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  add();
                }
              }}
              placeholder="name@company.com"
              className={cn(
                "w-full rounded-[var(--radius)] border bg-surface px-3 py-2 text-[13px] text-ink outline-none transition-colors",
                inputError ? "border-[var(--danger)]" : "border-line focus:border-brand",
              )}
            />
            <Button type="button" onClick={() => add()} disabled={!input.trim() || recipients.length >= MAX_RECIPIENTS} icon={<Plus size={14} />}>
              {t("add")}
            </Button>
          </div>
          {inputError && <p className="text-[11.5px] text-[var(--danger)]">⚠ {inputError}</p>}
        </div>

        <label className="flex items-center gap-2 text-[13px] text-ink-2 cursor-pointer">
          <input type="checkbox" checked={includeItems} onChange={(e) => setIncludeItems(e.target.checked)} className="accent-brand" />
          {t.pick("แนบรายการงานที่ต้องทำต่อ", "Include action items")}
        </label>

        {error && <p className="rounded-[var(--radius)] bg-[var(--danger-bg)] px-3 py-2 text-[12px] text-[var(--danger)]">{error}</p>}
      </div>
    </Modal>
  );
}

/* ── สถานะ pipeline ──────────────────────────────────────────────────── */

const STAGE_LABEL: Record<string, [string, string]> = {
  upload: ["รับไฟล์", "Upload"],
  asr: ["ถอดเสียง", "Transcription"],
  summarize: ["สรุปเนื้อหาและงานที่ต้องทำ", "Summary & action items"],
  index: ["จัดทำดัชนีสำหรับถาม-ตอบ", "Index for Q&A"],
  followup: ["ตรวจงานค้างจากการประชุมก่อน ๆ", "Check open tasks from earlier meetings"],
  done: ["พร้อมใช้งาน", "Ready"],
};

export function PipelineStatus({ meeting, onRetry }: { meeting: Meeting; onRetry?: () => void }) {
  const t = useT();
  const failed = meeting.status === "failed";

  return (
    <div>
      <ol className="space-y-0">
        {meeting.pipeline.map((step, i) => {
          const last = i === meeting.pipeline.length - 1;
          return (
            <li key={step.stage} className="flex gap-3">
              <div className="flex flex-col items-center">
                <span
                  className={cn(
                    "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[11px] font-semibold",
                    step.state === "ok" && "border-[var(--ok)] bg-[var(--ok-bg)] text-[var(--ok)]",
                    step.state === "running" && "border-brand bg-[var(--brand-soft)] text-brand",
                    step.state === "failed" && "border-[var(--danger)] bg-[var(--danger-bg)] text-[var(--danger)]",
                    step.state === "skipped" && "border-[var(--warn)] bg-[var(--warn-bg)] text-[var(--warn)]",
                    step.state === "pending" && "border-line bg-surface text-ink-4",
                  )}
                >
                  {step.state === "ok" ? (
                    <Check size={13} strokeWidth={3} />
                  ) : step.state === "running" ? (
                    <Loader2 size={13} className="animate-spin" />
                  ) : step.state === "failed" ? (
                    <AlertOctagon size={13} />
                  ) : step.state === "skipped" ? (
                    <MinusCircle size={13} />
                  ) : (
                    i + 1
                  )}
                </span>
                {!last && <span className={cn("w-px flex-1", step.state === "ok" ? "bg-[var(--ok)]" : "bg-line")} style={{ minHeight: 18 }} />}
              </div>
              <div className={cn("min-w-0 flex-1", last ? "pb-0" : "pb-4")}>
                <p
                  className={cn(
                    "text-[13.5px] font-medium",
                    step.state === "pending" ? "text-ink-4" : "text-ink",
                    step.state === "failed" && "text-[var(--danger)]",
                  )}
                >
                  {STAGE_LABEL[step.stage]?.[t.lang === "th" ? 0 : 1] ?? step.stage}
                </p>
                {step.state === "ok" && step.detail && <p className="mt-0.5 text-[12px] text-ink-3">{step.detail}</p>}
                {step.error && (
                  <p
                    className={cn(
                      "mt-1.5 rounded-[var(--radius)] px-3 py-2 text-[12.5px] leading-relaxed",
                      step.state === "skipped" ? "bg-[var(--warn-bg)] text-[var(--warn)]" : "bg-[var(--danger-bg)] text-[var(--danger)]",
                    )}
                  >
                    {step.error}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      {failed && onRetry && (
        <div className="mt-4 flex flex-wrap items-center gap-3 rounded-[var(--radius)] border border-line bg-surface-2 p-3.5">
          <Badge tone="danger">{t.pick("ประมวลผลไม่สำเร็จ", "Processing failed")}</Badge>
          <p className="flex-1 text-[12.5px] leading-snug text-ink-2">
            {t.pick("ระบบไม่สร้างข้อมูลทดแทน ทุกอย่างที่เห็นมาจากไฟล์จริงเท่านั้น", "No substitute data is generated.")}
          </p>
          <Button size="sm" icon={<RotateCw size={14} />} onClick={onRetry}>
            {t("retry")}
          </Button>
        </div>
      )}
    </div>
  );
}

export function MeetingStatusBadge({ meeting }: { meeting: Meeting }) {
  const t = useT();
  if (meeting.status === "processing")
    return (
      <Badge tone="brand">
        <Loader2 size={11} className="animate-spin" /> {t.pick("กำลังประมวลผล", "Processing")}
      </Badge>
    );
  if (meeting.status === "failed") return <Badge tone="danger">{t.pick("ประมวลผลไม่สำเร็จ", "Failed")}</Badge>;
  return null;
}
