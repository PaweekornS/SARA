"use client";

import { useImperativeHandle, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  Calendar,
  Check,
  Clock,
  Copy,
  Download,
  FileText,
  FolderKanban,
  Headphones,
  ListChecks,
  Mail,
  Pause,
  Play,
  Plus,
  RotateCcw,
  RotateCw,
  Sparkles,
  Trash2,
} from "lucide-react";
import { ActionItemEditor, ActionItemList } from "@/components/action-items";
import { PageBody, PageHeader } from "@/components/app-shell";
import { EmailSummaryModal, PipelineStatus } from "@/components/meeting-ingest";
import { Button, Card, ConfirmModal, ErrorNote, Field, Input, Loading, Modal, cn } from "@/components/ui";
import * as api from "@/lib/api";
import { useCollection, useMeeting, useMeetingActions, useSegments, useTemplates } from "@/lib/data";
import { formatThaiDate, formatTimecode, speakerLabel } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { invalidate } from "@/lib/query";
import type { Meeting, Segment } from "@/lib/types";

const SPEAKER_STYLES = [
  "bg-[var(--speaker-1-bg)] text-[var(--speaker-1)] border-[var(--speaker-1)]/20",
  "bg-[var(--speaker-2-bg)] text-[var(--speaker-2)] border-[var(--speaker-2)]/20",
  "bg-[var(--speaker-3-bg)] text-[var(--speaker-3)] border-[var(--speaker-3)]/20",
  "bg-[var(--speaker-4-bg)] text-[var(--speaker-4)] border-[var(--speaker-4)]/20",
];

