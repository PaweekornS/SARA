"use client";

/**
 * M9 — หน้าตรวจทานหลังประมวลผลเสร็จ
 * หลักการ: ทุกอย่างที่ AI ผลิตต้องแก้ได้ และต้องมีคนกดยืนยันก่อนมีผล
 * จุดที่ระบบไม่มั่นใจถูกดันขึ้นบนสุดเสมอ เพื่อให้คนตรวจโฟกัสถูกที่ (FR-M9-05)
 */

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  BadgeCheck,
  CheckCircle2,
  ChevronRight,
  Clock,
  Download,
  ListChecks,
  MessageSquareQuote,
  Mic,
  ShieldQuestion,
  Sparkles,
  UserCheck,
} from "lucide-react";
import { PageBody, PageHeader } from "@/components/app-shell";
import { PipelineStatus } from "@/components/meeting-ingest";
import { ResolutionDrawer, ResolutionRow } from "@/components/resolution-detail";
import {
  Badge,
  Button,
  Card,
  CardHead,
  ConfidenceBar,
  EmptyState,
  EvidenceQuote,
  Field,
  Input,
  Modal,
  Segmented,
  Select,
  StatusPill,
  Textarea,
  cn,
} from "@/components/ui";
import { useT } from "@/lib/i18n";
import * as api from "@/lib/api";
import {
  STATUS_LABEL_TH,
  assignSpeaker,
  decideProposal,
  formatThaiDate,
  formatTimecode,
  personName,
  retryMeeting,
  useApp,
} from "@/lib/store";
import { buildMinutesHtml, downloadDoc } from "@/lib/export-doc";
import type { Proposal, Uuid } from "@/lib/types";

type Tab = "proposals" | "speakers" | "transcript" | "resolutions";

const KIND_ORDER: Record<Proposal["kind"], number> = {
  status_change: 0,
  supersede: 1,
  new_resolution: 2,
  speaker_identity: 3,
};

