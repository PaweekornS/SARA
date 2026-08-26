"use client";

/** M2 & v3.0.0 — อัปโหลด + แสดงสถานะ pipeline + สรุปตาม Template + Quick Share */

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AlertOctagon,
  Check,
  Copy,
  FileAudio,
  FileText,
  Loader2,
  Mail,
  Plus,
  RotateCw,
  Share2,
  Sparkles,
  Upload,
  UserPlus,
  X,
} from "lucide-react";
import { Badge, Button, Field, Input, Modal, cn } from "./ui";
import { useT } from "@/lib/i18n";
import * as api from "@/lib/api";
import { useApp } from "@/lib/store";
import type { Meeting, MeetingTemplateType } from "@/lib/types";

const MAX_MB = 500;

const TEMPLATE_OPTIONS: { id: MeetingTemplateType; name: string; icon: string; desc: string }[] = [
  {
    id: "general",
    name: "เลขานุการทั่วไป / ผู้บริหาร (Executive)",
    icon: "📋",
    desc: "เน้นมติที่ประชุม, ข้อตกลงร่วม และ Action Items",
  },
  {
    id: "marketing",
    name: "การตลาดและการเติบโต (Marketing)",
    icon: "📈",
    desc: "เน้นแคมเปญ, กลุ่มเป้าหมาย, ไอเดีย, KPIs และ Timeline",
  },
  {
    id: "finance",
    name: "บัญชีและการเงิน (Finance & Budget)",
    icon: "💰",
    desc: "เน้นการจัดสรรงบประมาณ, ต้นทุน, ความเสี่ยง และตัวเลข",
  },
  {
    id: "tech_standup",
    name: "ทีมพัฒนาและเทคนิค (Tech Standup)",
    icon: "💻",
    desc: "เน้นงานที่เสร็จ, งานที่กำลังทำ, Blockers และ Release Plan",
  },
];

function getTodayIso(): string {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function UploadMeetingModal({
  open,
  onClose,
  seriesId,
}: {
  open: boolean;
  onClose: () => void;
  seriesId: string;
}) {
  const t = useT();
  const router = useRouter();
  const { db } = useApp();
  const inputRef = useRef<HTMLInputElement>(null);

  const nextSeq =
    Math.max(0, ...db.meetings.filter((m) => m.series_id === seriesId).map((m) => m.sequence_no)) + 1;

  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [seqNo, setSeqNo] = useState(nextSeq);
  const [date, setDate] = useState(getTodayIso());
  const [template, setTemplate] = useState<MeetingTemplateType>("general");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setDate(getTodayIso());
      setSeqNo(
        Math.max(0, ...db.meetings.filter((m) => m.series_id === seriesId).map((m) => m.sequence_no)) + 1,
      );
    }
  }, [open, db.meetings, seriesId]);

  const isAudio = (name: string) => /\.(mp3|wav|m4a|aac|ogg|flac)$/i.test(name);
  const isTranscript = (name: string) => /\.(txt|docx?|pdf)$/i.test(name);

  const pick = (f: File) => {
    if (!isAudio(f.name) && !isTranscript(f.name)) {
      setError(t.pick("รองรับไฟล์เสียง (mp3, wav, m4a) และเอกสาร (txt, docx, pdf)", "Unsupported file type"));
      return;
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setError(t.pick(`ไฟล์ใหญ่เกิน ${MAX_MB} MB`, `File exceeds ${MAX_MB} MB`));
      return;
    }
    setError(null);
    setFile(f);
  };

  const submit = async () => {
    if (!file || !date) return;
    setBusy(true);
    try {
      const id = await api.uploadMeeting({
        series_id: seriesId,
        sequence_no: seqNo,
        meeting_date: date,
        file_name: file.name,
        source_kind: isAudio(file.name) ? "audio" : "transcript",
        simulate_asr_failure: false,
        file,
      });
      onClose();
      setFile(null);
      router.push(`/collections/${seriesId}/meetings/${id}`);
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
        "รองรับทั้งไฟล์บันทึกเสียงและเอกสารสรุป พร้อมเลือกรูปแบบการสรุปเฉพาะทาง",
        "Supports audio recordings and documents with specialized domain prompt templates.",
      )}
      width="max-w-xl"
      footer={
        <>
          <Button onClick={onClose}>{t("cancel")}</Button>
          <Button
            variant="primary"
            onClick={submit}
            disabled={!file || !date || busy}
            icon={busy ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}
          >
            {t.pick("เริ่มประมวลผล AI", "Start AI Processing")}
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
            accept=".mp3,.wav,.m4a,.aac,.ogg,.flac,.txt,.doc,.docx,.pdf"
            onChange={(e) => e.target.files?.[0] && pick(e.target.files[0])}
          />
          <div className="mb-2.5 flex h-11 w-11 items-center justify-center rounded-full bg-[var(--brand-soft)] text-brand">
            {file ? isAudio(file.name) ? <FileAudio size={20} /> : <FileText size={20} /> : <Upload size={20} />}
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
                {t.pick(`เสียง mp3 · wav · m4a หรือเอกสาร txt · docx · pdf (ไม่เกิน ${MAX_MB} MB)`, "Audio mp3/wav/m4a or text/docx/pdf")}
              </p>
            </>
          )}
        </div>

        {error && (
          <p className="rounded-[var(--radius)] bg-[var(--danger-bg)] px-3 py-2 text-[12.5px] text-[var(--danger)]">{error}</p>
        )}

        <Field label={t.pick("รูปแบบการสรุป (Domain Template)", "Summarization Template")}>
          <div className="grid grid-cols-2 gap-2">
            {TEMPLATE_OPTIONS.map((opt) => (
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
                  <span>{opt.icon}</span>
                  <span>{opt.name.split(" ")[0]}</span>
                </div>
                <p className="mt-1 text-[11px] leading-tight text-ink-3 line-clamp-2">{opt.desc}</p>
              </button>
            ))}
          </div>
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t.pick("ครั้งที่", "Sequence no.")}>
            <Input type="number" value={seqNo} onChange={(e) => setSeqNo(Number(e.target.value))} className="tnum" min={1} />
          </Field>
          <Field label={t.pick("วันที่ประชุม", "Meeting date")}>
            <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </Field>
        </div>
      </div>
    </Modal>
  );
}

