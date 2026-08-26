"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import {
  Bot,
  Calendar,
  CheckCircle2,
  Clock,
  CornerDownLeft,
  FileSearch,
  FolderKanban,
  Headphones,
  Loader2,
  Search,
  Sparkles,
  Trash2,
  User,
} from "lucide-react";
import { PageBody, PageHeader } from "@/components/app-shell";
import { Badge, Button, Card, EmptyState, cn } from "@/components/ui";
import { useT } from "@/lib/i18n";
import * as api from "@/lib/api";
import { clearQa, formatThaiDate, formatTimecode, useApp } from "@/lib/store";

const SUGGESTIONS = [
  "สรุปเงื่อนไขราคาและงบประมาณที่ตกลงกันไว้",
  "งานใดบ้างที่มีกำหนดส่งมอบภายในสัปดาห์นี้",
  "ประเด็นปัญหาหรือ Blockers ที่ทีมพบในการประชุมล่าสุด",
  "มีมติหรือการตัดสินใจอะไรที่ยังค้างดำเนินการบ้าง",
];

export default function AskSaraCopilotPage() {
  const t = useT();
  const { db } = useApp();
  const searchParams = useSearchParams();
  const initialQuery = searchParams.get("q");

  const params = useParams<{ id: string }>();
  const seriesId = params.id;
  const collection = db.series.find((s) => s.id === seriesId);
  const meetings = db.meetings.filter((m) => m.series_id === seriesId);

  const history = db.qa[seriesId] ?? [];
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [selectedMeetingIds, setSelectedMeetingIds] = useState<string[]>([]);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history.length, busy]);

  useEffect(() => {
    if (initialQuery && initialQuery.trim()) {
      ask(initialQuery.trim());
    }
  }, [initialQuery]);

  const ask = async (q: string) => {
    const text = q.trim();
    if (!text || busy) return;
    setQuestion("");
    setBusy(true);
    try {
      await api.askSeries(seriesId, text);
    } finally {
      setBusy(false);
    }
  };

  const toggleMeetingFilter = (mid: string) => {
    setSelectedMeetingIds((prev) =>
      prev.includes(mid) ? prev.filter((id) => id !== mid) : [...prev, mid],
    );
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
            <span className="text-brand font-medium">Ask SARA Copilot</span>
          </div>
        }
        title={
          <div className="flex items-center gap-2.5">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand text-white shadow-xs">
              <Sparkles size={16} />
            </span>
            <span>Ask SARA · Cross-Meeting Copilot</span>
          </div>
        }
        desc={t.pick(
          "ผู้ช่วย AI วิเคราะห์และค้นหาคำตอบข้ามทุกการประชุมในคอลเลกชันนี้ พร้อมอ้างอิง Timestamp ที่คลิกฟังเสียงจริงได้ทันที",
          "Ask questions across all meetings in this workspace. Verified with interactive timestamp citations.",
        )}
        actions={
          history.length > 0 ? (
            <Button icon={<Trash2 size={15} />} onClick={() => clearQa(seriesId)}>
              {t.pick("ล้างประวัติการคุย", "Clear history")}
            </Button>
          ) : undefined
        }
      />

      <PageBody className="space-y-4 max-w-[1000px] pb-24">
        {/* Meeting Scope Filter Pills */}
        <div className="flex flex-wrap items-center gap-2 rounded-[var(--radius)] border border-line bg-[var(--bg-surface)] p-3 text-[12.5px]">
          <span className="font-semibold text-ink-2 flex items-center gap-1.5">
            <FileSearch size={14} className="text-brand" />
            {t.pick("ขอบเขตการค้นหา:", "Scope:")}
          </span>

          <button
            onClick={() => setSelectedMeetingIds([])}
            className={cn(
              "rounded-full px-3 py-1 font-medium transition-colors cursor-pointer text-[12px]",
              selectedMeetingIds.length === 0
                ? "bg-brand text-white shadow-xs"
                : "bg-surface-2 text-ink-3 hover:bg-sunken hover:text-ink",
            )}
          >
            {t.pick(`ทุกการประชุม (${meetings.length})`, `All Meetings (${meetings.length})`)}
          </button>

          {meetings.map((m) => {
            const isSelected = selectedMeetingIds.includes(m.id);
            return (
              <button
                key={m.id}
                onClick={() => toggleMeetingFilter(m.id)}
                className={cn(
                  "rounded-full border px-2.5 py-1 text-[11.5px] transition-colors cursor-pointer",
                  isSelected
                    ? "border-brand bg-[var(--brand-soft)] font-medium text-brand"
                    : "border-line bg-[var(--bg-surface)] text-ink-3 hover:border-ink-4",
                )}
              >
                #{m.sequence_no} {m.title || formatThaiDate(m.meeting_date)}
              </button>
            );
          })}
        </div>

        {/* Empty State */}
        {history.length === 0 && !busy && (
          <Card className="border-dashed py-8 text-center">
            <EmptyState
              icon={<Sparkles size={24} className="text-brand" />}
              title={t.pick("ถามอะไรก็ได้เกี่ยวกับการประชุมในคอลเลกชันนี้", "Ask anything across these meetings")}
              desc={t.pick(
                "AI จะสแกนทั้งทะเบียนมติและบทสนทนาคำต่อคำเพื่อเรียบเรียงคำตอบที่กระชับและถูกต้อง",
                "SARA scans resolutions, decisions, and speech transcripts across all sessions.",
              )}
            />
            <div className="mt-4 flex flex-wrap justify-center gap-2 px-6">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => ask(s)}
                  className="rounded-full border border-line bg-[var(--bg-surface)] px-3.5 py-1.5 text-[12.5px] text-ink-2 transition-all hover:border-brand hover:bg-[var(--brand-soft)] hover:text-brand cursor-pointer shadow-xs"
                >
                  {s}
                </button>
              ))}
            </div>
          </Card>
        )}

        {/* Chat History */}
        <div className="space-y-6">
          {history.map((a) => (
            <div key={a.id} className="space-y-3">
              {/* User Message */}
              <div className="flex justify-end">
                <div className="flex items-start gap-2 max-w-[85%]">
                  <div className="rounded-[var(--radius)] rounded-tr-sm bg-brand px-4 py-2.5 text-[13.5px] leading-relaxed text-white shadow-xs">
                    {a.question}
                  </div>
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-surface-2 text-ink-3 text-[11px] font-bold">
                    U
                  </div>
                </div>
              </div>

              {/* SARA AI Response */}
              <div className="flex items-start gap-3">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-brand text-white shadow-xs mt-1">
                  <Sparkles size={14} />
                </div>

                <div className="flex-1 space-y-3 min-w-0">
                  <Card className="border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 sm:p-5 shadow-xs">
                    <div className="prose prose-sm max-w-none text-ink leading-relaxed text-[13.5px] whitespace-pre-line">
                      {a.answer}
                    </div>

                    {/* Citations & Evidence Trail */}
                    {a.citations && a.citations.length > 0 && (
                      <div className="mt-4 border-t border-line pt-3 space-y-2">
                        <p className="text-[11.5px] font-semibold uppercase tracking-wider text-ink-4 flex items-center gap-1.5">
                          <Headphones size={12} className="text-brand" />
                          {t.pick("แหล่งอ้างอิงและจุดที่พูดถึง (Verifiable Citations):", "Verifiable Citations:")}
                        </p>
                        <div className="space-y-1.5">
                          {a.citations.map((c, idx) => {
                            const meeting = meetings.find((m) => m.id === c.meeting_id);
                            return (
                              <div
                                key={idx}
                                className="flex flex-wrap items-start justify-between gap-2 rounded-[var(--radius)] bg-surface-2 p-2.5 text-[12.5px] text-ink-2"
                              >
                                <p className="italic text-ink-2 flex-1 min-w-[200px]">
                                  “{c.quote}”
                                </p>
                                {meeting && (
                                  <Link
                                    href={`/collections/${seriesId}/meetings/${meeting.id}`}
                                    className="inline-flex items-center gap-1 rounded bg-[var(--brand-soft)] px-2 py-0.5 text-[11px] font-medium text-brand hover:underline shrink-0"
                                  >
                                    <Clock size={11} />
                                    <span>ครั้งที่ #{meeting.sequence_no}</span>
                                  </Link>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </Card>
                </div>
              </div>
            </div>
          ))}

          {busy && (
            <div className="flex items-start gap-3">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-brand text-white shadow-xs mt-1 animate-pulse">
                <Sparkles size={14} />
              </div>
              <Card className="flex items-center gap-2.5 p-4 text-[13px] text-ink-3">
                <Loader2 size={16} className="animate-spin text-brand" />
                <span>{t.pick("กำลังค้นหาและสังเคราะห์คำตอบจากการประชุมทั้งหมด…", "Searching & synthesizing cross-meeting insights…")}</span>
              </Card>
            </div>
          )}

          <div ref={endRef} />
        </div>

        {/* Sticky Input Form */}
        <div className="no-print fixed bottom-0 left-0 right-0 z-30 border-t border-[var(--border-subtle)] bg-[var(--bg-surface)]/90 backdrop-blur-md py-3 px-4 sm:px-8">
          <div className="mx-auto max-w-[1000px]">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                ask(question);
              }}
              className="relative flex items-center"
            >
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder={t.pick(
                  "พิมพ์คำถามเพื่อสืบค้นข้อมูลจากการประชุมในคอลเลกชันนี้...",
                  "Ask anything across meetings in this workspace...",
                )}
                disabled={busy}
                className="w-full rounded-xl border border-line bg-[var(--bg-surface)] py-3 pl-4 pr-24 text-[13.5px] text-ink focus:border-brand focus:outline-none shadow-sm"
              />
              <button
                type="submit"
                disabled={!question.trim() || busy}
                className="absolute right-2 flex items-center gap-1.5 rounded-lg bg-brand px-3.5 py-1.5 text-[12.5px] font-medium text-white hover:bg-[var(--brand-hover)] disabled:opacity-40 cursor-pointer transition-colors"
              >
                <span>{t.pick("ส่ง", "Ask")}</span>
                <CornerDownLeft size={13} />
              </button>
            </form>
          </div>
        </div>
      </PageBody>
    </>
  );
}
