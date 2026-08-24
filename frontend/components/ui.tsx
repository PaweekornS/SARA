"use client";

/** ชิ้นส่วน UI พื้นฐานที่ทั้งแอปใช้ร่วมกัน — ไม่มี dependency นอกจาก Tailwind + lucide */

import React, { useEffect, useRef } from "react";
import { AlertTriangle, X } from "lucide-react";
import type { ResolutionStatus } from "@/lib/types";

export function cn(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

/* ── Button ──────────────────────────────────────────────────────────── */

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger" | "seal";
  size?: "sm" | "md" | "lg";
  icon?: React.ReactNode;
};

const BTN_VARIANT: Record<NonNullable<ButtonProps["variant"]>, string> = {
  primary: "bg-brand text-[var(--brand-ink)] hover:bg-[var(--brand-hover)] shadow-[var(--shadow-1)]",
  secondary: "bg-surface text-ink border border-[var(--line-strong)] hover:bg-sunken",
  ghost: "text-ink-2 hover:bg-sunken hover:text-ink",
  danger: "bg-[var(--danger)] text-white hover:opacity-90",
  seal: "bg-[var(--seal-soft)] text-[var(--seal)] border border-[color-mix(in_srgb,var(--seal)_28%,transparent)] hover:bg-[color-mix(in_srgb,var(--seal)_14%,transparent)]",
};

const BTN_SIZE: Record<NonNullable<ButtonProps["size"]>, string> = {
  sm: "h-8 px-3 text-[13px] gap-1.5",
  md: "h-10 px-4 text-sm gap-2",
  lg: "h-11 px-5 text-[15px] gap-2",
};

export function Button({ variant = "secondary", size = "md", icon, className, children, ...rest }: ButtonProps) {
  return (
    <button
      {...rest}
      className={cn(
        "inline-flex items-center justify-center rounded-[var(--radius)] font-medium transition-colors",
        "disabled:opacity-45 disabled:pointer-events-none active:translate-y-px cursor-pointer",
        BTN_VARIANT[variant],
        BTN_SIZE[size],
        className,
      )}
    >
      {icon}
      {children}
    </button>
  );
}

/* ── Card ────────────────────────────────────────────────────────────── */

export function Card({ className, children, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      {...rest}
      className={cn("rounded-[var(--radius)] border border-line bg-surface shadow-[var(--shadow-1)]", className)}
    >
      {children}
    </div>
  );
}

export function CardHead({
  title,
  desc,
  right,
  className,
}: {
  title: React.ReactNode;
  desc?: React.ReactNode;
  right?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-start justify-between gap-4 border-b border-line px-5 py-4", className)}>
      <div className="min-w-0">
        <h2 className="text-[15px] font-semibold leading-tight text-ink">{title}</h2>
        {desc && <p className="mt-1 text-[13px] leading-snug text-ink-3">{desc}</p>}
      </div>
      {right && <div className="shrink-0">{right}</div>}
    </div>
  );
}

/* ── สถานะมติ ─────────────────────────────────────────────────────────── */

const STATUS_STYLE: Record<ResolutionStatus, { bg: string; fg: string }> = {
  proposed: { bg: "var(--st-proposed-bg)", fg: "var(--st-proposed)" },
  confirmed: { bg: "var(--st-confirmed-bg)", fg: "var(--st-confirmed)" },
  in_progress: { bg: "var(--st-progress-bg)", fg: "var(--st-progress)" },
  blocked: { bg: "var(--st-blocked-bg)", fg: "var(--st-blocked)" },
  done: { bg: "var(--st-done-bg)", fg: "var(--st-done)" },
  cancelled: { bg: "var(--st-cancelled-bg)", fg: "var(--st-cancelled)" },
  superseded: { bg: "var(--st-superseded-bg)", fg: "var(--st-superseded)" },
};

/** สีจุดสถานะ ใช้ตอนต้องการแค่จุดเดียวไม่ใช่ป้ายเต็ม */
export function statusColor(status: ResolutionStatus) {
  return STATUS_STYLE[status].fg;
}

