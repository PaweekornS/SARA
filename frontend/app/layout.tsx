import type { Metadata } from "next";
import { IBM_Plex_Sans_Thai, IBM_Plex_Mono, Sarabun } from "next/font/google";
import "./globals.css";
import { AppShell } from "@/components/app-shell";

/* ตัวอักษรหลัก — Plex Sans Thai อ่านง่ายในตารางข้อมูลหนาแน่น และมีน้ำหนักครบ */
const plexThai = IBM_Plex_Sans_Thai({
  variable: "--font-plex-thai",
  subsets: ["thai", "latin"],
  weight: ["300", "400", "500", "600", "700"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

/* Sarabun ใช้เฉพาะหน้าตัวอย่างเอกสาร ให้หน้าจอใกล้เคียง TH Sarabun New ใน Word */
const sarabun = Sarabun({
  variable: "--font-sarabun",
  subsets: ["thai", "latin"],
  weight: ["400", "700"],
});

export const metadata: Metadata = {
  title: "SARA · ระบบสารบรรณการประชุมอัตโนมัติ",
  description:
    "แปลงไฟล์เสียงประชุมเป็นรายงานการประชุมตามระเบียบสารบรรณ และติดตามมติทุกข้อข้ามการประชุมจนกว่าจะปิดจ๊อบ",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="th"
      suppressHydrationWarning
      className={`${plexThai.variable} ${plexMono.variable} ${sarabun.variable}`}
    >
      <body>
        {/* ตั้งธีมก่อน paint แรก ไม่งั้นผู้ใช้ธีมมืดจะเห็นจอขาววาบทุกครั้งที่โหลด */}
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var s=JSON.parse(localStorage.getItem("sara_v2_state")||"{}");if(s.theme==="dark")document.documentElement.classList.add("dark")}catch(e){}`,
          }}
        />
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
