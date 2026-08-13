"use client";

/**
 * แผงรายละเอียดมติ — M4 + M6-06
 * รวมทุกอย่างที่ตอบคำถาม "แล้วถ้า AI มั่วล่ะ" ไว้ในที่เดียว:
 * ข้อความมติ · ที่มาถึงระดับ timestamp · ไทม์ไลน์การถูกอ้างถึงข้ามการประชุม · ประวัติการแก้ทุกครั้ง
 */

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowRightLeft,
  Clock,
  FileText,
  History,
  Link2,
  PenLine,
  Quote,
  X,
} from "lucide-react";
import {
  Badge,
  Button,
  ConfidenceBar,
  EvidenceQuote,
  Field,
  Input,
  Modal,
  Select,
  StatusPill,
  Textarea,
  cn,
  statusColor,
} from "./ui";
import { useT } from "@/lib/i18n";
import {
  LINK_LABEL_TH,
  NEXT_STATUSES,
  STATUS_LABEL_TH,
  assigneeNames,
  changeResolutionStatus,
  formatThaiDate,
  formatTimecode,
  overdueDays,
  personName,
  updateResolution,
  useApp,
} from "@/lib/store";
import type { Resolution, ResolutionStatus, Uuid } from "@/lib/types";

export function ResolutionDrawer({ resolutionId, onClose }: { resolutionId: Uuid | null; onClose: () => void }) {
  const t = useT();
  const { db } = useApp();
  const r = db.resolutions.find((x) => x.id === resolutionId);
  const [editing, setEditing] = useState(false);
  const [statusTarget, setStatusTarget] = useState<ResolutionStatus | null>(null);

  if (!r) return null;

  const originMeeting = db.meetings.find((m) => m.id === r.origin_meeting_id);
  const od = overdueDays(r);
  const links = db.links
    .filter((l) => l.resolution_id === r.id)
    .sort((a, b) => a.created_at.localeCompare(b.created_at));
  const history = db.history
    .filter((h) => h.resolution_id === r.id)
    .sort((a, b) => b.changed_at.localeCompare(a.changed_at));
  const supersededBy = db.resolutions.find((x) => x.id === r.superseded_by_id);

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-[rgba(10,15,25,0.4)]" onClick={onClose} />
      <aside className="fade-up relative flex h-full w-full max-w-[620px] flex-col border-l border-line bg-surface shadow-[var(--shadow-3)]">
        {/* หัวแผง */}
        <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-[12px] font-medium text-brand">{r.ref_no}</span>
              <StatusPill status={r.status} label={STATUS_LABEL_TH[r.status]} size="sm" />
              {od > 0 && (
                <Badge tone="danger">
                  <AlertTriangle size={11} />
                  {t("overdueBy")} {od} {t("days")}
                </Badge>
              )}
              {r.postpone_count >= 3 && (
                <Badge tone="warn">
                  ⚑ {t("postponedTimes")} {r.postpone_count} {t("times")}
                </Badge>
              )}
            </div>
            <p className="mt-2 text-[14.5px] font-medium leading-relaxed text-ink">{r.text}</p>
          </div>
          <button onClick={onClose} className="rounded p-1.5 text-ink-3 hover:bg-sunken hover:text-ink cursor-pointer">
            <X size={17} />
          </button>
        </div>

        {/* ปุ่มดำเนินการ */}
        <div className="flex flex-wrap gap-2 border-b border-line px-5 py-3">
          <Button size="sm" icon={<PenLine size={14} />} onClick={() => setEditing(true)}>
            {t("edit")}
          </Button>
          {NEXT_STATUSES[r.status].map((s) => (
            <Button key={s} size="sm" variant={s === "done" ? "primary" : "secondary"} onClick={() => setStatusTarget(s)}>
              → {STATUS_LABEL_TH[s]}
            </Button>
          ))}
        </div>

        <div className="flex-1 space-y-6 overflow-y-auto px-5 py-5">
          {/* ข้อมูลหลัก */}
          <section className="grid grid-cols-2 gap-x-4 gap-y-3.5">
            <Info label={t("assignee")}>
              <div className="flex flex-wrap gap-1.5">
                {assigneeNames(db, r).length === 0 ? (
                  <span className="text-ink-3">-</span>
                ) : (
                  assigneeNames(db, r).map((p) => (
                    <Badge key={p.id} tone={p.is_department ? "seal" : "brand"}>
                      {p.full_name}
                    </Badge>
                  ))
                )}
              </div>
            </Info>
            <Info label={t("dueDate")}>
              <span className={cn("tnum", od > 0 && "font-medium text-[var(--danger)]")}>
                {r.due_date ? formatThaiDate(r.due_date) : "-"}
              </span>
              {r.original_due_date && r.original_due_date !== r.due_date && (
                <span className="ml-2 text-[12px] text-ink-3 line-through">{formatThaiDate(r.original_due_date)}</span>
              )}
            </Info>
            <Info label={t("origin")}>
              {originMeeting
                ? `ครั้งที่ ${originMeeting.sequence_no}/${originMeeting.fiscal_year} · ${r.origin_agenda_item ?? "-"}`
                : "-"}
              <span className="ml-1.5 text-[12px] text-ink-3">
                {originMeeting ? formatThaiDate(originMeeting.meeting_date, true) : ""}
              </span>
            </Info>
            <Info label={t.pick("ผู้เสนอ", "Proposed by")}>{personName(db, r.proposer_person_id)}</Info>
            <Info label={t.pick("ความมั่นใจของการสกัด", "Extraction confidence")}>
              <ConfidenceBar value={r.extraction_confidence} />
            </Info>
            <Info label={t.pick("แก้ไขล่าสุด", "Last updated")}>
              <span className="tnum text-[12.5px] text-ink-3">{r.updated_at.replace("T", " ").slice(0, 16)}</span>
            </Info>
          </section>

          {supersededBy && (
            <div className="flex items-start gap-2.5 rounded-[var(--radius)] border border-line bg-sunken p-3">
              <ArrowRightLeft size={15} className="mt-0.5 shrink-0 text-ink-3" />
              <p className="text-[13px] leading-relaxed text-ink-2">
                {t.pick("มติข้อนี้ถูกแทนที่ด้วย", "Superseded by")}{" "}
                <span className="font-medium text-ink">{supersededBy.ref_no}</span> — “{supersededBy.text}”
              </p>
            </div>
          )}

          {/* ไทม์ไลน์ข้ามการประชุม */}
          <section>
            <SectionTitle icon={<Link2 size={14} />}>
              {t("timeline")}
              <span className="ml-1.5 text-ink-4">({links.length})</span>
            </SectionTitle>
            <ol className="mt-3 space-y-0">
              {links.map((l, i) => {
                const m = db.meetings.find((x) => x.id === l.meeting_id);
                return (
                  <li key={l.id} className="relative flex gap-3 pb-4 last:pb-0">
                    <div className="flex flex-col items-center">
                      <span
                        className={cn(
                          "mt-1 h-2.5 w-2.5 shrink-0 rounded-full ring-4",
                          l.link_type === "closed"
                            ? "bg-[var(--ok)] ring-[var(--ok-bg)]"
                            : l.link_type === "created"
                              ? "bg-brand ring-[var(--brand-soft)]"
                              : "bg-ink-4 ring-sunken",
                        )}
                      />
                      {i < links.length - 1 && <span className="w-px flex-1 bg-line" />}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-[13px] font-medium text-ink">
                          {t.pick("การประชุมครั้งที่", "Meeting")} {m?.sequence_no}/{m?.fiscal_year}
                        </span>
                        <Badge>{LINK_LABEL_TH[l.link_type]}</Badge>
                        <span className="tnum text-[12px] text-ink-3">
                          {m ? formatThaiDate(m.meeting_date, true) : ""}
                        </span>
                      </div>
                      <EvidenceQuote
                        className="mt-2"
                        text={l.evidence_text}
                        meta={
                          <>
                            <span className="inline-flex items-center gap-1">
                              <Clock size={11} />
                              <span className="tnum font-mono">{formatTimecode(l.evidence_start_ms)}</span>
                            </span>
                            <ConfidenceBar value={l.confidence} />
                          </>
                        }
                      />
                    </div>
                  </li>
                );
              })}
            </ol>
          </section>

          {/* ประวัติการแก้ไข */}
          <section>
            <SectionTitle icon={<History size={14} />}>
              {t("history")}
              <span className="ml-1.5 text-ink-4">({history.length})</span>
            </SectionTitle>
            {history.length === 0 ? (
              <p className="mt-2 text-[13px] text-ink-3">{t.pick("ยังไม่มีการแก้ไข", "No changes yet")}</p>
            ) : (
              <ul className="mt-3 space-y-2.5">
                {history.map((h) => (
                  <li key={h.id} className="rounded-[var(--radius)] border border-line px-3.5 py-2.5">
                    <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-[13px]">
                      <span className="font-medium text-ink">{FIELD_LABEL[h.field] ?? h.field}</span>
                      <span className="text-ink-3 line-through">{renderValue(h.field, h.old_value)}</span>
                      <span className="text-ink-4">→</span>
                      <span className="font-medium text-ink">{renderValue(h.field, h.new_value)}</span>
                    </div>
                    <p className="mt-1 text-[12px] leading-snug text-ink-3">
                      {h.reason} · {h.changed_by} · <span className="tnum">{h.changed_at.replace("T", " ").slice(0, 16)}</span>
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </aside>

      <EditResolutionModal open={editing} onClose={() => setEditing(false)} resolution={r} />
      <StatusChangeModal
        open={statusTarget !== null}
        target={statusTarget}
        resolution={r}
        onClose={() => setStatusTarget(null)}
      />
    </div>
  );
}

const FIELD_LABEL: Record<string, string> = {
  status: "สถานะ",
  due_date: "กำหนดแล้วเสร็จ",
  text: "ข้อความมติ",
  assignee_ids: "ผู้รับผิดชอบ",
};

function renderValue(field: string, value: string) {
  if (field === "status") return STATUS_LABEL_TH[value as ResolutionStatus] ?? value;
  if (field === "due_date") return value ? formatThaiDate(value, true) : "-";
  if (value.length > 40) return `${value.slice(0, 40)}…`;
  return value || "-";
}

function Info({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-[11.5px] font-medium uppercase tracking-wide text-ink-4">{label}</p>
      <div className="mt-1 text-[13.5px] text-ink">{children}</div>
    </div>
  );
}

function SectionTitle({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <h3 className="flex items-center gap-2 text-[13px] font-semibold text-ink">
      <span className="text-ink-3">{icon}</span>
      {children}
    </h3>
  );
}

/* ── แก้ไขมติ ─────────────────────────────────────────────────────────── */

export function EditResolutionModal({
  open,
  onClose,
  resolution,
}: {
  open: boolean;
  onClose: () => void;
  resolution: Resolution;
}) {
  const t = useT();
  const { db } = useApp();
  const [text, setText] = useState(resolution.text);
  const [due, setDue] = useState(resolution.due_date ?? "");
  const [assignees, setAssignees] = useState<Uuid[]>(resolution.assignee_ids);
  const [reason, setReason] = useState("");

  const dirty =
    text !== resolution.text ||
    due !== (resolution.due_date ?? "") ||
    JSON.stringify(assignees) !== JSON.stringify(resolution.assignee_ids);

  const postponing = useMemo(
    () => Boolean(resolution.due_date && due && due > resolution.due_date),
    [due, resolution.due_date],
  );

  const submit = () => {
    updateResolution(
      resolution.id,
      { text, due_date: due || null, assignee_ids: assignees },
      reason.trim() || "แก้ไขด้วยผู้ใช้",
    );
    onClose();
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t.pick("แก้ไขมติ", "Edit resolution")}
      desc={t.pick("ทุกการแก้ไขถูกบันทึกเป็นประวัติ พร้อมผู้แก้และเหตุผล", "Every change is recorded with author and reason.")}
      width="max-w-2xl"
      footer={
        <>
          <Button onClick={onClose}>{t("cancel")}</Button>
          <Button variant="primary" onClick={submit} disabled={!dirty}>
            {t("save")}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label={t.pick("ข้อความมติ", "Resolution text")}>
          <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={4} />
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label={t("dueDate")}
            hint={postponing ? "⚑ การเลื่อนกำหนดจะถูกนับเป็นการเลื่อนซ้ำ 1 ครั้ง" : undefined}
          >
            <Input type="date" value={due} onChange={(e) => setDue(e.target.value)} />
          </Field>
          <Field label={t.pick("กำหนดเดิม", "Original due date")}>
            <Input value={resolution.original_due_date ?? "-"} disabled className="tnum" />
          </Field>
        </div>

        <Field label={t("assignee")}>
          <div className="max-h-40 space-y-0.5 overflow-y-auto rounded-[var(--radius)] border border-line p-2">
            {db.people.map((p) => (
              <label key={p.id} className="flex cursor-pointer items-center gap-2.5 rounded px-2 py-1.5 hover:bg-sunken">
                <input
                  type="checkbox"
                  checked={assignees.includes(p.id)}
                  onChange={(e) =>
                    setAssignees((prev) => (e.target.checked ? [...prev, p.id] : prev.filter((id) => id !== p.id)))
                  }
                  className="h-4 w-4 accent-[var(--brand)]"
                />
                <span className="text-[13px] text-ink">{p.full_name}</span>
                {p.is_department && <Badge tone="seal">{t.pick("หน่วยงาน", "Dept")}</Badge>}
              </label>
            ))}
          </div>
        </Field>

        <Field label={`${t("reason")} (${t("optional")})`}>
          <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="เช่น ที่ประชุมอนุมัติให้ขยายเวลา" />
        </Field>
      </div>
    </Modal>
  );
}

/* ── เปลี่ยนสถานะ ─────────────────────────────────────────────────────── */

export function StatusChangeModal({
  open,
  onClose,
  resolution,
  target,
  meetingId = null,
}: {
  open: boolean;
  onClose: () => void;
  resolution: Resolution;
  target: ResolutionStatus | null;
  meetingId?: Uuid | null;
}) {
  const t = useT();
  const { db } = useApp();
  const [reason, setReason] = useState("");
  const [linkMeeting, setLinkMeeting] = useState<string>(meetingId ?? "");

  if (!target) return null;
  const closing = target === "done" || target === "cancelled";

  const submit = () => {
    changeResolutionStatus(resolution.id, target, reason.trim() || STATUS_LABEL_TH[target], {
      meeting_id: linkMeeting || null,
    });
    setReason("");
    onClose();
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`${t("changeStatus")} → ${STATUS_LABEL_TH[target]}`}
      desc={resolution.ref_no}
      footer={
        <>
          <Button onClick={onClose}>{t("cancel")}</Button>
          <Button variant={closing ? "primary" : "secondary"} onClick={submit} disabled={closing && !reason.trim()}>
            {t("confirm")}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {closing && (
          <div className="flex items-start gap-2.5 rounded-[var(--radius)] border border-[color-mix(in_srgb,var(--warn)_35%,transparent)] bg-[var(--warn-bg)] p-3">
            <AlertTriangle size={15} className="mt-0.5 shrink-0 text-[var(--warn)]" />
            <p className="text-[12.5px] leading-relaxed text-ink-2">
              {t.pick(
                "การปิดมติต้องมีเหตุผลกำกับเสมอ ระบบไม่ปิดมติเองโดยไม่มีคนยืนยัน เพราะการปิดผิดร้ายแรงกว่าการปิดช้า",
                "Closing always requires a reason. The system never closes a resolution on its own — a false close is far worse than a late one.",
              )}
            </p>
          </div>
        )}

        <div className="rounded-[var(--radius)] bg-sunken p-3">
          <p className="text-[13px] leading-relaxed text-ink-2">“{resolution.text}”</p>
        </div>

        <Field label={`${t("reason")}${closing ? "" : ` (${t("optional")})`}`}>
          <Textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            placeholder={
              target === "done"
                ? "เช่น ที่ประชุมครั้งที่ 6/2569 รับทราบว่าดำเนินการแล้วเสร็จ ตามคำสั่งที่ 118/2569"
                : "ระบุเหตุผลของการเปลี่ยนสถานะ"
            }
            autoFocus
          />
        </Field>

        <Field label={t.pick("การประชุมที่เป็นต้นเหตุ", "Source meeting")} hint={t.pick("ใช้เป็นหลักฐานอ้างอิงในไทม์ไลน์", "Recorded as evidence in the timeline")}>
          <Select value={linkMeeting} onChange={(e) => setLinkMeeting(e.target.value)}>
            <option value="">{t.pick("— ไม่ระบุ —", "— none —")}</option>
            {db.meetings
              .filter((m) => m.series_id === resolution.series_id)
              .sort((a, b) => b.sequence_no - a.sequence_no)
              .map((m) => (
                <option key={m.id} value={m.id}>
                  ครั้งที่ {m.sequence_no}/{m.fiscal_year} · {formatThaiDate(m.meeting_date, true)}
                </option>
              ))}
          </Select>
        </Field>
      </div>
    </Modal>
  );
}

/* ── แถวมติแบบย่อ ใช้ในลิสต์และแดชบอร์ด ─────────────────────────────── */

export function ResolutionRow({
  resolution,
  onOpen,
  compact = false,
}: {
  resolution: Resolution;
  onOpen: () => void;
  compact?: boolean;
}) {
  const t = useT();
  const { db } = useApp();
  const od = overdueDays(resolution);
  const origin = db.meetings.find((m) => m.id === resolution.origin_meeting_id);

  return (
    <button
      onClick={onOpen}
      className="group flex w-full items-start gap-3 border-b border-line px-4 py-3.5 text-left transition-colors last:border-b-0 hover:bg-surface-2 cursor-pointer"
    >
      <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full" style={{ background: statusColor(resolution.status) }} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-mono text-[11.5px] text-ink-3">{resolution.ref_no}</span>
          {od > 0 && (
            <Badge tone="danger">
              <AlertTriangle size={10} />
              {t("overdueBy")} {od} {t("days")}
            </Badge>
          )}
          {resolution.postpone_count >= 3 && <Badge tone="warn">⚑ {resolution.postpone_count} {t("times")}</Badge>}
          {resolution.extraction_confidence < 0.75 && (
            <Badge tone="warn">
              <Quote size={10} /> {t("lowConfidence")}
            </Badge>
          )}
        </div>
        <p className={cn("mt-1 leading-relaxed text-ink", compact ? "line-clamp-2 text-[13px]" : "text-[13.5px]")}>
          {resolution.text}
        </p>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-ink-3">
          <span className="inline-flex items-center gap-1">
            <FileText size={11} />
            {origin ? `ครั้งที่ ${origin.sequence_no}/${origin.fiscal_year}` : "-"}
          </span>
          <span>{assigneeNames(db, resolution).map((p) => p.full_name).join(", ") || "-"}</span>
          {resolution.due_date && (
            <span className={cn("tnum", od > 0 && "font-medium text-[var(--danger)]")}>
              {t("dueDate")} {formatThaiDate(resolution.due_date, true)}
            </span>
          )}
        </div>
      </div>
      <div className="shrink-0 pt-0.5">
        <StatusPill status={resolution.status} label={STATUS_LABEL_TH[resolution.status]} size="sm" />
      </div>
    </button>
  );
}
