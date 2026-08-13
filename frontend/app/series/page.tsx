"use client";

/** M1 — ทะเบียนชุดการประชุม (FR-M1-01 ถึง 05) */

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, CalendarDays, Layers, Plus, Trash2, Users } from "lucide-react";
import { PageBody, PageHeader } from "@/components/app-shell";
import { Button, Card, ConfirmModal, EmptyState, Field, Input, Modal, Select } from "@/components/ui";
import { useT } from "@/lib/i18n";
import {
  createSeries,
  deleteSeries,
  formatThaiDate,
  seriesStats,
  useApp,
} from "@/lib/store";
import type { Cadence, MeetingSeries } from "@/lib/types";

const CADENCE_LABEL: Record<Cadence, [string, string]> = {
  monthly: ["รายเดือน", "Monthly"],
  quarterly: ["รายไตรมาส", "Quarterly"],
  biannual: ["ทุก 6 เดือน", "Every 6 months"],
  adhoc: ["ตามวาระ", "Ad hoc"],
};

export default function SeriesListPage() {
  const t = useT();
  const { db } = useApp();
  const [open, setOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<MeetingSeries | null>(null);

  return (
    <>
      <PageHeader
        title={t.pick("ชุดการประชุม", "Meeting series")}
        desc={t.pick(
          "มติผูกกับชุดการประชุม ไม่ใช่กับการประชุมครั้งใดครั้งหนึ่ง ระบบจึงจำเรื่องค้างข้ามครั้งได้",
          "Resolutions belong to a series, not a single meeting — that is how the system remembers across meetings.",
        )}
        actions={
          <Button variant="primary" icon={<Plus size={16} />} onClick={() => setOpen(true)}>
            {t.pick("สร้างชุดการประชุม", "New series")}
          </Button>
        }
      />

      <PageBody>
        {db.series.length === 0 ? (
          <Card>
            <EmptyState
              icon={<Layers size={20} />}
              title={t.pick("ยังไม่มีชุดการประชุม", "No meeting series yet")}
              desc={t.pick("เริ่มจากสร้างชุดการประชุม เช่น คณะกรรมการบริหาร ปีงบประมาณ 2569", "Start by creating one.")}
              action={
                <Button variant="primary" icon={<Plus size={16} />} onClick={() => setOpen(true)}>
                  {t.pick("สร้างชุดการประชุม", "New series")}
                </Button>
              }
            />
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {db.series.map((s) => {
              const stats = seriesStats(db, s.id);
              const meetingCount = db.meetings.filter((m) => m.series_id === s.id).length;
              return (
                <Card key={s.id} className="group relative overflow-hidden p-5 transition-shadow hover:shadow-[var(--shadow-2)]">
                  {/* ทั้งใบคลิกได้ ไม่ใช่เฉพาะตัวหนังสือ — ปุ่มลบซ้อนทับอยู่ด้านบนด้วย z-index */}
                  <Link href={`/series/${s.id}`} className="absolute inset-0" aria-label={s.name} />

                  <div className="pointer-events-none relative flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-[11px] font-medium uppercase tracking-wider text-ink-4">{s.committee_type}</p>
                      <p className="mt-1 text-[16px] font-semibold leading-snug text-ink group-hover:text-brand">
                        {s.name}
                      </p>
                    </div>
                    <button
                      onClick={() => setPendingDelete(s)}
                      className="pointer-events-auto relative rounded p-1.5 text-ink-4 opacity-0 transition-opacity hover:bg-sunken hover:text-[var(--danger)] group-hover:opacity-100 cursor-pointer"
                      title={t("delete")}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>

                  <div className="mt-4 grid grid-cols-4 gap-2 rounded-[var(--radius)] bg-sunken px-3 py-2.5">
                    <MiniStat label={t("statTotal")} value={stats.total} />
                    <MiniStat label={t("statOpen")} value={stats.open} />
                    <MiniStat label={t("statOverdue")} value={stats.overdue} tone="var(--danger)" />
                    <MiniStat label={t.pick("ประชุมแล้ว", "Meetings")} value={meetingCount} />
                  </div>

                  <div className="pointer-events-none relative mt-4 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[12.5px] text-ink-3">
                    <span className="inline-flex items-center gap-1.5">
                      <Users size={13} /> {s.member_ids.length} {t.pick("ท่าน", "members")}
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <CalendarDays size={13} />
                      {t.pick("ประชุมครั้งถัดไป", "Next")}{" "}
                      {s.next_meeting_date ? formatThaiDate(s.next_meeting_date, true) : "-"}
                    </span>
                    <span>{CADENCE_LABEL[s.cadence][t.lang === "th" ? 0 : 1]}</span>
                    <span className="ml-auto inline-flex items-center gap-1.5 font-medium text-brand transition-all group-hover:gap-2.5">
                      {t.pick("เปิดภาพรวมมติ", "Open dashboard")} <ArrowRight size={14} />
                    </span>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </PageBody>

      <CreateSeriesModal open={open} onClose={() => setOpen(false)} />

      <ConfirmModal
        open={pendingDelete !== null}
        onClose={() => setPendingDelete(null)}
        title={t.pick("ลบชุดการประชุม", "Delete series")}
        confirmLabel={t("delete")}
        onConfirm={() => {
          if (pendingDelete) deleteSeries(pendingDelete.id);
          setPendingDelete(null);
        }}
      >
        {t.pick(
          `การประชุมและมติทั้งหมดใน “${pendingDelete?.name ?? ""}” จะถูกลบไปด้วย และกู้คืนไม่ได้`,
          `All meetings and resolutions in “${pendingDelete?.name ?? ""}” will be deleted permanently.`,
        )}
      </ConfirmModal>
    </>
  );
}

function MiniStat({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <div>
      <p className="tnum text-[19px] font-semibold leading-none" style={{ color: tone ?? "var(--ink)" }}>
        {value}
      </p>
      <p className="mt-1 text-[11px] leading-tight text-ink-3">{label}</p>
    </div>
  );
}

function CreateSeriesModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const t = useT();
  const { db } = useApp();
  const [name, setName] = useState("");
  const [committee, setCommittee] = useState("คณะกรรมการบริหาร");
  const [fiscalYear, setFiscalYear] = useState(2569);
  const [cadence, setCadence] = useState<Cadence>("monthly");
  const [nextDate, setNextDate] = useState("");
  const [members, setMembers] = useState<string[]>([]);

  const submit = () => {
    if (!name.trim()) return;
    createSeries({
      name: name.trim(),
      committee_type: committee,
      fiscal_year: fiscalYear,
      agenda_template_id: "tpl-official-th",
      cadence,
      next_meeting_date: nextDate || null,
      member_ids: members,
    });
    setName("");
    setMembers([]);
    onClose();
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t.pick("สร้างชุดการประชุม", "New meeting series")}
      desc={t.pick("มติทั้งหมดจะถูกผูกกับชุดนี้ และถูกยกขึ้นวาระสืบเนื่องอัตโนมัติ", "All resolutions attach to this series.")}
      footer={
        <>
          <Button onClick={onClose}>{t("cancel")}</Button>
          <Button variant="primary" onClick={submit} disabled={!name.trim()}>
            {t.pick("สร้าง", "Create")}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label={t.pick("ชื่อชุดการประชุม", "Series name")}>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="คณะกรรมการบริหาร ปีงบประมาณ 2569"
            autoFocus
          />
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t.pick("ประเภทคณะกรรมการ", "Committee type")}>
            <Input value={committee} onChange={(e) => setCommittee(e.target.value)} />
          </Field>
          <Field label={t.pick("ปีงบประมาณ", "Fiscal year")}>
            <Input
              type="number"
              value={fiscalYear}
              onChange={(e) => setFiscalYear(Number(e.target.value))}
              className="tnum"
            />
          </Field>
          <Field label={t.pick("รอบการประชุม", "Cadence")}>
            <Select value={cadence} onChange={(e) => setCadence(e.target.value as Cadence)}>
              {(Object.keys(CADENCE_LABEL) as Cadence[]).map((c) => (
                <option key={c} value={c}>
                  {CADENCE_LABEL[c][t.lang === "th" ? 0 : 1]}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t.pick("วันประชุมครั้งถัดไป", "Next meeting date")}>
            <Input type="date" value={nextDate} onChange={(e) => setNextDate(e.target.value)} />
          </Field>
        </div>

        <Field
          label={t.pick("กรรมการประจำชุด", "Standing members")}
          hint={t.pick("เลือกจากทะเบียนบุคคลระดับองค์กร", "From the org-level people registry")}
        >
          <div className="max-h-44 space-y-1 overflow-y-auto rounded-[var(--radius)] border border-line p-2">
            {db.people
              .filter((p) => !p.is_department)
              .map((p) => (
                <label key={p.id} className="flex cursor-pointer items-center gap-2.5 rounded px-2 py-1.5 hover:bg-sunken">
                  <input
                    type="checkbox"
                    checked={members.includes(p.id)}
                    onChange={(e) =>
                      setMembers((prev) => (e.target.checked ? [...prev, p.id] : prev.filter((id) => id !== p.id)))
                    }
                    className="h-4 w-4 accent-[var(--brand)]"
                  />
                  <span className="text-[13px] text-ink">{p.full_name}</span>
                  <span className="truncate text-[12px] text-ink-3">{p.position}</span>
                </label>
              ))}
          </div>
        </Field>
      </div>
    </Modal>
  );
}
