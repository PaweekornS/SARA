"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import Script from "next/script";
import { useSearchParams } from "next/navigation";
import { FlaskConical, Loader2 } from "lucide-react";
import { SaraMark } from "@/components/app-shell";
import { Button, Card, ErrorNote, Loading } from "@/components/ui";
import * as api from "@/lib/api";
import { useT } from "@/lib/i18n";
import { clearCache } from "@/lib/query";

const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "";
/* บัญชี demo มีไว้ตอนพัฒนาบนเครื่องที่ยังไม่ได้ตั้ง Google — บน prod backend ก็ปิด /auth/demo อยู่แล้ว */
const SHOW_DEMO = !GOOGLE_CLIENT_ID || process.env.NODE_ENV !== "production";

interface GoogleIdentity {
  accounts: {
    id: {
      initialize: (opts: { client_id: string; callback: (r: { credential: string }) => void }) => void;
      renderButton: (el: HTMLElement, opts: Record<string, unknown>) => void;
    };
  };
}

declare global {
  interface Window {
    google?: GoogleIdentity;
  }
}

export default function LoginPage() {
  return (
    <Suspense fallback={<Loading />}>
      <Login />
    </Suspense>
  );
}

/** กันไม่ให้ ?next= พาออกนอกเว็บ (open redirect) */
function safeNext(raw: string | null): string {
  return raw && raw.startsWith("/") && !raw.startsWith("//") ? raw : "/collections";
}

function Login() {
  const t = useT();
  const next = safeNext(useSearchParams().get("next"));
  const buttonRef = useRef<HTMLDivElement>(null);
  const [gisReady, setGisReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const finish = () => {
    clearCache();
    window.location.assign(next);
  };

  useEffect(() => {
    if (!gisReady || !GOOGLE_CLIENT_ID || !window.google || !buttonRef.current) return;
    window.google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: async ({ credential }) => {
        setBusy(true);
        setError(null);
        try {
          await api.auth.google(credential);
          finish();
        } catch (e) {
          setError(e instanceof Error ? e.message : String(e));
          setBusy(false);
        }
      },
    });
    window.google.accounts.id.renderButton(buttonRef.current, { theme: "outline", size: "large", width: 300, locale: "th" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gisReady]);

  const demo = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.auth.demo();
      finish();
    } catch (e) {
      setError(
        e instanceof api.ApiError && e.status === 404
          ? t.pick("เซิร์ฟเวอร์นี้ปิดการใช้บัญชีทดลอง", "Demo login is disabled on this server")
          : e instanceof Error
            ? e.message
            : String(e),
      );
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-dvh items-center justify-center px-4">
      {GOOGLE_CLIENT_ID && <Script src="https://accounts.google.com/gsi/client" strategy="afterInteractive" onReady={() => setGisReady(true)} />}

      <Card className="w-full max-w-sm space-y-6 p-7">
        <div className="flex items-center gap-3">
          <SaraMark />
          <div>
            <p className="text-[18px] font-bold leading-none text-ink">SARA</p>
            <p className="mt-1 text-[12px] text-ink-3">{t.pick("ผู้ช่วยสรุปการประชุม", "AI meeting assistant")}</p>
          </div>
        </div>

        <div className="space-y-1.5">
          <h1 className="text-[17px] font-semibold text-ink">{t.pick("เข้าสู่ระบบ", "Sign in")}</h1>
          <p className="text-[13px] leading-relaxed text-ink-3">
            {t.pick(
              "อัปโหลดเสียงประชุม ได้สรุปภาษาไทยและรายการงานที่ต้องทำ แล้วถามย้อนหลังข้ามการประชุมได้ ข้อมูลของคุณเห็นได้เฉพาะคุณ",
              "Upload a meeting, get a Thai summary and to-dos, and ask across meetings later. Only you can see your data.",
            )}
          </p>
        </div>

        {GOOGLE_CLIENT_ID ? (
          <div className="flex min-h-[44px] justify-center">
            {busy ? <Loader2 size={20} className="animate-spin text-brand" /> : <div ref={buttonRef} />}
          </div>
        ) : (
          <p className="rounded-[var(--radius)] bg-surface-2 px-3 py-2 text-[12px] text-ink-3">
            {t.pick("ยังไม่ได้ตั้ง Google Client ID (NEXT_PUBLIC_GOOGLE_CLIENT_ID)", "Google Client ID is not configured")}
          </p>
        )}

        {SHOW_DEMO && (
          <Button className="w-full" icon={<FlaskConical size={15} />} onClick={demo} disabled={busy}>
            {t.pick("ทดลองใช้ด้วยบัญชี demo", "Try with demo account")}
          </Button>
        )}

        {error && <ErrorNote error={error} />}
      </Card>
    </div>
  );
}
