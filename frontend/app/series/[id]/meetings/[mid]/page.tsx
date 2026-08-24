"use client";

/**
 * หน้ารายละเอียดการประชุม — หน้าเดียวสรุปเนื้อหาสำคัญและมติจากการประชุม
 * พร้อมฟังก์ชันให้ผู้ใช้ระบุ/กำกับฝ่ายที่รับผิดชอบในแต่ละมติ (User Annotation)
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  BadgeCheck,
  Building2,
  Calendar,
  Check,
  CheckCircle2,
  Download,
  FileText,
  ListChecks,
  Sparkles,
  UserCheck,
  Users,
  X,
} from "lucide-react";
import { PageBody, PageHeader } from "@/components/app-shell";
import { PipelineStatus, ReuploadMeetingModal } from "@/components/meeting-ingest";
import { ResolutionDrawer, ResolutionRow } from "@/components/resolution-detail";
import {
  Badge,
  Button,
  Card,
  CardHead,
  EmptyState,
  Field,
  Modal,
  Select,
  StatTile,
  cn,
} from "@/components/ui";
import { useT } from "@/lib/i18n";
import * as api from "@/lib/api";
import {
  LIVE,
  assigneeNames,
  formatThaiDate,
  overdueDays,
  pollMeeting,
  updateResolution,
  useApp,
} from "@/lib/store";
import { buildMinutesHtml, downloadDoc } from "@/lib/export-doc";
import type { Resolution, Uuid } from "@/lib/types";

export default function MeetingReviewPage() {
  const t = useT();
  const router = useRouter();
  const { db } = useApp();
  const { id: seriesId, mid } = useParams<{ id: string; mid: string }>();

  const meeting = db.meetings.find((m) => m.id === mid);
  const series = db.series.find((s) => s.id === seriesId);
  const [openRes, setOpenRes] = useState<string | null>(null);
  const [annotateRes, setAnnotateRes] = useState<Resolution | null>(null);
  const [approveOpen, setApproveOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);

  useEffect(() => {
    if (meeting && meeting.status === "processing" && LIVE) {
      pollMeeting(meeting.id);
    }
  }, [meeting?.id, meeting?.status]);

  if (!meeting) {
    return (
      <PageBody>
        <Card>
          <EmptyState title={t.pick("ไม่พบการประชุมนี้", "Meeting not found")} />
        </Card>
      </PageBody>
    );
  }

  const segments = db.segments
    .filter((s) => s.meeting_id === meeting.id)
    .sort((a, b) => a.start_ms - b.start_ms);

  const speakerIds = [
    ...new Set(
      segments
        .map((s) => s.person_id)
        .filter((id): id is string => Boolean(id))
    ),
  ];
  const speakerPeople = db.people.filter((p) => speakerIds.includes(p.id));

  const created = db.resolutions.filter((r) => r.origin_meeting_id === meeting.id);
  const closed = db.resolutions.filter((r) => r.closed_meeting_id === meeting.id);
  const linked = db.links
    .filter((l) => l.meeting_id === meeting.id && l.link_type !== "created")
    .map((l) => db.resolutions.find((r) => r.id === l.resolution_id))
    .filter((r): r is Resolution => r != null && r.origin_meeting_id !== meeting.id);

  // รวมมติที่ถูกติดตาม/ปิดในการประชุมนี้โดยไม่ซ้ำ
  const followedUp = Array.from(new Set([...closed, ...linked]));

  const processing = meeting.status === "processing";
  const failed = meeting.status === "failed";
  const approved = meeting.status === "approved" || meeting.status === "distributed";

  const departments = db.people.filter((p) => p.is_department);

  return (
    <>
      <PageHeader
        eyebrow={
          <Link
            href={`/series/${seriesId}/meetings`}
            className="inline-flex items-center gap-1.5 hover:text-brand"
          >
            <ArrowLeft size={13} /> {t("navMeetings")}
          </Link>
        }
        title={`${t.pick("การประชุมครั้งที่", "Meeting")} ${meeting.sequence_no}/${meeting.fiscal_year}`}
        desc={
          <span className="tnum">
            {series ? `${series.name} · ` : ""}
            {formatThaiDate(meeting.meeting_date)}
            {approved && meeting.approved_by && ` · ${t.pick("รับรองโดย", "approved by")} ${meeting.approved_by}`}
          </span>
        }
        actions={
          <>
            {/* <Button
              icon={<Download size={15} />}
              onClick={() => {
                const url = api.minutesExportUrl(meeting.id);
                if (url) window.open(url, "_blank");
                else
                  downloadDoc(
                    `รายงานการประชุมครั้งที่-${meeting.sequence_no}-${meeting.fiscal_year}`,
                    buildMinutesHtml(db, meeting)
                  );
              }}
              disabled={processing || failed}
            >
              {t.pick("รายงานการประชุม .docx", "Minutes .docx")}
            </Button> */}
            {approved ? (
              <Badge tone="ok" className="h-10 px-3 text-[13px]">
                <BadgeCheck size={15} /> {t("approved")}
              </Badge>
            ) : (
              <Button
                variant="primary"
                icon={<CheckCircle2 size={15} />}
                disabled={processing || failed}
                onClick={() => setApproveOpen(true)}
              >
                {t("approve")}
              </Button>
            )}
          </>
        }
      />

      <PageBody className="space-y-5">
        {/* กำลังประมวลผล / ล้มเหลว */}
        {(processing || failed) && (
          <Card>
            <CardHead
              title={processing ? t("processing") : t.pick("ประมวลผลไม่สำเร็จ", "Processing failed")}
              desc={
                processing
                  ? t.pick(
                      "ระบบกำลังสรุปเนื้อหาและสกัดมติของการประชุมนี้...",
                      "Summarizing meeting content and extracting resolutions..."
                    )
                  : undefined
              }
            />
            <div className="px-5 py-5">
              <PipelineStatus meeting={meeting} onRetry={() => setUploadOpen(true)} />
            </div>
          </Card>
        )}

        {!processing && !failed && (
          <>
            {/* สถิติสรุปภาพรวมการประชุม */}
            <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatTile
                icon={<Calendar size={15} />}
                label={t.pick("วันที่ประชุม", "Meeting Date")}
                value={formatThaiDate(meeting.meeting_date, true)}
              />
              <StatTile
                icon={<Sparkles size={15} />}
                label={t.pick("มติใหม่ที่สกัดได้", "Extracted Resolutions")}
                value={created.length}
                tone="brand"
              />
              <StatTile
                icon={<ListChecks size={15} />}
                label={t.pick("มติเดิมที่ติดตาม/ปิด", "Followed-up / Closed")}
                value={followedUp.length}
                tone={followedUp.length > 0 ? "ok" : "neutral"}
              />
              <StatTile
                icon={<Users size={15} />}
                label={t.pick("ผู้เข้าร่วม/ผู้พูด", "Speakers")}
                value={speakerPeople.length || segments.length ? Math.max(speakerPeople.length, 1) : 0}
              />
            </section>

            {/* ส่วนที่ 1: สรุปสาระสำคัญของการประชุม */}
            <Card className="overflow-hidden">
              <CardHead
                title={t.pick("สรุปสาระสำคัญของการประชุม", "Meeting Executive Summary")}
                desc={t.pick(
                  `การประชุม ${series?.name ?? ""} ครั้งที่ ${meeting.sequence_no}/${meeting.fiscal_year}`,
                  `Summary of meeting ${meeting.sequence_no}/${meeting.fiscal_year}`
                )}
              />
              <div className="space-y-4 px-5 py-4">
                <div className="rounded-[var(--radius)] bg-surface-2 p-4 text-[13.5px] leading-relaxed text-ink-2">
                  <p>
                    {meeting.summary ? (
                      meeting.summary
                    ) : (
                      `ที่ประชุมได้ดำเนินการประชุมตามระเบียบวาระ โดยมีการพิจารณาติดตามความคืบหน้าการดำเนินงานตามมติเดิม และพิจารณาประเด็นข้อเสนอใหม่เพื่อขับเคลื่อนการดำเนินงานของคณะกรรมการ${
                        created.length > 0
                          ? ` ทั้งนี้ ที่ประชุมได้มีมติเห็นชอบในเรื่องสำคัญจำนวน ${created.length} เรื่อง`
                          : " โดยไม่มีการลงมติใหม่เพิ่มเติมในครั้งนี้"
                      }`
                    )}
                  </p>
                </div>

                {speakerPeople.length > 0 && (
                  <div className="border-t border-line pt-3.5">
                    <h4 className="mb-2 text-[12.5px] font-medium text-ink-3">
                      {t.pick("ผู้มีบทบาทสำคัญในการประชุม", "Key Participants")}
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {speakerPeople.map((p) => (
                        <span
                          key={p.id}
                          className="inline-flex items-center gap-1.5 rounded-full bg-sunken px-3 py-1 text-[12px] text-ink-2"
                        >
                          <span className="h-1.5 w-1.5 rounded-full bg-brand" />
                          <span className="font-medium">{p.full_name}</span>
                          {p.position && <span className="text-ink-4">({p.position})</span>}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </Card>

            {/* ส่วนที่ 2: มติจากการประชุมครั้งนี้ พร้อมเครื่องมือระบุฝ่ายรับผิดชอบ */}
            <div className="space-y-4">
              {/* มติใหม่ */}
              <Card className="overflow-hidden">
                <CardHead
                  title={t.pick("มติที่เกิดขึ้นใหม่จากการประชุมครั้งนี้", "New Resolutions Created")}
                  desc={t.pick(
                    "มติที่สกัดได้จากการประชุม — สามารถระบุ/ปรับเปลี่ยนฝ่ายที่รับผิดชอบในแต่ละข้อได้",
                    "Extracted resolutions from this meeting — annotate responsible department for each"
                  )}
                  right={
                    <Badge tone={created.length > 0 ? "brand" : "neutral"}>
                      {created.length} {t.pick("ข้อ", "items")}
                    </Badge>
                  }
                />
                {created.length === 0 ? (
                  <EmptyState
                    icon={<ListChecks size={20} />}
                    title={t.pick("ไม่มีมติใหม่ที่เกิดขึ้นในการประชุมครั้งนี้", "No new resolutions created")}
                    desc={t.pick(
                      "การประชุมครั้งนี้ไม่มีการลงมติข้อใหม่",
                      "No new resolutions originated from this meeting."
                    )}
                  />
                ) : (
                  <div className="divide-y divide-line">
                    {created.map((r) => {
                      const od = overdueDays(r);
                      const assignees = assigneeNames(db, r);
                      const hasDept = assignees.length > 0;
                      return (
                        <div
                          key={r.id}
                          className="group flex flex-col gap-2.5 p-4 transition-colors hover:bg-surface-2 sm:flex-row sm:items-center sm:justify-between"
                        >
                          <div
                            className="min-w-0 flex-1 cursor-pointer"
                            onClick={() => setOpenRes(r.id)}
                          >
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-mono text-[12px] font-medium text-brand">{r.ref_no}</span>
                              <Badge tone={r.status === "done" ? "ok" : od > 0 ? "danger" : "brand"}>
                                {r.status === "done" ? "เสร็จ" : od > 0 ? "เกินกำหนด" : "กำลังดำเนินการ"}
                              </Badge>
                            </div>
                            <p className="mt-1 text-[13.5px] font-medium leading-relaxed text-ink hover:text-brand">
                              {r.text}
                            </p>
                            <div className="mt-2 flex flex-wrap items-center gap-2">
                              <span className="text-[12px] text-ink-3">
                                {t.pick("ฝ่ายที่รับผิดชอบ:", "Responsible department:")}
                              </span>
                              {hasDept ? (
                                assignees.map((p) => (
                                  <Badge key={p.id} tone={p.is_department ? "seal" : "brand"} className="text-[12px]">
                                    <Building2 size={11} className="mr-1" />
                                    {p.full_name}
                                  </Badge>
                                ))
                              ) : (
                                <Badge tone="warn" className="text-[11.5px]">
                                  {t.pick("ยังไม่ได้ระบุฝ่ายรับผิดชอบ", "No department assigned")}
                                </Badge>
                              )}
                            </div>
                          </div>

                          <div className="flex shrink-0 items-center gap-2 pt-1 sm:pt-0">
                            <Button
                              size="sm"
                              variant={hasDept ? "secondary" : "primary"}
                              icon={<UserCheck size={13} />}
                              onClick={() => setAnnotateRes(r)}
                            >
                              {hasDept ? t.pick("เปลี่ยนฝ่าย", "Change department") : t.pick("ระบุฝ่ายรับผิดชอบ", "Assign department")}
                            </Button>
                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={() => setOpenRes(r.id)}
                            >
                              {t.pick("ดูรายละเอียด", "Details")}
                            </Button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </Card>

              {/* มติเดิมที่ติดตามผลและปิด */}
              {followedUp.length > 0 && (
                <Card className="overflow-hidden">
                  <CardHead
                    title={t.pick(
                      "มติเดิมที่ติดตามผลและปิดในการประชุมนี้",
                      "Followed-up & Closed Resolutions"
                    )}
                    desc={t.pick(
                      "มติจากครั้งก่อนที่ได้รับการรายงานความคืบหน้าหรือปิดมติในการประชุมนี้",
                      "Prior resolutions updated or closed during this meeting"
                    )}
                    right={
                      <Badge tone="ok">
                        {followedUp.length} {t.pick("ข้อ", "items")}
                      </Badge>
                    }
                  />
                  <div>
                    {followedUp.map((r) => (
                      <ResolutionRow
                        key={r.id}
                        resolution={r}
                        onOpen={() => setOpenRes(r.id)}
                      />
                    ))}
                  </div>
                </Card>
              )}
            </div>
          </>
        )}
      </PageBody>

      {/* Drawer ดูรายละเอียดมติ */}
      <ResolutionDrawer resolutionId={openRes} onClose={() => setOpenRes(null)} />

      {/* Modal ให้ผู้ใช้เลือก/ระบุฝ่ายที่รับผิดชอบ (User Annotation) */}
      {annotateRes && (
        <AnnotateDepartmentModal
          open={Boolean(annotateRes)}
          onClose={() => setAnnotateRes(null)}
          resolution={annotateRes}
        />
      )}

      {/* Modal รับรองรายงานการประชุม */}
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
                router.push("/actions");
              }}
            >
              {t("confirm")}
            </Button>
          </>
        }
      >
        <ul className="space-y-2 text-[13px] leading-relaxed text-ink-2">
          <li>
            • {t.pick("มติที่รอรับรองในการประชุมนี้จะเปลี่ยนเป็น “รับรองแล้ว” อัตโนมัติ", "Proposed resolutions become confirmed.")}
          </li>
          <li>
            • {t.pick("ระบบจะปลดล็อกการสร้างร่างวาระครั้งถัดไปและการส่งอีเมล", "Agenda generation and email dispatch unlock.")}
          </li>
          <li>
            • {t.pick("การรับรองถูกบันทึกในบันทึกการใช้งานพร้อมชื่อผู้รับรอง", "The approval is written to the audit log.")}
          </li>
        </ul>
      </Modal>

      {/* Modal อัปโหลดไฟล์การประชุมใหม่สำหรับลองใหม่ */}
      <ReuploadMeetingModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        meeting={meeting}
      />
    </>
  );
}

/** Modal ให้ผู้ใช้เลือก/ระบุฝ่ายที่รับผิดชอบ (User Annotation) */
function AnnotateDepartmentModal({
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
  const [selectedIds, setSelectedIds] = useState<Uuid[]>(resolution.assignee_ids);

  // รายชื่อหน่วยงาน/ฝ่ายทั้งหมด
  const deptList = Array.from(
    new Set([
      ...db.people.filter((p) => p.is_department).map((p) => p.full_name),
      ...db.people.map((p) => p.department).filter(Boolean),
    ])
  );
  const deptEntities = db.people.filter((p) => p.is_department);
  const people = db.people.filter((p) => !p.is_department);

  // หาฝ่ายปัจจุบันที่เลือกอยู่
  const currentSelectedDept = () => {
    for (const id of selectedIds) {
      const p = db.people.find((x) => x.id === id);
      if (p) {
        if (p.is_department) return p.full_name;
        if (p.department) return p.department;
      }
    }
    return "";
  };

  const handleDeptChange = (deptName: string) => {
    if (!deptName) {
      setSelectedIds((prev) =>
        prev.filter((id) => {
          const p = db.people.find((x) => x.id === id);
          return p && !p.is_department;
        })
      );
      return;
    }
    // 1. หา department entity ตรงๆ
    let target = db.people.find(
      (p) => p.is_department && (p.full_name === deptName || p.department === deptName)
    );
    // 2. ถ้าไม่มี ให้หาตัวแทนบุคคลในฝ่ายนั้น
    if (!target) {
      target = db.people.find((p) => p.department === deptName || p.full_name === deptName);
    }

    if (target) {
      setSelectedIds((prev) => {
        const nonDeptIds = prev.filter((id) => {
          const p = db.people.find((x) => x.id === id);
          return p && !p.is_department && p.department !== deptName;
        });
        return [target.id, ...nonDeptIds];
      });
    }
  };

  const handlePersonChange = (personId: string) => {
    if (!personId) return;
    if (!selectedIds.includes(personId)) {
      setSelectedIds((prev) => [...prev, personId]);
    }
  };

  const removeAssignee = (id: Uuid) => {
    setSelectedIds((prev) => prev.filter((x) => x !== id));
  };

  const save = () => {
    updateResolution(
      resolution.id,
      { assignee_ids: selectedIds },
      "ผู้ใช้ระบุฝ่ายรับผิดชอบในการตรวจทาน"
    );
    onClose();
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t.pick("ระบุฝ่ายที่รับผิดชอบ", "Assign Responsible Department")}
      desc={resolution.ref_no}
      width="max-w-lg"
      footer={
        <>
          <Button onClick={onClose}>{t("cancel")}</Button>
          <Button variant="primary" onClick={save}>
            {t("save")}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="rounded-[var(--radius)] bg-surface-2 p-3 text-[13px] text-ink-2">
          “{resolution.text}”
        </div>

        <Field label={t.pick("เลือกหน่วยงาน/ฝ่ายที่รับผิดชอบ", "Select Responsible Department")}>
          <Select
            value={currentSelectedDept()}
            onChange={(e) => handleDeptChange(e.target.value)}
          >
            <option value="">{t.pick("— เลือกหน่วยงาน/ฝ่าย —", "— Select Department —")}</option>
            {deptList.map((dept) => (
              <option key={dept} value={dept}>
                {dept}
              </option>
            ))}
          </Select>
        </Field>

        <Field label={t.pick("หรือเลือกบุคคลผู้รับผิดชอบโดยตรง (ระบุเพิ่มได้ / ไม่บังคับ)", "Or Select Individual Assignee (Optional)")}>
          <Select
            value=""
            onChange={(e) => handlePersonChange(e.target.value)}
          >
            <option value="">{t.pick("— เลือกบุคคลผู้รับผิดชอบ (ไม่จำเป็น) —", "— Select Person (Optional) —")}</option>
            {people.map((p) => (
              <option key={p.id} value={p.id}>
                {p.full_name} {p.department ? `(${p.department})` : ""} {p.position ? `— ${p.position}` : ""}
              </option>
            ))}
          </Select>
        </Field>

        {selectedIds.length > 0 && (
          <div>
            <label className="mb-2 block text-[12.5px] font-medium text-ink-3">
              {t.pick("ผู้รับผิดชอบที่เลือกไว้:", "Selected Assignees:")}
            </label>
            <div className="flex flex-wrap gap-2">
              {selectedIds.map((id) => {
                const person = db.people.find((p) => p.id === id);
                if (!person) return null;
                return (
                  <span
                    key={id}
                    className="inline-flex items-center gap-1.5 rounded-full bg-[var(--brand-soft)] px-3 py-1 text-[12.5px] font-medium text-brand"
                  >
                    {person.is_department ? <Building2 size={13} /> : <UserCheck size={13} />}
                    <span>{person.full_name}</span>
                    <button
                      type="button"
                      onClick={() => removeAssignee(id)}
                      className="ml-1 rounded-full p-0.5 hover:bg-brand/20 cursor-pointer"
                      title={t.pick("นำออก", "Remove")}
                    >
                      <X size={12} />
                    </button>
                  </span>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
