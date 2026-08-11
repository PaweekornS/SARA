"use client";

/** M2/M9 — รายการการประชุมในชุด พร้อมสถานะรายงาน */

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AlertOctagon, ChevronRight, FileAudio, FileStack, FileText, Loader2, Plus } from "lucide-react";
import { PageBody, PageHeader } from "@/components/app-shell";
import { UploadMeetingModal } from "@/components/meeting-ingest";
import { Badge, Button, Card, EmptyState, cn } from "@/components/ui";
import { useT } from "@/lib/i18n";
import { formatThaiDate, useApp } from "@/lib/store";
import type { MeetingStatus } from "@/lib/types";

const MEETING_STATUS: Record<MeetingStatus, { th: string; en: string; tone: "neutral" | "brand" | "warn" | "ok" | "danger" }> = {
  draft: { th: "รอตรวจทาน", en: "Draft", tone: "warn" },
  processing: { th: "กำลังประมวลผล", en: "Processing", tone: "brand" },
  failed: { th: "ประมวลผลไม่สำเร็จ", en: "Failed", tone: "danger" },
  reviewed: { th: "ตรวจทานแล้ว", en: "Reviewed", tone: "brand" },
  approved: { th: "รับรองรายงานแล้ว", en: "Approved", tone: "ok" },
  distributed: { th: "เผยแพร่แล้ว", en: "Distributed", tone: "ok" },
};

export default function MeetingsPage() {
  const t = useT();
  const { db } = useApp();
  const seriesId = useParams<{ id: string }>().id;
  const [uploadOpen, setUploadOpen] = useState(false);

  const meetings = db.meetings
    .filter((m) => m.series_id === seriesId)
    .sort((a, b) => b.sequence_no - a.sequence_no);

  const pendingReview = meetings.filter((m) => m.status === "draft" || m.status === "reviewed").length;

  return (
    <>
      <PageHeader
        title={t("navMeetings")}
        desc={t.pick(
          "อัปโหลดไฟล์เสียงของการประชุมครั้งใหม่ ระบบจะถอดเสียง แยกผู้พูด สกัดมติ และจับคู่กับมติค้างของชุดนี้ให้",
          "Upload a new recording — SARA transcribes, diarizes, extracts resolutions and links them to open items.",
        )}
        actions={
          <Button variant="primary" icon={<Plus size={16} />} onClick={() => setUploadOpen(true)}>
            {t("uploadMeeting")}
          </Button>
        }
      />

      <PageBody className="space-y-4">
        {pendingReview > 0 && (
          <div className="flex items-center gap-2.5 rounded-[var(--radius)] border border-[color-mix(in_srgb,var(--warn)_30%,transparent)] bg-[var(--warn-bg)] px-4 py-3">
            <span className="text-[var(--warn)]">⚑</span>
            <p className="text-[13px] text-ink-2">
              {t.pick(
                `มีการประชุม ${pendingReview} ครั้งที่ยังไม่ได้รับรองรายงาน — สร้างวาระและส่งอีเมลจากการประชุมที่ยังไม่รับรองไม่ได้`,
                `${pendingReview} meeting(s) awaiting approval — agenda and email are blocked until approved.`,
              )}
            </p>
          </div>
        )}

        <Card className="overflow-hidden">
          {meetings.length === 0 ? (
            <EmptyState
              icon={<FileStack size={20} />}
              title={t.pick("ยังไม่มีการประชุมในชุดนี้", "No meetings yet")}
              action={
                <Button variant="primary" icon={<Plus size={16} />} onClick={() => setUploadOpen(true)}>
                  {t("uploadMeeting")}
                </Button>
              }
            />
          ) : (
            meetings.map((m) => {
              const created = db.resolutions.filter((r) => r.origin_meeting_id === m.id).length;
              const closed = db.resolutions.filter((r) => r.closed_meeting_id === m.id).length;
              const pending = db.proposals.filter((p) => p.meeting_id === m.id && p.decision === "pending").length;
              const st = MEETING_STATUS[m.status];
              return (
                <Link
                  key={m.id}
                  href={`/series/${seriesId}/meetings/${m.id}`}
                  className="flex items-center gap-4 border-b border-line px-4 py-4 transition-colors last:border-b-0 hover:bg-surface-2"
                >
                  <div
                    className={cn(
                      "flex h-10 w-10 shrink-0 items-center justify-center rounded-[var(--radius)]",
                      m.status === "failed" ? "bg-[var(--danger-bg)] text-[var(--danger)]" : "bg-sunken text-ink-3",
                    )}
                  >
                    {m.status === "processing" ? (
                      <Loader2 size={17} className="animate-spin text-brand" />
                    ) : m.status === "failed" ? (
                      <AlertOctagon size={17} />
                    ) : m.source_kind === "audio" ? (
                      <FileAudio size={17} />
                    ) : (
                      <FileText size={17} />
                    )}
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="tnum text-[14px] font-semibold text-ink">
                        {t.pick("ครั้งที่", "Meeting")} {m.sequence_no}/{m.fiscal_year}
                      </span>
                      <Badge tone={st.tone}>{t.lang === "th" ? st.th : st.en}</Badge>
                      {pending > 0 && (
                        <Badge tone="warn">
                          {pending} {t.pick("รายการรอยืนยัน", "pending")}
                        </Badge>
                      )}
                    </div>
                    <p className="tnum mt-1 text-[12.5px] text-ink-3">
                      {formatThaiDate(m.meeting_date)}
                      {m.approved_by && ` · ${t.pick("รับรองโดย", "approved by")} ${m.approved_by}`}
                    </p>
                  </div>

                  <div className="hidden shrink-0 gap-5 text-right sm:flex">
                    <div>
                      <p className="tnum text-[16px] font-semibold text-brand">+{created}</p>
                      <p className="text-[11px] text-ink-3">{t.pick("มติใหม่", "created")}</p>
                    </div>
                    <div>
                      <p className="tnum text-[16px] font-semibold text-[var(--ok)]">{closed}</p>
                      <p className="text-[11px] text-ink-3">{t.pick("ปิดมติ", "closed")}</p>
                    </div>
                  </div>

                  <ChevronRight size={16} className="shrink-0 text-ink-4" />
                </Link>
              );
            })
          )}
        </Card>
      </PageBody>

      <UploadMeetingModal open={uploadOpen} onClose={() => setUploadOpen(false)} seriesId={seriesId} />
    </>
  );
}