export function ReuploadMeetingModal({
  open,
  onClose,
  meeting,
}: {
  open: boolean;
  onClose: () => void;
  meeting: Meeting;
}) {
  const t = useT();
  const inputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isAudio = (name: string) => /\.(mp3|wav|m4a|aac|ogg|flac)$/i.test(name);
  const isTranscript = (name: string) => /\.(txt|docx?|pdf)$/i.test(name);

  const pick = (f: File) => {
    if (!isAudio(f.name) && !isTranscript(f.name)) {
      setError(t.pick("รองรับเฉพาะไฟล์เสียง (mp3, wav, m4a) และเอกสาร (txt, docx, pdf)", "Unsupported file type"));
      return;
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setError(t.pick(`ไฟล์ใหญ่เกิน ${MAX_MB} MB`, `File exceeds ${MAX_MB} MB`));
      return;
    }
    setError(null);
    setFile(f);
  };

  const submit = async () => {
    if (!file) return;
    setBusy(true);
    try {
      await api.reuploadMeeting(meeting.id, file, false);
      onClose();
      setFile(null);
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
      title={t.pick("อัปโหลดไฟล์ใหม่สำหรับการประชุมนี้", "Reupload file for this meeting")}
      desc={t.pick(
        "การอัปโหลดไฟล์ใหม่จะล้างข้อมูลผลลัพธ์รอบเดิม และเริ่มประมวลผลตั้งแต่ต้น",
        "Uploading a new file will reset previous extraction results.",
      )}
      width="max-w-lg"
      footer={
        <>
          <Button onClick={onClose}>{t("cancel")}</Button>
          <Button
            variant="primary"
            onClick={submit}
            disabled={!file || busy}
            icon={busy ? <Loader2 size={15} className="animate-spin" /> : undefined}
          >
            {t.pick("อัปโหลดและประมวลผลใหม่", "Upload and reprocess")}
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
            accept=".mp3,.wav,.m4a,.aac,.ogg,.flac,.txt,.doc,.docx,.pdf"
            onChange={(e) => e.target.files?.[0] && pick(e.target.files[0])}
          />
          <div className="mb-2.5 flex h-10 w-10 items-center justify-center rounded-full bg-[var(--brand-soft)] text-brand">
            {file ? isAudio(file.name) ? <FileAudio size={18} /> : <FileText size={18} /> : <Upload size={18} />}
          </div>
          {file ? (
            <>
              <p className="text-[13.5px] font-medium text-ink">{file.name}</p>
              <p className="tnum mt-0.5 text-[12px] text-ink-3">{(file.size / 1024 / 1024).toFixed(1)} MB</p>
            </>
          ) : (
            <>
              <p className="text-[13.5px] font-medium text-ink">
                {t.pick("ลากไฟล์ใหม่มาวาง หรือคลิกเพื่อเลือกไฟล์", "Drop a new file here or click to browse")}
              </p>
              <p className="mt-1 text-[12px] text-ink-3">
                {t.pick(`ไฟล์เสียงหรือเอกสารไม่เกิน ${MAX_MB} MB`, "Audio or document")}
              </p>
            </>
          )}
        </div>

        {error && (
          <p className="rounded-[var(--radius)] bg-[var(--danger-bg)] px-3 py-2 text-[12.5px] text-[var(--danger)]">{error}</p>
        )}
      </div>
    </Modal>
  );
}

/* ── 1-Click Quick Email Share Modal ─────────────────────────────────────── */

export function QuickEmailShareModal({
  open,
  onClose,
  title,
  summary,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  summary: string;
}) {
  const t = useT();
  const { db } = useApp();
  const [recipients, setRecipients] = useState<string[]>([]);
  const [currentInput, setCurrentInput] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);
  const [subject, setSubject] = useState(title ? `สรุปการประชุม: ${title}` : "สรุปการประชุมโดย SARA");
  const [sending, setSending] = useState(false);
  const [sentSuccess, setSentSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset state when opening
  useEffect(() => {
    if (open) {
      setRecipients([]);
      setCurrentInput("");
      setInputError(null);
      setError(null);
      setSentSuccess(false);
      setSubject(title ? `สรุปการประชุม: ${title}` : "สรุปการประชุมโดย SARA");
    }
  }, [open, title]);

  // Validate email address format & presence of @
  const validateEmail = (email: string): { valid: boolean; reason?: string } => {
    const trimmed = email.trim();
    if (!trimmed) {
      return { valid: false, reason: t.pick("กรุณากรอกที่อยู่อีเมล", "Email address is required") };
    }
    if (!trimmed.includes("@")) {
      return {
        valid: false,
        reason: t.pick("อีเมลต้องมีเครื่องหมาย '@' (เช่น user@example.com)", "Email must contain '@' (e.g. user@example.com)"),
      };
    }
    const [localPart, domainPart] = trimmed.split("@");
    if (!localPart || !domainPart) {
      return {
        valid: false,
        reason: t.pick("รูปแบบอีเมลไม่สมบูรณ์ (เช่น user@example.com)", "Incomplete email format (e.g. user@example.com)"),
      };
    }
    if (!domainPart.includes(".") || domainPart.startsWith(".") || domainPart.endsWith(".")) {
      return {
        valid: false,
        reason: t.pick("โดเมนอีเมลต้องมีนามสกุล '.' (เช่น gmail.com, novatech.io)", "Domain must have a valid extension (e.g. gmail.com, novatech.io)"),
      };
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(trimmed)) {
      return {
        valid: false,
        reason: t.pick("รูปแบบอีเมลไม่ถูกต้อง", "Invalid email address format"),
      };
    }
    return { valid: true };
  };

  const handleAddRecipient = (emailToAdd?: string) => {
    const target = (emailToAdd ?? currentInput).trim();
    if (!target) return;

    const validation = validateEmail(target);
    if (!validation.valid) {
      setInputError(validation.reason || "Invalid email");
      return;
    }

    if (recipients.map((r) => r.toLowerCase()).includes(target.toLowerCase())) {
      setInputError(t.pick("อีเมลนี้ถูกเพิ่มไปแล้ว", "This email is already in the list"));
      return;
    }

    if (recipients.length >= 10) {
      setInputError(t.pick("เพิ่มผู้รับได้สูงสุด 10 คน", "Maximum 10 recipients allowed"));
      return;
    }

    setRecipients((prev) => [...prev, target]);
    setCurrentInput("");
    setInputError(null);
  };

  const handleRemoveRecipient = (indexToRemove: number) => {
    setRecipients((prev) => prev.filter((_, i) => i !== indexToRemove));
    setInputError(null);
  };

  // Quick suggestions from workspace people
  const availableSuggestions = db.people.filter(
    (p) => p.email && !p.is_department && !recipients.map((r) => r.toLowerCase()).includes(p.email.toLowerCase()),
  );

  const handleSend = async () => {
    // If user has typed an unadded valid email, auto-add it before sending
    let finalRecipients = [...recipients];
    if (currentInput.trim()) {
      const validation = validateEmail(currentInput.trim());
      if (validation.valid && !finalRecipients.map((r) => r.toLowerCase()).includes(currentInput.trim().toLowerCase())) {
        finalRecipients = [...finalRecipients, currentInput.trim()];
        setRecipients(finalRecipients);
        setCurrentInput("");
      }
    }

    if (finalRecipients.length === 0) {
      setError(t.pick("กรุณาเพิ่มอีเมลผู้รับอย่างน้อย 1 คน", "Please add at least one recipient"));
      return;
    }

    setSending(true);
    setError(null);
    try {
      if (finalRecipients.length > 10) {
        throw new Error(t.pick("จำกัดไม่เกิน 10 อีเมลต่อครั้ง", "Maximum 10 recipients allowed"));
      }

      await api.sendDirectEmail({
        recipients: finalRecipients,
        subject: subject || "สรุปการประชุมโดย SARA",
        summary_text: summary,
        template_name: "General",
      });
      setSentSuccess(true);
      setTimeout(() => {
        setSentSuccess(false);
        onClose();
      }, 1500);
    } catch (err: any) {
      setError(err.message || String(err));
    } finally {
      setSending(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t.pick("ส่งสรุปการประชุมผ่านอีเมล", "Share Summary via Email")}
      desc={t.pick("ส่งอีเมลสรุปเนื้อหาและมติไปยังผู้เข้าร่วมประชุมได้ทันที", "Dispatch summary to meeting participants.")}
      width="max-w-lg"
      footer={
        <>
          <Button onClick={onClose}>{t("cancel")}</Button>
          <Button
            variant="primary"
            onClick={handleSend}
            disabled={(recipients.length === 0 && !currentInput.trim()) || sending}
            icon={sending ? <Loader2 size={14} className="animate-spin" /> : sentSuccess ? <Check size={14} /> : <Mail size={14} />}
          >
            {sentSuccess
              ? t.pick("ส่งสำเร็จ!", "Sent!")
              : sending
              ? t.pick("กำลังส่ง…", "Sending…")
              : t.pick(`ส่งอีเมล (${recipients.length})`, `Send Email (${recipients.length})`)}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label={t.pick("หัวข้ออีเมล", "Subject")}>
          <Input value={subject} onChange={(e) => setSubject(e.target.value)} />
        </Field>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-[12.5px] font-medium text-ink-2">
              {t.pick("รายชื่ออีเมลผู้รับ", "Recipient List")}
            </label>
            <span className="text-[11px] text-ink-4">
              {recipients.length} / 10 {t.pick("คน", "recipients")}
            </span>
          </div>

          {/* Recipient Chips Container */}
          {recipients.length > 0 ? (
            <div className="flex flex-wrap gap-1.5 p-2.5 rounded-[var(--radius)] border border-line bg-surface-2 min-h-[48px] max-h-[130px] overflow-y-auto">
              {recipients.map((email, i) => (
                <span
                  key={i}
                  className="inline-flex items-center gap-1.5 rounded-full bg-[var(--brand-soft)] border border-brand/20 px-3 py-1 text-[12px] font-medium text-brand animate-fade-in"
                >
                  <Mail size={12} className="shrink-0 text-brand" />
                  <span className="truncate max-w-[200px]">{email}</span>
                  <button
                    type="button"
                    onClick={() => handleRemoveRecipient(i)}
                    className="rounded-full p-0.5 hover:bg-brand/20 text-brand cursor-pointer transition-colors"
                    title={t("delete")}
                  >
                    <X size={13} />
                  </button>
                </span>
              ))}
            </div>
          ) : (
            <div className="rounded-[var(--radius)] border border-dashed border-line p-3 text-center text-[12px] text-ink-4 bg-surface-2/50">
              {t.pick("ยังไม่มีผู้รับ (พิมพ์อีเมลด้านล่างแล้วกดปุ่ม + เพิ่ม)", "No recipients added yet (type email below and click + Add)")}
            </div>
          )}

          {/* Add Recipient Input with Button */}
          <div className="pt-1">
            <div className="flex gap-2">
              <div className="relative flex-1">
                <input
                  type="email"
                  value={currentInput}
                  onChange={(e) => {
                    setCurrentInput(e.target.value);
                    if (inputError) setInputError(null);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleAddRecipient();
                    }
                  }}
                  placeholder="name@company.com"
                  className={cn(
                    "w-full rounded-[var(--radius)] border bg-surface px-3 py-2 text-[13px] text-ink outline-none transition-colors",
                    inputError ? "border-[var(--danger)] focus:border-[var(--danger)]" : "border-line focus:border-brand",
                  )}
                />
              </div>
              <Button
                type="button"
                variant="secondary"
                onClick={() => handleAddRecipient()}
                disabled={!currentInput.trim() || recipients.length >= 10}
                icon={<Plus size={14} />}
              >
                {t.pick("เพิ่ม", "Add")}
              </Button>
            </div>
            {inputError && (
              <p className="mt-1.5 text-[11.5px] text-[var(--danger)] flex items-center gap-1">
                <span>⚠</span> {inputError}
              </p>
            )}
          </div>

          {/* Quick Team Suggestions */}
          {availableSuggestions.length > 0 && (
            <div className="pt-2 space-y-1.5">
              <p className="text-[11px] font-medium text-ink-4 uppercase tracking-wider">
                {t.pick("เพิ่มด่วนจากสมาชิกในทีม:", "Quick select team member:")}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {availableSuggestions.slice(0, 4).map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => handleAddRecipient(p.email)}
                    className="inline-flex items-center gap-1.5 rounded-[var(--radius)] border border-line bg-surface px-2.5 py-1 text-[11.5px] text-ink-2 hover:border-brand hover:text-brand hover:bg-[var(--brand-soft)] cursor-pointer transition-colors"
                  >
                    <UserPlus size={12} className="text-brand shrink-0" />
                    <span>{p.full_name}</span>
                    <span className="text-[10px] text-ink-4">({p.email})</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {error && (
          <p className="rounded-[var(--radius)] bg-[var(--danger-bg)] px-3 py-2 text-[12px] text-[var(--danger)]">
            {error}
          </p>
        )}
      </div>
    </Modal>
  );
}

/* ── 1-Click Copy Summary Button ─────────────────────────────────────────── */

export function CopySummaryButton({ summary, title }: { summary: string; title: string }) {
  const t = useT();
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (!summary) return;
    const text = `# ${title}\n\n${summary}\n\n---\n*สรุปโดย SARA · Smart AI Meeting Assistant*`;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  };

  return (
    <Button size="sm" variant="ghost" onClick={handleCopy} icon={copied ? <Check size={13} className="text-ok" /> : <Copy size={13} />}>
      {copied ? t.pick("คัดลอกแล้ว", "Copied!") : t.pick("คัดลอก Markdown", "Copy Markdown")}
    </Button>
  );
}

/* ── สถานะ pipeline ──────────────────────────────────────────────────── */

const STAGE_LABEL: Record<string, [string, string]> = {
  upload: ["รับไฟล์", "Upload"],
  asr: ["ถอดเสียง", "Transcription"],
  extract: ["สรุปเนื้อหาและสกัดมติ", "Summarize & Extract Resolutions"],
  done: ["พร้อมตรวจทาน", "Ready for review"],
};

export function PipelineStatus({ meeting, onRetry }: { meeting: Meeting; onRetry?: () => void }) {
  const t = useT();
  const failed = meeting.pipeline.find((p) => p.state === "failed");

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
                    step.state === "pending" && "border-line bg-surface text-ink-4",
                  )}
                >
                  {step.state === "ok" ? (
                    <Check size={13} strokeWidth={3} />
                  ) : step.state === "running" ? (
                    <Loader2 size={13} className="animate-spin" />
                  ) : step.state === "failed" ? (
                    <AlertOctagon size={13} />
                  ) : (
                    i + 1
                  )}
                </span>
                {!last && (
                  <span
                    className={cn("w-px flex-1", step.state === "ok" ? "bg-[var(--ok)]" : "bg-line")}
                    style={{ minHeight: 18 }}
                  />
                )}
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
                {step.error && (
                  <p className="mt-1.5 rounded-[var(--radius)] bg-[var(--danger-bg)] px-3 py-2 text-[12.5px] leading-relaxed text-[var(--danger)]">
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
            {t.pick(
              "ไม่มีการสร้างข้อมูลทดแทน ทุกอย่างที่ท่านเห็นในระบบมาจากไฟล์จริงเท่านั้น",
              "No substitute data was generated — everything in the system comes from the real file only.",
            )}
          </p>
          <Button size="sm" icon={<RotateCw size={14} />} onClick={onRetry}>
            {t("retry")}
          </Button>
        </div>
      )}
    </div>
  );
}