export default function MeetingReviewPage() {
  const t = useT();
  const router = useRouter();
  const { db } = useApp();
  const { id: seriesId, mid } = useParams<{ id: string; mid: string }>();

  const meeting = db.meetings.find((m) => m.id === mid);
  const [tab, setTab] = useState<Tab>("proposals");
  const [openRes, setOpenRes] = useState<string | null>(null);
  const [approveOpen, setApproveOpen] = useState(false);

  if (!meeting) {
    return (
      <PageBody>
        <Card>
          <EmptyState title={t.pick("ไม่พบการประชุมนี้", "Meeting not found")} />
        </Card>
      </PageBody>
    );
  }

  const proposals = db.proposals.filter((p) => p.meeting_id === meeting.id);
  const pending = proposals.filter((p) => p.decision === "pending");
  const segments = db.segments.filter((s) => s.meeting_id === meeting.id).sort((a, b) => a.start_ms - b.start_ms);
  const speakerLabels = [...new Set(segments.map((s) => s.speaker_label))].sort();
  const unmapped = speakerLabels.filter((l) => !segments.find((s) => s.speaker_label === l)?.person_id);
  const created = db.resolutions.filter((r) => r.origin_meeting_id === meeting.id);
  const closed = db.resolutions.filter((r) => r.closed_meeting_id === meeting.id);

  const processing = meeting.status === "processing";
  const failed = meeting.status === "failed";
  const canApprove = !processing && !failed && pending.length === 0 && unmapped.length === 0;
  const approved = meeting.status === "approved" || meeting.status === "distributed";

  /* ปุ่มที่กดไม่ได้โดยไม่บอกเหตุผล คือทางตัน — บอกให้ชัดว่าเหลืออะไรและกดไปทำต่อได้ที่ไหน */
  const blockers: Array<{ label: string; tab: Tab }> = [];
  if (pending.length > 0)
    blockers.push({
      label: t.pick(`ตรวจข้อเสนอที่เหลืออีก ${pending.length} รายการ`, `${pending.length} proposals left to review`),
      tab: "proposals",
    });
  if (unmapped.length > 0)
    blockers.push({
      label: t.pick(`ระบุตัวผู้พูดอีก ${unmapped.length} คน`, `${unmapped.length} speakers unidentified`),
      tab: "speakers",
    });

  return (
    <>
      <PageHeader
        eyebrow={
          <Link href={`/series/${seriesId}/meetings`} className="inline-flex items-center gap-1.5 hover:text-brand">
            <ArrowLeft size={13} /> {t("navMeetings")}
          </Link>
        }
        title={`${t.pick("การประชุมครั้งที่", "Meeting")} ${meeting.sequence_no}/${meeting.fiscal_year}`}
        desc={
          <span className="tnum">
            {formatThaiDate(meeting.meeting_date)}
            {approved && meeting.approved_by && ` · ${t.pick("รับรองโดย", "approved by")} ${meeting.approved_by}`}
          </span>
        }
        actions={
          <>
            <Button
              icon={<Download size={15} />}
              onClick={() =>
                downloadDoc(`รายงานการประชุมครั้งที่-${meeting.sequence_no}-${meeting.fiscal_year}`, buildMinutesHtml(db, meeting))
              }
              disabled={processing || failed}
            >
              {t.pick("รายงานการประชุม .docx", "Minutes .docx")}
            </Button>
            {approved ? (
              <Badge tone="ok" className="h-10 px-3 text-[13px]">
                <BadgeCheck size={15} /> {t("approved")}
              </Badge>
            ) : (
              <Button variant="primary" icon={<CheckCircle2 size={15} />} disabled={!canApprove} onClick={() => setApproveOpen(true)}>
                {t("approve")}
              </Button>
            )}
          </>
        }
        tabs={
          !processing &&
          !failed && (
            <Segmented
              value={tab}
              onChange={setTab}
              options={[
                { value: "proposals", label: t.pick("สิ่งที่ระบบเสนอ", "Proposals"), count: pending.length },
                { value: "speakers", label: t("speakers"), count: unmapped.length || undefined },
                { value: "transcript", label: t("transcript"), count: segments.length },
                { value: "resolutions", label: t.pick("มติจากการประชุมนี้", "Resolutions"), count: created.length },
              ]}
            />
          )
        }
      />

      <PageBody className="space-y-5">
        {/* เหลืออะไรก่อนรับรองได้ — กดที่ป้ายเพื่อกระโดดไปทำต่อได้เลย */}
        {!processing && !failed && !approved && blockers.length > 0 && (
          <div className="flex flex-wrap items-center gap-2.5 rounded-[var(--radius)] border border-line bg-surface px-4 py-3">
            <span className="text-[13px] text-ink-2">
              {t.pick(`เหลืออีก ${blockers.length} อย่างก่อนรับรองรายงานได้:`, "Before you can approve:")}
            </span>
            {blockers.map((b) => (
              <button
                key={b.tab}
                onClick={() => setTab(b.tab)}
                className="inline-flex items-center gap-1.5 rounded-full bg-[var(--warn-bg)] px-3 py-1 text-[12.5px] font-medium text-[var(--warn)] hover:brightness-95 cursor-pointer"
              >
                {b.label}
                <ChevronRight size={13} />
              </button>
            ))}
          </div>
        )}

        {/* กำลังประมวลผล / ล้มเหลว */}
        {(processing || failed) && (
          <Card>
            <CardHead
              title={processing ? t("processing") : t.pick("ประมวลผลไม่สำเร็จ", "Processing failed")}
              desc={
                processing
                  ? t.pick(
                      "ระบบดึงมติค้างของชุดการประชุมนี้ไปเป็นบริบทให้แล้ว จะแจ้งเมื่อพร้อมให้ตรวจทาน",
                      "Open resolutions from this series are loaded as context.",
                    )
                  : undefined
              }
            />
            <div className="px-5 py-5">
              <PipelineStatus meeting={meeting} onRetry={() => retryMeeting(meeting.id)} />
            </div>
          </Card>
        )}

        {!processing && !failed && (
          <>
            {/* สรุปผลการจับคู่ข้ามการประชุม — ของขึ้นโต๊ะที่คนดูเดโมต้องเห็นก่อน */}
            {tab === "proposals" && (
              <>
                <div className="grid gap-3 sm:grid-cols-3">
                  <SummaryTile
                    icon={<Sparkles size={15} />}
                    label={t.pick("มติใหม่ที่สกัดได้", "New resolutions")}
                    value={proposals.filter((p) => p.kind === "new_resolution").length}
                  />
                  <SummaryTile
                    icon={<ListChecks size={15} />}
                    label={t.pick("จับคู่กับมติเดิมได้", "Matched to existing")}
                    value={proposals.filter((p) => p.kind === "status_change").length}
                    tone="var(--ok)"
                  />
                  <SummaryTile
                    icon={<ShieldQuestion size={15} />}
                    label={t.pick("จุดที่ระบบไม่มั่นใจ", "Low-confidence items")}
                    value={proposals.filter((p) => p.confidence < 0.75).length}
                    tone="var(--warn)"
                  />
                </div>

                <Card className="overflow-hidden">
                  <CardHead
                    title={t("proposalsTitle")}
                    desc={t.pick(
                      "ระบบเสนอได้ แต่ไม่เปลี่ยนอะไรเองทั้งสิ้น การปิดมติต้องมาจากปุ่มที่ท่านกดเท่านั้น",
                      "The system proposes; nothing changes until you accept.",
                    )}
                    right={
                      pending.length === 0 ? (
                        <Badge tone="ok">
                          <CheckCircle2 size={12} /> {t.pick("ตรวจครบแล้ว", "All reviewed")}
                        </Badge>
                      ) : (
                        <Badge tone="warn">
                          {pending.length} {t.pick("รายการรอ", "pending")}
                        </Badge>
                      )
                    }
                  />
                  {proposals.length === 0 ? (
                    <EmptyState
                      icon={<Sparkles size={20} />}
                      title={t.pick("ไม่มีข้อเสนอจากระบบ", "No proposals")}
                      desc={t.pick("ระบบไม่พบมติหรือการรายงานผลในการประชุมครั้งนี้", "Nothing was extracted from this meeting.")}
                    />
                  ) : (
                    <div className="divide-y divide-[var(--line)]">
                      {[...proposals]
                        /* ยังไม่ตัดสินขึ้นก่อน → จับคู่มติเดิมก่อนมติใหม่ก่อนระบุผู้พูด → ในกลุ่มเดียวกันเอาที่ไม่มั่นใจขึ้นก่อน */
                        .sort(
                          (a, b) =>
                            Number(a.decision !== "pending") - Number(b.decision !== "pending") ||
                            KIND_ORDER[a.kind] - KIND_ORDER[b.kind] ||
                            a.confidence - b.confidence,
                        )
                        .map((p) => (
                          <ProposalCard key={p.id} proposal={p} onOpenResolution={setOpenRes} />
                        ))}
                    </div>
                  )}
                </Card>
              </>
            )}

            {tab === "speakers" && <SpeakerMapping meetingId={meeting.id} />}

            {tab === "transcript" && (
              <Card className="overflow-hidden">
                <CardHead
                  title={t("transcript")}
                  desc={t.pick(
                    "ทุกท่อนเก็บ timestamp ไว้ เพื่อให้ย้อนกลับไปตรวจหลักฐานของมติได้เสมอ",
                    "Every segment keeps its timestamp so any resolution can be traced back.",
                  )}
                />
                <div className="divide-y divide-[var(--line)]">
                  {segments.map((s) => (
                    <div key={s.id} className="flex gap-4 px-5 py-3.5">
                      <div className="w-[92px] shrink-0">
                        <p className="tnum font-mono text-[12px] text-ink-3">{formatTimecode(s.start_ms)}</p>
                        <p
                          className={cn(
                            "mt-1 truncate text-[12px] font-medium",
                            s.person_id ? "text-brand" : "text-[var(--warn)]",
                          )}
                          title={s.person_id ? personName(db, s.person_id) : s.speaker_label}
                        >
                          {s.person_id ? personName(db, s.person_id) : s.speaker_label}
                        </p>
                      </div>
                      <p className="flex-1 text-[13.5px] leading-relaxed text-ink-2">{s.text}</p>
                      <div className="hidden shrink-0 pt-0.5 sm:block">
                        <ConfidenceBar value={s.confidence} showLabel={false} />
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {tab === "resolutions" && (
              <div className="space-y-5">
                <Card className="overflow-hidden">
                  <CardHead title={t.pick("มติที่เกิดในการประชุมครั้งนี้", "Resolutions created here")} />
                  {created.length === 0 ? (
                    <EmptyState icon={<ListChecks size={20} />} title={t.pick("ยังไม่มีมติที่ยืนยันแล้ว", "None yet")} />
                  ) : (
                    created.map((r) => <ResolutionRow key={r.id} resolution={r} onOpen={() => setOpenRes(r.id)} />)
                  )}
                </Card>

                <Card className="overflow-hidden">
                  <CardHead
                    title={t.pick("มติเดิมที่ถูกปิดจากการประชุมครั้งนี้", "Older resolutions closed here")}
                    desc={t.pick("นี่คือส่วนที่พิสูจน์ว่าระบบจำเรื่องค้างข้ามการประชุมได้จริง", "Proof the system remembers across meetings.")}
                  />
                  {closed.length === 0 ? (
                    <EmptyState icon={<CheckCircle2 size={20} />} title={t.pick("ยังไม่มีมติที่ถูกปิด", "None closed")} />
                  ) : (
                    closed.map((r) => <ResolutionRow key={r.id} resolution={r} onOpen={() => setOpenRes(r.id)} />)
                  )}
                </Card>
              </div>
            )}
          </>
        )}
      </PageBody>

      <ResolutionDrawer resolutionId={openRes} onClose={() => setOpenRes(null)} />

      <Modal
        open={approveOpen}
        onClose={() => setApproveOpen(false)}
        title={t("approve")}
        desc={`${t.pick("ครั้งที่", "Meeting")} ${meeting.sequence_no}/${meeting.fiscal_year}`}
        footer={
          <>
            <Button onClick={() => setApproveOpen(false)}>{t("cancel")}</Button>
            <Button
              variant="primary"
              onClick={async () => {
                await api.approveMeeting(meeting.id);
                setApproveOpen(false);
                router.push(`/series/${seriesId}/agenda`);
              }}
            >
              {t("confirm")}
            </Button>
          </>
        }
      >
        <ul className="space-y-2 text-[13px] leading-relaxed text-ink-2">
          <li>• {t.pick("มติที่รอรับรองในการประชุมนี้จะเปลี่ยนเป็น “รับรองแล้ว” อัตโนมัติ", "Proposed resolutions become confirmed.")}</li>
          <li>• {t.pick("ระบบจะปลดล็อกการสร้างร่างวาระครั้งถัดไปและการส่งอีเมล", "Agenda generation and email dispatch unlock.")}</li>
          <li>• {t.pick("การรับรองถูกบันทึกในบันทึกการใช้งานพร้อมชื่อผู้รับรอง", "The approval is written to the audit log.")}</li>
        </ul>
      </Modal>
    </>
  );
}

function SummaryTile({ icon, label, value, tone }: { icon: React.ReactNode; label: string; value: number; tone?: string }) {
  return (
    <Card className="flex items-center gap-3 p-4">
      <span
        className="flex h-9 w-9 items-center justify-center rounded-full"
        style={{ background: "var(--sunken, var(--surface-sunken))", color: tone ?? "var(--brand)" }}
      >
        {icon}
      </span>
      <div>
        <p className="tnum text-[20px] font-semibold leading-none" style={{ color: tone ?? "var(--ink)" }}>
          {value}
        </p>
        <p className="mt-1 text-[12px] text-ink-3">{label}</p>
      </div>
    </Card>
  );
}

/* ── การ์ดข้อเสนอ ─────────────────────────────────────────────────────── */

function ProposalCard({ proposal, onOpenResolution }: { proposal: Proposal; onOpenResolution: (id: string) => void }) {
  const t = useT();
  const { db } = useApp();
  const target = db.resolutions.find((r) => r.id === proposal.resolution_id);
  const decided = proposal.decision !== "pending";

  /* ฟอร์มแก้ไขก่อนยอมรับ — ทุกอย่างที่ AI ผลิตต้องแก้ได้ (FR-M9-02) */
  const [text, setText] = useState(proposal.title);
  const [due, setDue] = useState("");
  const [assignees, setAssignees] = useState<Uuid[]>([]);
  /* ตั้งใจไม่เลือกล่วงหน้า — ระบบบอกว่าไม่เดา ก็ต้องไม่เดาจริง ๆ ในช่องนี้ด้วย */
  const [personId, setPersonId] = useState<string>("");
  const [saveAlias, setSaveAlias] = useState(true);

  /* เบาะแสจากคำเรียกในห้องประชุม — alias ที่เคยยืนยันแล้วและโผล่ในช่วงเวลาใกล้กัน */
  const aliasHint = (() => {
    if (proposal.kind !== "speaker_identity") return null;
    const segs = db.segments.filter((s) => s.meeting_id === proposal.meeting_id);
    for (const a of db.aliases) {
      if (!proposal.candidate_person_ids?.includes(a.person_id)) continue;
      if (segs.some((s) => s.text.includes(a.alias))) {
        return { alias: a.alias, person_id: a.person_id, confidence: a.confidence };
      }
    }
    return null;
  })();

  const lowConfidence = proposal.confidence < 0.75;

  return (
    <div className={cn("px-5 py-4", decided && "bg-surface-2 opacity-70")}>
      <div className="flex flex-wrap items-center gap-2">
        <KindBadge kind={proposal.kind} />
        {lowConfidence && !decided && (
          <Badge tone="warn">
            <ShieldQuestion size={11} /> {t("lowConfidence")}
          </Badge>
        )}
        <span className="ml-auto flex items-center gap-2">
          <span className="text-[11.5px] text-ink-3">{t("confidence")}</span>
          <ConfidenceBar value={proposal.confidence} />
        </span>
      </div>

      {/* มติเดิมที่ถูกจับคู่ */}
      {target && (
        <button
          onClick={() => onOpenResolution(target.id)}
          className="mt-3 block w-full rounded-[var(--radius)] border border-line bg-surface-2 px-3.5 py-3 text-left hover:border-brand cursor-pointer"
        >
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-mono text-[11.5px] text-brand">{target.ref_no}</span>
            <StatusPill status={target.status} label={STATUS_LABEL_TH[target.status]} size="sm" />
            {proposal.proposed_status && (
              <>
                <span className="text-ink-4">→</span>
                <StatusPill status={proposal.proposed_status} label={STATUS_LABEL_TH[proposal.proposed_status]} size="sm" />
              </>
            )}
          </div>
          <p className="mt-1.5 text-[13px] leading-relaxed text-ink-2">{target.text}</p>
        </button>
      )}

      {/* ข้อเสนอมติใหม่ — แก้ได้ก่อนยอมรับ */}
      {proposal.kind === "new_resolution" && !decided && (
        <div className="mt-3 space-y-3">
          <Field label={t.pick("ข้อความมติที่จะบันทึก", "Resolution text")}>
            <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} />
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t("assignee")}>
              <Select
                value={assignees[0] ?? ""}
                onChange={(e) => setAssignees(e.target.value ? [e.target.value] : [])}
              >
                <option value="">{t.pick("— เลือกผู้รับผิดชอบ —", "— select —")}</option>
                {db.people.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.full_name}
                    {p.is_department ? " (หน่วยงาน)" : ""}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label={t("dueDate")}>
              <Input type="date" value={due} onChange={(e) => setDue(e.target.value)} />
            </Field>
          </div>
        </div>
      )}
      {proposal.kind === "new_resolution" && decided && (
        <p className="mt-3 text-[13.5px] leading-relaxed text-ink-2">{proposal.title}</p>
      )}

      {/* ระบุตัวผู้พูด */}
      {proposal.kind === "speaker_identity" && !decided && (
        <div className="mt-3 space-y-3">
          <p className="text-[13.5px] font-medium text-ink">
            {t.pick("ระบบไม่มั่นใจว่า", "Unsure who")} <span className="font-mono">{proposal.speaker_label}</span>{" "}
            {t.pick("คือใคร จึงไม่เดาให้", "is — so it will not guess")}
          </p>
          {aliasHint && (
            <div className="flex items-start gap-2.5 rounded-[var(--radius)] bg-[var(--brand-soft)] px-3.5 py-2.5">
              <UserCheck size={15} className="mt-0.5 shrink-0 text-brand" />
              <p className="text-[12.5px] leading-relaxed text-ink-2">
                {t.pick("ในที่ประชุมมีการเรียกว่า", "Heard the nickname")} <b>“{aliasHint.alias}”</b>{" "}
                {t.pick("ซึ่งเคยยืนยันไว้ว่าหมายถึง", "previously confirmed as")}{" "}
                <b>{personName(db, aliasHint.person_id)}</b>
              </p>
            </div>
          )}
          <Field label={t.pick("ผู้พูดคนนี้คือ", "This speaker is")}>
            <Select value={personId} onChange={(e) => setPersonId(e.target.value)}>
              <option value="">{t.pick("— เลือกบุคคล —", "— select —")}</option>
              {db.people
                .filter((p) => !p.is_department)
                .map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.full_name} · {p.position}
                  </option>
                ))}
            </Select>
          </Field>
          {aliasHint && (
            <label className="flex cursor-pointer items-center gap-2.5 text-[12.5px] text-ink-2">
              <input
                type="checkbox"
                checked={saveAlias}
                onChange={(e) => setSaveAlias(e.target.checked)}
                className="h-4 w-4 accent-[var(--brand)]"
              />
              {t.pick(`จำไว้ว่า “${aliasHint.alias}” หมายถึงคนนี้ จะได้ไม่ต้องถามอีก`, `Remember “${aliasHint.alias}” permanently`)}
            </label>
          )}
        </div>
      )}

      {/* หลักฐาน */}
      <EvidenceQuote
        className="mt-3"
        text={proposal.evidence_text}
        meta={
          <>
            <span className="inline-flex items-center gap-1">
              <Clock size={11} />
              <span className="tnum font-mono">{formatTimecode(proposal.evidence_start_ms)}</span>
            </span>
            <span className="inline-flex items-center gap-1">
              <MessageSquareQuote size={11} />
              {t("evidence")}
            </span>
          </>
        }
      />

      {/* ปุ่มตัดสิน */}
      <div className="mt-3.5 flex flex-wrap items-center gap-2">
        {decided ? (
          <Badge tone={proposal.decision === "accepted" ? "ok" : "neutral"}>
            {proposal.decision === "accepted" ? `✓ ${t.pick("ยืนยันแล้ว", "Accepted")}` : `✕ ${t.pick("ปฏิเสธแล้ว", "Rejected")}`}
          </Badge>
        ) : (
          <>
            <Button
              variant="primary"
              size="sm"
              onClick={() =>
                decideProposal(proposal.id, "accepted", {
                  text,
                  assignee_ids: assignees,
                  due_date: due || null,
                  person_id: personId || null,
                  save_alias: saveAlias && aliasHint ? aliasHint.alias : undefined,
                })
              }
              disabled={proposal.kind === "speaker_identity" && !personId}
            >
              {proposal.proposed_status === "done"
                ? t.pick("ยืนยันปิดมติ", "Confirm close")
                : t("accept")}
            </Button>
            <Button size="sm" onClick={() => decideProposal(proposal.id, "rejected")}>
              {t("reject")}
            </Button>
            {proposal.proposed_status === "done" && (
              <span className="text-[12px] text-ink-3">
                {t.pick("ระบบเสนอเท่านั้น — มติจะปิดก็ต่อเมื่อท่านกดปุ่มนี้", "Proposal only — closes when you press this")}
              </span>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function KindBadge({ kind }: { kind: Proposal["kind"] }) {
  const t = useT();
  const map: Record<Proposal["kind"], { label: string; tone: "brand" | "ok" | "warn" | "seal" }> = {
    status_change: { label: t.pick("จับคู่มติเดิม", "Matched existing"), tone: "ok" },
    new_resolution: { label: t.pick("มติใหม่", "New resolution"), tone: "brand" },
    speaker_identity: { label: t.pick("ระบุตัวผู้พูด", "Speaker identity"), tone: "warn" },
    supersede: { label: t.pick("แทนที่มติเดิม", "Supersede"), tone: "seal" },
  };
  const m = map[kind];
  return <Badge tone={m.tone}>{m.label}</Badge>;
}

/* ── การจับคู่ผู้พูดกับบุคคลจริง (FR-M2-07) ──────────────────────────── */

function SpeakerMapping({ meetingId }: { meetingId: string }) {
  const t = useT();
  const { db } = useApp();
  const segments = db.segments.filter((s) => s.meeting_id === meetingId);
  const labels = [...new Set(segments.map((s) => s.speaker_label))].sort();

  return (
    <Card className="overflow-hidden">
      <CardHead
        title={t.pick("จับคู่ผู้พูดกับบุคคลในทะเบียน", "Map speakers to registered people")}
        desc={t.pick(
          "ทำครั้งเดียว ระบบจำ voice profile ต่อชุดการประชุม ครั้งหน้าจะเดาให้ล่วงหน้าและถามเฉพาะที่ไม่มั่นใจ",
          "Map once — the voice profile is remembered for this series.",
        )}
      />
      <div className="divide-y divide-[var(--line)]">
        {labels.map((label) => {
          const segs = segments.filter((s) => s.speaker_label === label);
          const personId = segs[0]?.person_id ?? "";
          const totalMs = segs.reduce((sum, s) => sum + (s.end_ms - s.start_ms), 0);
          return (
            <div key={label} className="flex flex-wrap items-center gap-4 px-5 py-4">
              <div className="flex min-w-[190px] items-center gap-3">
                <span
                  className={cn(
                    "flex h-9 w-9 items-center justify-center rounded-full",
                    personId ? "bg-[var(--brand-soft)] text-brand" : "bg-[var(--warn-bg)] text-[var(--warn)]",
                  )}
                >
                  <Mic size={16} />
                </span>
                <div>
                  <p className="font-mono text-[13px] font-medium text-ink">{label}</p>
                  <p className="tnum text-[11.5px] text-ink-3">
                    {segs.length} {t.pick("ท่อน", "segments")} · {formatTimecode(totalMs)}
                  </p>
                </div>
              </div>

              <p className="hidden min-w-0 flex-1 truncate text-[12.5px] italic text-ink-3 lg:block">
                “{segs[0]?.text}”
              </p>

              <div className="w-[280px]">
                <Select value={personId ?? ""} onChange={(e) => assignSpeaker(meetingId, label, e.target.value || null)}>
                  <option value="">{t.pick("— ยังไม่ระบุ —", "— unassigned —")}</option>
                  {db.people
                    .filter((p) => !p.is_department)
                    .map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.full_name} · {p.position}
                      </option>
                    ))}
                </Select>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
