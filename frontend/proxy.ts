import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * ยังไม่มี cookie session → ส่งไปหน้า login ก่อนจะ render หน้าไหน ๆ
 * (เช็คแค่ว่ามี cookie — ความถูกต้องของ token ให้ backend ตรวจ ถ้าหมดอายุ API จะตอบ 401 แล้ว lib/api.ts พาไป login เอง)
 */
export function proxy(request: NextRequest) {
  if (request.cookies.has("access_token")) return NextResponse.next();

  const login = new URL("/login", request.url);
  login.searchParams.set("next", request.nextUrl.pathname + request.nextUrl.search);
  return NextResponse.redirect(login);
}

export const config = {
  // ⚠ ห้ามให้ proxy จับ /api — ระหว่างที่มี proxy, Next.js จะบัฟเฟอร์ body ของ path ที่จับไว้ไม่เกิน 10 MB
  //   แล้วตัดส่วนเกินทิ้งเงียบ ๆ ไฟล์เสียงที่อัปโหลดจะไปถึง backend ไม่ครบ
  matcher: ["/((?!api/|login|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|ico|webp)$).*)"],
};
