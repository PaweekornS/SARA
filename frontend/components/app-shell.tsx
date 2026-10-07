"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Bot, ChevronDown, FileStack, FolderKanban, Gauge, LogOut, Menu, Moon, Plus, Settings, Sparkles, Sun, X } from "lucide-react";
import * as api from "@/lib/api";
import { useCollections, useMe } from "@/lib/data";
import { useT } from "@/lib/i18n";
import { clearCache, invalidate } from "@/lib/query";
import { hydratePrefs, toggleTheme, usePrefs } from "@/lib/store";
import { Button, Field, Input, Modal, cn } from "./ui";

/* หน้าที่ไม่ต้องมีแถบเมนู (ยังไม่ได้เข้าสู่ระบบ) */
const BARE_PATHS = ["/login"];

/* ── โครงหน้าหลัก: แถบซ้าย + ส่วนเนื้อหา ───────────────────────────── */

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  useEffect(() => hydratePrefs(), []);

  if (BARE_PATHS.some((p) => pathname.startsWith(p))) {
    return <div className="min-h-dvh bg-[var(--bg-app)] text-ink">{children}</div>;
  }
  return <Workspace>{children}</Workspace>;
}

function useActiveCollectionId(): string | undefined {
  const pathname = usePathname();
  return pathname.match(/^\/collections\/([^/]+)/)?.[1];
}

