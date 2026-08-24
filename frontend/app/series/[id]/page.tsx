"use client";

/** M6 — แดชบอร์ดมติ: ต้องเข้าใจได้ใน 10 วินาที และไม่ยาวเกิน 1 หน้าจอในส่วนบน */

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowRight,
  CalendarClock,
  CheckCircle2,
  ListChecks,
  Timer,
  Upload,
} from "lucide-react";
import { PageBody, PageHeader } from "@/components/app-shell";
import { UploadMeetingModal } from "@/components/meeting-ingest";
import { ResolutionDrawer, ResolutionRow } from "@/components/resolution-detail";
import { Badge, Button, Card, CardHead, EmptyState, StatTile, StatusPill, cn, statusColor } from "@/components/ui";
import { useT } from "@/lib/i18n";
import {
  STATUS_LABEL_TH,
  assigneeNames,
  daysUntil,
  formatThaiDate,
  isOpen,
  overdueDays,
  seriesStats,
  useApp,
} from "@/lib/store";
import type { ResolutionStatus } from "@/lib/types";

export default function SeriesDashboardPage() {
  const t = useT();
  const { db } = useApp();
  const params = useParams<{ id: string }>();
  const seriesId = params.id;
  const series = db.series.find((s) => s.id === seriesId);
  const [openId, setOpenId] = useState<string | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);

  if (!series) {
    return (
      <PageBody>
        <Card>
          <EmptyState title={t.pick("ไม่พบชุดการประชุมนี้", "Series not found")} />
        </Card>
      </PageBody>
    );
  }

  const stats = seriesStats(db, seriesId);
  const resolutions = db.resolutions.filter((r) => r.series_id === seriesId);
  const overdue = resolutions.filter((r) => overdueDays(r) > 0).sort((a, b) => overdueDays(b) - overdueDays(a));
  const meetings = db.meetings.filter((m) => m.series_id === seriesId).sort((a, b) => b.sequence_no - a.sequence_no);
  const lastMeeting = meetings[0];
  const nextIn = series.next_meeting_date ? daysUntil(series.next_meeting_date) : null;

  const statusCounts = (Object.keys(STATUS_LABEL_TH) as ResolutionStatus[])
    .map((s) => ({ status: s, count: resolutions.filter((r) => r.status === s).length }))
    .filter((x) => x.count > 0);

  return (
    <>
      <PageHeader
        eyebrow={
          <>
            <span>{series.committee_type}</span>
            <span className="text-ink-4">·</span>
            <span className="tnum">ปีงบประมาณ {series.fiscal_year}</span>
          </>
        }
        title={series.name}
        desc={
          lastMeeting
            ? t.pick(
                `ประชุมล่าสุด ครั้งที่ ${lastMeeting.sequence_no}/${lastMeeting.fiscal_year} เมื่อ ${formatThaiDate(lastMeeting.meeting_date)}`,
                `Last meeting ${lastMeeting.sequence_no}/${lastMeeting.fiscal_year}`,
              )
            : undefined
        }
        actions={
          <Button variant="primary" icon={<Upload size={15} />} onClick={() => setUploadOpen(true)}>
            {t("uploadMeeting")}
          </Button>
        }
      />

      <PageBody className="space-y-5">
        {/* แถวสถิติ — มติทั้งหมด, กำลังดำเนินการ, เกินกำหนด */}
        <section className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <StatTile label={t("statTotal")} value={stats.total} icon={<ListChecks size={15} />} />
          <StatTile
            label={t("statOpen")}
            value={stats.open}
            tone={stats.open > 0 ? "warn" : "neutral"}
            icon={<Timer size={15} />}
            hint={t.pick(`ในจำนวนนี้เกินกำหนด ${stats.overdue} ข้อ`, `${stats.overdue} overdue`)}
          />
          <StatTile
            label={t("statOverdue")}
            value={stats.overdue}
            tone={stats.overdue > 0 ? "danger" : "ok"}
            icon={<AlertTriangle size={15} />}
          />
        </section>

        {/* แถบสัดส่วนสถานะ อ่านครั้งเดียวจบ */}
        <Card className="p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-[13px] font-medium text-ink-2">{t.pick("สัดส่วนสถานะมติทั้งชุด", "Status breakdown")}</p>
            {nextIn !== null && (
              <Badge tone={nextIn <= 7 ? "warn" : "neutral"}>
                <CalendarClock size={11} />
                {t.pick("ประชุมครั้งถัดไปอีก", "Next meeting in")} {nextIn} {t("days")} ·{" "}
                {formatThaiDate(series.next_meeting_date!, true)}
              </Badge>
            )}
          </div>
          <div className="mt-3 flex h-2.5 w-full overflow-hidden rounded-full bg-sunken">
            {statusCounts.map((s) => (
              <span
                key={s.status}
                className="shrink-0"
                title={`${STATUS_LABEL_TH[s.status]} ${s.count}`}
                style={{ width: `${(s.count / stats.total) * 100}%`, background: statusColor(s.status) }}
              />
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2">
            {statusCounts.map((s) => (
              <span key={s.status} className="inline-flex items-center gap-1.5 text-[12.5px] text-ink-2">
                <span className="h-2 w-2 rounded-full" style={{ background: statusColor(s.status) }} />
                {STATUS_LABEL_TH[s.status]}
                <span className="tnum font-medium text-ink">{s.count}</span>
              </span>
            ))}
          </div>
        </Card>

        {/* มติค้าง เรียงตามวันที่เกิน */}
        <Card className="overflow-hidden">
          <CardHead
            title={t("overdueList")}
            desc={t.pick("เรื่องที่อยู่บนสุดคือเรื่องที่องค์กรลืมนานที่สุด", "Top items are what the org has forgotten longest")}
            right={
              <Link href={`/series/${seriesId}/resolutions`}>
                <Button size="sm" variant="ghost" icon={<ArrowRight size={14} />}>
                  {t("navResolutions")}
                </Button>
              </Link>
            }
          />
          {overdue.length === 0 ? (
            <EmptyState icon={<CheckCircle2 size={20} />} title={t("noOverdue")} />
          ) : (
            <div>
              {overdue.map((r) => (
                <ResolutionRow key={r.id} resolution={r} onOpen={() => setOpenId(r.id)} compact />
              ))}
            </div>
          )}
        </Card>

        {/* แถบการประชุมล่าสุด */}
        <Card className="overflow-hidden">
          <CardHead
            title={t.pick("ไทม์ไลน์การประชุมในชุดนี้", "Meetings in this series")}
            right={
              <Link href={`/series/${seriesId}/meetings`}>
                <Button size="sm" variant="ghost" icon={<ArrowRight size={14} />}>
                  {t("navMeetings")}
                </Button>
              </Link>
            }
          />
          <div className="flex gap-3 overflow-x-auto px-5 py-4">
            {meetings
              .slice()
              .reverse()
              .map((m) => {
                const created = db.resolutions.filter((r) => r.origin_meeting_id === m.id).length;
                const closed = db.resolutions.filter((r) => r.closed_meeting_id === m.id).length;
                return (
                  <Link
                    key={m.id}
                    href={`/series/${seriesId}/meetings/${m.id}`}
                    className="min-w-[168px] shrink-0 rounded-[var(--radius)] border border-line px-3.5 py-3 transition-colors hover:border-brand hover:bg-surface-2"
                  >
                    <p className="tnum text-[13px] font-semibold text-ink">
                      ครั้งที่ {m.sequence_no}/{m.fiscal_year}
                    </p>
                    <p className="tnum mt-0.5 text-[12px] text-ink-3">{formatThaiDate(m.meeting_date, true)}</p>
                    <div className="mt-2.5 flex gap-3 text-[12px]">
                      <span className="text-ink-2">
                        <span className="tnum font-medium text-brand">+{created}</span> {t.pick("มติใหม่", "new")}
                      </span>
                      <span className="text-ink-2">
                        <span className="tnum font-medium text-[var(--ok)]">✓{closed}</span> {t.pick("ปิด", "closed")}
                      </span>
                    </div>
                  </Link>
                );
              })}
            {series.next_meeting_date && (
              <Link
                href={`/series/${seriesId}/agenda`}
                className={cn(
                  "min-w-[168px] shrink-0 rounded-[var(--radius)] border border-dashed border-[var(--line-strong)] px-3.5 py-3",
                  "transition-colors hover:border-brand hover:bg-[var(--brand-soft)]",
                )}
              >
                <p className="tnum text-[13px] font-semibold text-ink-3">
                  ครั้งที่ {(meetings[0]?.sequence_no ?? 0) + 1}/{series.fiscal_year}
                </p>
                <p className="tnum mt-0.5 text-[12px] text-ink-4">{formatThaiDate(series.next_meeting_date, true)}</p>
                <p className="mt-2.5 text-[12px] font-medium text-brand">{t.pick("เตรียมวาระ →", "Prepare agenda →")}</p>
              </Link>
            )}
          </div>
        </Card>
      </PageBody>

      <ResolutionDrawer resolutionId={openId} onClose={() => setOpenId(null)} />
      <UploadMeetingModal open={uploadOpen} onClose={() => setUploadOpen(false)} seriesId={seriesId} />
    </>
  );
}