export default function MeetingPage() {
  const t = useT();
  const router = useRouter();
  const { id: collectionId, mid: meetingId } = useParams<{ id: string; mid: string }>();
  const { data: collection } = useCollection(collectionId);
  const { data: meeting, error, loading, reload } = useMeeting(meetingId);

  const [emailOpen, setEmailOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  if (error) {
    return (
      <PageBody>
        <ErrorNote error={error} onRetry={reload} />
        <Link href={`/collections/${collectionId}`} className="mt-4 inline-block text-[13px] text-brand hover:underline">
          {t.pick("← กลับหน้าคอลเลกชัน", "← Back to collection")}
        </Link>
      </PageBody>
    );
  }
  if (loading || !meeting) return <Loading />;

  const ready = meeting.status === "ready";

  const retry = async () => {
    setActionError(null);
    try {
      await api.meetings.retry(meeting.id);
      invalidate(`meetings:${meeting.id}`, `collections:${collectionId}`);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e));
    }
  };

  const remove = async () => {
    try {
      await api.meetings.remove(meeting.id);
      invalidate("collections");
      router.push(`/collections/${collectionId}`);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e));
      setDeleteOpen(false);
    }
  };

  return (
    <>
      <PageHeader
        eyebrow={
          <div className="flex items-center gap-1.5 text-[12px] text-ink-3">
            <FolderKanban size={13} className="text-brand" />
            <Link href={`/collections/${collectionId}`} className="hover:text-brand transition-colors">
              {collection?.name || "Collection"}
            </Link>
            <span>/</span>
            <span>{t.pick("การประชุม", "Meeting")}</span>
          </div>
        }
        title={meeting.title}
        desc={
          <div className="flex flex-wrap items-center gap-3 text-[13px] text-ink-3">
            <span className="flex items-center gap-1">
              <Calendar size={13} /> {formatThaiDate(meeting.meeting_date ?? meeting.created_at)}
            </span>
            {meeting.source_filename && (
              <span className="flex items-center gap-1">
                <FileText size={13} /> {meeting.source_filename}
              </span>
            )}
          </div>
        }
        actions={
          <div className="flex items-center gap-2">
            {ready && (
              <>
                <a
                  href={api.meetings.exportUrl(meeting.id)}
                  className="flex items-center gap-1.5 rounded-[var(--radius)] border border-line bg-[var(--bg-surface)] px-3 py-1.5 text-[12.5px] font-medium text-ink-2 hover:bg-sunken hover:text-ink transition-colors shadow-xs"
                >
                  <Download size={14} />
                  <span>.docx</span>
                </a>
                <button
                  onClick={() => setEmailOpen(true)}
                  className="flex items-center gap-1.5 rounded-[var(--radius)] bg-brand px-3.5 py-1.5 text-[12.5px] font-medium text-white hover:bg-[var(--brand-hover)] cursor-pointer transition-colors shadow-xs"
                >
                  <Mail size={14} />
                  <span>{t.pick("ส่งอีเมลสรุป", "Email summary")}</span>
                </button>
              </>
            )}
            <button
              onClick={() => setDeleteOpen(true)}
              className="rounded-[var(--radius)] border border-line p-2 text-ink-3 hover:bg-sunken hover:text-[var(--danger)] cursor-pointer transition-colors"
              title={t("delete")}
              aria-label={t("delete")}
            >
              <Trash2 size={14} />
            </button>
          </div>
        }
      />

      <PageBody className="space-y-4 max-w-[1300px] pb-16">
        {actionError && <ErrorNote error={actionError} />}

        {ready ? (
          <ReadyMeeting meeting={meeting} />
        ) : (
          <Card className="mx-auto max-w-xl p-6">
            <h3 className="mb-4 text-[15px] font-semibold text-ink">
              {meeting.status === "processing" ? t.pick("กำลังประมวลผลการประชุม…", "Processing meeting…") : t.pick("ประมวลผลไม่สำเร็จ", "Processing failed")}
            </h3>
            <PipelineStatus meeting={meeting} onRetry={retry} />
            {meeting.status === "processing" && (
              <p className="mt-4 text-[12px] text-ink-4">
                {t.pick("ปิดหน้านี้ได้ ระบบประมวลผลต่อเบื้องหลัง ไฟล์เสียงยาวอาจใช้เวลาหลายนาที", "You can leave this page — processing continues in the background.")}
              </p>
            )}
          </Card>
        )}
      </PageBody>

      {ready && <EmailSummaryModal open={emailOpen} onClose={() => setEmailOpen(false)} meeting={meeting} />}

      <ConfirmModal
        open={deleteOpen}
        onClose={() => setDeleteOpen(false)}
        title={t.pick("ลบการประชุมนี้?", "Delete this meeting?")}
        confirmLabel={t("delete")}
        cancelLabel={t("cancel")}
        onConfirm={remove}
      >
        {t.pick(`ไฟล์ บันทึก สรุป และงานของ “${meeting.title}” จะถูกลบถาวร`, `The file, transcript, summary and tasks of "${meeting.title}" will be deleted.`)}
      </ConfirmModal>
    </>
  );
}

