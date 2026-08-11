"use client";

/**
 * M5 — ร่างระเบียบวาระการประชุมครั้งถัดไป
 * ซ้าย: แก้/ลบ/สลับลำดับได้ทุกข้อ (FR-M5-07)  ขวา: หน้ากระดาษที่จะได้จริงตอน export
 */

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Check,
  Download,
  FileWarning,
  PenLine,
  Plus,
  Printer,
  RefreshCw,
  ScrollText,
  Trash2,
  X,
} from "lucide-react";
import { PageBody, PageHeader } from "@/components/app-shell";
import { Badge, Button, Card, CardHead, EmptyState, Input, Textarea, cn } from "@/components/ui";
import { useT } from "@/lib/i18n";
import * as api from "@/lib/api";
import {
  addAgendaItem,
  editAgendaItem,
  formatThaiDate,
  moveAgendaItem,
  removeAgendaItem,
  overdueDays,
  useApp,
} from "@/lib/store";
import { buildAgendaHtml, downloadDoc, toThaiNumeral } from "@/lib/export-doc";
import type { AgendaItem } from "@/lib/types";

const SECTIONS: Array<{ no: 1 | 2 | 3 | 4 | 5; th: string; en: string }> = [
  { no: 1, th: "เรื่องที่ประธานแจ้งให้ที่ประชุมทราบ", en: "Chair's announcements" },
  { no: 2, th: "เรื่องรับรองรายงานการประชุม", en: "Approval of previous minutes" },
  { no: 3, th: "เรื่องสืบเนื่องจากการประชุมครั้งก่อน", en: "Matters arising" },
  { no: 4, th: "เรื่องเสนอเพื่อพิจารณา", en: "Matters for consideration" },
  { no: 5, th: "เรื่องอื่น ๆ", en: "Any other business" },
];

