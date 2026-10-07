"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { CalendarDays, ChevronRight, FileAudio, FileStack, FileText, FolderKanban, Upload } from "lucide-react";
import { PageBody, PageHeader } from "@/components/app-shell";
import { MeetingStatusBadge, UploadMeetingModal } from "@/components/meeting-ingest";
import { Button, Card, EmptyState, ErrorNote, Loading } from "@/components/ui";
import { useCollection, useCollectionMeetings, useTemplates } from "@/lib/data";
import { formatThaiDate } from "@/lib/format";
import { useT } from "@/lib/i18n";

export default function CollectionMeetingsListPage() {
  const t = useT();
  const collectionId = useParams<{ id: string }>().id;
  const { data: collection } = useCollection(collectionId);
  const { data: meetings, error, loading, reload } = useCollectionMeetings(collectionId);
  const { data: templates = [] } = useTemplates();
  const [uploadOpen, setUploadOpen] = useState(false);

  const templateName = (id: string) => templates.find((tpl) => tpl.id === id)?.name.split(" (")[0] ?? id;

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
            <span>Meetings</span>
          </div>
        }
        title={t.pick("รายการประชุมและบันทึกสรุป", "Meetings & Transcripts")}
        desc={t.pick(
          "อัปโหลดไฟล์เสียงหรือเอกสาร ระบบจะถอดเสียง สรุป และดึงงานที่ต้องทำให้อัตโนมัติ",
          "Upload recordings or documents — SARA transcribes, summarizes and extracts action items.",
        )}
        actions={
          <Button variant="primary" icon={<Upload size={15} />} onClick={() => setUploadOpen(true)}>
            {t.pick("อัปโหลดการประชุม", "Upload Meeting")}
          </Button>
        }
      />

      <PageBody className="space-y-4 max-w-[1100px]">
        {error && <ErrorNote error={error} onRetry={reload} />}
        {loading && !meetings ? (
          <Loading />
        ) : (
          <Card className="overflow-hidden divide-y divide-line/60">
            {!meetings || meetings.length === 0 ? (
              <EmptyState
                icon={<FileStack size={24} className="text-brand" />}
                title={t.pick("ยังไม่มีการประชุมในคอลเลกชันนี้", "No meetings in this collection")}
                desc={t.pick("อัปโหลดไฟล์เสียงเพื่อเริ่มใช้งาน", "Upload a meeting to get started.")}
                action={
                  <Button variant="primary" icon={<Upload size={15} />} onClick={() => setUploadOpen(true)}>
                    {t.pick("อัปโหลดการประชุม", "Upload Meeting")}
                  </Button>
                }
              />
            ) : (
              meetings.map((m) => (
                <Link
                  key={m.id}
                  href={`/collections/${collectionId}/meetings/${m.id}`}
                  className="flex items-center justify-between gap-4 p-4 transition-colors hover:bg-surface-2 group"
                >
                  <div className="flex items-center gap-3.5 min-w-0">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[var(--brand-soft)] text-brand group-hover:scale-105 transition-transform">
                      {m.source_kind === "audio" ? <FileAudio size={18} /> : <FileText size={18} />}
                    </div>

                    <div className="min-w-0 space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[14.5px] font-semibold text-ink group-hover:text-brand transition-colors truncate">{m.title}</span>
                        <MeetingStatusBadge meeting={m} />
                      </div>
                      <div className="flex flex-wrap items-center gap-3 text-[12px] text-ink-3">
                        <span className="flex items-center gap-1">
                          <CalendarDays size={12} /> {formatThaiDate(m.meeting_date ?? m.created_at)}
                        </span>
                        <span>{templateName(m.template)}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[12.5px] font-medium text-brand group-hover:underline hidden sm:inline">
                      {t.pick("เปิดดูสรุป", "View")}
                    </span>
                    <ChevronRight size={16} className="text-ink-4 group-hover:text-brand transition-colors" />
                  </div>
                </Link>
              ))
            )}
          </Card>
        )}
      </PageBody>

      <UploadMeetingModal open={uploadOpen} onClose={() => setUploadOpen(false)} collectionId={collectionId} />
    </>
  );
}