export function StatusPill({
  status,
  label,
  size = "md",
}: {
  status: ResolutionStatus;
  label: string;
  size?: "sm" | "md";
}) {
  const s = STATUS_STYLE[status];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full font-medium whitespace-nowrap",
        size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-[12px]",
      )}
      style={{ background: s.bg, color: s.fg }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: s.fg }} />
      {label}
    </span>
  );
}

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: React.ReactNode;
  tone?: "neutral" | "brand" | "danger" | "warn" | "ok" | "seal";
  className?: string;
}) {
  const tones: Record<string, string> = {
    neutral: "bg-sunken text-ink-2",
    brand: "bg-[var(--brand-soft)] text-brand",
    danger: "bg-[var(--danger-bg)] text-[var(--danger)]",
    warn: "bg-[var(--warn-bg)] text-[var(--warn)]",
    ok: "bg-[var(--ok-bg)] text-[var(--ok)]",
    seal: "bg-[var(--seal-soft)] text-[var(--seal)]",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium whitespace-nowrap",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

/* ── ฟอร์ม ───────────────────────────────────────────────────────────── */

export function Field({
  label,
  hint,
  children,
  className,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <label className={cn("block", className)}>
      <span className="mb-1.5 block text-[13px] font-medium text-ink-2">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-[12px] text-ink-3">{hint}</span>}
    </label>
  );
}

const inputCls =
  "w-full rounded-[var(--radius)] border border-[var(--line-strong)] bg-surface px-3 py-2 text-sm text-ink " +
  "placeholder:text-ink-4 focus:border-brand focus:outline-none focus:ring-2 focus:ring-[color-mix(in_srgb,var(--brand)_18%,transparent)]";

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cn(inputCls, "h-10", props.className)} />;
}

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cn(inputCls, "min-h-[88px] leading-relaxed", props.className)} />;
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={cn(inputCls, "h-10 cursor-pointer pr-8", props.className)} />;
}

/* ── Modal ───────────────────────────────────────────────────────────── */

export function Modal({
  open,
  onClose,
  title,
  desc,
  children,
  footer,
  width = "max-w-lg",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  desc?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  width?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    ref.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 sm:p-8">
      <div className="fixed inset-0 bg-[rgba(10,15,25,0.45)] backdrop-blur-[2px]" onClick={onClose} />
      <div
        ref={ref}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cn(
          "fade-up relative z-10 w-full rounded-xl border border-line bg-surface shadow-[var(--shadow-3)] outline-none",
          width,
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div>
            <h3 className="text-[15px] font-semibold text-ink">{title}</h3>
            {desc && <p className="mt-1 text-[13px] text-ink-3">{desc}</p>}
          </div>
          <button
            onClick={onClose}
            className="-mr-1 -mt-1 rounded p-1.5 text-ink-3 hover:bg-sunken hover:text-ink cursor-pointer"
            aria-label="ปิด"
          >
            <X size={16} />
          </button>
        </div>
        <div className="px-5 py-4">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-line px-5 py-3.5">{footer}</div>}
      </div>
    </div>
  );
}

/**
 * กล่องยืนยันการทำลายข้อมูล
 * ตั้งใจไม่ใช้ window.confirm() เพราะหน้าตาเป็นของเบราว์เซอร์ ไม่ใช่ของระบบ
 * และอ่านยากกว่าเมื่อข้อความเป็นภาษาไทยยาว ๆ
 */
export function ConfirmModal({
  open,
  onClose,
  onConfirm,
  title,
  confirmLabel,
  cancelLabel = "ยกเลิก",
  children,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  confirmLabel: string;
  cancelLabel?: string;
  children: React.ReactNode;
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      width="max-w-md"
      footer={
        <>
          <Button onClick={onClose}>{cancelLabel}</Button>
          <Button variant="danger" onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--danger-bg)] text-[var(--danger)]">
          <AlertTriangle size={16} />
        </span>
        <p className="text-[13.5px] leading-relaxed text-ink-2">{children}</p>
      </div>
    </Modal>
  );
}

