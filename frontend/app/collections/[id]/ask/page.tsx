"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { CornerDownLeft, FolderKanban, Headphones, Loader2, Sparkles, Trash2 } from "lucide-react";
import { PageBody, PageHeader } from "@/components/app-shell";
import { Button, Card, EmptyState, ErrorNote, Loading } from "@/components/ui";
import * as api from "@/lib/api";
import { useCollection, useQaHistory } from "@/lib/data";
import { formatTimecode } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { setCached } from "@/lib/query";
import type { QaEntry } from "@/lib/types";

const SUGGESTIONS = [
  "สรุปงบประมาณที่ตกลงกันไว้",
  "งานใดบ้างที่มีกำหนดส่งภายในสัปดาห์นี้",
  "ปัญหาหรือ Blockers ที่ทีมพบในการประชุมล่าสุด",
  "มีงานอะไรที่ยังค้างอยู่บ้าง",
];

export default function AskPage() {
  return (
    <Suspense fallback={<Loading />}>
      <AskCopilot />
    </Suspense>
  );
}

function AskCopilot() {
  const t = useT();
  const collectionId = useParams<{ id: string }>().id;
  const initialQuery = useSearchParams().get("q");
  const { data: collection } = useCollection(collectionId);
  const { data: historyDesc, error: historyError, loading } = useQaHistory(collectionId);
  const history = [...(historyDesc ?? [])].reverse();

  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const askedInitial = useRef(false);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history.length, pending]);

  const ask = async (q: string) => {
    const text = q.trim();
    if (!text || pending) return;
    setQuestion("");
    setPending(text);
    setError(null);
    try {
      const entry = await api.collections.ask(collectionId, text);
      setCached<QaEntry[]>(`collections:${collectionId}:qa`, (cur) => [entry, ...(cur ?? [])]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setQuestion(text);
    } finally {
      setPending(null);
    }
  };

  useEffect(() => {
    if (initialQuery && !askedInitial.current) {
      askedInitial.current = true;
      void ask(initialQuery);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuery]);

  const clear = async () => {
    try {
      await api.collections.clearQa(collectionId);
      setCached<QaEntry[]>(`collections:${collectionId}:qa`, () => []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <>
      <PageHeader
        eyebrow={
          <div className="flex items-center gap-1.5 text-[12px] text-ink-3">
            <FolderKanban size={13} className="text-brand" />
            <Link href={`/collections/${collectionId}`} className="hover:text-brand transition-colors">
              {collection?.name || "Collection"}
            </Link>
            <span>/</span>
            <span className="text-brand font-medium">Ask SARA Copilot</span>
          </div>
        }
        title={
          <div className="flex items-center gap-2.5">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand text-white shadow-xs">
              <Sparkles size={16} />
            </span>
            <span>Ask SARA · Cross-Meeting Copilot</span>
          </div>
        }
        desc={t.pick(
          "ถามคำถามข้ามทุกการประชุมในคอลเลกชันนี้ คำตอบอ้างอิงข้อความจริงจากบันทึก คลิกเพื่อเปิดดูการประชุมต้นทาง",
          "Ask across all meetings in this collection. Answers cite the transcript.",
        )}
        actions={
          history.length > 0 ? (
            <Button icon={<Trash2 size={15} />} onClick={() => void clear()}>
              {t.pick("ล้างประวัติการคุย", "Clear history")}
            </Button>
          ) : undefined
        }
      />

      <PageBody className="space-y-4 max-w-[1000px] pb-28">
        {historyError && <ErrorNote error={historyError} />}

        {loading && !historyDesc ? (
          <Loading />
        ) : (
          history.length === 0 &&
          !pending && (
            <Card className="border-dashed py-8 text-center">
              <EmptyState
                icon={<Sparkles size={24} className="text-brand" />}
                title={t.pick("ถามอะไรก็ได้เกี่ยวกับการประชุมในคอลเลกชันนี้", "Ask anything across these meetings")}
                desc={t.pick("SARA ค้นจากสรุป งานที่ต้องทำ และบทสนทนาคำต่อคำ แล้วเรียบเรียงคำตอบให้", "SARA searches summaries, action items and transcripts.")}
              />
              <div className="mt-4 flex flex-wrap justify-center gap-2 px-6">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => void ask(s)}
                    className="rounded-full border border-line bg-[var(--bg-surface)] px-3.5 py-1.5 text-[12.5px] text-ink-2 transition-all hover:border-brand hover:bg-[var(--brand-soft)] hover:text-brand cursor-pointer shadow-xs"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </Card>
          )
        )}

        <div className="space-y-6">
          {history.map((a) => (
            <Exchange key={a.id} entry={a} collectionId={collectionId} />
          ))}

          {pending && (
            <div className="space-y-3">
              <UserBubble text={pending} />
              <div className="flex items-start gap-3">
                <div className="mt-1 flex h-7 w-7 shrink-0 animate-pulse items-center justify-center rounded-lg bg-brand text-white shadow-xs">
                  <Sparkles size={14} />
                </div>
                <Card className="flex items-center gap-2.5 p-4 text-[13px] text-ink-3">
                  <Loader2 size={16} className="animate-spin text-brand" />
                  <span>{t.pick("กำลังค้นหาและเรียบเรียงคำตอบ…", "Searching & composing an answer…")}</span>
                </Card>
              </div>
            </div>
          )}

          {error && <ErrorNote error={error} />}
          <div ref={endRef} />
        </div>

        <div className="no-print fixed bottom-0 left-0 right-0 z-30 border-t border-[var(--border-subtle)] bg-[var(--bg-surface)]/90 backdrop-blur-md py-3 px-4 sm:px-8 lg:left-[264px]">
          <div className="mx-auto max-w-[1000px]">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void ask(question);
              }}
              className="relative flex items-center"
            >
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder={t.pick("พิมพ์คำถามเกี่ยวกับการประชุมในคอลเลกชันนี้...", "Ask anything about these meetings...")}
                disabled={Boolean(pending)}
                maxLength={1000}
                className="w-full rounded-xl border border-line bg-[var(--bg-surface)] py-3 pl-4 pr-24 text-[13.5px] text-ink focus:border-brand focus:outline-none shadow-sm"
              />
              <button
                type="submit"
                disabled={!question.trim() || Boolean(pending)}
                className="absolute right-2 flex items-center gap-1.5 rounded-lg bg-brand px-3.5 py-1.5 text-[12.5px] font-medium text-white hover:bg-[var(--brand-hover)] disabled:opacity-40 cursor-pointer transition-colors"
              >
                <span>{t.pick("ส่ง", "Ask")}</span>
                <CornerDownLeft size={13} />
              </button>
            </form>
          </div>
        </div>
      </PageBody>
    </>
  );
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] rounded-[var(--radius)] rounded-tr-sm bg-brand px-4 py-2.5 text-[13.5px] leading-relaxed text-white shadow-xs">
        {text}
      </div>
    </div>
  );
}

