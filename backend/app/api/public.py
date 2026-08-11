"""
FR-M7-08 — ผู้รับผิดชอบแจ้งสถานะมติกลับได้โดยไม่ต้องล็อกอิน (magic link)

ขอบเขตของลิงก์: อัปเดตมติข้อเดียวที่ระบุในโทเคนเท่านั้น
เปลี่ยนไป done ไม่ได้จากทางนี้ — การปิดมติต้องผ่านฝ่ายเลขานุการเสมอ (§4.2)
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import read_magic_token
from app.db.models import Person, Resolution, ResolutionStatus
from app.db.session import get_db
from app.services.agenda_builder import STATUS_LABEL_TH
from app.services.resolutions import change_status, overdue_days
from app.services.thai_format import thai_date

router = APIRouter(prefix="/public", tags=["Public"])

#  ผู้รับผิดชอบรายงานได้แค่ 2 อย่างนี้ — "เสร็จแล้ว" ต้องให้เลขาฯ ยืนยันจากที่ประชุม
ALLOWED = {
    ResolutionStatus.IN_PROGRESS: "กำลังดำเนินการ",
    ResolutionStatus.BLOCKED: "ติดปัญหา ยังดำเนินการต่อไม่ได้",
}

PAGE = """<!DOCTYPE html><html lang="th"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>แจ้งความคืบหน้ามติ · SARA</title>
<style>
 body {{ font-family: "IBM Plex Sans Thai", Tahoma, sans-serif; background:#f4f5f7; color:#131a26;
        margin:0; padding:24px; line-height:1.7; }}
 .card {{ max-width:640px; margin:24px auto; background:#fff; border:1px solid #dfe3ea;
         border-radius:10px; padding:24px; }}
 .quote {{ border-left:3px solid #9a7517; background:#fbf3df; padding:12px 16px; margin:16px 0; }}
 .meta {{ color:#6b7688; font-size:14px; }}
 button {{ background:#1e3a6e; color:#fff; border:0; border-radius:8px; padding:10px 18px;
          font-size:15px; cursor:pointer; margin-right:8px; font-family:inherit; }}
 .ok {{ color:#196b45; font-weight:600; }}
 .err {{ color:#b3261e; font-weight:600; }}
 textarea {{ width:100%; min-height:80px; border:1px solid #c8cfda; border-radius:8px;
            padding:10px; font-family:inherit; font-size:15px; }}
</style></head><body><div class="card">{content}</div></body></html>"""


def _page(content: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(PAGE.format(content=content), status_code=status_code)


async def _load(token: str, db: AsyncSession) -> tuple[Resolution, Person]:
    data = read_magic_token(token)
    if not data:
        raise HTTPException(status_code=403, detail="ลิงก์ไม่ถูกต้องหรือหมดอายุแล้ว")
    resolution = await db.get(Resolution, UUID(data["r"]))
    person = await db.get(Person, UUID(data["p"]))
    if resolution is None or person is None:
        raise HTTPException(status_code=404, detail="ไม่พบมติหรือผู้รับผิดชอบตามลิงก์นี้")
    return resolution, person


@router.get("/resolutions/{token}", response_class=HTMLResponse)
async def show(token: str, db: AsyncSession = Depends(get_db)):
    try:
        resolution, person = await _load(token, db)
    except HTTPException as err:
        return _page(f'<p class="err">{err.detail}</p>', err.status_code)

    od = overdue_days(resolution)
    buttons = "".join(
        f'<button type="submit" name="status" value="{key}">{label}</button>' for key, label in ALLOWED.items()
    )
    return _page(
        f"<h2>แจ้งความคืบหน้ามติ</h2>"
        f'<p class="meta">เรียน {person.full_name}</p>'
        f'<div class="quote">{resolution.text}</div>'
        f'<p class="meta">{resolution.ref_no} · กำหนดแล้วเสร็จ {thai_date(resolution.due_date)}'
        f'{f" · เกินกำหนดแล้ว {od} วัน" if od else ""}<br/>'
        f"สถานะปัจจุบัน: {STATUS_LABEL_TH.get(resolution.status, resolution.status)}</p>"
        f'<form method="post" action="/api/public/resolutions/{token}">'
        f'<p><textarea name="note" placeholder="รายละเอียดความคืบหน้า (ไม่บังคับ)"></textarea></p>'
        f"<p>{buttons}</p></form>"
        f'<p class="meta">หากดำเนินการแล้วเสร็จ กรุณาแจ้งฝ่ายเลขานุการ '
        f"เนื่องจากการปิดมติต้องได้รับการยืนยันจากที่ประชุม</p>"
    )


@router.post("/resolutions/{token}", response_class=HTMLResponse)
async def submit(
    token: str,
    status: str = Form(...),
    note: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
):
    try:
        resolution, person = await _load(token, db)
    except HTTPException as err:
        return _page(f'<p class="err">{err.detail}</p>', err.status_code)

    if status not in ALLOWED:
        return _page('<p class="err">สถานะที่เลือกไม่ถูกต้อง</p>', 422)

    try:
        await change_status(
            db,
            resolution,
            status,
            reason=note.strip() or f"ผู้รับผิดชอบแจ้งสถานะผ่านลิงก์: {ALLOWED[status]}",
            actor=f"{person.full_name} (ผ่าน magic link)",
        )
    except HTTPException as err:
        return _page(f'<p class="err">{err.detail}</p>', err.status_code)

    await db.commit()
    return _page(
        f'<h2 class="ok">บันทึกเรียบร้อยแล้ว</h2>'
        f"<p>ระบบบันทึกสถานะ “{ALLOWED[status]}” สำหรับ {resolution.ref_no} แล้ว "
        f"ฝ่ายเลขานุการจะเห็นการแจ้งนี้ในระบบทันที</p>"
        f'<p class="meta">ขอบคุณครับ/ค่ะ</p>'
    )
