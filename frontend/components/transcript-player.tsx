"use client";

/**
 * M9 — ฟังเสียงจริงคู่กับบันทึกคำต่อคำ (FR-M2-08)
 *
 * ทุกท่อนเก็บ timestamp ไว้แล้ว ส่วนที่ยังขาดคือเสียง ถ้าอ้างอิงเวลาได้แต่ฟังย้อนไม่ได้
 * ผู้ตรวจทานก็ต้องเชื่อข้อความที่ระบบถอดมาอยู่ดี ที่นี่จึงผูกเวลาของแต่ละท่อน
 * เข้ากับหัวอ่านเสียง กดบรรทัดไหนก็ฟังตรงจุดนั้น
 *
 * ถ้าไม่มีไฟล์เสียง (อัปโหลดเป็น transcript หรือโหมด mock) จะแสดงบันทึกเฉย ๆ
 * ไม่โผล่ปุ่มเล่นที่กดแล้วเงียบ
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Clock, Pause, Play, RotateCcw } from "lucide-react";

import { Badge, Card, CardHead, ConfidenceBar, EmptyState, cn } from "./ui";
import { useT } from "@/lib/i18n";
import { activeSegmentIndex, formatTimecode, personName, useApp } from "@/lib/store";
import type { TranscriptSegment } from "@/lib/types";

export function TranscriptPlayer({
  segments,
  audioUrl,
  initialMs = null,
  citedSegmentIds = [],
}: {
  /** ต้องเรียงตาม start_ms มาแล้ว — activeSegmentIndex คิดบนสมมติฐานนี้ */
  segments: TranscriptSegment[];
  audioUrl: string | null;
  /** เวลาที่ต้องกระโดดไปเมื่อเปิดหน้าจากลิงก์อ้างอิง (?t=) */
  initialMs?: number | null;
  citedSegmentIds?: string[];
}) {
  const t = useT();
  const { db } = useApp();

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);
  const activeRef = useRef<HTMLElement | null>(null);
  const seekApplied = useRef(false);

  const [currentMs, setCurrentMs] = useState(initialMs ?? 0);
  const [playing, setPlaying] = useState(false);
  const [failed, setFailed] = useState(false);
  const [audioMs, setAudioMs] = useState(0);

  const cited = new Set(citedSegmentIds);
  const active = activeSegmentIndex(segments, currentMs);
  const lastEnd = segments.length ? segments[segments.length - 1].end_ms : 0;
  // ความยาวจาก metadata แม่นกว่า แต่ก่อนโหลดเสร็จใช้ท้ายท่อนสุดท้ายไปก่อน
  const totalMs = audioMs > 0 ? audioMs : lastEnd;

  const seek = useCallback((ms: number, andPlay: boolean) => {
    const el = audioRef.current;
    if (!el) return;
    el.currentTime = Math.max(0, ms) / 1000;
    setCurrentMs(Math.max(0, ms));
    // กดบรรทัดคือ user gesture อยู่แล้ว แต่ตอนเปิดหน้ามาจากลิงก์ยังไม่ใช่
    // เบราว์เซอร์จะปฏิเสธ autoplay จึง seek เฉย ๆ ไม่ต้องโวยวาย
    if (andPlay) void el.play().catch(() => undefined);
  }, []);

  // กระโดดไปเวลาที่ลิงก์อ้างอิงระบุ ทำครั้งเดียวหลัง metadata พร้อม
  const applyInitialSeek = useCallback(() => {
    if (seekApplied.current || initialMs == null) return;
    seekApplied.current = true;
    seek(initialMs, false);
  }, [initialMs, seek]);

  // ไล่ตามหัวอ่าน แต่เลื่อนเฉพาะเมื่อบรรทัดหลุดจอ ไม่งั้นคนที่อ่านล่วงหน้าจะถูกดึงกลับ
  useEffect(() => {
    const line = activeRef.current;
    const list = listRef.current;
    if (!line || !list) return;
    const lineBox = line.getBoundingClientRect();
    const listBox = list.getBoundingClientRect();
    if (lineBox.top < listBox.top || lineBox.bottom > listBox.bottom) {
      line.scrollIntoView({ block: "center", behavior: "smooth" });
    }
  }, [active]);

  if (!segments.length) {
    return (
      <Card>
        <EmptyState
          icon={<Clock size={18} />}
          title={t.pick("ยังไม่มีบันทึกคำต่อคำ", "No transcript yet")}
          desc={t.pick(
            "บันทึกจะปรากฏเมื่อระบบถอดเสียงเสร็จ",
            "The transcript appears once processing finishes.",
          )}
        />
      </Card>
    );
  }

  const playable = Boolean(audioUrl) && !failed;

  return (
    <div className="space-y-4">
      <Card className="overflow-hidden">
        <CardHead
          title={t("transcript")}
          desc={t.pick(
            "ทุกท่อนเก็บ timestamp ไว้ เพื่อให้ย้อนกลับไปตรวจหลักฐานของมติได้เสมอ",
            "Every segment keeps its timestamp so any resolution can be traced back.",
          )}
          right={
            playable ? (
              <Badge tone="brand">{t.pick("กดบรรทัดเพื่อฟัง", "Tap a line to play")}</Badge>
            ) : failed ? (
              <Badge tone="warn">
                <AlertTriangle size={11} />
                {t("audioFailed")}
              </Badge>
            ) : (
              <Badge tone="neutral">{t("noAudio")}</Badge>
            )
          }
        />

        <div ref={listRef} className="divide-y divide-[var(--line)]">
          {segments.map((s, index) => {
            const isActive = index === active;
            const isCited = cited.has(s.id);
            const speaker = s.person_id ? personName(db, s.person_id) : s.speaker_label;

            const body = (
              <>
                <div className="w-[92px] shrink-0">
                  <p
                    className={cn(
                      "tnum font-mono text-[12px]",
                      isCited ? "font-medium text-[var(--seal)]" : "text-ink-3",
                      isActive && !isCited && "text-brand",
                    )}
                  >
                    {formatTimecode(s.start_ms)}
                  </p>
                  <p
                    className={cn(
                      "mt-1 truncate text-[12px] font-medium",
                      s.person_id ? "text-brand" : "text-[var(--warn)]",
                    )}
                    title={speaker}
                  >
                    {speaker}
                  </p>
                </div>
                <p className={cn("flex-1 text-[13.5px] leading-relaxed", isActive ? "text-ink" : "text-ink-2")}>
                  {s.text}
                </p>
                <div className="hidden shrink-0 pt-0.5 sm:block">
                  <ConfidenceBar value={s.confidence} showLabel={false} />
                </div>
              </>
            );

            const shell = cn(
              // เส้นซ้ายโปร่งไว้ทุกแถว กันเนื้อหาขยับเมื่อแถวใดถูกอ้างอิง
              "flex w-full gap-4 border-l-2 border-transparent px-5 py-3.5 text-left transition-colors",
              // ท่อนที่ถูกอ้างอิงคาดเส้นตราทองแบบเดียวกับ EvidenceQuote และต้องเห็นได้
              // แม้หัวอ่านมาถึงแถวนั้นแล้ว เพราะตอนกดลิงก์อ้างอิงมา สองอย่างนี้เป็นแถวเดียวกัน
              isCited && "border-[var(--seal)]",
              isActive
                ? "bg-[var(--brand-soft)]"
                : isCited
                  ? "bg-[var(--seal-soft)]"
                  : playable && "hover:bg-sunken",
            );

            // ทำเป็นปุ่มเฉพาะเมื่อฟังได้จริง ไม่งั้นเป็นแค่ข้อความอ่าน
            return playable ? (
              <button
                key={s.id}
                ref={isActive ? (activeRef as React.Ref<HTMLButtonElement>) : undefined}
                type="button"
                onClick={() => seek(s.start_ms, true)}
                title={t("jumpToMoment")}
                className={cn(shell, "cursor-pointer")}
              >
                {body}
              </button>
            ) : (
              <div
                key={s.id}
                ref={isActive ? (activeRef as React.Ref<HTMLDivElement>) : undefined}
                className={shell}
              >
                {body}
              </div>
            );
          })}
        </div>
      </Card>

      {audioUrl && (
        <>
          {/* แถบควบคุมลอยอยู่ล่างจอแบบเดียวกับช่องถามในหน้า M8 */}
          {!failed && (
            <div className="no-print sticky bottom-4 z-10 flex items-center gap-3 rounded-[var(--radius)] border border-line bg-surface p-2.5 shadow-[var(--shadow-2)]">
              <button
                type="button"
                onClick={() => {
                  const el = audioRef.current;
                  if (!el) return;
                  if (el.paused) void el.play().catch(() => setFailed(true));
                  else el.pause();
                }}
                aria-label={playing ? t("pause") : t("play")}
                className="flex h-9 w-9 shrink-0 cursor-pointer items-center justify-center rounded-full bg-brand text-[var(--brand-ink)] transition-colors hover:bg-[var(--brand-hover)]"
              >
                {playing ? <Pause size={15} /> : <Play size={15} className="ml-0.5" />}
              </button>

              <button
                type="button"
                onClick={() => seek(Math.max(0, currentMs - 10_000), false)}
                aria-label={t("back10")}
                className="hidden h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-full text-ink-3 transition-colors hover:bg-sunken hover:text-ink sm:flex"
              >
                <RotateCcw size={14} />
              </button>

              <span className="tnum shrink-0 font-mono text-[12px] text-ink">
                {formatTimecode(currentMs)}
              </span>

              <input
                type="range"
                min={0}
                max={Math.max(1, Math.round(totalMs / 1000))}
                value={Math.round(currentMs / 1000)}
                onChange={(event) => seek(Number(event.target.value) * 1000, false)}
                aria-label={t.pick("เลื่อนหาช่วงเวลา", "Seek")}
                className="h-1.5 min-w-0 flex-1 cursor-pointer appearance-none rounded-full bg-sunken accent-[var(--brand)]"
              />

              <span className="tnum shrink-0 font-mono text-[12px] text-ink-3">
                {formatTimecode(totalMs)}
              </span>
            </div>
          )}

          <audio
            ref={audioRef}
            src={audioUrl}
            preload="metadata"
            className="hidden"
            onLoadedMetadata={(event) => {
              const seconds = event.currentTarget.duration;
              if (Number.isFinite(seconds)) setAudioMs(Math.round(seconds * 1000));
              applyInitialSeek();
            }}
            onTimeUpdate={(event) => setCurrentMs(Math.round(event.currentTarget.currentTime * 1000))}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            onError={() => setFailed(true)}
          />
        </>
      )}
    </div>
  );
}
