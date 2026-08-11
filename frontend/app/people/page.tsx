"use client";

/** M3 — ทะเบียนบุคคลระดับองค์กร + alias (FR-M3-01 ถึง 05) */

import { useState } from "react";
import { Building2, Plus, Search, Tag, Trash2, UserPlus, X } from "lucide-react";
import { PageBody, PageHeader } from "@/components/app-shell";
import { Badge, Button, Card, CardHead, ConfirmModal, EmptyState, Field, Input, Modal, cn } from "@/components/ui";
import { useT } from "@/lib/i18n";
import { addAlias, deletePerson, removeAlias, upsertPerson, useApp } from "@/lib/store";
import type { Person } from "@/lib/types";

export default function PeoplePage() {
  const t = useT();
  const { db } = useApp();
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState<Person | null>(null);
  const [creating, setCreating] = useState<"person" | "department" | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Person | null>(null);

  const rows = db.people.filter((p) => {
    if (!query.trim()) return true;
    const q = query.trim().toLowerCase();
    const aliasText = db.aliases.filter((a) => a.person_id === p.id).map((a) => a.alias).join(" ");
    return `${p.full_name} ${p.position} ${p.department} ${p.email} ${aliasText}`.toLowerCase().includes(q);
  });

  return (
    <>
      <PageHeader
        title={t("navPeople")}
        desc={t.pick(
          "ชื่อคนไทยในห้องประชุมปนกันทั้งชื่อเล่น ตำแหน่ง และคำนำหน้า ระบบจึงไม่เดาเอง แต่ให้ยืนยันครั้งแรกแล้วจำถาวรเป็น alias",
          "Thai meeting speech mixes nicknames, titles and roles — SARA never guesses; it asks once and remembers.",
        )}
        actions={
          <>
            <Button icon={<Building2 size={15} />} onClick={() => setCreating("department")}>
              {t.pick("เพิ่มหน่วยงาน", "Add department")}
            </Button>
            <Button variant="primary" icon={<UserPlus size={15} />} onClick={() => setCreating("person")}>
              {t.pick("เพิ่มบุคคล", "Add person")}
            </Button>
          </>
        }
      />

      <PageBody className="space-y-4">
        <div className="relative max-w-md">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-4" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t.pick("ค้นชื่อ ตำแหน่ง หน่วยงาน หรือชื่อเล่นที่เคยยืนยันไว้", "Search name, position or alias")}
            className="pl-9"
          />
        </div>

        <Card className="overflow-hidden">
          <CardHead
            title={`${t.pick("บุคคลและหน่วยงานทั้งหมด", "People and departments")} (${rows.length})`}
            desc={t.pick("คลิกเพื่อแก้ไขข้อมูลและจัดการชื่อเรียกที่ระบบใช้จับคู่", "Click to edit and manage aliases")}
          />
          {rows.length === 0 ? (
            <EmptyState title={t.pick("ไม่พบรายชื่อที่ค้นหา", "No matches")} />
          ) : (
            <div className="divide-y divide-[var(--line)]">
              {rows.map((p) => {
                const aliases = db.aliases.filter((a) => a.person_id === p.id);
                const openCount = db.resolutions.filter(
                  (r) => r.assignee_ids.includes(p.id) && ["confirmed", "in_progress", "blocked"].includes(r.status),
                ).length;
                return (
                  <div key={p.id} className="flex flex-wrap items-center gap-4 px-5 py-4">
                    <span
                      className={cn(
                        "flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[13px] font-semibold",
                        p.is_department ? "bg-[var(--seal-soft)] text-[var(--seal)]" : "bg-[var(--brand-soft)] text-brand",
                      )}
                    >
                      {p.is_department ? <Building2 size={17} /> : p.full_name.replace(/^(นาย|นาง|นางสาว)/, "").trim().charAt(0)}
                    </span>

                    <div className="min-w-[200px] flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          onClick={() => setEditing(p)}
                          className="text-[14px] font-medium text-ink hover:text-brand cursor-pointer"
                        >
                          {p.full_name}
                        </button>
                        {p.is_department && <Badge tone="seal">{t.pick("หน่วยงาน", "Department")}</Badge>}
                        {openCount > 0 && (
                          <Badge tone="warn">
                            {openCount} {t.pick("มติค้าง", "open")}
                          </Badge>
                        )}
                      </div>
                      <p className="mt-0.5 text-[12.5px] text-ink-3">
                        {p.position}
                        {p.department && ` · ${p.department}`}
                      </p>
                      <p className="mt-0.5 font-mono text-[12px] text-ink-4">{p.email}</p>
                    </div>

                    <div className="flex min-w-[220px] flex-1 flex-wrap items-center gap-1.5">
                      {aliases.length === 0 && (
                        <span className="text-[12px] text-ink-4">{t.pick("ยังไม่มีชื่อเรียกที่บันทึกไว้", "No aliases")}</span>
                      )}
                      {aliases.map((a) => (
                        <span
                          key={a.id}
                          className="group inline-flex items-center gap-1 rounded-full bg-sunken px-2.5 py-1 text-[12px] text-ink-2"
                          title={
                            a.source === "confirmed_extraction"
                              ? `ยืนยันจากที่ประชุม · ความมั่นใจ ${Math.round(a.confidence * 100)}%`
                              : "เพิ่มด้วยผู้ใช้"
                          }
                        >
                          <Tag size={10} className="text-ink-4" />
                          {a.alias}
                          <button
                            onClick={() => removeAlias(a.id)}
                            className="opacity-0 transition-opacity hover:text-[var(--danger)] group-hover:opacity-100 cursor-pointer"
                          >
                            <X size={11} />
                          </button>
                        </span>
                      ))}
                      <AliasAdder personId={p.id} />
                    </div>

                    <button
                      onClick={() => setPendingDelete(p)}
                      className="shrink-0 rounded p-2 text-ink-4 hover:bg-sunken hover:text-[var(--danger)] cursor-pointer"
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
          `ชื่อเรียกทั้งหมดของ “${pendingDelete?.full_name ?? ""}” จะถูกลบไปด้วย มติที่มอบหมายไว้จะไม่มีผู้รับผิดชอบ`,
          `All aliases for “${pendingDelete?.full_name ?? ""}” will be removed too.`,
        )}
      </ConfirmModal>

      <PersonModal
        open={editing !== null || creating !== null}
        onClose={() => {
          setEditing(null);
          setCreating(null);
        }}
        person={editing}
        isDepartment={creating === "department"}
      />
    </>
  );
}

function AliasAdder({ personId }: { personId: string }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");

  if (!open)
    return (
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1 rounded-full border border-dashed border-[var(--line-strong)] px-2.5 py-1 text-[12px] text-ink-3 hover:border-brand hover:text-brand cursor-pointer"
      >
        <Plus size={11} /> {t.pick("ชื่อเรียก", "alias")}
      </button>
    );

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        addAlias(personId, value);
        setValue("");
        setOpen(false);
      }}
      className="inline-flex items-center gap-1"
    >
      <input
        autoFocus
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={() => !value && setOpen(false)}
        placeholder={t.pick("เช่น พี่หนึ่ง", "e.g. nickname")}
        className="h-7 w-32 rounded-full border border-[var(--line-strong)] bg-surface px-2.5 text-[12px] text-ink focus:border-brand focus:outline-none"
      />
    </form>
  );
}

function PersonModal({
  open,
  onClose,
  person,
  isDepartment,
}: {
  open: boolean;
  onClose: () => void;
  person: Person | null;
  isDepartment: boolean;
}) {
  const t = useT();
  const dept = person?.is_department ?? isDepartment;
  const [form, setForm] = useState({
    full_name: person?.full_name ?? "",
    position: person?.position ?? (dept ? "หน่วยงาน" : ""),
    department: person?.department ?? "",
    email: person?.email ?? "",
  });

  /* modal ถูก unmount ทุกครั้งที่ปิด จึงไม่ต้อง sync state ย้อนกลับ */
  const key = person?.id ?? (isDepartment ? "new-dept" : "new-person");

  return (
    <Modal
      key={key}
      open={open}
      onClose={onClose}
      title={
        person
          ? t.pick("แก้ไขข้อมูล", "Edit")
          : dept
            ? t.pick("เพิ่มหน่วยงานเป็นผู้รับผิดชอบ", "Add department")
            : t.pick("เพิ่มบุคคล", "Add person")
      }
      desc={
        dept
          ? t.pick("ใช้เมื่อที่ประชุมมอบหมายเป็นหน่วยงาน ไม่ได้ระบุตัวบุคคล เช่น “ฝ่ายพัสดุ”", "For assignments made to a unit, not a person.")
          : undefined
      }
      footer={
        <>
          <Button onClick={onClose}>{t("cancel")}</Button>
          <Button
            variant="primary"
            disabled={!form.full_name.trim()}
            onClick={() => {
              upsertPerson({ id: person?.id, ...form, is_department: dept, is_active: true });
              onClose();
            }}
          >
            {t("save")}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label={dept ? t.pick("ชื่อหน่วยงาน", "Department name") : t.pick("ชื่อ-นามสกุล", "Full name")}>
          <Input
            value={form.full_name}
            onChange={(e) => setForm({ ...form, full_name: e.target.value })}
            placeholder={dept ? "ฝ่ายพัสดุ" : "นายสมชาย ใจดี"}
            autoFocus
          />
        </Field>
        {!dept && (
          <Field label={t.pick("ตำแหน่ง", "Position")}>
            <Input value={form.position} onChange={(e) => setForm({ ...form, position: e.target.value })} />
          </Field>
        )}
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t.pick("หน่วยงาน/ฝ่าย", "Unit")}>
            <Input value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} />
          </Field>
          <Field label={t.pick("อีเมล", "Email")} hint={t.pick("ใช้ส่งรายงานและการแจ้งเตือนมติ", "Used for reminders")}>
            <Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </Field>
        </div>
      </div>
    </Modal>
  );
}
