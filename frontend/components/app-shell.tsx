"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  AlertTriangle,
  BadgeCheck,
  CalendarClock,
  ChevronDown,
  FileStack,
  Gauge,
  Languages,
  ListChecks,
  Menu,
  Moon,
  RotateCcw,
  ScrollText,
  Send,
  ShieldCheck,
  Sun,
  Users,
  X,
} from "lucide-react";
import { useT } from "@/lib/i18n";
import { LIVE, hydrate, loadFromServer, resetDemo, setError, setLang, toggleTheme, useApp } from "@/lib/store";
import { ConfirmModal, cn } from "./ui";

/* ── โครงหน้า: แถบซ้าย + เนื้อหา ─────────────────────────────────────── */

export function AppShell({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => hydrate(), []);

  return (
    <div className="flex min-h-dvh bg-paper">
      <Sidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <button
          onClick={() => setMobileOpen(true)}
          className="no-print sticky top-0 z-20 flex items-center gap-2 border-b border-line bg-surface px-4 py-3 text-sm font-medium text-ink lg:hidden cursor-pointer"
        >
          <Menu size={18} />
          SARA
        </button>
        <ConnectionBanner />
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}

/** ความล้มเหลวของการซิงก์ต้องไม่เงียบ ไม่งั้นผู้ใช้จะคิดว่าบันทึกแล้วทั้งที่ยังไม่ได้บันทึก */
function ConnectionBanner() {
  const t = useT();
  const { lastError, loading } = useApp();

  if (!LIVE || (!lastError && !loading)) return null;

  return (
    <div
      className={cn(
        "no-print flex flex-wrap items-center gap-3 border-b px-5 py-2.5 text-[13px]",
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

function Sidebar({ mobileOpen, onClose }: { mobileOpen: boolean; onClose: () => void }) {
  const t = useT();
  const pathname = usePathname();
  const { db, theme, lang } = useApp();
  const series = db.series;
  const pendingActions = db.actions.filter((a) => a.status === "pending_approval").length;

  const match = pathname.match(/^\/series\/([^/]+)/);
  const activeSeriesId = match?.[1] ?? series[0]?.id;
  const activeSeries = series.find((s) => s.id === activeSeriesId) ?? series[0];
  const base = `/series/${activeSeries?.id ?? ""}`;

  const [switcherOpen, setSwitcherOpen] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);

  const seriesNav = [
    { href: base, label: t("navDashboard"), icon: <Gauge size={16} />, exact: true },
    { href: `${base}/resolutions`, label: t("navResolutions"), icon: <ListChecks size={16} /> },
    { href: `${base}/meetings`, label: t("navMeetings"), icon: <FileStack size={16} /> },
    { href: `${base}/agenda`, label: t("navAgenda"), icon: <ScrollText size={16} /> },
    { href: `${base}/ask`, label: t("navAsk"), icon: <CalendarClock size={16} /> },
  ];

  const orgNav = [
    { href: "/people", label: t("navPeople"), icon: <Users size={16} /> },
    { href: "/actions", label: t("navActions"), icon: <Send size={16} />, badge: pendingActions },
    { href: "/audit", label: t("navAudit"), icon: <ShieldCheck size={16} /> },
  ];

  return (
    <>
      {mobileOpen && <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={onClose} />}
      <aside
        className={cn(
          "no-print fixed inset-y-0 left-0 z-40 flex w-[264px] shrink-0 flex-col border-r border-line bg-surface transition-transform lg:sticky lg:top-0 lg:h-dvh lg:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        {/* ตราสัญลักษณ์ */}
        <div className="flex items-center gap-3 px-4 py-4">
          <SaraMark />
          <div className="min-w-0 flex-1">
            <p className="text-[15px] font-semibold leading-none tracking-tight text-ink">SARA</p>
            <p className="mt-1 truncate text-[11px] leading-none text-ink-3">{t("appTagline")}</p>
          </div>
          <button onClick={onClose} className="rounded p-1 text-ink-3 hover:bg-sunken lg:hidden cursor-pointer">
            <X size={16} />
          </button>
        </div>

        {/* ตัวสลับชุดการประชุม */}
        <div className="px-3">
          <div className="relative">
            <button
              onClick={() => setSwitcherOpen((v) => !v)}
              className="flex w-full items-center gap-2 rounded-[var(--radius)] border border-line bg-surface-2 px-3 py-2.5 text-left hover:border-[var(--line-strong)] cursor-pointer"
            >
              <div className="min-w-0 flex-1">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-ink-4">{t("navSeries")}</p>
                <p className="mt-0.5 truncate text-[13px] font-medium leading-tight text-ink">
                  {activeSeries?.name ?? "—"}
                </p>
              </div>
              <ChevronDown size={14} className={cn("shrink-0 text-ink-3 transition-transform", switcherOpen && "rotate-180")} />
            </button>

            {switcherOpen && (
              <div className="fade-up absolute left-0 right-0 top-full z-10 mt-1 overflow-hidden rounded-[var(--radius)] border border-line bg-surface shadow-[var(--shadow-2)]">
                {series.map((s) => (
                  <Link
                    key={s.id}
                    href={`/series/${s.id}`}
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
                <Link
                  href="/series"
                  onClick={() => {
                    setSwitcherOpen(false);
                    onClose();
                  }}
                  className="block border-t border-line px-3 py-2.5 text-[12.5px] font-medium text-ink-3 hover:bg-sunken"
                >
                  {t.pick("จัดการชุดการประชุมทั้งหมด →", "Manage all series →")}
                </Link>
              </div>
            )}
          </div>
        </div>

        <nav className="mt-4 flex-1 space-y-6 overflow-y-auto px-3 pb-4">
          <NavGroup label={t.pick("ชุดการประชุมนี้", "This series")}>
            {seriesNav.map((item) => (
              <NavLink
                key={item.href}
                {...item}
                onNavigate={onClose}
                active={item.exact ? pathname === item.href : pathname.startsWith(item.href)}
              />
            ))}
          </NavGroup>

          <NavGroup label={t.pick("ระดับองค์กร", "Organization")}>
            {orgNav.map((item) => (
              <NavLink key={item.href} {...item} onNavigate={onClose} active={pathname.startsWith(item.href)} />
            ))}
          </NavGroup>
        </nav>

        {/* เครื่องมือท้ายแถบ */}
        <div className="space-y-2 border-t border-line px-3 py-3">
          <div className="flex gap-2">
            <button
              onClick={() => setLang(lang === "th" ? "en" : "th")}
              className="flex flex-1 items-center justify-center gap-1.5 rounded-[var(--radius)] border border-line px-2 py-2 text-[12px] font-medium text-ink-2 hover:bg-sunken cursor-pointer"
              title={lang === "th" ? "Switch to English" : "เปลี่ยนเป็นภาษาไทย"}
            >
              <Languages size={14} />
              {lang === "th" ? "ไทย" : "EN"}
            </button>
            <button
              onClick={toggleTheme}
              className="flex flex-1 items-center justify-center gap-1.5 rounded-[var(--radius)] border border-line px-2 py-2 text-[12px] font-medium text-ink-2 hover:bg-sunken cursor-pointer"
              title={t("theme")}
            >
              {theme === "light" ? <Moon size={14} /> : <Sun size={14} />}
              {theme === "light" ? t.pick("มืด", "Dark") : t.pick("สว่าง", "Light")}
            </button>
          </div>
          <button
            onClick={() => setResetOpen(true)}
            className="flex w-full items-center justify-center gap-1.5 rounded-[var(--radius)] px-2 py-2 text-[12px] text-ink-3 hover:bg-sunken hover:text-ink cursor-pointer"
          >
            <RotateCcw size={13} />
            {t("resetDemo")}
          </button>
        </div>
      </aside>

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
          "การประชุม มติ และวาระที่สร้างระหว่างทดลองใช้จะหายทั้งหมด แล้วกลับไปเป็นข้อมูลตั้งต้นของเดโม",
          "Everything created during this session will be discarded and replaced with the demo seed data.",
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
  active,
  badge,
  onNavigate,
}: {
  href: string;
  label: string;
  icon: React.ReactNode;
  active: boolean;
  badge?: number;
  onNavigate?: () => void;
}) {
  return (
    <Link
      href={href}
      onClick={onNavigate}
      className={cn(
        "flex items-center gap-2.5 rounded-[var(--radius)] px-3 py-2 text-[13.5px] font-medium transition-colors",
        active ? "bg-[var(--brand-soft)] text-brand" : "text-ink-2 hover:bg-sunken hover:text-ink",
      )}
    >
      <span className={active ? "text-brand" : "text-ink-3"}>{icon}</span>
      <span className="flex-1 truncate">{label}</span>
      {badge ? (
        <span className="tnum rounded-full bg-[var(--danger)] px-1.5 py-0.5 text-[10px] font-semibold text-white">
          {badge}
        </span>
      ) : null}
    </Link>
  );
}

/** ตราประจำระบบ — วงกลมหมึกน้ำเงิน ขอบทอง สื่อเอกสารที่ผ่านการรับรอง */
function SaraMark() {
  return (
    <div className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand">
      <span className="absolute inset-[3px] rounded-full border border-[color-mix(in_srgb,var(--seal)_60%,transparent)]" />
      <BadgeCheck size={17} className="text-[var(--brand-ink)]" strokeWidth={2.1} />
    </div>
  );
}

/* ── หัวหน้าเพจ ──────────────────────────────────────────────────────── */

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
    <header className="border-b border-line bg-surface">
      <div className="mx-auto max-w-[1180px] px-5 pb-5 pt-6 sm:px-8">
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
  return <div className={cn("mx-auto max-w-[1180px] px-5 py-6 sm:px-8", className)}>{children}</div>;
}
