"use client";

/** M2 — อัปโหลด + แสดงสถานะ pipeline เป็นขั้น (FR-M2-01 ถึง 05) */

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertOctagon, Check, FileAudio, FileText, Loader2, RotateCw, Upload } from "lucide-react";
import { Badge, Button, Field, Input, Modal, cn } from "./ui";
import { useT } from "@/lib/i18n";
import * as api from "@/lib/api";
import { useApp } from "@/lib/store";
import type { Meeting } from "@/lib/types";

const MAX_MB = 500;

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
  const series = db.series.find((s) => s.id === seriesId);

  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [seqNo, setSeqNo] = useState(nextSeq);
  const [date, setDate] = useState(getTodayIso());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setDate(getTodayIso());
    }
  }, [open]);

  const isAudio = (name: string) => /\.(mp3|wav|m4a|aac|ogg|flac)$/i.test(name);
  const isTranscript = (name: string) => /\.(txt|docx?)$/i.test(name);

  const pick = (f: File) => {
    if (!isAudio(f.name) && !isTranscript(f.name)) {
      setError(t.pick("รองรับเฉพาะไฟล์เสียง (mp3, wav, m4a) และ transcript (txt, docx)", "Unsupported file type"));
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
      router.push(`/series/${seriesId}/meetings/${id}`);
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
      title={t("uploadMeeting")}
      desc={t.pick(
        "ระบบจะดึงมติค้างของชุดการประชุมนี้ไปเป็นบริบท แล้วจับคู่คำพูดใหม่กับมติเดิมให้อัตโนมัติ",
        "Open resolutions from this series are used as context for cross-meeting matching.",
      )}
      width="max-w-xl"
      footer={
        <>
          <Button onClick={onClose}>{t("cancel")}</Button>
          <Button variant="primary" onClick={submit} disabled={!file || !date || busy} icon={busy ? <Loader2 size={15} className="animate-spin" /> : undefined}>
            {t.pick("เริ่มประมวลผล", "Start processing")}
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
            accept=".mp3,.wav,.m4a,.aac,.ogg,.flac,.txt,.doc,.docx"
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
                {t.pick("ลากไฟล์มาวาง หรือคลิกเพื่อเลือก", "Drop a file here or click to browse")}
              </p>
              <p className="mt-1 text-[12px] text-ink-3">
                {t.pick(`ไฟล์เสียง mp3 · wav · m4a ไม่เกิน ${MAX_MB} MB หรือ transcript txt · docx`, "Audio or transcript")}
              </p>
            </>
          )}
        </div>

        {error && (
          <p className="rounded-[var(--radius)] bg-[var(--danger-bg)] px-3 py-2 text-[12.5px] text-[var(--danger)]">{error}</p>
        )}

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
  const isTranscript = (name: string) => /\.(txt|docx?)$/i.test(name);

  const pick = (f: File) => {
    if (!isAudio(f.name) && !isTranscript(f.name)) {
      setError(t.pick("รองรับเฉพาะไฟล์เสียง (mp3, wav, m4a) และ transcript (txt, docx)", "Unsupported file type"));
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
      title={t.pick("ลองใหม่ — อัปโหลดไฟล์การประชุม", "Retry — Upload Meeting File")}
      desc={t.pick(
        `อัปโหลดไฟล์เสียงหรือ transcript ใหม่สำหรับการประชุมครั้งที่ ${meeting.sequence_no}/${meeting.fiscal_year}`,
        `Upload a new audio or transcript file for meeting ${meeting.sequence_no}/${meeting.fiscal_year}.`,
      )}
      width="max-w-xl"
      footer={
        <>
          <Button onClick={onClose}>{t("cancel")}</Button>
          <Button
            variant="primary"
            onClick={submit}
            disabled={!file || busy}
            icon={busy ? <Loader2 size={15} className="animate-spin" /> : undefined}
          >
            {t.pick("เริ่มประมวลผลใหม่", "Start re-processing")}
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
            accept=".mp3,.wav,.m4a,.aac,.ogg,.flac,.txt,.doc,.docx"
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
                {t.pick(`ไฟล์เสียง mp3 · wav · m4a ไม่เกิน ${MAX_MB} MB หรือ transcript txt · docx`, "Audio or transcript")}
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