export default function AgendaPage() {
  const t = useT();
  const { db } = useApp();
  const seriesId = useParams<{ id: string }>().id;
  const series = db.series.find((s) => s.id === seriesId);
  const draft = db.agendas.find((a) => a.series_id === seriesId);
  const [busy, setBusy] = useState(false);

  /* FR-M9-04 — ห้ามสร้างวาระจากการประชุมที่ยังไม่รับรอง */
  const meetings = db.meetings.filter((m) => m.series_id === seriesId);
  const unapproved = meetings.filter((m) => m.status === "draft" || m.status === "reviewed" || m.status === "processing");
  const blocked = unapproved.length > 0;

  const generate = async () => {
    setBusy(true);
    try {
      await api.generateAgenda(seriesId);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader
        title={t("navAgenda")}
        desc={t.pick(
          "ระบบยกมติที่ยังไม่ปิดของชุดนี้ขึ้นเป็นวาระที่ 3 ให้เอง พร้อมที่มา ผู้รับผิดชอบ กำหนด และจำนวนวันที่เกิน",
          "Open resolutions are lifted into section 3 automatically, with origin, assignee, due date and days overdue.",
        )}
        actions={
          <>
            {draft && (
              <>
                <Button icon={<Printer size={15} />} onClick={() => window.print()}>
                  {t("exportPdf")}
                </Button>
                <Button
                  variant="seal"
                  icon={<Download size={15} />}
                  onClick={() =>
                    downloadDoc(`ระเบียบวาระครั้งที่-${draft.target_sequence_no}-${series?.fiscal_year}`, buildAgendaHtml(db, draft))
                  }
                >
                  {t("exportDocx")}
                </Button>
              </>
            )}
            <Button
              variant="primary"
              icon={<RefreshCw size={15} className={busy ? "animate-spin" : undefined} />}
              onClick={generate}
              disabled={busy || blocked}
            >
              {draft ? t.pick("สร้างใหม่จากข้อมูลล่าสุด", "Regenerate") : t("generateAgenda")}
            </Button>
          </>
        }
      />

      <PageBody className="space-y-5">
        {blocked && (
          <Card className="flex flex-wrap items-center gap-3 border-[color-mix(in_srgb,var(--warn)_35%,transparent)] bg-[var(--warn-bg)] p-4">
            <FileWarning size={18} className="shrink-0 text-[var(--warn)]" />
            <p className="min-w-0 flex-1 text-[13px] leading-relaxed text-ink-2">
              {t.pick(
                `มีการประชุม ${unapproved.length} ครั้งที่ยังไม่ได้รับรองรายงาน ระบบจึงยังไม่สร้างวาระให้ เพราะมติจากรายงานที่ยังไม่รับรองยังไม่มีผลผูกพัน`,
                `${unapproved.length} meeting(s) not yet approved — resolutions from unapproved minutes are not binding.`,
              )}
            </p>
            <Link href={`/series/${seriesId}/meetings/${unapproved[0].id}`}>
              <Button size="sm">{t.pick("ไปตรวจทาน", "Go review")}</Button>
            </Link>
          </Card>
        )}

        {!draft ? (
          <Card className="border-dashed">
            <EmptyState
              icon={<ScrollText size={20} />}
              title={t.pick("ยังไม่ได้สร้างร่างระเบียบวาระ", "No agenda draft yet")}
              desc={t.pick(
                "กดสร้าง แล้วระบบจะไล่มติค้างทั้งหมดของชุดนี้ขึ้นวาระสืบเนื่องให้ภายในไม่กี่วินาที แทนการเปิดรายงานเก่าย้อนหลังทีละไฟล์",
                "Generate to lift every open resolution into the agenda automatically.",
              )}
              action={
                <Button variant="primary" icon={<ScrollText size={16} />} onClick={generate} disabled={blocked}>
                  {t("generateAgenda")}
                </Button>
              }
            />
          </Card>
        ) : (
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            {/* ตัวแก้ไข */}
            <div className="no-print space-y-4">
              <Card className="flex flex-wrap items-center justify-between gap-3 p-4">
                <div>
                  <p className="tnum text-[14px] font-semibold text-ink">
                    {t.pick("ร่างวาระ ครั้งที่", "Agenda draft")} {draft.target_sequence_no}/{series?.fiscal_year}
                  </p>
                  <p className="tnum mt-0.5 text-[12.5px] text-ink-3">
                    {draft.target_meeting_date ? formatThaiDate(draft.target_meeting_date) : t.pick("ยังไม่ระบุวันประชุม", "date TBD")}
                  </p>
                </div>
                <Badge tone="brand">
                  {draft.items.filter((i) => i.section_no === 3).length} {t.pick("เรื่องสืบเนื่อง", "carried over")}
                </Badge>
              </Card>

              {SECTIONS.map((section) => {
                const items = draft.items
                  .filter((i) => i.section_no === section.no)
                  .sort((a, b) => a.sort_order - b.sort_order);
                return (
                  <Card key={section.no} className="overflow-hidden">
                    <CardHead
                      title={`${t.pick("ระเบียบวาระที่", "Section")} ${toThaiNumeral(section.no)} ${t.lang === "th" ? section.th : section.en}`}
                      right={
                        <Button size="sm" variant="ghost" icon={<Plus size={14} />} onClick={() => addAgendaItem(draft.id, section.no)}>
                          {t("add")}
                        </Button>
                      }
                    />
                    {items.length === 0 ? (
                      <p className="px-5 py-4 text-[13px] text-ink-3">{t.pick("(ไม่มี)", "(none)")}</p>
                    ) : (
                      <div className="divide-y divide-[var(--line)]">
                        {items.map((item, idx) => (
                          <AgendaItemEditor
                            key={item.id}
                            item={item}
                            index={idx}
                            first={idx === 0}
                            last={idx === items.length - 1}
                            draftId={draft.id}
                          />
                        ))}
                      </div>
                    )}
                  </Card>
                );
              })}
            </div>

            {/* ตัวอย่างเอกสารจริง */}
            <div className="xl:sticky xl:top-5 xl:self-start">
              <Card className="overflow-hidden">
                <CardHead
                  className="no-print"
                  title={t.pick("ตัวอย่างเอกสารที่จะได้", "Document preview")}
                  desc={t.pick("ฟอนต์ TH Sarabun ขนาด 16 pt ตามระเบียบสารบรรณ · เปิดแก้ต่อใน Word ได้ทันที", "TH Sarabun 16pt, editable in Word")}
                />
                <div className="max-h-[76vh] overflow-y-auto bg-[#e9ebef] p-4 print:max-h-none print:bg-white print:p-0">
                  <div className="doc-paper mx-auto max-w-[820px] px-[8%] py-10 shadow-[var(--shadow-2)] print:shadow-none">
                    <AgendaPaper draftId={draft.id} />
                  </div>
                </div>
              </Card>
            </div>
          </div>
        )}
      </PageBody>
    </>
  );
}

/* ── ข้อวาระที่แก้ไขได้ ───────────────────────────────────────────────── */

function AgendaItemEditor({
  item,
  index,
  first,
  last,
  draftId,
}: {
  item: AgendaItem;
  index: number;
  first: boolean;
  last: boolean;
  draftId: string;
}) {
  const t = useT();
  const { db } = useApp();
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(item.title);
  const [body, setBody] = useState(item.body);

  const linked = db.resolutions.find((r) => r.id === item.resolution_id);
  const od = linked ? overdueDays(linked) : 0;

  const save = () => {
    editAgendaItem(draftId, item.id, { title, body });
    setEditing(false);
  };

  return (
    <div className="px-4 py-3.5">
      <div className="flex items-start gap-3">
        <span className="tnum mt-0.5 shrink-0 font-mono text-[12px] text-ink-4">
          {toThaiNumeral(item.section_no)}.{toThaiNumeral(index + 1)}
        </span>

        <div className="min-w-0 flex-1">
          {editing ? (
            <div className="space-y-2">
              <Input value={title} onChange={(e) => setTitle(e.target.value)} autoFocus />
              <Textarea value={body} onChange={(e) => setBody(e.target.value)} rows={5} className="font-[inherit]" />
              <div className="flex gap-2">
                <Button size="sm" variant="primary" icon={<Check size={14} />} onClick={save}>
                  {t("save")}
                </Button>
                <Button size="sm" icon={<X size={14} />} onClick={() => setEditing(false)}>
                  {t("cancel")}
                </Button>
              </div>
            </div>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-[13.5px] font-medium leading-snug text-ink">{item.title}</p>
                {od > 0 && (
                  <Badge tone="danger">
                    <AlertTriangle size={10} /> {t("overdueBy")} {od} {t("days")}
                  </Badge>
                )}
                {linked && linked.postpone_count >= 3 && <Badge tone="warn">⚑ {linked.postpone_count}</Badge>}
              </div>
              {item.body && (
                <p className="mt-1.5 whitespace-pre-line text-[12.5px] leading-relaxed text-ink-3">{item.body}</p>
              )}
            </>
          )}
        </div>

        {!editing && (
          <div className="flex shrink-0 gap-0.5">
            <IconBtn title={t.pick("เลื่อนขึ้น", "Move up")} disabled={first} onClick={() => moveAgendaItem(draftId, item.id, -1)}>
              <ArrowUp size={14} />
            </IconBtn>
            <IconBtn title={t.pick("เลื่อนลง", "Move down")} disabled={last} onClick={() => moveAgendaItem(draftId, item.id, 1)}>
              <ArrowDown size={14} />
            </IconBtn>
            <IconBtn title={t("edit")} onClick={() => setEditing(true)}>
              <PenLine size={14} />
            </IconBtn>
            <IconBtn title={t("delete")} danger onClick={() => removeAgendaItem(draftId, item.id)}>
              <Trash2 size={14} />
            </IconBtn>
          </div>
        )}
      </div>
    </div>
  );
}

function IconBtn({
  children,
  onClick,
  disabled,
  title,
  danger,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  title: string;
  danger?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={cn(
        "rounded p-1.5 text-ink-3 transition-colors hover:bg-sunken hover:text-ink disabled:opacity-30 cursor-pointer disabled:cursor-default",
        danger && "hover:text-[var(--danger)]",
      )}
    >
      {children}
    </button>
  );
}

/* ── หน้ากระดาษตัวอย่าง ──────────────────────────────────────────────── */

function AgendaPaper({ draftId }: { draftId: string }) {
  const { db } = useApp();
  const draft = db.agendas.find((a) => a.id === draftId);
  if (!draft) return null;
  const series = db.series.find((s) => s.id === draft.series_id);

  return (
    <article>
      <h1 className="text-center text-[22px] font-bold leading-snug">ระเบียบวาระการประชุม{series?.name}</h1>
      <p className="mt-1 text-center text-[18px]">
        ครั้งที่ {toThaiNumeral(draft.target_sequence_no)}/{toThaiNumeral(series?.fiscal_year ?? 2569)}
      </p>
      {draft.target_meeting_date && (
        <p className="text-center text-[18px]">วันที่ {toThaiNumeral(formatThaiDate(draft.target_meeting_date))}</p>
      )}

      <div className="mt-8 space-y-5">
        {SECTIONS.map((section) => {
          const items = draft.items
            .filter((i) => i.section_no === section.no)
            .sort((a, b) => a.sort_order - b.sort_order);
          return (
            <section key={section.no}>
              <h2 className="text-[18px] font-bold">
                ระเบียบวาระที่ {toThaiNumeral(section.no)} {section.th}
              </h2>
              {items.length === 0 ? (
                <p className="ml-8 text-[17px] text-[#555]">(ไม่มี)</p>
              ) : (
                items.map((item, idx) => (
                  <div key={item.id} className="ml-8 mt-2">
                    <p className="font-bold">
                      {toThaiNumeral(section.no)}.{toThaiNumeral(idx + 1)} {item.title}
                    </p>
                    {item.body && <p className="whitespace-pre-line">{item.body}</p>}
                  </div>
                ))
              )}
            </section>
          );
        })}
      </div>

      <div className="mt-14 flex justify-between text-center text-[16px]">
        <div>
          <p>(ลงชื่อ) .......................................</p>
          <p className="mt-1">ผู้จดรายงานการประชุม</p>
        </div>
        <div>
          <p>(ลงชื่อ) .......................................</p>
          <p className="mt-1">ผู้ตรวจรายงานการประชุม</p>
        </div>
      </div>
    </article>
  );
}
