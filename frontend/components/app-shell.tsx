"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  AlertTriangle,
  Bot,
  CalendarClock,
  ChevronDown,
  FileStack,
  FolderKanban,
  FolderPlus,
  Gauge,
  Menu,
  Moon,
  Plus,
  RotateCcw,
  Settings,
  Sparkles,
  Sun,
  Upload,
  X,
} from "lucide-react";
import { useT } from "@/lib/i18n";
import { LIVE, createSeries, hydrate, loadFromServer, resetDemo, setActiveSeriesId, setError, toggleTheme, useApp } from "@/lib/store";
import { ConfirmModal, Modal, cn } from "./ui";
import { UploadMeetingModal } from "./meeting-ingest";
import * as api from "@/lib/api";

/* ── โครงหน้าหลัก: แถบซ้าย + ส่วนเนื้อหา ───────────────────────────── */

export function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const pathname = usePathname();
  const { db, theme, activeSeriesId: storedSeriesId } = useApp();
  const t = useT();

  const match = pathname.match(/^\/(?:series|collections)\/([^/]+)/);
  const pathSeriesId = match?.[1];

  const isHomePage = pathname === "/" || pathname === "/collections";

  const activeSeriesId = pathSeriesId || storedSeriesId || db.series[0]?.id;
  const activeSeries = db.series.find((s) => s.id === activeSeriesId) ?? db.series[0];

  useEffect(() => hydrate(), []);

  return (
    <div className="flex min-h-dvh bg-[var(--bg-app)] text-ink">
      <Sidebar
        mobileOpen={mobileOpen}
        onClose={() => setMobileOpen(false)}
        onOpenUpload={() => setUploadOpen(true)}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top Header Bar */}
        <header className="no-print sticky top-0 z-20 flex h-14 items-center justify-between border-b border-[var(--border-subtle)] bg-[var(--bg-surface)]/80 backdrop-blur-md px-4 sm:px-6 transition-colors">
          <div className="flex items-center gap-2.5 min-w-0">
            <button
              onClick={() => setMobileOpen(true)}
              className="flex items-center gap-2 text-sm font-medium text-ink lg:hidden cursor-pointer p-1.5 -ml-1.5 rounded-[var(--radius)] hover:bg-sunken shrink-0"
              aria-label="Open navigation"
            >
              <Menu size={18} />
            </button>
            {!isHomePage && activeSeries && (
              <div className="flex items-center gap-2 min-w-0">
                <div className="flex items-center gap-2 text-[13.5px] font-semibold text-ink truncate">
                  <span className="truncate">{activeSeries.name}</span>
                </div>
                {activeSeries.fiscal_year && (
                  <span className="hidden sm:inline-flex items-center rounded-full bg-[var(--brand-soft)] px-2 py-0.5 text-[11px] font-medium text-brand shrink-0">
                    ปี {activeSeries.fiscal_year}
                  </span>
                )}
              </div>
            )}
          </div>

          <div className="flex items-center gap-2 ml-auto shrink-0">
            <UserProfileBadge />

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

        <ConnectionBanner />
        <main className="min-w-0 flex-1">{children}</main>
      </div>

      {activeSeries && (
        <UploadMeetingModal
          open={uploadOpen}
          onClose={() => setUploadOpen(false)}
          seriesId={activeSeries.id}
        />
      )}
    </div>
  );
}

