"use client";

import { useState } from "react";
import Link from "next/link";
import { CircleCheckBig, FileStack, FolderKanban, Plus, Search, Sparkles, Trash2 } from "lucide-react";
import { NewCollectionModal, PageBody, PageHeader } from "@/components/app-shell";
import { Button, Card, ConfirmModal, EmptyState, ErrorNote, Loading } from "@/components/ui";
import * as api from "@/lib/api";
import { useCollections } from "@/lib/data";
import { useT } from "@/lib/i18n";
import { invalidate } from "@/lib/query";
import type { Collection } from "@/lib/types";

export default function CollectionsListPage() {
  const t = useT();
  const { data: collections, error, loading, reload } = useCollections();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [pendingDelete, setPendingDelete] = useState<Collection | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const q = search.toLowerCase();
  const filtered = (collections ?? []).filter(
    (c) => c.name.toLowerCase().includes(q) || c.description.toLowerCase().includes(q),
  );

  return (
    <>
      <PageHeader
        title={t.pick("คอลเลกชันการประชุม", "Meeting Collections")}
        desc={t.pick(
          "จัดกลุ่มการประชุมตามโปรเจกต์หรือทีม เพื่อถามคำถามข้ามการประชุมและติดตามงานค้างได้ในที่เดียว",
          "Group meetings by project or team to ask across meetings and track open tasks.",
        )}
        actions={
          <Button variant="primary" icon={<Plus size={16} />} onClick={() => setOpen(true)}>
            {t.pick("สร้างคอลเลกชันใหม่", "New Collection")}
          </Button>
        }
      />

      <PageBody className="space-y-5">
        <div className="relative max-w-md">
          <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-3" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t.pick("ค้นหาชื่อคอลเลกชัน...", "Search collections...")}
            className="w-full rounded-[var(--radius)] border border-line bg-[var(--bg-surface)] py-2 pl-9 pr-4 text-[13px] text-ink focus:border-brand focus:outline-none"
          />
        </div>

        {error && <ErrorNote error={error} onRetry={reload} />}
        {deleteError && <ErrorNote error={deleteError} />}

        {loading && !collections ? (
          <Loading />
        ) : filtered.length === 0 ? (
          <Card>
            <EmptyState
              icon={<FolderKanban size={24} className="text-brand" />}
              title={search ? t.pick("ไม่พบคอลเลกชันที่ค้นหา", "No collections found") : t.pick("ยังไม่มีคอลเลกชัน", "No collections yet")}
              desc={t.pick("สร้างคอลเลกชันแรกสำหรับทีมหรือโปรเจกต์ของคุณ", "Create your first collection.")}
              action={
                <Button variant="primary" icon={<Plus size={16} />} onClick={() => setOpen(true)}>
                  {t.pick("สร้างคอลเลกชันใหม่", "New Collection")}
                </Button>
              }
            />
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {filtered.map((c) => (
              <Card
                key={c.id}
                className="group relative flex flex-col justify-between overflow-hidden border-[var(--border-subtle)] bg-[var(--bg-surface)] p-5 transition-all hover:border-brand/40 hover:shadow-[var(--shadow-2)] cursor-pointer"
              >
                <Link href={`/collections/${c.id}`} className="absolute inset-0 z-0" aria-label={c.name} />

                <div className="relative z-1 pointer-events-none">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--brand-soft)] text-brand">
                      <FolderKanban size={16} />
                    </div>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        setPendingDelete(c);
                      }}
                      className="pointer-events-auto relative z-10 rounded p-1.5 text-ink-4 opacity-0 transition-opacity hover:bg-sunken hover:text-[var(--danger)] group-hover:opacity-100 cursor-pointer"
                      title={t("delete")}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>

                  <h3 className="mt-3 text-[16px] font-semibold leading-snug text-ink group-hover:text-brand transition-colors">{c.name}</h3>
                  {c.description && <p className="mt-1 line-clamp-2 text-[12.5px] text-ink-3">{c.description}</p>}
                </div>

                <div className="relative z-1 mt-5 space-y-3 pointer-events-none">
                  <div className="flex items-center justify-between border-t border-line pt-3 text-[12px] text-ink-3">
                    <span className="flex items-center gap-1.5">
                      <FileStack size={14} /> {c.meeting_count} {t.pick("การประชุม", "meetings")}
                    </span>
                    <span className="flex items-center gap-1.5">
                      <CircleCheckBig size={14} className="text-brand" /> {c.open_action_count} {t.pick("งานค้าง", "open tasks")}
                    </span>
                  </div>

                  <div className="pointer-events-auto relative z-10 flex gap-2 pt-1">
                    <Link
                      href={`/collections/${c.id}`}
                      className="flex-1 rounded-[var(--radius)] bg-surface-2 py-1.5 text-center text-[12px] font-medium text-ink-2 hover:bg-brand hover:text-white transition-colors"
                    >
                      {t.pick("เปิดคอลเลกชัน", "Open")}
                    </Link>
                    <Link
                      href={`/collections/${c.id}/ask`}
                      className="flex items-center justify-center gap-1 rounded-[var(--radius)] bg-[var(--brand-soft)] px-3 py-1.5 text-[12px] font-medium text-brand hover:bg-brand hover:text-white transition-colors"
                    >
                      <Sparkles size={13} />
                      <span>Copilot</span>
                    </Link>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </PageBody>

      <NewCollectionModal open={open} onClose={() => setOpen(false)} />

      <ConfirmModal
        open={Boolean(pendingDelete)}
        onClose={() => setPendingDelete(null)}
        title={t.pick("ลบคอลเลกชันนี้?", "Delete collection?")}
        confirmLabel={t("delete")}
        cancelLabel={t("cancel")}
        onConfirm={async () => {
          if (!pendingDelete) return;
          setDeleteError(null);
          try {
            await api.collections.remove(pendingDelete.id);
            invalidate("collections");
          } catch (e) {
            setDeleteError(e instanceof Error ? e.message : String(e));
          }
          setPendingDelete(null);
        }}
      >
        {t.pick(
          `การประชุม ไฟล์ และสรุปทั้งหมดใน “${pendingDelete?.name}” จะถูกลบถาวร`,
          `All meetings, files and summaries in "${pendingDelete?.name}" will be permanently deleted.`,
        )}
      </ConfirmModal>
    </>
  );
}
