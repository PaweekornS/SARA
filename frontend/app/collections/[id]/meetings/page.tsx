"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  CalendarDays,
  ChevronRight,
  FileAudio,
  FileStack,
  FileText,
  FolderKanban,
  Headphones,
  Loader2,
  Plus,
  Sparkles,
  Upload,
} from "lucide-react";
import { PageBody, PageHeader } from "@/components/app-shell";
import { UploadMeetingModal } from "@/components/meeting-ingest";
import { Badge, Button, Card, EmptyState, cn } from "@/components/ui";
import { useT } from "@/lib/i18n";
import { formatThaiDate, useApp } from "@/lib/store";

export default function CollectionMeetingsListPage() {
  const t = useT();
  const { db } = useApp();
  const seriesId = useParams<{ id: string }>().id;
  const [uploadOpen, setUploadOpen] = useState(false);

  const collection = db.series.find((s) => s.id === seriesId);
  const meetings = db.meetings
    .filter((m) => m.series_id === seriesId)
    .sort((a, b) => new Date(b.meeting_date).getTime() - new Date(a.meeting_date).getTime());

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
            <span>Meetings</span>
          </div>
        }
        title={t.pick("รายการประชุมและบันทึกสรุป", "Meetings & Transcripts")}
        desc={t.pick(
          "อัปโหลดไฟล์เสียงหรือเอกสาร ระบบจะถอดเสียง จำแนกผู้พูด และสรุปประเด็นการดำเนินงานให้อัตโนมัติ",
          "Upload recordings or documents — SARA transcribes, identifies speakers, and extracts key action items.",
        )}
        actions={
          <Button variant="primary" icon={<Upload size={15} />} onClick={() => setUploadOpen(true)}>
            {t.pick("อัปโหลดการประชุม", "Upload Meeting")}
          </Button>
        }
      />

      <PageBody className="space-y-4 max-w-[1100px]">
        <Card className="overflow-hidden divide-y divide-line/60">
          {meetings.length === 0 ? (
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
            meetings.map((m) => {
              const resolutions = db.resolutions.filter((r) => r.origin_meeting_id === m.id);
              const segments = db.segments.filter((s) => s.meeting_id === m.id);

              return (
                <Link
                  key={m.id}
                  href={`/collections/${seriesId}/meetings/${m.id}`}
                  className="flex items-center justify-between gap-4 p-4 transition-colors hover:bg-surface-2 group"
                >
                  <div className="flex items-center gap-3.5 min-w-0">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[var(--brand-soft)] text-brand group-hover:scale-105 transition-transform">
                      {m.source_kind === "audio" ? <FileAudio size={18} /> : <FileText size={18} />}
                    </div>

                    <div className="min-w-0 space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[14.5px] font-semibold text-ink group-hover:text-brand transition-colors truncate">
                          {m.title || `การประชุมครั้งที่ ${m.sequence_no}`}
                        </span>
                        <span className="rounded bg-surface-2 px-1.5 py-0.2 text-[10.5px] font-medium text-ink-3">
                          #{m.sequence_no}
                        </span>
                      </div>

                      <div className="flex flex-wrap items-center gap-3 text-[12px] text-ink-3">
                        <span className="flex items-center gap-1">
                          <CalendarDays size={12} /> {formatThaiDate(m.meeting_date)}
                        </span>
                        <span className="flex items-center gap-1">
                          <Headphones size={12} /> {segments.length} ท่อนคำพูด
                        </span>
                        <span className="flex items-center gap-1 text-brand">
                          <Sparkles size={12} /> {resolutions.length} ข้อสรุป
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[12.5px] font-medium text-brand group-hover:underline hidden sm:inline">
                      เปิดดูสรุป
                    </span>
                    <ChevronRight size={16} className="text-ink-4 group-hover:text-brand transition-colors" />
                  </div>
                </Link>
              );
            })
          )}
        </Card>
      </PageBody>

      <UploadMeetingModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        seriesId={seriesId}
      />
    </>
  );
}
