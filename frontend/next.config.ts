import type { NextConfig } from "next";

/*
 * บนเซิร์ฟเวอร์ reverse proxy ส่ง /api ไป backend เอง (ตัด /api ออกก่อนส่ง) — rewrite นี้จึงไม่ถูกใช้
 * บนเครื่องตัวเองไม่มี proxy ตัวนั้น Next.js เลยทำหน้าที่แทนแบบเดียวกัน หน้าเว็บกับ API จึงเป็น same-origin ทั้งสองที่
 * ค่าถูกฝังตอน build: docker ใช้ http://api:8000, npm run dev ใช้ค่า default
 */
const API_PROXY_TARGET = process.env.API_PROXY_TARGET ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_PROXY_TARGET}/:path*` }];
  },
  experimental: {
    // ค่าเริ่มต้น 30 วินาทีสั้นกว่าเวลาที่ ASR/LLM ใช้ตอบ (ถาม-ตอบรอ LLM ได้ถึง 3 นาที, อัปโหลดไฟล์ใหญ่ก็นาน)
    proxyTimeout: 10 * 60 * 1000,
  },
};

export default nextConfig;
