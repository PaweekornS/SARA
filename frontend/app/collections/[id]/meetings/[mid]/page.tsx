"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Calendar,
  Check,
  CheckCircle2,
  Clock,
  Copy,
  Download,
  FileText,
  FolderKanban,
  Headphones,
  Mail,
  Pause,
  Play,
  RotateCcw,
  RotateCw,
  Share2,
  Sparkles,
  Volume2,
} from "lucide-react";
import { PageBody, PageHeader } from "@/components/app-shell";
import { QuickEmailShareModal } from "@/components/meeting-ingest";
import { Badge, Button, Card, EmptyState, cn } from "@/components/ui";
import { useT } from "@/lib/i18n";
import { assigneeNames, formatThaiDate, formatTimecode, useApp } from "@/lib/store";

export default function MeetingStudioPage() {
  const t = useT();
  const params = useParams<{ id: string; mid: string }>();
  const seriesId = params.id;
  const meetingId = params.mid;

  const { db } = useApp();
  const collection = db.series.find((s) => s.id === seriesId);
  const meeting = db.meetings.find((m) => m.id === meetingId);

  const [playing, setPlaying] = useState(false);
  const [currentTimeMs, setCurrentTimeMs] = useState(0);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [emailModalOpen, setEmailModalOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const audioRef = useRef<HTMLAudioElement | null>(null);

  if (!meeting) {
    return (
      <PageBody>
        <Card>
          <EmptyState
            icon={<FileText size={24} />}
            title={t.pick("ไม่พบการประชุมนี้", "Meeting not found")}
            action={
              <Link
                href={`/collections/${seriesId}`}
                className="rounded-[var(--radius)] bg-brand px-4 py-2 text-[13px] text-white"
              >
                {t.pick("กลับหน้าคอลเลกชัน", "Back to collection")}
              </Link>
            }
          />
        </Card>
      </PageBody>
    );
  }

  const segments = db.segments
    .filter((s) => s.meeting_id === meeting.id)
    .sort((a, b) => a.start_ms - b.start_ms);

  const resolutions = db.resolutions.filter((r) => r.origin_meeting_id === meeting.id);
  const totalDurationMs = segments.length > 0 ? segments[segments.length - 1].end_ms : 60000;

  // Speaker label mapping
  const speakerSet = Array.from(new Set(segments.map((s) => s.speaker_label || "Speaker 1")));

  const getSpeakerStyle = (speaker: string) => {
    const idx = speakerSet.indexOf(speaker);
    if (idx === 0) return "bg-[var(--speaker-1-bg)] text-[var(--speaker-1)] border-[var(--speaker-1)]/20";
    if (idx === 1) return "bg-[var(--speaker-2-bg)] text-[var(--speaker-2)] border-[var(--speaker-2)]/20";
    if (idx === 2) return "bg-[var(--speaker-3-bg)] text-[var(--speaker-3)] border-[var(--speaker-3)]/20";
    return "bg-[var(--speaker-4-bg)] text-[var(--speaker-4)] border-[var(--speaker-4)]/20";
  };

  const handleSeek = (ms: number) => {
    setCurrentTimeMs(ms);
    if (audioRef.current) {
      audioRef.current.currentTime = ms / 1000;
      if (!playing) {
        audioRef.current.play().catch(() => {});
        setPlaying(true);
      }
    }
  };

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (playing) {
      audioRef.current.pause();
      setPlaying(false);
    } else {
      audioRef.current.play().catch(() => {});
      setPlaying(true);
    }
  };

  const handleSpeedChange = (speed: number) => {
    setPlaybackSpeed(speed);
    if (audioRef.current) {
      audioRef.current.playbackRate = speed;
    }
  };

  // Construct Markdown summary
  const markdownSummary = `## สรุปการประชุม: ${meeting.title || `ครั้งที่ ${meeting.sequence_no}`}
**วันที่:** ${formatThaiDate(meeting.meeting_date)}
**คอลเลกชัน:** ${collection?.name || "Workspace"}

### 📌 ประเด็นสำคัญและข้อสรุป (Key Takeaways)
${resolutions.map((r, i) => `${i + 1}. **${r.ref_no || "ข้อสรุป"}:** ${r.text}`).join("\n") || "• สรุปการประชุมเสร็จสมบูรณ์"}

### 🎯 แผนการดำเนินงาน (Action Items)
${resolutions.map((r) => {
  const names = assigneeNames(db, r).map((p) => p.full_name).join(", ");
  return `- [ ] ${r.text} *(ผู้รับผิดชอบ: ${names || "ทีมงาน"})*`;
}).join("\n") || "- [ ] ติดตามความคืบหน้าในรอบถัดไป"}
`;

  const handleCopyMarkdown = () => {
    navigator.clipboard.writeText(markdownSummary);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const handleExportMarkdown = () => {
    const blob = new Blob([markdownSummary], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `meeting_summary_${meeting.sequence_no}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <PageHeader
        eyebrow={
          <div className="flex items-center gap-1.5 text-[12px] text-ink-3">
            <FolderKanban size={13} className="text-brand" />
            <Link href={`/collections/${seriesId}`} className="hover:text-brand transition-colors">
              {collection?.name || "Collection"}
            </Link>
            <span>/</span>
            <span>การประชุม #{meeting.sequence_no}</span>
          </div>
        }
        title={meeting.title || `การประชุมครั้งที่ ${meeting.sequence_no}`}
        desc={
          <div className="flex flex-wrap items-center gap-3 text-[13px] text-ink-3">
            <span className="flex items-center gap-1">
              <Calendar size={13} /> {formatThaiDate(meeting.meeting_date)}
            </span>
            <span className="flex items-center gap-1">
              <Clock size={13} /> {formatTimecode(totalDurationMs)}
            </span>
            <span className="flex items-center gap-1">
              <Headphones size={13} /> {speakerSet.length} {t.pick("ผู้พูด", "speakers")}
            </span>
          </div>
        }
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={handleCopyMarkdown}
              className="flex items-center gap-1.5 rounded-[var(--radius)] border border-line bg-[var(--bg-surface)] px-3 py-1.5 text-[12.5px] font-medium text-ink-2 hover:bg-sunken hover:text-ink cursor-pointer transition-colors shadow-xs"
            >
              {copied ? <Check size={14} className="text-ok" /> : <Copy size={14} />}
              <span>{copied ? t.pick("คัดลอกแล้ว!", "Copied!") : t.pick("คัดลอก Markdown", "Copy Markdown")}</span>
            </button>

            <button
              onClick={() => setEmailModalOpen(true)}
              className="flex items-center gap-1.5 rounded-[var(--radius)] bg-brand px-3.5 py-1.5 text-[12.5px] font-medium text-white hover:bg-[var(--brand-hover)] cursor-pointer transition-colors shadow-xs"
            >
              <Mail size={14} />
              <span>{t.pick("ส่งอีเมลสรุป", "Share Email")}</span>
            </button>
          </div>
        }
      />

      <PageBody className="space-y-4 max-w-[1300px] pb-16">
        {/* Top Sticky Audio Player Bar */}
        <div className="rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 shadow-sm">
          <audio
            ref={audioRef}
            src="/sample_meeting.mp3"
            onTimeUpdate={(e) => setCurrentTimeMs(e.currentTarget.currentTime * 1000)}
            onEnded={() => setPlaying(false)}
          />

          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            {/* Play/Pause & Skip buttons */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleSeek(Math.max(0, currentTimeMs - 10000))}
                className="rounded-lg p-2 text-ink-3 hover:bg-sunken hover:text-ink cursor-pointer"
                title="ย้อนกลับ 10 วินาที"
              >
                <RotateCcw size={16} />
              </button>

              <button
                onClick={togglePlay}
                className="flex h-10 w-10 items-center justify-center rounded-full bg-brand text-white shadow-xs hover:bg-[var(--brand-hover)] cursor-pointer transition-transform hover:scale-105"
              >
                {playing ? <Pause size={17} /> : <Play size={17} className="ml-0.5" />}
              </button>

              <button
                onClick={() => handleSeek(Math.min(totalDurationMs, currentTimeMs + 10000))}
                className="rounded-lg p-2 text-ink-3 hover:bg-sunken hover:text-ink cursor-pointer"
                title="ข้ามไปข้างหน้า 10 วินาที"
              >
                <RotateCw size={16} />
              </button>

              <span className="text-[12.5px] font-mono text-ink-2 pl-2">
                {formatTimecode(currentTimeMs)} / {formatTimecode(totalDurationMs)}
              </span>
            </div>

            {/* Scrubber Progress */}
            <div className="flex-1 w-full max-w-md mx-2">
              <input
                type="range"
                min={0}
                max={totalDurationMs}
                value={currentTimeMs}
                onChange={(e) => handleSeek(Number(e.target.value))}
                className="w-full h-1.5 bg-surface-2 rounded-lg appearance-none cursor-pointer accent-brand"
              />
            </div>

            {/* Playback Speed Switcher */}
            <div className="flex items-center gap-1">
              {[1, 1.25, 1.5, 2].map((spd) => (
                <button
                  key={spd}
                  onClick={() => handleSpeedChange(spd)}
                  className={cn(
                    "rounded px-2 py-1 text-[11.5px] font-medium transition-colors cursor-pointer",
                    playbackSpeed === spd
                      ? "bg-brand text-white"
                      : "text-ink-3 hover:bg-sunken hover:text-ink",
                  )}
                >
                  {spd}x
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* 2-Column Split: Transcript (Left/Center) vs Smart Summary Studio (Right) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          {/* Transcript Column (7 cols) */}
          <div className="lg:col-span-7 space-y-3">
            <div className="flex items-center justify-between px-1">
              <h3 className="text-[14px] font-semibold text-ink flex items-center gap-2">
                <FileText size={15} className="text-brand" />
                <span>{t.pick("บทสนทนาคำต่อคำ (Interactive Transcript)", "Interactive Transcript")}</span>
              </h3>
              <span className="text-[11.5px] text-ink-4">คลิกประโยคเพื่อฟังเสียง</span>
            </div>

            <Card className="max-h-[600px] overflow-y-auto p-4 divide-y divide-line/60">
              {segments.length === 0 ? (
                <p className="py-6 text-center text-[13px] text-ink-3">ไม่มีข้อมูลบทสนทนา</p>
              ) : (
                segments.map((s) => {
                  const isCurrent = currentTimeMs >= s.start_ms && currentTimeMs <= s.end_ms;
                  return (
                    <div
                      key={s.id}
                      onClick={() => handleSeek(s.start_ms)}
                      className={cn(
                        "group py-3 px-2 rounded-lg cursor-pointer transition-all",
                        isCurrent ? "bg-[var(--brand-soft)] ring-1 ring-brand/30" : "hover:bg-surface-2",
                      )}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span
                          className={cn(
                            "rounded border px-2 py-0.5 text-[11px] font-semibold",
                            getSpeakerStyle(s.speaker_label || "Speaker 1"),
                          )}
                        >
                          {s.speaker_label || "Speaker 1"}
                        </span>
                        <span className="text-[11px] font-mono text-ink-4 group-hover:text-brand">
                          {formatTimecode(s.start_ms)}
                        </span>
                      </div>
                      <p className="text-[13.5px] leading-relaxed text-ink-2 group-hover:text-ink">
                        {s.text}
                      </p>
                    </div>
                  );
                })
              )}
            </Card>
          </div>

          {/* Smart Summary Studio (5 cols) */}
          <div className="lg:col-span-5 space-y-3">
            <div className="flex items-center justify-between px-1">
              <h3 className="text-[14px] font-semibold text-ink flex items-center gap-2">
                <Sparkles size={15} className="text-brand" />
                <span>{t.pick("สรุปข้อมูลอัจฉริยะ (Smart Summary)", "Smart Summary")}</span>
              </h3>
              <span className="rounded bg-brand/10 px-2 py-0.5 text-[11px] font-semibold text-brand">
                General / Executive
              </span>
            </div>

            <Card className="p-5 space-y-5">
              {/* Summary Section */}
              <div className="space-y-2">
                <h4 className="text-[13px] font-semibold uppercase tracking-wider text-ink-4">
                  ภาพรวมการประชุม (Executive Summary)
                </h4>
                <p className="text-[13px] text-ink-2 leading-relaxed bg-surface-2 p-3 rounded-[var(--radius)]">
                  {meeting.title || "การประชุม"} ได้ข้อสรุปสำคัญเกี่ยวกับแผนการดำเนินงานและการแบ่งหน้าที่รับผิดชอบ
                  โดยมีมติที่ผ่านการยืนยันทั้งหมด {resolutions.length} รายการ
                </p>
              </div>

              {/* Key Takeaways / Decisions */}
              <div className="space-y-2.5">
                <h4 className="text-[13px] font-semibold uppercase tracking-wider text-ink-4 flex items-center justify-between">
                  <span>ข้อสรุป & การตัดสินใจ ({resolutions.length})</span>
                </h4>
                <div className="space-y-2">
                  {resolutions.map((r, idx) => {
                    const names = assigneeNames(db, r).map((p) => p.full_name).join(", ");
                    return (
                      <div
                        key={r.id}
                        className="rounded-[var(--radius)] border border-line bg-[var(--bg-surface)] p-3 text-[12.5px] space-y-1"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-brand">{r.ref_no || `ข้อสรุปที่ ${idx + 1}`}</span>
                          {names && (
                            <span className="rounded bg-surface-2 px-1.5 py-0.5 text-[10.5px] text-ink-3">
                              {names}
                            </span>
                          )}
                        </div>
                        <p className="text-ink-2 leading-relaxed">{r.text}</p>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Quick Action Footer */}
              <div className="border-t border-line pt-4 flex flex-wrap gap-2">
                <button
                  onClick={handleCopyMarkdown}
                  className="flex-1 flex items-center justify-center gap-1.5 rounded-[var(--radius)] border border-line bg-surface-2 py-2 text-[12.5px] font-medium text-ink hover:bg-sunken cursor-pointer transition-colors"
                >
                  <Copy size={13} />
                  <span>{copied ? "คัดลอกแล้ว!" : "Copy Markdown"}</span>
                </button>

                <button
                  onClick={handleExportMarkdown}
                  className="flex items-center justify-center gap-1.5 rounded-[var(--radius)] border border-line bg-surface-2 px-3 py-2 text-[12.5px] font-medium text-ink hover:bg-sunken cursor-pointer transition-colors"
                  title="Download .md"
                >
                  <Download size={13} />
                </button>
              </div>
            </Card>
          </div>
        </div>
      </PageBody>

      <QuickEmailShareModal
        open={emailModalOpen}
        onClose={() => setEmailModalOpen(false)}
        title={meeting.title || `การประชุมครั้งที่ ${meeting.sequence_no}`}
        summary={markdownSummary}
      />
    </>
  );
}
