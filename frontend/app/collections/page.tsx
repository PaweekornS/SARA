"use client";

import { useState } from "react";
import Link from "next/link";
import {
  CalendarDays,
  FileStack,
  FolderKanban,
  Plus,
  Search,
  Sparkles,
  Trash2,
  Users,
} from "lucide-react";
import { PageBody, PageHeader } from "@/components/app-shell";
import { Button, Card, ConfirmModal, EmptyState, Field, Input, Modal } from "@/components/ui";
import { useT } from "@/lib/i18n";
import {
  createSeries,
  deleteSeries,
  formatThaiDate,
  seriesStats,
  useApp,
} from "@/lib/store";
import type { MeetingSeries } from "@/lib/types";

export default function CollectionsListPage() {
  const t = useT();
  const { db } = useApp();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [pendingDelete, setPendingDelete] = useState<MeetingSeries | null>(null);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const filtered = db.series.filter(
    (s) =>
      s.name.toLowerCase().includes(search.toLowerCase()) ||
      (s.committee_type && s.committee_type.toLowerCase().includes(search.toLowerCase())),
  );

  const handleCreate = async () => {
    if (!name.trim()) return;
    await createSeries({
      name: name.trim(),
      committee_type: description.trim() || "General Project",
      cadence: "adhoc",
      fiscal_year: new Date().getFullYear() + 543,
      member_ids: [],
    });
    setName("");
    setDescription("");
    setOpen(false);
  };

  return (
    <>
      <PageHeader
        title={t.pick("คอลเลกชันการประชุม (Collections)", "Meeting Collections")}
        desc={t.pick(
          "จัดระเบียบการประชุมตามโปรเจกต์ ทีม หรือลูกค้า เพื่อให้ระบบจดจำบริบทระยะยาวและตอบคำถามข้ามการประชุมได้",
          "Organize meetings by project, team, or client to unlock cross-meeting AI recall and synthesis.",
        )}
        actions={
          <Button variant="primary" icon={<Plus size={16} />} onClick={() => setOpen(true)}>
            {t.pick("สร้างคอลเลกชันใหม่", "New Collection")}
          </Button>
        }
      />

      <PageBody className="space-y-5">
        {/* Search Bar */}
        <div className="relative max-w-md">
          <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-3" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t.pick("ค้นหาชื่อคอลเลกชัน หรือโปรเจกต์...", "Search collections or projects...")}
            className="w-full rounded-[var(--radius)] border border-line bg-[var(--bg-surface)] py-2 pl-9 pr-4 text-[13px] text-ink focus:border-brand focus:outline-none"
          />
        </div>

        {filtered.length === 0 ? (
          <Card>
            <EmptyState
              icon={<FolderKanban size={24} className="text-brand" />}
              title={t.pick("ไม่พบคอลเลกชันที่ค้นหา", "No collections found")}
              desc={t.pick("สร้างคอลเลกชันแรกสำหรับทีมหรือโปรเจกต์ของคุณ", "Get started by creating your first collection.")}
              action={
                <Button variant="primary" icon={<Plus size={16} />} onClick={() => setOpen(true)}>
                  {t.pick("สร้างคอลเลกชันใหม่", "New Collection")}
                </Button>
              }
            />
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {filtered.map((s) => {
              const stats = seriesStats(db, s.id);
              const meetings = db.meetings.filter((m) => m.series_id === s.id);
              const lastMeeting = meetings.sort((a, b) => new Date(b.meeting_date).getTime() - new Date(a.meeting_date).getTime())[0];

              return (
                <Card
                  key={s.id}
                  className="group relative flex flex-col justify-between overflow-hidden border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5 transition-all hover:border-brand/40 hover:shadow-[var(--shadow-2)] cursor-pointer"
                >
                  {/* Stretched click layer across full card boundary */}
                  <Link href={`/collections/${s.id}`} className="absolute inset-0 z-0" aria-label={s.name} />

                  <div className="relative z-1 pointer-events-none">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--brand-soft)] text-brand">
                          <FolderKanban size={16} />
                        </div>
                        <span className="rounded bg-surface-2 px-2 py-0.5 text-[11px] font-medium text-ink-3">
                          {s.committee_type || "Project"}
                        </span>
                      </div>

                      <button
                        type="button"
                        onClick={(e) => {
                          e.preventDefault();
                          e.stopPropagation();
                          setPendingDelete(s);
                        }}
                        className="pointer-events-auto relative z-10 rounded p-1.5 text-ink-4 opacity-0 transition-opacity hover:bg-sunken hover:text-[var(--danger)] group-hover:opacity-100 cursor-pointer"
                        title={t("delete")}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>

                    <h3 className="mt-3 text-[16px] font-semibold leading-snug text-ink group-hover:text-brand transition-colors">
                      {s.name}
                    </h3>
                  </div>

                  <div className="relative z-1 mt-5 space-y-3 pointer-events-none">
                    <div className="flex items-center justify-between border-t border-line pt-3 text-[12px] text-ink-3">
                      <span className="flex items-center gap-1.5">
                        <FileStack size={14} /> {meetings.length} {t.pick("การประชุม", "meetings")}
                      </span>
                      <span className="flex items-center gap-1.5">
                        <Sparkles size={14} className="text-brand" /> {stats.total} {t.pick("ข้อสรุป/มติ", "takeaways")}
                      </span>
                    </div>

                    <div className="pointer-events-auto relative z-10 flex gap-2 pt-1">
                      <Link
                        href={`/collections/${s.id}`}
                        className="flex-1 rounded-[var(--radius)] bg-surface-2 py-1.5 text-center text-[12px] font-medium text-ink-2 hover:bg-brand hover:text-white transition-colors"
                      >
                        {t.pick("เปิดคอลเลกชัน", "Open Workspace")}
                      </Link>
                      <Link
                        href={`/collections/${s.id}/ask`}
                        className="flex items-center justify-center gap-1 rounded-[var(--radius)] bg-[var(--brand-soft)] px-3 py-1.5 text-[12px] font-medium text-brand hover:bg-brand hover:text-white transition-colors"
                        title="Ask Copilot"
                      >
                        <Sparkles size={13} />
                        <span>Copilot</span>
                      </Link>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </PageBody>

      {/* New Collection Modal */}
      <Modal open={open} onClose={() => setOpen(false)} title={t.pick("สร้างคอลเลกชันใหม่", "New Collection")}>
        <div className="space-y-4 pt-1">
          <Field label={t.pick("ชื่อคอลเลกชัน / โปรเจกต์", "Collection / Project Name")} required>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Q4 Marketing Campaign / Sprint Alpha"
              autoFocus
            />
          </Field>

          <Field label={t.pick("คำอธิบายสั้นๆ (แท็ก)", "Description / Tag")}>
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. ทีมการตลาด / ลูกค้า Enterprise"
            />
          </Field>

          <div className="flex justify-end gap-2 pt-3">
            <Button variant="secondary" onClick={() => setOpen(false)}>
              {t("cancel")}
            </Button>
            <Button variant="primary" disabled={!name.trim()} onClick={handleCreate}>
              {t.pick("สร้างคอลเลกชัน", "Create")}
            </Button>
          </div>
        </div>
      </Modal>

      <ConfirmModal
        open={Boolean(pendingDelete)}
        onClose={() => setPendingDelete(null)}
        title={t.pick("ลบคอลเลกชันนี้?", "Delete collection?")}
        confirmLabel={t("delete")}
        cancelLabel={t("cancel")}
        destructive
        onConfirm={async () => {
          if (pendingDelete) {
            await deleteSeries(pendingDelete.id);
            setPendingDelete(null);
          }
        }}
      >
        {t.pick(
          `การประชุมและสรุปเนื้อหาทั้งหมดใน “${pendingDelete?.name}” จะถูกลบอย่างถาวร`,
          `All meetings and summaries in "${pendingDelete?.name}" will be deleted.`,
        )}
      </ConfirmModal>
    </>
  );
}