function Workspace({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const theme = usePrefs((p) => p.theme);
  const t = useT();
  const activeId = useActiveCollectionId();
  const { data: collections } = useCollections();
  const active = collections?.find((c) => c.id === activeId);

  return (
    <div className="flex min-h-dvh bg-[var(--bg-app)] text-ink">
      <Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="no-print sticky top-0 z-20 flex h-14 items-center justify-between border-b border-[var(--border-subtle)] bg-[var(--bg-surface)]/80 backdrop-blur-md px-4 sm:px-6 transition-colors">
          <div className="flex items-center gap-2.5 min-w-0">
            <button
              onClick={() => setMobileOpen(true)}
              className="flex items-center gap-2 text-sm font-medium text-ink lg:hidden cursor-pointer p-1.5 -ml-1.5 rounded-[var(--radius)] hover:bg-sunken shrink-0"
              aria-label="Open navigation"
            >
              <Menu size={18} />
            </button>
            {active && <span className="truncate text-[13.5px] font-semibold text-ink">{active.name}</span>}
          </div>

          <div className="flex items-center gap-2 ml-auto shrink-0">
            <UserMenu />
            <button
              onClick={toggleTheme}
              className="flex items-center justify-center rounded-[var(--radius)] border border-line bg-[var(--bg-surface)] p-2 text-ink-2 hover:bg-sunken hover:text-ink cursor-pointer shadow-xs transition-colors"
              title={t("theme")}
              aria-label={t("theme")}
            >
              {theme === "light" ? <Moon size={15} className="text-brand" /> : <Sun size={15} className="text-amber-400" />}
            </button>
          </div>
        </header>

        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}

export async function logout() {
  try {
    await api.auth.logout();
  } finally {
    clearCache();
    window.location.assign("/login");
  }
}

function UserMenu() {
  const t = useT();
  const { data: me } = useMe();
  const [open, setOpen] = useState(false);
  if (!me) return null;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 rounded-[var(--radius)] border border-line bg-[var(--bg-surface)] px-2.5 py-1.5 text-[12px] font-medium text-ink-2 hover:bg-sunken hover:text-ink cursor-pointer transition-colors"
      >
        {me.picture ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={me.picture} alt="" className="h-5 w-5 rounded-full" referrerPolicy="no-referrer" />
        ) : (
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[var(--brand-soft)] text-[11px] font-semibold text-brand">
            {(me.name || me.email).charAt(0).toUpperCase()}
          </span>
        )}
        <span className="hidden sm:inline truncate max-w-[140px]">{me.name || me.email}</span>
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
          <div className="fade-up absolute right-0 top-full z-40 mt-1 w-56 rounded-[var(--radius)] border border-line bg-[var(--bg-surface)] p-1 shadow-[var(--shadow-2)]">
            <div className="px-3 py-2">
              <p className="truncate text-[13px] font-medium text-ink">{me.name}</p>
              <p className="truncate text-[11.5px] text-ink-3">{me.email}</p>
            </div>
            <button
              onClick={() => void logout()}
              className="flex w-full items-center gap-2 rounded px-3 py-2 text-[13px] text-ink-2 hover:bg-sunken hover:text-ink cursor-pointer"
            >
              <LogOut size={14} />
              {t("logout")}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export function NewCollectionModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const t = useT();
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api.collections.create({ name: name.trim(), description: description.trim() });
      invalidate("collections");
      setName("");
      setDescription("");
      onClose();
      router.push(`/collections/${created.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t.pick("สร้างคอลเลกชันใหม่", "New Collection")}
      desc={t.pick(
        "คอลเลกชันช่วยจัดกลุ่มการประชุมตามโปรเจกต์หรือทีม เพื่อให้ถามคำถามข้ามการประชุมและติดตามงานค้างได้",
        "Group meetings by project or team to ask across meetings and track open tasks.",
      )}
      footer={
        <>
          <Button onClick={onClose}>{t("cancel")}</Button>
          <Button variant="primary" disabled={!name.trim() || busy} onClick={submit}>
            {t.pick("สร้างคอลเลกชัน", "Create")}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label={t.pick("ชื่อคอลเลกชัน / โปรเจกต์", "Collection / Project Name")} required>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && void submit()}
            placeholder="e.g. Q4 Marketing Campaign / Sprint Alpha"
            autoFocus
          />
        </Field>
        <Field label={t.pick("คำอธิบายสั้นๆ", "Description")}>
          <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="e.g. ประชุมทีมการตลาดทุกวันจันทร์" />
        </Field>
        {error && <p className="text-[12.5px] text-[var(--danger)]">{error}</p>}
      </div>
    </Modal>
  );
}

function Sidebar({ mobileOpen, onClose }: { mobileOpen: boolean; onClose: () => void }) {
  const t = useT();
  const pathname = usePathname();
  const activeId = useActiveCollectionId();
  const { data: collections = [] } = useCollections();
  const active = collections.find((c) => c.id === activeId);
  const base = `/collections/${activeId ?? ""}`;

  const [switcherOpen, setSwitcherOpen] = useState(false);
  const [newCollectionOpen, setNewCollectionOpen] = useState(false);

  const mainNav = !activeId
    ? [{ href: "/collections", label: t.pick("คอลเลกชันทั้งหมด", "All Collections"), icon: <FolderKanban size={16} />, exact: true }]
    : [
        { href: base, label: t.pick("ภาพรวมคอลเลกชัน", "Collection Hub"), icon: <Gauge size={16} />, exact: true, badge: active?.open_action_count },
        { href: `${base}/meetings`, label: t.pick("รายการประชุม & สรุป", "Meetings & Transcripts"), icon: <FileStack size={16} /> },
        { href: `${base}/ask`, label: "Ask SARA Copilot", icon: <Sparkles size={16} className="text-brand" />, highlight: true },
      ];

  return (
    <>
      {mobileOpen && <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={onClose} />}
      <aside
        className={cn(
          "no-print fixed inset-y-0 left-0 z-40 flex w-[264px] shrink-0 flex-col border-r border-[var(--border-subtle)] bg-[var(--bg-surface)] transition-transform lg:sticky lg:top-0 lg:h-dvh lg:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex items-center justify-between gap-3 px-4 py-4">
          <Link href="/collections" onClick={onClose} className="flex min-w-0 flex-1 items-center gap-2.5 transition-opacity hover:opacity-85">
            <SaraMark />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5">
                <p className="text-[16px] font-bold leading-none tracking-tight text-ink">SARA</p>
                <span className="rounded bg-[var(--brand-soft)] px-1.5 py-0.5 text-[9.5px] font-semibold text-brand">v4.0</span>
              </div>
              <p className="mt-1 truncate text-[11px] leading-none text-ink-3">AI Meeting Workspace</p>
            </div>
          </Link>
          <button onClick={onClose} className="rounded p-1 text-ink-3 hover:bg-sunken lg:hidden cursor-pointer">
            <X size={16} />
          </button>
        </div>

        {activeId && (
          <div className="px-3">
            <div className="relative">
              <button
                onClick={() => setSwitcherOpen((v) => !v)}
                className="flex w-full items-center gap-2 rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--bg-surface-hover)] px-3 py-2.5 text-left hover:border-[var(--line-strong)] cursor-pointer transition-colors"
              >
                <FolderKanban size={15} className="text-brand shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-ink-4">Collection</p>
                  <p className="mt-0.5 truncate text-[13px] font-medium leading-tight text-ink">{active?.name ?? "—"}</p>
                </div>
                <ChevronDown size={14} className={cn("shrink-0 text-ink-3 transition-transform", switcherOpen && "rotate-180")} />
              </button>

              {switcherOpen && (
                <div className="fade-up absolute left-0 right-0 top-full z-10 mt-1 max-h-60 overflow-y-auto rounded-[var(--radius)] border border-line bg-[var(--bg-surface)] shadow-[var(--shadow-2)]">
                  {collections.map((c) => (
                    <Link
                      key={c.id}
                      href={`/collections/${c.id}`}
                      onClick={() => {
                        setSwitcherOpen(false);
                        onClose();
                      }}
                      className={cn(
                        "block px-3 py-2.5 text-[13px] leading-tight hover:bg-sunken",
                        c.id === activeId ? "bg-[var(--brand-soft)] font-medium text-brand" : "text-ink-2",
                      )}
                    >
                      {c.name}
                    </Link>
                  ))}
                  <button
                    onClick={() => {
                      setSwitcherOpen(false);
                      setNewCollectionOpen(true);
                    }}
                    className="flex w-full items-center gap-2 border-t border-line px-3 py-2 text-[12.5px] font-medium text-brand hover:bg-[var(--brand-soft)] cursor-pointer"
                  >
                    <Plus size={14} />
                    <span>{t.pick("สร้างคอลเลกชันใหม่", "New Collection")}</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        <nav className="mt-4 flex-1 space-y-6 overflow-y-auto px-3 pb-4">
          <NavGroup label={t.pick("เมนูหลัก", "Main Menu")}>
            {mainNav.map((item) => (
              <NavLink
                key={item.href}
                {...item}
                onNavigate={onClose}
                active={item.exact ? pathname === item.href : pathname.startsWith(item.href)}
              />
            ))}
          </NavGroup>

          <NavGroup label={t.pick("การตั้งค่า", "Preferences")}>
            <NavLink
              href="/settings"
              label={t.pick("ตั้งค่าบัญชี & ระบบ", "Settings & Account")}
              icon={<Settings size={16} />}
              onNavigate={onClose}
              active={pathname === "/settings"}
            />
          </NavGroup>
        </nav>
      </aside>

      <NewCollectionModal open={newCollectionOpen} onClose={() => setNewCollectionOpen(false)} />
    </>
  );
}

function NavGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="mb-1.5 px-3 text-[10px] font-semibold uppercase tracking-wider text-ink-4">{label}</p>
      <div className="space-y-0.5">{children}</div>
    </div>
  );
}

function NavLink({
  href,
  label,
  icon,
  badge,
  active,
  highlight,
  onNavigate,
}: {
  href: string;
  label: string;
  icon: React.ReactNode;
  badge?: number;
  active?: boolean;
  highlight?: boolean;
  onNavigate?: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={onNavigate}
      className={cn(
        "flex items-center gap-2.5 rounded-[var(--radius)] px-3 py-2 text-[13px] font-medium transition-all",
        active
          ? "bg-[var(--brand-soft)] text-brand font-semibold shadow-xs"
          : highlight
          ? "text-brand hover:bg-[var(--brand-soft)] hover:text-brand"
          : "text-ink-2 hover:bg-sunken hover:text-ink",
      )}
    >
      <span className={cn("shrink-0", active ? "text-brand" : "text-ink-3")}>{icon}</span>
      <span className="min-w-0 flex-1 truncate">{label}</span>
      {typeof badge === "number" && badge > 0 && (
        <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-brand px-1.5 text-[10.5px] font-semibold text-white tnum">
          {badge}
        </span>
      )}
    </Link>
  );
}

export function SaraMark() {
  return (
    <div className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand text-white shadow-xs">
      <Bot size={18} strokeWidth={2.2} />
    </div>
  );
}

/* ── ส่วนหัวหน้าเพจ ─────────────────────────────────────────────────── */

export function PageHeader({
  eyebrow,
  title,
  desc,
  actions,
  tabs,
}: {
  eyebrow?: React.ReactNode;
  title: React.ReactNode;
  desc?: React.ReactNode;
  actions?: React.ReactNode;
  tabs?: React.ReactNode;
}) {
  return (
    <header className="border-b border-[var(--border-subtle)] bg-[var(--bg-surface)] transition-colors">
      <div className="mx-auto max-w-[1240px] px-5 pb-5 pt-6 sm:px-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            {eyebrow && <div className="mb-1.5 flex items-center gap-2 text-[12px] text-ink-3">{eyebrow}</div>}
            <h1 className="text-[22px] font-semibold leading-tight tracking-tight text-ink">{title}</h1>
            {desc && <div className="mt-1.5 max-w-2xl text-[13.5px] leading-relaxed text-ink-3">{desc}</div>}
          </div>
          {actions && <div className="no-print flex flex-wrap items-center gap-2">{actions}</div>}
        </div>
        {tabs && <div className="no-print mt-4">{tabs}</div>}
      </div>
    </header>
  );
}

export function PageBody({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("mx-auto max-w-[1240px] px-5 py-6 sm:px-8", className)}>{children}</div>;
}
