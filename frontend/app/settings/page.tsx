"use client";

import { useState } from "react";
import {
  Activity,
  Bot,
  Check,
  CheckCircle2,
  Database,
  Globe,
  HardDrive,
  Laptop,
  Moon,
  RotateCcw,
  Server,
  Settings,
  ShieldCheck,
  Sun,
  User,
  Zap,
} from "lucide-react";
import { PageBody, PageHeader } from "@/components/app-shell";
import { Badge, Button, Card, ConfirmModal, cn } from "@/components/ui";
import { useT } from "@/lib/i18n";
import { LIVE, resetDemo, toggleTheme, useApp } from "@/lib/store";

export default function SettingsPage() {
  const t = useT();
  const { theme, db } = useApp();
  const [resetOpen, setResetOpen] = useState(false);

  const [googleConnected, setGoogleConnected] = useState(false);

  const totalMeetings = db.meetings.length;
  const totalCollections = db.series.length;
  const totalResolutions = db.resolutions.length;

  return (
    <>
      <PageHeader
        title={t.pick("การตั้งค่าระบบ (Settings & Workspace)", "Settings & Workspace")}
        desc={t.pick(
          "จัดการบัญชีผู้ใช้ โหมดการแสดงผล และตรวจสอบสถานะการเชื่อมต่อ AI Backend",
          "Manage account, appearance preferences, and local AI gateway integration.",
        )}
      />

      <PageBody className="space-y-6 max-w-[900px] pb-16">
        {/* User Profile & Authentication */}
        <Card className="p-6 space-y-5">
          <div className="flex items-center justify-between border-b border-line pb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--brand-soft)] text-brand text-[18px] font-bold">
                U
              </div>
              <div>
                <h3 className="text-[16px] font-semibold text-ink">ผู้ใช้งานทั่วไป (Demo Workspace)</h3>
                <p className="text-[12.5px] text-ink-3">user@sara-ai.local · สิทธิ์ใช้งานระดับ Workspace Admin</p>
              </div>
            </div>
            <span className="rounded-full bg-ok/10 px-2.5 py-1 text-[11.5px] font-semibold text-ok">
              Active
            </span>
          </div>

          <div className="space-y-3">
            <h4 className="text-[13.5px] font-semibold text-ink">การเชื่อมต่อบัญชีภายนอก (OAuth 2.0)</h4>
            <div className="flex items-center justify-between rounded-[var(--radius)] border border-line bg-surface-2 p-3.5">
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white border border-line shadow-xs">
                  <span className="font-bold text-red-500 text-[14px]">G</span>
                </div>
                <div>
                  <p className="text-[13px] font-medium text-ink">Google Account</p>
                  <p className="text-[11.5px] text-ink-3">
                    {googleConnected ? "เชื่อมต่อแล้ว (user@gmail.com)" : "ยังไม่ได้เชื่อมต่อ Google OAuth"}
                  </p>
                </div>
              </div>

              <Button
                variant={googleConnected ? "secondary" : "primary"}
                onClick={() => setGoogleConnected(!googleConnected)}
              >
                {googleConnected ? t.pick("ยกเลิกการเชื่อมต่อ", "Disconnect") : t.pick("เชื่อมต่อด้วย Google", "Connect Google")}
              </Button>
            </div>
          </div>
        </Card>

        {/* Workspace Usage & Stats */}
        <Card className="p-6 space-y-4">
          <h3 className="text-[15.5px] font-semibold text-ink flex items-center gap-2">
            <HardDrive size={17} className="text-brand" />
            <span>{t.pick("ปริมาณการใช้งานในระบบ (Workspace Quotas)", "Workspace Storage & Quota")}</span>
          </h3>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="rounded-[var(--radius)] bg-surface-2 p-3.5 text-center">
              <p className="text-[11.5px] text-ink-3">คอลเลกชัน / โฟลเดอร์</p>
              <p className="text-[20px] font-bold text-brand mt-1">{totalCollections}</p>
            </div>
            <div className="rounded-[var(--radius)] bg-surface-2 p-3.5 text-center">
              <p className="text-[11.5px] text-ink-3">การประชุมทั้งหมด</p>
              <p className="text-[20px] font-bold text-ink mt-1">{totalMeetings}</p>
            </div>
            <div className="rounded-[var(--radius)] bg-surface-2 p-3.5 text-center">
              <p className="text-[11.5px] text-ink-3">ข้อสรุป & มติที่สกัดได้</p>
              <p className="text-[20px] font-bold text-ok mt-1">{totalResolutions}</p>
            </div>
          </div>
        </Card>

        {/* Appearance & Themes */}
        <Card className="p-6 space-y-4">
          <h3 className="text-[15.5px] font-semibold text-ink flex items-center gap-2">
            <Laptop size={17} className="text-brand" />
            <span>{t.pick("ธีมและการแสดงผล (Appearance)", "Appearance")}</span>
          </h3>

          <div className="grid grid-cols-2 gap-3 max-w-sm">
            <button
              onClick={() => theme === "dark" && toggleTheme()}
              className={cn(
                "flex items-center justify-center gap-2 rounded-[var(--radius)] border p-3 text-[13px] font-medium transition-all cursor-pointer",
                theme === "light"
                  ? "border-brand bg-[var(--brand-soft)] text-brand shadow-xs font-semibold"
                  : "border-line bg-surface-2 text-ink-3 hover:text-ink",
              )}
            >
              <Sun size={15} />
              <span>Light Mode</span>
            </button>

            <button
              onClick={() => theme === "light" && toggleTheme()}
              className={cn(
                "flex items-center justify-center gap-2 rounded-[var(--radius)] border p-3 text-[13px] font-medium transition-all cursor-pointer",
                theme === "dark"
                  ? "border-brand bg-[var(--brand-soft)] text-brand shadow-xs font-semibold"
                  : "border-line bg-surface-2 text-ink-3 hover:text-ink",
              )}
            >
              <Moon size={15} />
              <span>Dark Mode</span>
            </button>
          </div>
        </Card>

        {/* AI Gateway & System Connection Health */}
        <Card className="p-6 space-y-4">
          <h3 className="text-[15.5px] font-semibold text-ink flex items-center gap-2">
            <Server size={17} className="text-brand" />
            <span>{t.pick("สถานะระบบ & AI Infrastructure", "System & AI Infrastructure")}</span>
          </h3>

          <div className="space-y-2 text-[12.5px]">
            <div className="flex items-center justify-between border-b border-line py-2">
              <span className="text-ink-3">ASR Service (AI4Thai / Pathumma)</span>
              <span className="font-medium text-ok flex items-center gap-1">
                <CheckCircle2 size={13} /> เชื่อมต่อพร้อมใช้งาน
              </span>
            </div>
            <div className="flex items-center justify-between border-b border-line py-2">
              <span className="text-ink-3">LLM Extraction Engine (ThaiLLM 8B / Qwen 3.5)</span>
              <span className="font-medium text-ok flex items-center gap-1">
                <CheckCircle2 size={13} /> ปกติ (Chunked Streaming)
              </span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-ink-3">FastMCP Action & Email Dispatch Server</span>
              <span className="font-medium text-ok flex items-center gap-1">
                <CheckCircle2 size={13} /> Active (Port 8001)
              </span>
            </div>
          </div>
        </Card>

        {/* Danger Zone: Reset Workspace */}
        <Card className="p-6 border-red-500/20 bg-red-500/5 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-[14px] font-semibold text-red-600 dark:text-red-400">
                {t.pick("ล้างข้อมูลและรีเซ็ตเดโม (Reset Workspace)", "Reset Demo Workspace")}
              </h4>
              <p className="text-[12.5px] text-ink-3 mt-0.5">
                ล้างข้อมูลการประชุมและประวัติคำถามทั้งหมดกลับเป็นค่าเริ่มต้น
              </p>
            </div>
            <Button variant="danger" icon={<RotateCcw size={14} />} onClick={() => setResetOpen(true)}>
              {t.pick("รีเซ็ตเดโม", "Reset Data")}
            </Button>
          </div>
        </Card>
      </PageBody>

      <ConfirmModal
        open={resetOpen}
        onClose={() => setResetOpen(false)}
        title={t("resetDemo")}
        confirmLabel={t.pick("ล้างข้อมูล", "Reset")}
        cancelLabel={t("cancel")}
        destructive
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