function UserProfileBadge() {
  const t = useT();
  const [user, setUser] = useState<{ name: string; email: string; loggedIn: boolean }>({
    name: "ผู้ใช้ทั่วไป (Demo)",
    email: "user@sara-ai.local",
    loggedIn: false,
  });
  const [loginModal, setLoginModal] = useState(false);

  return (
    <>
      <button
        onClick={() => setLoginModal(true)}
        className="flex items-center gap-1.5 rounded-[var(--radius)] border border-line bg-[var(--bg-surface)] px-2.5 py-1.5 text-[12px] font-medium text-ink-2 hover:bg-sunken hover:text-ink cursor-pointer transition-colors"
      >
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[var(--brand-soft)] text-[11px] font-semibold text-brand">
          {user.name.charAt(0)}
        </span>
        <span className="hidden sm:inline truncate max-w-[120px]">{user.name}</span>
      </button>

      <ConfirmModal
        open={loginModal}
        onClose={() => setLoginModal(false)}
        title={t.pick("เข้าสู่ระบบ SARA (Google Account)", "Sign in to SARA")}
        confirmLabel={t.pick("เข้าสู่ระบบด้วย Google", "Sign in with Google")}
        cancelLabel={t("cancel")}
        onConfirm={() => {
          setUser({ name: "Demo Google User", email: "user@gmail.com", loggedIn: true });
          setLoginModal(false);
        }}
      >
        <div className="space-y-2.5 text-[13px] text-ink-2">
          <p>
            {t.pick(
              "เข้าสู่ระบบด้วยบัญชี Google เพื่อบันทึกประวัติการประชุม สรุปข้อมูล และใช้งานระบบค้นหาอัจฉริยะ (RAG Copilot)",
              "Sign in with your Google Account to sync meetings, summaries, and cross-meeting AI Copilot.",
            )}
          </p>
          <div className="rounded-[var(--radius)] bg-surface-2 p-3 text-[12px] text-ink-3 space-y-1">
            <div>✓ เข้าใช้งานได้ทันทีแบบไม่ต้องรออนุมัติ</div>
            <div>✓ รองรับการแบ่งโฟลเดอร์/คอลเลกชันตามโปรเจกต์</div>
            <div>✓ ปลอดภัยด้วยมาตรฐาน OAuth 2.0 / OpenID Connect</div>
          </div>
        </div>
      </ConfirmModal>
    </>
  );
}

function ConnectionBanner() {
  const t = useT();
  const { lastError, loading } = useApp();

  if (!LIVE || (!lastError && !loading)) return null;

  return (
    <div
      className={cn(
        "no-print flex flex-wrap items-center gap-3 border-b px-5 py-2 text-[13px]",
        lastError
          ? "border-[color-mix(in_srgb,var(--danger)_30%,transparent)] bg-[var(--danger-bg)] text-[var(--danger)]"
          : "border-line bg-surface-2 text-ink-3",
      )}
    >
      {lastError ? (
        <>
          <AlertTriangle size={15} className="shrink-0" />
          <span className="min-w-0 flex-1">{lastError}</span>
          <button
            onClick={() => {
              setError(null);
              void loadFromServer();
            }}
            className="rounded border border-current px-2.5 py-1 text-[12px] font-medium cursor-pointer"
          >
            {t.pick("ลองใหม่", "Retry")}
          </button>
        </>
      ) : (
        <span>{t.pick("กำลังซิงก์ข้อมูลกับเซิร์ฟเวอร์…", "Syncing…")}</span>
      )}
    </div>
  );
}