/* ── ส่วนประกอบเล็ก ๆ ────────────────────────────────────────────────── */

export function EmptyState({
  icon,
  title,
  desc,
  action,
}: {
  icon?: React.ReactNode;
  title: string;
  desc?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      {icon && (
        <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-sunken text-ink-3">{icon}</div>
      )}
      <p className="text-sm font-medium text-ink">{title}</p>
      {desc && <p className="mt-1.5 max-w-sm text-[13px] leading-relaxed text-ink-3">{desc}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/** แถบความมั่นใจของ AI — FR-M3-06 / FR-M9-05 */
export function ConfidenceBar({ value, showLabel = true }: { value: number; showLabel?: boolean }) {
  const pct = Math.round(value * 100);
  const tone = value >= 0.85 ? "var(--ok)" : value >= 0.7 ? "var(--warn)" : "var(--danger)";
  return (
    <span className="inline-flex items-center gap-2 whitespace-nowrap">
      <span className="h-1.5 w-14 overflow-hidden rounded-full bg-sunken">
        <span className="block h-full rounded-full" style={{ width: `${pct}%`, background: tone }} />
      </span>
      {showLabel && (
        <span className="tnum text-[11px] font-medium" style={{ color: tone }}>
          {pct}%
        </span>
      )}
    </span>
  );
}

export function StatTile({
  label,
  value,
  unit,
  tone = "neutral",
  hint,
  icon,
}: {
  label: string;
  value: React.ReactNode;
  unit?: string;
  tone?: "neutral" | "danger" | "warn" | "ok" | "brand";
  hint?: string;
  icon?: React.ReactNode;
}) {
  const colors: Record<string, string> = {
    neutral: "var(--ink)",
    danger: "var(--danger)",
    warn: "var(--warn)",
    ok: "var(--ok)",
    brand: "var(--brand)",
  };
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[12.5px] font-medium text-ink-3">{label}</span>
        {icon && <span className="text-ink-4">{icon}</span>}
      </div>
      <div className="mt-2 flex items-baseline gap-1.5">
        <span className="tnum text-[30px] font-semibold leading-none tracking-tight" style={{ color: colors[tone] }}>
          {value}
        </span>
        {unit && <span className="text-[13px] font-medium text-ink-3">{unit}</span>}
      </div>
      {hint && <p className="mt-1.5 text-[12px] leading-snug text-ink-3">{hint}</p>}
    </Card>
  );
}

/** อ้างอิงคำต่อคำจาก transcript — ใช้ทุกที่ที่ต้องโชว์หลักฐาน */
export function EvidenceQuote({
  text,
  meta,
  className,
}: {
  text: string;
  meta?: React.ReactNode;
  className?: string;
}) {
  return (
    <blockquote
      className={cn(
        "rounded-r-[var(--radius)] border-l-2 border-[var(--seal)] bg-[var(--seal-soft)] px-3.5 py-2.5",
        className,
      )}
    >
      <p className="text-[13px] leading-relaxed text-ink-2">“{text}”</p>
      {meta && <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[11.5px] text-ink-3">{meta}</div>}
    </blockquote>
  );
}

export function Segmented<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T;
  onChange: (v: T) => void;
  options: Array<{ value: T; label: string; count?: number }>;
}) {
  return (
    <div className="inline-flex flex-wrap gap-1 rounded-[var(--radius)] bg-sunken p-1">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "cursor-pointer rounded-[6px] px-2.5 py-1.5 text-[13px] font-medium transition-colors",
            value === o.value ? "bg-surface text-ink shadow-[var(--shadow-1)]" : "text-ink-3 hover:text-ink",
          )}
        >
          {o.label}
          {o.count !== undefined && <span className="tnum ml-1.5 text-[11px] text-ink-4">{o.count}</span>}
        </button>
      ))}
    </div>
  );
}
