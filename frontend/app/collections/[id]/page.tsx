"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowRight,
  Bot,
  CalendarDays,
  CheckCircle2,
  Clock,
  Copy,
  FileStack,
  FolderKanban,
  Headphones,
  Plus,
  Send,
  Sparkles,
  Timer,
  Upload,
} from "lucide-react";
import { PageBody, PageHeader } from "@/components/app-shell";
import { UploadMeetingModal } from "@/components/meeting-ingest";
import { Badge, Button, Card, EmptyState, cn } from "@/components/ui";
import { useT } from "@/lib/i18n";
import { formatThaiDate, seriesStats, useApp } from "@/lib/store";

export default function CollectionWorkspacePage() {
  const t = useT();
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const seriesId = params.id;
  const { db } = useApp();

  const [uploadOpen, setUploadOpen] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [askInput, setAskInput] = useState("");

  const collection = db.series.find((s) => s.id === seriesId);

  if (!collection) {
    return (
      <PageBody>
        <Card>
          <EmptyState
            icon={<FolderKanban size={24} />}
            title={t.pick("ไม่พบคอลเลกชันนี้", "Collection not found")}
            action={
              <Link href="/collections" className="rounded-[var(--radius)] bg-brand px-4 py-2 text-[13px] text-white">
                {t.pick("กลับหน้าคอลเลกชันทั้งหมด", "Back to collections")}
              </Link>
            }
          />
        </Card>
      </PageBody>
    );
  }

  const meetings = db.meetings
    .filter((m) => m.series_id === collection.id)
    .sort((a, b) => new Date(b.meeting_date).getTime() - new Date(a.meeting_date).getTime());

  const resolutions = db.resolutions.filter((r) => r.series_id === collection.id);
  const stats = seriesStats(db, collection.id);

  const handleCopySummary = (meetingId: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(meetingId);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleAsk = (e: React.FormEvent) => {
    e.preventDefault();
    if (!askInput.trim()) return;
    router.push(`/collections/${collection.id}/ask?q=${encodeURIComponent(askInput.trim())}`);
  };

  return (
    <>
      <PageHeader
        eyebrow={
          <div className="flex items-center gap-2">
            <FolderKanban size={14} className="text-brand" />
            <span className="font-medium text-ink-3">{collection.committee_type || "Workspace"}</span>
          </div>
        }
        title={collection.name}
        desc={t.pick(
          `คอลเลกชันนี้มีการประชุมบันทึกไว้ ${meetings.length} ครั้ง และ ${resolutions.length} ข้อสรุป/มติ`,
          `${meetings.length} meetings tracked across this workspace collection.`,
        )}
        actions={
          <div className="flex gap-2">
            <Link
              href={`/collections/${collection.id}/ask`}
              className="flex items-center gap-1.5 rounded-[var(--radius)] bg-[var(--brand-soft)] px-3.5 py-1.5 text-[13px] font-medium text-brand hover:bg-brand hover:text-white transition-colors"
            >
              <Sparkles size={14} />
              <span>{t.pick("Ask SARA Copilot", "Ask Copilot")}</span>
            </Link>
            <Button variant="primary" icon={<Upload size={15} />} onClick={() => setUploadOpen(true)}>
              {t.pick("อัปโหลดการประชุม", "Upload Meeting")}
            </Button>
          </div>
        }
      />

      <PageBody className="space-y-6">
        {/* HERO: Cross-Meeting Copilot Search Card */}
        <div className="relative overflow-hidden rounded-[var(--radius)] border border-brand/30 bg-gradient-to-r from-[var(--brand-soft)] via-[var(--bg-surface)] to-[var(--brand-soft)] p-5 sm:p-6 shadow-sm">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-md bg-brand text-white">
                  <Sparkles size={13} />
                </span>
                <h2 className="text-[15.5px] font-semibold text-ink">Ask SARA · Cross-Meeting Intelligence</h2>
              </div>
              <p className="text-[13px] text-ink-3">
                {t.pick(
                  "ถามคำถามข้ามทุกการประชุมในคอลเลกชันนี้ ระบบจะดึงคำตอบพร้อมระบุ Timestamp ที่ยืนยันได้ทันที",
                  "Ask questions across all meetings in this workspace. SARA retrieves answers with verified timestamp citations.",
                )}
              </p>
            </div>
            <Link
              href={`/collections/${collection.id}/ask`}
              className="flex shrink-0 items-center gap-1 text-[13px] font-medium text-brand hover:underline"
            >
              {t.pick("เปิดแชทเต็มจอ →", "Open full chat →")}
            </Link>
          </div>

          <form onSubmit={handleAsk} className="mt-4 flex gap-2">
            <div className="relative flex-1">
              <input
                type="text"
                value={askInput}
                onChange={(e) => setAskInput(e.target.value)}
                placeholder={t.pick(
                  "ถามคำถาม เช่น “ลูกค้าสรุปเงื่อนไขราคาและงบประมาณไว้ว่าอย่างไรบ้าง?”",
                  "e.g. What were the agreed deadlines and budget constraints across recent sessions?",
                )}
                className="w-full rounded-[var(--radius)] border border-line bg-[var(--bg-surface)] py-2.5 pl-3.5 pr-10 text-[13px] text-ink focus:border-brand focus:outline-none shadow-xs"
              />
              <button
                type="submit"
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md bg-brand p-1.5 text-white hover:bg-[var(--brand-hover)] cursor-pointer"
              >
                <ArrowRight size={14} />
              </button>
            </div>
          </form>

          <div className="mt-3 flex flex-wrap items-center gap-2 text-[12px] text-ink-3">
            <span className="font-medium text-ink-4">💡 แนะนำ:</span>
            {[
              "สรุปงานที่ต้องส่งมอบสัปดาห์นี้",
              "เงื่อนไขราคาและงบประมาณที่ตกลงกัน",
              "ประเด็นที่ยังค้างรอการตัดสินใจ",
            ].map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => router.push(`/collections/${collection.id}/ask?q=${encodeURIComponent(q)}`)}
                className="rounded-full border border-line bg-[var(--bg-surface)] px-2.5 py-1 text-[11.5px] hover:border-brand hover:text-brand cursor-pointer transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </div>

        {/* Meeting Timeline Grid */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-[16px] font-semibold text-ink flex items-center gap-2">
              <FileStack size={17} className="text-brand" />
              <span>{t.pick("รายการประชุมในคอลเลกชันนี้", "Meetings & Transcripts")}</span>
            </h3>
            <span className="text-[12.5px] text-ink-3">
              {meetings.length} {t.pick("รายการ", "sessions")}
            </span>
          </div>

          {meetings.length === 0 ? (
            <Card className="border-dashed py-8">
              <EmptyState
                icon={<Upload size={22} className="text-brand" />}
                title={t.pick("ยังไม่มีการประชุมในคอลเลกชันนี้", "No meetings uploaded yet")}
                desc={t.pick("อัปโหลดไฟล์เสียง (.mp3, .m4a, .wav) หรือเอกสาร (.pdf, .docx, .txt)", "Drop an audio recording or document to extract minutes & action plans.")}
                action={
                  <Button variant="primary" icon={<Upload size={15} />} onClick={() => setUploadOpen(true)}>
                    {t.pick("อัปโหลดการประชุมแรก", "Upload First Meeting")}
                  </Button>
                }
              />
            </Card>
          ) : (
            <div className="space-y-3.5">
              {meetings.map((m) => {
                const meetingResolutions = resolutions.filter((r) => r.origin_meeting_id === m.id);
                const segments = db.segments.filter((s) => s.meeting_id === m.id);
                const summaryText = meetingResolutions.map((r) => `• ${r.text}`).join("\n") || "การประชุมบันทึกเรียบร้อยแล้ว";

                return (
                  <Card
                    key={m.id}
                    className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 p-5 transition-all hover:border-brand/40 hover:shadow-sm"
                  >
                    <div className="space-y-2 min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2 text-[12px] text-ink-3">
                        <span className="rounded bg-[var(--brand-soft)] px-2 py-0.5 font-semibold text-brand text-[11px]">
                          ครั้งที่ #{m.sequence_no}
                        </span>
                        <span className="flex items-center gap-1">
                          <CalendarDays size={13} /> {formatThaiDate(m.meeting_date)}
                        </span>
                        <span className="flex items-center gap-1">
                          <Headphones size={13} /> {segments.length} {t.pick("ท่อนคำพูด", "segments")}
                        </span>
                        <span className="rounded bg-surface-2 px-2 py-0.5 font-medium text-ink-3">
                          {m.source_kind === "audio" ? "Audio (AI4Thai ASR)" : "Document"}
                        </span>
                      </div>

                      <Link
                        href={`/collections/${collection.id}/meetings/${m.id}`}
                        className="text-[16px] font-semibold text-ink hover:text-brand transition-colors block"
                      >
                        {m.title || `การประชุมครั้งที่ ${m.sequence_no}`}
                      </Link>

                      {meetingResolutions.length > 0 && (
                        <div className="space-y-1 pt-1">
                          {meetingResolutions.slice(0, 2).map((r) => (
                            <p key={r.id} className="text-[13px] text-ink-2 line-clamp-1 flex items-start gap-1.5">
                              <span className="text-brand shrink-0">✓</span>
                              <span>{r.text}</span>
                            </p>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-2 shrink-0 self-end md:self-center">
                      <button
                        onClick={() => handleCopySummary(m.id, summaryText)}
                        className="flex items-center gap-1.5 rounded-[var(--radius)] border border-line bg-[var(--bg-surface)] px-3 py-1.5 text-[12px] font-medium text-ink-2 hover:bg-sunken hover:text-ink cursor-pointer transition-colors"
                        title="Copy Summary Markdown"
                      >
                        <Copy size={13} />
                        <span>{copiedId === m.id ? t.pick("คัดลอกแล้ว!", "Copied!") : t.pick("คัดลอกสรุป", "Copy Markdown")}</span>
                      </button>

                      <Link
                        href={`/collections/${collection.id}/meetings/${m.id}`}
                        className="flex items-center gap-1 rounded-[var(--radius)] bg-brand px-3.5 py-1.5 text-[12px] font-medium text-white hover:bg-[var(--brand-hover)] transition-colors"
                      >
                        <span>{t.pick("เปิดสตูดิโอ", "Open Studio")}</span>
                        <ArrowRight size={13} />
                      </Link>
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </section>
      </PageBody>

      <UploadMeetingModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        seriesId={collection.id}
      />
    </>
  );
}
