"use client";

/** M8 — ถาม-ตอบข้ามการประชุม ทุกคำตอบต้องอ้างอิงกลับได้เสมอ (FR-M8-02) */

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Clock, CornerDownLeft, Database, FileSearch, Loader2, Search, Sparkles, Trash2 } from "lucide-react";
import { PageBody, PageHeader } from "@/components/app-shell";
import { ResolutionDrawer } from "@/components/resolution-detail";
import { Badge, Button, Card, EmptyState, EvidenceQuote, Input, cn } from "@/components/ui";
import { useT } from "@/lib/i18n";
import * as api from "@/lib/api";
import { clearQa, formatThaiDate, formatTimecode, useApp } from "@/lib/store";

const SUGGESTIONS = [
  "เรื่องระบบสารบรรณอิเล็กทรอนิกส์ เคยมีมติว่าอะไรบ้าง",
  "มติเรื่องจัดซื้อครุภัณฑ์คอมพิวเตอร์ ตอนนี้ถึงไหนแล้ว",
  "คณะทำงานจัดทำคำของบประมาณ แต่งตั้งหรือยัง",
  "มีเรื่องอะไรที่ฝ่ายพัสดุรับผิดชอบบ้าง",
];

export default function AskPage() {
  const t = useT();
  const { db } = useApp();
  const seriesId = useParams<{ id: string }>().id;
  const history = db.qa[seriesId] ?? [];

  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [openRes, setOpenRes] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history.length, busy]);

  const ask = async (q: string) => {
    const text = q.trim();
    if (!text || busy) return;
    setQuestion("");
    setBusy(true);
    try {
      await api.askSeries(seriesId, text);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader
        title={t("navAsk")}
        desc={t.pick(
          "ค้นจากทะเบียนมติก่อนเสมอ ถ้าไม่พบจึงค่อยไล่จากบันทึกคำต่อคำ และจะอ้างอิงกลับไปที่การประชุมและ timestamp ทุกครั้ง",
          "Answers come from the resolution table first, transcript search second — always with citations.",
        )}
        actions={
          history.length > 0 ? (
            <Button icon={<Trash2 size={15} />} onClick={() => clearQa(seriesId)}>
              {t.pick("ล้างประวัติคำถาม", "Clear history")}
            </Button>
          ) : undefined
        }
      />

      <PageBody className="space-y-4">
        {history.length === 0 && !busy && (
          <Card className="border-dashed">
            <EmptyState
              icon={<Sparkles size={20} />}
              title={t.pick("ลองถามเรื่องที่ค้างมานาน", "Ask about something long-running")}
              desc={t.pick(
                "ระบบมองเห็นทุกการประชุมในชุดนี้พร้อมกัน ไม่ต้องเปิดรายงานเก่าย้อนหลังทีละไฟล์",
                "SARA sees every meeting in this series at once.",
              )}
            />
            <div className="flex flex-wrap justify-center gap-2 px-6 pb-6">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => ask(s)}
                  className="rounded-full border border-line px-3.5 py-2 text-[12.5px] text-ink-2 transition-colors hover:border-brand hover:bg-[var(--brand-soft)] hover:text-brand cursor-pointer"
                >
                  {s}
                </button>
              ))}
            </div>
          </Card>
        )}

        {history.map((a) => (
          <div key={a.id} className="space-y-3">
            <div className="flex justify-end">
              <p className="max-w-[80%] rounded-[var(--radius)] rounded-tr-sm bg-brand px-4 py-2.5 text-[13.5px] leading-relaxed text-[var(--brand-ink)]">
                {a.question}
              </p>
            </div>

            <Card className="overflow-hidden">
              <div className="flex items-center gap-2 border-b border-line px-4 py-2.5">
                <Badge tone={a.source === "resolution_table" ? "brand" : "neutral"}>
                  {a.source === "resolution_table" ? <Database size={11} /> : <FileSearch size={11} />}
                  {t("answerSource")}: {a.source === "resolution_table" ? t("fromResolutions") : t("fromTranscript")}
                </Badge>
              </div>

              <p className="whitespace-pre-line px-4 py-3.5 text-[13.5px] leading-relaxed text-ink">{a.answer}</p>

              {/* คำถามเชิงมติ ตอบเป็นไทม์ไลน์ ไม่ใช่ย่อหน้าเดียว — FR-M8-03 */}
              {a.timeline.length > 0 && (
                <div className="border-t border-line px-4 py-3.5">
                  <p className="mb-3 text-[12px] font-semibold uppercase tracking-wide text-ink-4">
                    {t.pick("ลำดับเหตุการณ์ข้ามการประชุม", "Cross-meeting timeline")}
                  </p>
                  <ol>
                    {a.timeline.map((e, i) => (
                      <li key={i} className="flex gap-3 pb-3.5 last:pb-0">
                        <div className="flex flex-col items-center">
                          <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-brand ring-4 ring-[var(--brand-soft)]" />
                          {i < a.timeline.length - 1 && <span className="w-px flex-1 bg-line" />}
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-[13px] font-medium text-ink">
                            {e.label}
                            <span className="tnum ml-2 text-[12px] font-normal text-ink-3">
                              {e.date ? formatThaiDate(e.date, true) : ""}
                            </span>
                          </p>
                          <p className="mt-1 text-[12.5px] leading-relaxed text-ink-3">“{e.detail}”</p>
                        </div>
                      </li>
                    ))}
                  </ol>
                </div>
              )}

              {a.citations.length > 0 && (
                <div className="space-y-2.5 border-t border-line bg-surface-2 px-4 py-3.5">
                  <p className="text-[12px] font-semibold uppercase tracking-wide text-ink-4">
                    {t.pick("อ้างอิง", "Citations")} ({a.citations.length})
                  </p>
                  {a.citations.map((c, i) => {
                    const m = db.meetings.find((x) => x.id === c.meeting_id);
                    return (
                      <EvidenceQuote
                        key={i}
                        text={c.quote}
                        meta={
                          <>
                            <span>
                              {t.pick("ครั้งที่", "Meeting")} {m?.sequence_no}/{m?.fiscal_year} ·{" "}
                              <span className="tnum">{m ? formatThaiDate(m.meeting_date, true) : ""}</span>
                            </span>
                            {/* timecode กดได้ พาไปเปิดบันทึกตรงช่วงที่อ้างถึงแล้วกดฟังได้ทันที
                                ถ้าไม่รู้เวลา (อ้างจากทะเบียนมติ) แสดงเป็นข้อความเฉย ๆ */}
                            {c.start_ms == null ? (
                              <span className="inline-flex items-center gap-1">
                                <Clock size={11} />
                                <span className="tnum font-mono">{formatTimecode(c.start_ms)}</span>
                              </span>
                            ) : (
                              <Link
                                href={`/series/${seriesId}/meetings/${c.meeting_id}?t=${c.start_ms}${
                                  c.segment_id ? `&seg=${c.segment_id}` : ""
                                }`}
                                title={t("jumpToMoment")}
                                className="inline-flex cursor-pointer items-center gap-1 font-medium text-brand hover:underline"
                              >
                                <Clock size={11} />
                                <span className="tnum font-mono">{formatTimecode(c.start_ms)}</span>
                              </Link>
                            )}
                            {c.resolution_id && (
                              <button
                                onClick={() => setOpenRes(c.resolution_id!)}
                                className="font-medium text-brand hover:underline cursor-pointer"
                              >
                                {t.pick("เปิดมติ", "Open resolution")} →
                              </button>
                            )}
                          </>
                        }
                      />
                    );
                  })}
                </div>
              )}
            </Card>
          </div>
        ))}

        {busy && (
          <Card className="flex items-center gap-2.5 px-4 py-3.5">
            <Loader2 size={15} className="animate-spin text-brand" />
            <span className="text-[13px] text-ink-3">
              {t.pick("กำลังค้นจากทะเบียนมติและบันทึกการประชุมทุกครั้ง…", "Searching resolutions and transcripts…")}
            </span>
          </Card>
        )}

        <div ref={endRef} />

        {/* ช่องถาม */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            ask(question);
          }}
          className="sticky bottom-4 flex gap-2 rounded-[var(--radius)] border border-line bg-surface p-2 shadow-[var(--shadow-2)]"
        >
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-4" />
            <Input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder={t("askPlaceholder")}
              className={cn("border-transparent pl-9 focus:border-transparent focus:ring-0")}
            />
          </div>
          <Button type="submit" variant="primary" disabled={!question.trim() || busy} icon={<CornerDownLeft size={15} />}>
            {t.pick("ถาม", "Ask")}
          </Button>
        </form>
      </PageBody>

      <ResolutionDrawer resolutionId={openRes} onClose={() => setOpenRes(null)} />
    </>
  );
}
