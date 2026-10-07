"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowRight, CalendarDays, CircleCheckBig, Copy, FileStack, FolderKanban, Sparkles, Upload } from "lucide-react";
import { ActionItemList } from "@/components/action-items";
import { PageBody, PageHeader } from "@/components/app-shell";
import { MeetingStatusBadge, UploadMeetingModal } from "@/components/meeting-ingest";
import { Badge, Button, Card, EmptyState, ErrorNote, Loading } from "@/components/ui";
import { useCollection, useCollectionActions, useCollectionMeetings } from "@/lib/data";
import { formatThaiDate } from "@/lib/format";
import { useT } from "@/lib/i18n";
import type { Meeting } from "@/lib/types";

export default function CollectionHubPage() {
  const t = useT();
  const router = useRouter();
  const collectionId = useParams<{ id: string }>().id;
  const { data: collection, error, loading, reload } = useCollection(collectionId);
  const { data: meetings = [] } = useCollectionMeetings(collectionId);
  const { data: items = [] } = useCollectionActions(collectionId);

  const [uploadOpen, setUploadOpen] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [askInput, setAskInput] = useState("");

  if (error) {
    return (
      <PageBody>
        <ErrorNote error={error} onRetry={reload} />
        <Link href="/collections" className="mt-4 inline-block text-[13px] text-brand hover:underline">
          {t.pick("← กลับหน้าคอลเลกชันทั้งหมด", "← Back to collections")}
        </Link>
      </PageBody>
    );
  }
  if (loading || !collection) return <Loading />;

  const meetingTitle = new Map(meetings.map((m) => [m.id, m.title]));
  //  งานที่ระบบคิดว่าเสร็จแล้วขึ้นก่อน เพราะรอผู้ใช้ตัดสินใจ
  const openItems = items
    .filter((i) => !i.done)
    .sort((a, b) => Number(Boolean(b.suggested_done_meeting_id)) - Number(Boolean(a.suggested_done_meeting_id)));
  const suggestions = openItems.filter((i) => i.suggested_done_meeting_id).length;

  const copySummary = async (m: Meeting) => {
    const text = [`# ${m.title}`, m.summary, ...m.key_points.map((p) => `- ${p}`)].filter(Boolean).join("\n\n");
    await navigator.clipboard.writeText(text);
    setCopiedId(m.id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const ask = (q: string) => {
    if (q.trim()) router.push(`/collections/${collectionId}/ask?q=${encodeURIComponent(q.trim())}`);
  };

  return (
    <>
      <PageHeader
        eyebrow={
          <div className="flex items-center gap-2">
            <FolderKanban size={14} className="text-brand" />
            <span className="font-medium text-ink-3">Collection</span>
          </div>
        }
        title={collection.name}
        desc={
          collection.description ||
          t.pick(
            `มีการประชุม ${collection.meeting_count} ครั้ง และงานค้าง ${collection.open_action_count} รายการ`,
            `${collection.meeting_count} meetings · ${collection.open_action_count} open tasks`,
          )
        }
        actions={
          <div className="flex gap-2">
            <Link
              href={`/collections/${collectionId}/ask`}
              className="flex items-center gap-1.5 rounded-[var(--radius)] bg-[var(--brand-soft)] px-3.5 py-1.5 text-[13px] font-medium text-brand hover:bg-brand hover:text-white transition-colors"
            >
              <Sparkles size={14} />
              <span>Ask SARA Copilot</span>
            </Link>
            <Button variant="primary" icon={<Upload size={15} />} onClick={() => setUploadOpen(true)}>
              {t.pick("อัปโหลดการประชุม", "Upload Meeting")}
            </Button>
          </div>
        }
      />

      <PageBody className="space-y-6">
        {/* ถามข้ามการประชุม */}
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
                  "ถามคำถามข้ามทุกการประชุมในคอลเลกชันนี้ คำตอบอ้างอิงข้อความจริงจากบันทึก",
                  "Ask across every meeting in this collection. Answers quote the transcript.",
                )}
              </p>
            </div>
            <Link href={`/collections/${collectionId}/ask`} className="flex shrink-0 items-center gap-1 text-[13px] font-medium text-brand hover:underline">
              {t.pick("เปิดแชทเต็มจอ →", "Open full chat →")}
            </Link>
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              ask(askInput);
            }}
            className="mt-4 flex gap-2"
          >
            <div className="relative flex-1">
              <input
                type="text"
                value={askInput}
                onChange={(e) => setAskInput(e.target.value)}
                placeholder={t.pick("ถามคำถาม เช่น “งบประมาณที่ตกลงกันไว้เท่าไร?”", "e.g. What budget did we agree on?")}
                className="w-full rounded-[var(--radius)] border border-line bg-[var(--bg-surface)] py-2.5 pl-3.5 pr-10 text-[13px] text-ink focus:border-brand focus:outline-none shadow-xs"
              />
              <button type="submit" className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md bg-brand p-1.5 text-white hover:bg-[var(--brand-hover)] cursor-pointer">
                <ArrowRight size={14} />
              </button>
            </div>
          </form>

          <div className="mt-3 flex flex-wrap items-center gap-2 text-[12px] text-ink-3">
            <span className="font-medium text-ink-4">💡 แนะนำ:</span>
            {["สรุปงานที่ต้องส่งมอบสัปดาห์นี้", "งบประมาณที่ตกลงกันไว้", "ประเด็นที่ยังค้างรอการตัดสินใจ"].map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => ask(q)}
                className="rounded-full border border-line bg-[var(--bg-surface)] px-2.5 py-1 text-[11.5px] hover:border-brand hover:text-brand cursor-pointer transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </div>

        {/* งานค้าง */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="flex items-center gap-2 text-[16px] font-semibold text-ink">
              <CircleCheckBig size={17} className="text-brand" />
              <span>{t.pick("งานค้าง", "Open tasks")}</span>
              {suggestions > 0 && <Badge tone="brand">{t.pick(`${suggestions} รายการน่าจะเสร็จแล้ว`, `${suggestions} likely done`)}</Badge>}
            </h3>
            <span className="text-[12.5px] text-ink-3">
              {openItems.length} {t.pick("รายการ", "items")}
            </span>
          </div>
          <ActionItemList
            items={openItems}
            emptyText={t.pick("ไม่มีงานค้างในคอลเลกชันนี้", "No open tasks in this collection")}
            meetingLink={(i) => ({ href: `/collections/${collectionId}/meetings/${i.meeting_id}`, label: meetingTitle.get(i.meeting_id) ?? "" })}
          />
        </section>

        {/* การประชุม */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-[16px] font-semibold text-ink flex items-center gap-2">
              <FileStack size={17} className="text-brand" />
              <span>{t.pick("การประชุมในคอลเลกชันนี้", "Meetings")}</span>
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
                desc={t.pick("อัปโหลดไฟล์เสียง (.mp3, .m4a, .wav) หรือเอกสาร (.pdf, .docx, .txt)", "Upload an audio recording or a document.")}
                action={
                  <Button variant="primary" icon={<Upload size={15} />} onClick={() => setUploadOpen(true)}>
                    {t.pick("อัปโหลดการประชุมแรก", "Upload First Meeting")}
                  </Button>
                }
              />
            </Card>
          ) : (
            <div className="space-y-3.5">
              {meetings.map((m) => (
                <Card key={m.id} className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 p-5 transition-all hover:border-brand/40 hover:shadow-sm">
                  <div className="space-y-2 min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2 text-[12px] text-ink-3">
                      <span className="flex items-center gap-1">
                        <CalendarDays size={13} /> {formatThaiDate(m.meeting_date ?? m.created_at)}
                      </span>
                      <span className="rounded bg-surface-2 px-2 py-0.5 font-medium text-ink-3">
                        {m.source_kind === "audio" ? t.pick("ไฟล์เสียง", "Audio") : t.pick("เอกสาร", "Document")}
                      </span>
                      <MeetingStatusBadge meeting={m} />
                    </div>

                    <Link href={`/collections/${collectionId}/meetings/${m.id}`} className="block text-[16px] font-semibold text-ink hover:text-brand transition-colors">
                      {m.title}
                    </Link>
                    {m.summary && <p className="line-clamp-2 text-[13px] text-ink-2">{m.summary}</p>}
                  </div>

                  <div className="flex items-center gap-2 shrink-0 self-end md:self-center">
                    {m.status === "ready" && (
                      <button
                        onClick={() => void copySummary(m)}
                        className="flex items-center gap-1.5 rounded-[var(--radius)] border border-line bg-[var(--bg-surface)] px-3 py-1.5 text-[12px] font-medium text-ink-2 hover:bg-sunken hover:text-ink cursor-pointer transition-colors"
                      >
                        <Copy size={13} />
                        <span>{copiedId === m.id ? t.pick("คัดลอกแล้ว!", "Copied!") : t.pick("คัดลอกสรุป", "Copy summary")}</span>
                      </button>
                    )}
                    <Link
                      href={`/collections/${collectionId}/meetings/${m.id}`}
                      className="flex items-center gap-1 rounded-[var(--radius)] bg-brand px-3.5 py-1.5 text-[12px] font-medium text-white hover:bg-[var(--brand-hover)] transition-colors"
                    >
                      <span>{t.pick("เปิดดู", "Open")}</span>
                      <ArrowRight size={13} />
                    </Link>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </section>
      </PageBody>

      <UploadMeetingModal open={uploadOpen} onClose={() => setUploadOpen(false)} collectionId={collectionId} />
    </>
  );
}
