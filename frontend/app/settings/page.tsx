"use client";

import { HardDrive, Laptop, LogOut, Moon, Sun } from "lucide-react";
import { PageBody, PageHeader, logout } from "@/components/app-shell";
import { Button, Card, Loading, cn } from "@/components/ui";
import { useCollections, useMe } from "@/lib/data";
import { useT } from "@/lib/i18n";
import { toggleTheme, usePrefs } from "@/lib/store";

export default function SettingsPage() {
  const t = useT();
  const theme = usePrefs((p) => p.theme);
  const { data: me } = useMe();
  const { data: collections = [] } = useCollections();

  const totalMeetings = collections.reduce((n, c) => n + c.meeting_count, 0);
  const openTasks = collections.reduce((n, c) => n + c.open_action_count, 0);

  return (
    <>
      <PageHeader
        title={t.pick("การตั้งค่า", "Settings")}
        desc={t.pick("บัญชีผู้ใช้และการแสดงผล", "Account and appearance")}
      />

      <PageBody className="space-y-6 max-w-[900px] pb-16">
        <Card className="p-6">
          {!me ? (
            <Loading />
          ) : (
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                {me.picture ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={me.picture} alt="" className="h-12 w-12 rounded-full" referrerPolicy="no-referrer" />
                ) : (
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--brand-soft)] text-[18px] font-bold text-brand">
                    {(me.name || me.email).charAt(0).toUpperCase()}
                  </div>
                )}
                <div>
                  <h3 className="text-[16px] font-semibold text-ink">{me.name}</h3>
                  <p className="text-[12.5px] text-ink-3">
                    {me.email} · {me.provider === "google" ? "Google" : t.pick("บัญชีทดลอง", "Demo account")}
                  </p>
                </div>
              </div>
              <Button icon={<LogOut size={14} />} onClick={() => void logout()}>
                {t("logout")}
              </Button>
            </div>
          )}
        </Card>

        <Card className="p-6 space-y-4">
          <h3 className="flex items-center gap-2 text-[15.5px] font-semibold text-ink">
            <HardDrive size={17} className="text-brand" />
            <span>{t.pick("ข้อมูลของคุณ", "Your data")}</span>
          </h3>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Stat label={t.pick("คอลเลกชัน", "Collections")} value={collections.length} tone="text-brand" />
            <Stat label={t.pick("การประชุมทั้งหมด", "Meetings")} value={totalMeetings} tone="text-ink" />
            <Stat label={t.pick("งานค้าง", "Open tasks")} value={openTasks} tone="text-ok" />
          </div>
        </Card>

        <Card className="p-6 space-y-4">
          <h3 className="flex items-center gap-2 text-[15.5px] font-semibold text-ink">
            <Laptop size={17} className="text-brand" />
            <span>{t.pick("ธีมและการแสดงผล", "Appearance")}</span>
          </h3>
          <div className="grid max-w-sm grid-cols-2 gap-3">
            {(["light", "dark"] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => theme !== mode && toggleTheme()}
                className={cn(
                  "flex items-center justify-center gap-2 rounded-[var(--radius)] border p-3 text-[13px] font-medium transition-all cursor-pointer",
                  theme === mode
                    ? "border-brand bg-[var(--brand-soft)] font-semibold text-brand shadow-xs"
                    : "border-line bg-surface-2 text-ink-3 hover:text-ink",
                )}
              >
                {mode === "light" ? <Sun size={15} /> : <Moon size={15} />}
                <span>{mode === "light" ? "Light Mode" : "Dark Mode"}</span>
              </button>
            ))}
          </div>
        </Card>
      </PageBody>
    </>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="rounded-[var(--radius)] bg-surface-2 p-3.5 text-center">
      <p className="text-[11.5px] text-ink-3">{label}</p>
      <p className={cn("mt-1 text-[20px] font-bold", tone)}>{value}</p>
    </div>
  );
}
