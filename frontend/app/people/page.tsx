"use client";

/** M3 — ทะเบียนบุคคลระดับองค์กร (FR-M3-01 ถึง 05) */

import { useState } from "react";
import { Building2, Search, Trash2, UserPlus, Users } from "lucide-react";
import { PageBody, PageHeader } from "@/components/app-shell";
import { Badge, Button, Card, CardHead, ConfirmModal, EmptyState, Field, Input, Modal, cn } from "@/components/ui";
import { useT } from "@/lib/i18n";
import { deletePerson, upsertPerson, useApp } from "@/lib/store";
import type { Person } from "@/lib/types";

export default function PeoplePage() {
  const t = useT();
  const { db } = useApp();
  const [query, setQuery] = useState("");
  const [selectedDept, setSelectedDept] = useState<string>("all");
  const [editing, setEditing] = useState<Person | null>(null);
  const [creating, setCreating] = useState<boolean>(false);
  const [pendingDelete, setPendingDelete] = useState<Person | null>(null);

  // แสดงเฉพาะบุคคล/สมาชิก (ไม่รวมหน่วยงาน/ฝ่ายในตาราง)
  const members = db.people.filter((p) => !p.is_department);

  // รายการฝ่ายทั้งหมดสำหรับใช้เป็น Filter
  const deptList = Array.from(
    new Set([
      ...db.people.filter((p) => p.is_department).map((p) => p.full_name),
      ...members.map((p) => p.department).filter(Boolean),
    ])
  ).filter(Boolean);

  const rows = members.filter((p) => {
    if (selectedDept !== "all") {
      if (!p.department || !p.department.toLowerCase().includes(selectedDept.toLowerCase())) {
        return false;
      }
    }
    if (!query.trim()) return true;
    const q = query.trim().toLowerCase();
    return `${p.full_name} ${p.position} ${p.department} ${p.email}`.toLowerCase().includes(q);
  });

  return (
    <>
      <PageHeader
        title={t("navPeople")}
        desc={t.pick(
          "ทะเบียนสมาชิกและบุคลากรในองค์กร สำหรับมอบหมายและติดตามการดำเนินงานตามมติที่ประชุม",
          "Directory of organization members for assigning and tracking meeting resolutions.",
        )}
        actions={
          <Button variant="primary" icon={<UserPlus size={15} />} onClick={() => setCreating(true)}>
            {t.pick("เพิ่มบุคคล", "Add person")}
          </Button>
        }
      />

      <PageBody className="space-y-4">
        {/* แถบค้นหา และ ตัวกรองฝ่าย (Department Filter Buttons) */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative w-full max-w-md">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-4" />
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t.pick("ค้นชื่อ ตำแหน่ง หรือหน่วยงาน...", "Search name, position, or department...")}
              className="pl-9"
            />
          </div>
        </div>

        {/* ปุ่มกรองแยกตามฝ่าย */}
        {deptList.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            <span className="mr-1 text-[12.5px] font-medium text-ink-3">
              {t.pick("ฝ่าย/หน่วยงาน:", "Department:")}
            </span>
            <button
              type="button"
              onClick={() => setSelectedDept("all")}
              className={cn(
                "rounded-full px-3 py-1 text-[12px] font-medium transition-colors cursor-pointer",
                selectedDept === "all"
                  ? "bg-brand text-white shadow-xs"
                  : "border border-line bg-surface text-ink-2 hover:bg-surface-2"
              )}
            >
              {t.pick("ทั้งหมด", "All")} ({members.length})
            </button>
            {deptList.map((dept) => {
              const count = members.filter(
                (p) => p.department && p.department.toLowerCase().includes(dept.toLowerCase())
              ).length;
              const active = selectedDept === dept;
              return (
                <button
                  key={dept}
                  type="button"
                  onClick={() => setSelectedDept(active ? "all" : dept)}
                  className={cn(
                    "inline-flex items-center gap-1 rounded-full px-3 py-1 text-[12px] font-medium transition-colors cursor-pointer",
                    active
                      ? "bg-brand text-white shadow-xs"
                      : "border border-line bg-surface text-ink-2 hover:bg-surface-2"
                  )}
                >
                  <Building2 size={11} className={active ? "text-white" : "text-ink-4"} />
                  {dept}
                  <span className={cn("ml-0.5 text-[11px]", active ? "text-white/80" : "text-ink-4")}>
                    ({count})
                  </span>
                </button>
              );
            })}
          </div>
        )}

        <Card className="overflow-hidden">
          <CardHead
            title={`${t.pick("รายชื่อบุคคลทั้งหมด", "Members Directory")} (${rows.length})`}
            desc={t.pick("คลิกที่ชื่อเพื่อแก้ไขข้อมูลบุคคลในองค์กร", "Click name to edit member details")}
            right={
              selectedDept !== "all" ? (
                <Badge tone="seal">
                  {selectedDept} ({rows.length})
                </Badge>
              ) : undefined
            }
          />
          {rows.length === 0 ? (
            <EmptyState
              icon={<Users size={24} />}
              title={t.pick("ไม่พบรายชื่อบุคคลตามเงื่อนไขที่เลือก", "No members found")}
              desc={t.pick("ลองเปลี่ยนคำค้นหาหรือตัวกรองฝ่าย", "Try adjusting your search query or department filter.")}
            />
          ) : (
            <div className="divide-y divide-[var(--line)]">
              {rows.map((p) => {
                const openCount = db.resolutions.filter(
                  (r) => r.assignee_ids.includes(p.id) && ["confirmed", "in_progress", "blocked"].includes(r.status),
                ).length;
                return (
                  <div key={p.id} className="flex flex-wrap items-center gap-4 px-5 py-4 transition-colors hover:bg-surface-2">
                    <span
                      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--brand-soft)] text-[13px] font-semibold text-brand"
                    >
                      {p.full_name.replace(/^(นาย|นาง|นางสาว|ดร\.|ศ\.|รศ\.|ผศ\.)/, "").trim().charAt(0)}
                    </span>

                    <div className="min-w-[200px] flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          onClick={() => setEditing(p)}
                          className="text-[14px] font-medium text-ink hover:text-brand cursor-pointer"
                        >
                          {p.full_name}
                        </button>
                        {p.department && (
                          <Badge tone="seal" className="text-[11.5px]">
                            {p.department}
                          </Badge>
                        )}
                        {openCount > 0 && (
                          <Badge tone="warn" className="text-[11.5px]">
                            {openCount} {t.pick("มติค้าง", "open")}
                          </Badge>
                        )}
                      </div>
                      <p className="mt-0.5 text-[12.5px] text-ink-3">
                        {p.position || "-"}
                      </p>
                      {p.email && <p className="mt-0.5 font-mono text-[12px] text-ink-4">{p.email}</p>}
                    </div>

                    <button
                      onClick={() => setPendingDelete(p)}
                      className="shrink-0 rounded p-2 text-ink-4 hover:bg-sunken hover:text-[var(--danger)] cursor-pointer"
                      title={t.pick("ลบ", "Delete")}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      </PageBody>

      <ConfirmModal
        open={pendingDelete !== null}
        onClose={() => setPendingDelete(null)}
        title={t.pick("ลบออกจากทะเบียน", "Remove from registry")}
        confirmLabel={t("delete")}
        onConfirm={() => {
          if (pendingDelete) deletePerson(pendingDelete.id);
          setPendingDelete(null);
        }}
      >
        {t.pick(
          `ข้อมูลของ “${pendingDelete?.full_name ?? ""}” จะถูกลบออกจากทะเบียนบุคคล`,
          `“${pendingDelete?.full_name ?? ""}” will be removed from registry.`,
        )}
      </ConfirmModal>

      <PersonModal
        open={editing !== null || creating}
        onClose={() => {
          setEditing(null);
          setCreating(false);
        }}
        person={editing}
        departments={deptList}
      />
    </>
  );
}

function PersonModal({
  open,
  onClose,
  person,
  departments,
}: {
  open: boolean;
  onClose: () => void;
  person: Person | null;
  departments: string[];
}) {
  const t = useT();
  const [form, setForm] = useState({
    full_name: person?.full_name ?? "",
    position: person?.position ?? "",
    department: person?.department ?? "",
    email: person?.email ?? "",
  });

  const key = person?.id ?? "new-person";

  return (
    <Modal
      key={key}
      open={open}
      onClose={onClose}
      title={person ? t.pick("แก้ไขข้อมูลบุคคล", "Edit Person") : t.pick("เพิ่มบุคคล", "Add Person")}
      footer={
        <>
          <Button onClick={onClose}>{t("cancel")}</Button>
          <Button
            variant="primary"
            disabled={!form.full_name.trim()}
            onClick={() => {
              upsertPerson({ id: person?.id, ...form, is_department: false, is_active: true });
              onClose();
            }}
          >
            {t("save")}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label={t.pick("ชื่อ-นามสกุล", "Full name")}>
          <Input
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            placeholder="นายสมชาย ใจดี"
            autoFocus
          />
        </Field>
        <Field label={t.pick("ตำแหน่ง", "Position")}>
          <Input
            value={form.position}
            onChange={(e) => setForm({ ...form, position: e.target.value })}
            placeholder="ผู้อำนวยการส่วน..."
          />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t.pick("หน่วยงาน/ฝ่าย", "Department / Unit")}>
            <Input
              value={form.department}
              onChange={(e) => setForm({ ...form, department: e.target.value })}
              placeholder="ฝ่ายพัสดุ"
              list="dept-options"
            />
            <datalist id="dept-options">
              {departments.map((d) => (
                <option key={d} value={d} />
              ))}
            </datalist>
          </Field>
          <Field label={t.pick("อีเมล", "Email")} hint={t.pick("ใช้ส่งรายงานและการแจ้งเตือนมติ", "Used for reminders")}>
            <Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </Field>
        </div>
      </div>
    </Modal>
  );
}