function Sidebar({
  mobileOpen,
  onClose,
  onOpenUpload,
}: {
  mobileOpen: boolean;
  onClose: () => void;
  onOpenUpload: () => void;
}) {
  const t = useT();
  const router = useRouter();
  const pathname = usePathname();
  const { db, activeSeriesId: storedSeriesId } = useApp();
  const series = db.series;

  const match = pathname.match(/^\/(?:series|collections)\/([^/]+)/);
  const pathSeriesId = match?.[1];

  useEffect(() => {
    if (pathSeriesId) {
      setActiveSeriesId(pathSeriesId);
    }
  }, [pathSeriesId]);

  const activeSeriesId = pathSeriesId || storedSeriesId || series[0]?.id;
  const activeSeries = series.find((s) => s.id === activeSeriesId) ?? series[0];
  const base = `/collections/${activeSeries?.id ?? ""}`;

  const isHomePage = pathname === "/" || pathname === "/collections";

  const [switcherOpen, setSwitcherOpen] = useState(false);
  const [newCollectionOpen, setNewCollectionOpen] = useState(false);
  const [newCollectionName, setNewCollectionName] = useState("");
  const [resetOpen, setResetOpen] = useState(false);

  const mainNav = isHomePage
    ? [
        { href: "/collections", label: t.pick("คอลเลกชันทั้งหมด", "All Collections"), icon: <FolderKanban size={16} />, exact: true },
      ]
    : [
        { href: `${base}`, label: t.pick("ภาพรวมคอลเลกชัน", "Collection Hub"), icon: <Gauge size={16} />, exact: true },
        { href: `${base}/meetings`, label: t.pick("รายการประชุม & สรุป", "Meetings & Transcripts"), icon: <FileStack size={16} /> },
        { href: `${base}/ask`, label: t.pick("Ask SARA Copilot", "Ask SARA Copilot"), icon: <Sparkles size={16} className="text-brand" />, highlight: true },
      ];

  const handleCreateCollection = () => {
    if (!newCollectionName.trim()) return;
    try {
      const createdId = createSeries({
        name: newCollectionName.trim(),
        committee_type: "General Project",
        fiscal_year: new Date().getFullYear() + 543,
        cadence: "adhoc",
        member_ids: [],
      });
      if (createdId) {
        setActiveSeriesId(createdId);
        router.push(`/collections/${createdId}`);
      }
    } catch {
      // fallback handled in store
    }
    setNewCollectionName("");
    setNewCollectionOpen(false);
  };

  return (
    <>
      {mobileOpen && <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={onClose} />}
      <aside
        className={cn(
          "no-print fixed inset-y-0 left-0 z-40 flex w-[264px] shrink-0 flex-col border-r border-[var(--border-subtle)] bg-[var(--bg-surface)] transition-transform lg:sticky lg:top-0 lg:h-dvh lg:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        {/* Brand Logo */}
        <div className="flex items-center justify-between gap-3 px-4 py-4">
          <Link
            href="/collections"
            onClick={onClose}
            className="flex min-w-0 flex-1 items-center gap-2.5 transition-opacity hover:opacity-85"
          >
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

        {/* Collection Selector & Quick Switcher (Hidden on Home Page) */}
        {!isHomePage && (
          <div className="px-3">
            <div className="relative">
              <button
                onClick={() => setSwitcherOpen((v) => !v)}
                className="flex w-full items-center gap-2 rounded-[var(--radius)] border border-[var(--border-subtle)] bg-[var(--bg-surface-hover)] px-3 py-2.5 text-left hover:border-[var(--line-strong)] cursor-pointer transition-colors"
              >
                <FolderKanban size={15} className="text-brand shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-ink-4">Workspace / Collection</p>
                  <p className="mt-0.5 truncate text-[13px] font-medium leading-tight text-ink">
                    {activeSeries?.name ?? "—"}
                  </p>
                </div>
                <ChevronDown size={14} className={cn("shrink-0 text-ink-3 transition-transform", switcherOpen && "rotate-180")} />
              </button>

              {switcherOpen && (
                <div className="fade-up absolute left-0 right-0 top-full z-10 mt-1 max-h-60 overflow-y-auto rounded-[var(--radius)] border border-line bg-[var(--bg-surface)] shadow-[var(--shadow-2)]">
                  {series.map((s) => (
                    <Link
                      key={s.id}
                      href={`/collections/${s.id}`}
                      onClick={() => {
                        setSwitcherOpen(false);
                        onClose();
                      }}
                      className={cn(
                        "block px-3 py-2.5 text-[13px] leading-tight hover:bg-sunken",
                        s.id === activeSeries?.id ? "bg-[var(--brand-soft)] font-medium text-brand" : "text-ink-2",
                      )}
                    >
                      {s.name}
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
                    <span>{t.pick("สร้างคอลเลกชันใหม่", "+ New Collection")}</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Navigation items */}
        <nav className="mt-4 flex-1 space-y-6 overflow-y-auto px-3 pb-4">
          <NavGroup label={t.pick("เมนูหลัก", "Main Menu")}>
            {mainNav.map((item) => {
              const isActive = item.exact
                ? pathname === item.href || (item.href.startsWith("/collections") && pathname === item.href.replace("/collections", "/series"))
                : pathname.startsWith(item.href) || pathname.startsWith(item.href.replace("/collections", "/series"));
              return (
                <NavLink
                  key={item.href}
                  {...item}
                  onNavigate={onClose}
                  active={isActive}
                />
              );
            })}
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

        {/* Reset / Footer */}
        <div className="border-t border-[var(--border-subtle)] px-3 py-3 space-y-2">
          <button
            onClick={() => setResetOpen(true)}
            className="flex w-full items-center justify-center gap-1.5 rounded-[var(--radius)] border border-line px-2 py-2 text-[12px] text-ink-3 hover:bg-sunken hover:text-ink cursor-pointer transition-colors"
          >
            <RotateCcw size={13} />
            {t("resetDemo")}
          </button>
        </div>
      </aside>

      {/* New Collection Modal */}
      <Modal
        open={newCollectionOpen}
        onClose={() => setNewCollectionOpen(false)}
        title={t.pick("สร้างคอลเลกชันใหม่", "Create New Collection")}
      >
        <div className="space-y-4 pt-1">
          <p className="text-[13px] text-ink-3">
            {t.pick(
              "คอลเลกชันช่วยจัดกลุ่มการประชุมตามโปรเจกต์ ทีม หรือลูกค้า เพื่อให้ AI สามารถตอบคำถามข้ามการประชุมได้อย่างแม่นยำ",
              "Collections group meetings by project, team, or client for cross-meeting AI analysis.",
            )}
          </p>
          <div>
            <label className="block text-[12px] font-medium text-ink-2 mb-1.5">
              {t.pick("ชื่อคอลเลกชัน / โปรเจกต์", "Collection / Project Name")}
            </label>
            <input
              type="text"
              value={newCollectionName}
              onChange={(e) => setNewCollectionName(e.target.value)}
              placeholder="e.g. Q4 Growth & Marketing / Sprint Standups"
              className="w-full rounded-[var(--radius)] border border-line bg-[var(--bg-surface)] px-3 py-2 text-[13px] text-ink focus:border-brand focus:outline-none"
              autoFocus
              onKeyDown={(e) => e.key === "Enter" && handleCreateCollection()}
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button
              onClick={() => setNewCollectionOpen(false)}
              className="rounded-[var(--radius)] border border-line px-3 py-1.5 text-[13px] text-ink-2 hover:bg-sunken cursor-pointer"
            >
              {t("cancel")}
            </button>
            <button
              onClick={handleCreateCollection}
              disabled={!newCollectionName.trim()}
              className="rounded-[var(--radius)] bg-brand px-4 py-1.5 text-[13px] font-medium text-white hover:bg-[var(--brand-hover)] disabled:opacity-50 cursor-pointer"
            >
              {t.pick("สร้างคอลเลกชัน", "Create")}
            </button>
          </div>
        </div>
      </Modal>

      <ConfirmModal
        open={resetOpen}
        onClose={() => setResetOpen(false)}
        title={t("resetDemo")}
        confirmLabel={t.pick("ล้างข้อมูล", "Reset")}
        cancelLabel={t("cancel")}
        onConfirm={() => {
          resetDemo();
          setResetOpen(false);
        }}
      >
        {t.pick(
          "การประชุมและสรุปที่สร้างระหว่างทดลองใช้จะหายทั้งหมด แล้วกลับไปเป็นข้อมูลตั้งต้นของเดโม",
          "Everything created during this session will be discarded and replaced with demo seed data.",
        )}
      </ConfirmModal>
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

function SaraMark() {
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
            {desc && <p className="mt-1.5 max-w-2xl text-[13.5px] leading-relaxed text-ink-3">{desc}</p>}
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