function Exchange({ entry, collectionId }: { entry: QaEntry; collectionId: string }) {
  const t = useT();
  return (
    <div className="space-y-3">
      <UserBubble text={entry.question} />
      <div className="flex items-start gap-3">
        <div className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-brand text-white shadow-xs">
          <Sparkles size={14} />
        </div>
        <Card className="min-w-0 flex-1 border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4 sm:p-5 shadow-xs">
          <div className="whitespace-pre-line text-[13.5px] leading-relaxed text-ink">{entry.answer}</div>

          {entry.citations.length > 0 && (
            <div className="mt-4 space-y-2 border-t border-line pt-3">
              <p className="flex items-center gap-1.5 text-[11.5px] font-semibold uppercase tracking-wider text-ink-4">
                <Headphones size={12} className="text-brand" />
                {t.pick("แหล่งอ้างอิง", "Sources")}
              </p>
              <div className="space-y-1.5">
                {entry.citations.map((c, idx) => (
                  <div key={idx} className="flex flex-wrap items-start justify-between gap-2 rounded-[var(--radius)] bg-surface-2 p-2.5 text-[12.5px] text-ink-2">
                    <p className="min-w-[200px] flex-1 italic">“{c.quote}”</p>
                    <Link
                      href={`/collections/${collectionId}/meetings/${c.meeting_id}`}
                      className="inline-flex shrink-0 items-center gap-1 rounded bg-[var(--brand-soft)] px-2 py-0.5 text-[11px] font-medium text-brand hover:underline"
                    >
                      <span className="max-w-[220px] truncate">{c.meeting_label}</span>
                      {c.start_ms != null && <span className="font-mono">· {formatTimecode(c.start_ms)}</span>}
                    </Link>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