function ReadyMeeting({ meeting }: { meeting: Meeting }) {
  const t = useT();
  const { data: segments = [], loading: segLoading } = useSegments(meeting);
  const { data: items = [] } = useMeetingActions(meeting);
  const { data: templates = [] } = useTemplates();
  const template = templates.find((tpl) => tpl.id === meeting.template);

  const [currentMs, setCurrentMs] = useState(0);
  const [renaming, setRenaming] = useState<Segment | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const playerRef = useRef<AudioPlayerHandle>(null);

  const labels = Array.from(new Set(segments.map((s) => s.speaker_label)));
  const styleOf = (label: string) => SPEAKER_STYLES[labels.indexOf(label) % SPEAKER_STYLES.length];

  const markdown = [
    `## ${meeting.title}`,
    meeting.summary,
    meeting.key_points.length ? `### ประเด็นสำคัญ\n${meeting.key_points.map((p) => `- ${p}`).join("\n")}` : "",
    items.length
      ? `### งานที่ต้องทำ\n${items.map((i) => `- [${i.done ? "x" : " "}] ${i.text}${i.owner ? ` (${i.owner})` : ""}`).join("\n")}`
      : "",
  ]
    .filter(Boolean)
    .join("\n\n");

  const copy = async () => {
    await navigator.clipboard.writeText(markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <>
      {meeting.source_kind === "audio" && (
        <AudioPlayer
          ref={playerRef}
          src={api.meetings.audioUrl(meeting.id)}
          durationHintMs={segments.at(-1)?.end_ms ?? 0}
          onTime={setCurrentMs}
        />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* บันทึกคำต่อคำ */}
        <div className="lg:col-span-7 space-y-3">
          <div className="flex items-center justify-between px-1">
            <h3 className="text-[14px] font-semibold text-ink flex items-center gap-2">
              <FileText size={15} className="text-brand" />
              <span>{t.pick("บทสนทนาคำต่อคำ", "Transcript")}</span>
            </h3>
            <span className="text-[11.5px] text-ink-4">
              {t.pick("คลิกชื่อผู้พูดเพื่อตั้งชื่อ", "Click a speaker to rename")}
              {meeting.source_kind === "audio" && t.pick(" · คลิกประโยคเพื่อฟัง", " · click a line to play")}
            </span>
          </div>

          <Card className="max-h-[640px] overflow-y-auto p-4 divide-y divide-line/60">
            {segLoading ? (
              <Loading />
            ) : (
              segments.map((s) => {
                const isCurrent = meeting.source_kind === "audio" && currentMs >= s.start_ms && currentMs < s.end_ms;
                return (
                  <div
                    key={s.id}
                    onClick={() => playerRef.current?.seek(s.start_ms)}
                    className={cn(
                      "group py-3 px-2 rounded-lg transition-all",
                      meeting.source_kind === "audio" && "cursor-pointer",
                      isCurrent ? "bg-[var(--brand-soft)] ring-1 ring-brand/30" : "hover:bg-surface-2",
                    )}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setRenaming(s);
                        }}
                        className={cn("rounded border px-2 py-0.5 text-[11px] font-semibold cursor-pointer hover:opacity-80", styleOf(s.speaker_label))}
                      >
                        {speakerLabel(s)}
                      </button>
                      {meeting.source_kind === "audio" && (
                        <span className="text-[11px] font-mono text-ink-4 group-hover:text-brand">{formatTimecode(s.start_ms)}</span>
                      )}
                    </div>
                    <p className="text-[13.5px] leading-relaxed text-ink-2 group-hover:text-ink">{s.text}</p>
                  </div>
                );
              })
            )}
          </Card>
        </div>

        {/* สรุป */}
        <div className="lg:col-span-5 space-y-3">
          <div className="flex items-center justify-between px-1">
            <h3 className="text-[14px] font-semibold text-ink flex items-center gap-2">
              <Sparkles size={15} className="text-brand" />
              <span>{t.pick("สรุปอัจฉริยะ", "Smart Summary")}</span>
            </h3>
            {template && <span className="rounded bg-brand/10 px-2 py-0.5 text-[11px] font-semibold text-brand">{template.name.split(" (")[0]}</span>}
          </div>

          <Card className="p-5 space-y-5">
            <section className="space-y-2">
              <h4 className="text-[13px] font-semibold uppercase tracking-wider text-ink-4">{t.pick("ภาพรวม", "Overview")}</h4>
              <p className="whitespace-pre-line rounded-[var(--radius)] bg-surface-2 p-3 text-[13px] leading-relaxed text-ink-2">
                {meeting.summary || t.pick("— ไม่มีสรุป —", "— no summary —")}
              </p>
            </section>

            {meeting.key_points.length > 0 && (
              <section className="space-y-2">
                <h4 className="text-[13px] font-semibold uppercase tracking-wider text-ink-4">{t.pick("ประเด็นสำคัญ", "Key points")}</h4>
                <ul className="space-y-1.5 text-[13px] text-ink-2">
                  {meeting.key_points.map((p, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="text-brand">•</span>
                      <span>{p}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {Object.entries(meeting.details).map(([key, value]) => (
              <DetailSection key={key} label={template?.detail_labels[key] ?? key} value={value} />
            ))}

            <div className="border-t border-line pt-4">
              <button
                onClick={() => void copy()}
                className="flex w-full items-center justify-center gap-1.5 rounded-[var(--radius)] border border-line bg-surface-2 py-2 text-[12.5px] font-medium text-ink hover:bg-sunken cursor-pointer transition-colors"
              >
                {copied ? <Check size={13} className="text-ok" /> : <Copy size={13} />}
                <span>{copied ? t.pick("คัดลอกแล้ว!", "Copied!") : t.pick("คัดลอกเป็น Markdown", "Copy as Markdown")}</span>
              </button>
            </div>
          </Card>

          <div className="flex items-center justify-between px-1 pt-2">
            <h3 className="text-[14px] font-semibold text-ink flex items-center gap-2">
              <ListChecks size={15} className="text-brand" />
              <span>{t.pick("งานที่ต้องทำต่อ", "Action items")}</span>
            </h3>
            <Button size="sm" variant="ghost" icon={<Plus size={13} />} onClick={() => setAddOpen(true)}>
              {t("add")}
            </Button>
          </div>
          <ActionItemList items={items} emptyText={t.pick("ไม่มีงานจากการประชุมนี้", "No action items from this meeting")} />
        </div>
      </div>

      <SpeakerRenameModal meeting={meeting} segment={renaming} onClose={() => setRenaming(null)} />
      <ActionItemEditor meetingId={meeting.id} open={addOpen} onClose={() => setAddOpen(false)} />
    </>
  );
}

function DetailSection({ label, value }: { label: string; value: unknown }) {
  const lines: string[] = Array.isArray(value)
    ? value.map((v) => (v && typeof v === "object" ? Object.values(v).filter(Boolean).join(" · ") : String(v)))
    : typeof value === "string"
      ? [value]
      : [];
  if (lines.length === 0) return null;
  return (
    <section className="space-y-2">
      <h4 className="text-[13px] font-semibold uppercase tracking-wider text-ink-4">{label}</h4>
      <ul className="space-y-1.5 text-[13px] text-ink-2">
        {lines.map((line, i) => (
          <li key={i} className="flex gap-2">
            <span className="text-brand">•</span>
            <span>{line}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function SpeakerRenameModal({ meeting, segment, onClose }: { meeting: Meeting; segment: Segment | null; onClose: () => void }) {
  const t = useT();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastId, setLastId] = useState<string | null>(null);

  //  เปิดใหม่ด้วยผู้พูดคนอื่น → เติมชื่อเดิมของคนนั้น
  if (segment && segment.id !== lastId) {
    setLastId(segment.id);
    setName(segment.speaker_name);
    setError(null);
  }

  const save = async () => {
    if (!segment) return;
    setBusy(true);
    try {
      await api.meetings.renameSpeaker(meeting.id, segment.speaker_label, name.trim());
      invalidate(`meetings:${meeting.id}:segments`);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={Boolean(segment)}
      onClose={onClose}
      title={t.pick("ตั้งชื่อผู้พูด", "Rename speaker")}
      desc={t.pick(`ชื่อนี้จะใช้กับทุกท่อนของ ${segment?.speaker_label ?? ""} ในการประชุมนี้`, `Applies to every line by ${segment?.speaker_label ?? ""} in this meeting.`)}
      width="max-w-md"
      footer={
        <>
          <Button onClick={onClose}>{t("cancel")}</Button>
          <Button variant="primary" onClick={save} disabled={busy}>
            {t("save")}
          </Button>
        </>
      }
    >
      <Field label={t.pick("ชื่อ", "Name")} hint={t.pick("เว้นว่างเพื่อกลับไปใช้ชื่อเดิม", "Leave empty to reset")}>
        <Input value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && void save()} autoFocus maxLength={80} />
      </Field>
      {error && <p className="mt-2 text-[12.5px] text-[var(--danger)]">{error}</p>}
    </Modal>
  );
}

/* ── ตัวเล่นเสียง ─────────────────────────────────────────────────────── */

interface AudioPlayerHandle {
  seek: (ms: number) => void;
}

function AudioPlayer({
  src,
  durationHintMs,
  onTime,
  ref,
}: {
  src: string;
  durationHintMs: number;
  onTime: (ms: number) => void;
  ref: React.Ref<AudioPlayerHandle>;
}) {
  const t = useT();
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [currentMs, setCurrentMs] = useState(0);
  const [durationMs, setDurationMs] = useState(0);
  const [speed, setSpeed] = useState(1);
  const [failed, setFailed] = useState(false);
  const total = durationMs || durationHintMs;

  const seek = (ms: number) => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.currentTime = ms / 1000;
    void audio.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
  };

  useImperativeHandle(ref, () => ({ seek }));

  const toggle = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) {
      audio.pause();
      setPlaying(false);
    } else {
      void audio.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
    }
  };

  return (
    <div className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm">
      <audio
        ref={audioRef}
        src={src}
        preload="metadata"
        onLoadedMetadata={(e) => setDurationMs(e.currentTarget.duration * 1000 || 0)}
        onTimeUpdate={(e) => {
          const ms = e.currentTarget.currentTime * 1000;
          setCurrentMs(ms);
          onTime(ms);
        }}
        onEnded={() => setPlaying(false)}
        onError={() => setFailed(true)}
      />

      {failed ? (
        <p className="flex items-center gap-2 text-[12.5px] text-ink-3">
          <Headphones size={14} /> {t.pick("เล่นไฟล์เสียงนี้ไม่ได้ (ไฟล์อาจถูกลบหรือเบราว์เซอร์ไม่รองรับนามสกุลนี้)", "This audio cannot be played.")}
        </p>
      ) : (
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <button onClick={() => seek(Math.max(0, currentMs - 10_000))} className="rounded-lg p-2 text-ink-3 hover:bg-sunken hover:text-ink cursor-pointer" title="-10s">
              <RotateCcw size={16} />
            </button>
            <button
              onClick={toggle}
              className="flex h-10 w-10 items-center justify-center rounded-full bg-brand text-white shadow-xs hover:bg-[var(--brand-hover)] cursor-pointer transition-transform hover:scale-105"
              aria-label={playing ? "Pause" : "Play"}
            >
              {playing ? <Pause size={17} /> : <Play size={17} className="ml-0.5" />}
            </button>
            <button onClick={() => seek(Math.min(total, currentMs + 10_000))} className="rounded-lg p-2 text-ink-3 hover:bg-sunken hover:text-ink cursor-pointer" title="+10s">
              <RotateCw size={16} />
            </button>
            <span className="flex items-center gap-1 pl-2 font-mono text-[12.5px] text-ink-2">
              <Clock size={12} /> {formatTimecode(currentMs)} / {formatTimecode(total)}
            </span>
          </div>

          <div className="flex-1 w-full max-w-md mx-2">
            <input
              type="range"
              min={0}
              max={total || 1}
              value={currentMs}
              onChange={(e) => seek(Number(e.target.value))}
              className="w-full h-1.5 bg-surface-2 rounded-lg appearance-none cursor-pointer accent-brand"
            />
          </div>

          <div className="flex items-center gap-1">
            {[1, 1.25, 1.5, 2].map((s) => (
              <button
                key={s}
                onClick={() => {
                  setSpeed(s);
                  if (audioRef.current) audioRef.current.playbackRate = s;
                }}
                className={cn(
                  "rounded px-2 py-1 text-[11.5px] font-medium transition-colors cursor-pointer",
                  speed === s ? "bg-brand text-white" : "text-ink-3 hover:bg-sunken hover:text-ink",
                )}
              >
                {s}x
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
