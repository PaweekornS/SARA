"""M5 — ร่างระเบียบวาระ: อ่าน แก้ไขลำดับ และส่งออกเป็น .docx"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import AgendaDraft, AgendaItem, MeetingSeries, Resolution
from app.db.session import get_db
from app.schemas import AgendaItemsPatch, AgendaOut
from app.services.agenda_builder import SECTION_TITLES, STATUS_LABEL_TH, assignee_names
from app.services.docx_export import build_agenda_docx
from app.services.resolutions import get_or_404, overdue_days

# ── Global Variables & Constants ─────────────────────────────────────────────

router = APIRouter(prefix="/agenda", tags=["Agenda"])


# ── Functions & Route Handlers ───────────────────────────────────────────────

async def _items(db: AsyncSession, draft_id: UUID) -> list[AgendaItem]:
    rows = await db.execute(
        select(AgendaItem).where(AgendaItem.agenda_draft_id == draft_id).order_by(AgendaItem.sort_order)
    )
    return list(rows.scalars().all())


async def _out(db: AsyncSession, draft: AgendaDraft) -> AgendaOut:
    return AgendaOut.model_validate(
        {
            "id": draft.id,
            "series_id": draft.series_id,
            "target_meeting_date": draft.target_meeting_date,
            "target_sequence_no": draft.target_sequence_no,
            "status": draft.status,
            "created_at": draft.created_at,
            "items": await _items(db, draft.id),
        }
    )


@router.get("/{agenda_id}", response_model=AgendaOut)
async def get_agenda(agenda_id: UUID, db: AsyncSession = Depends(get_db)):
    draft = await get_or_404(db, AgendaDraft, agenda_id, "ร่างระเบียบวาระ")
    return await _out(db, draft)


@router.patch("/{agenda_id}/items", response_model=AgendaOut)
async def patch_items(agenda_id: UUID, payload: AgendaItemsPatch, db: AsyncSession = Depends(get_db)):
    """
    FR-M5-07 ผู้ใช้ลาก/ลบ/เพิ่มวาระและแก้ลำดับได้ก่อน export

    ฝั่ง client ส่งรายการทั้งชุดกลับมา ที่นี่จึงแทนที่ทั้งก้อน
    ง่ายกว่าและถูกต้องกว่าการ diff ทีละแถวสำหรับข้อมูลขนาดหลักสิบแถว
    """
    draft = await get_or_404(db, AgendaDraft, agenda_id, "ร่างระเบียบวาระ")

    for existing in await _items(db, draft.id):
        await db.delete(existing)

    for i, item in enumerate(payload.items, start=1):
        db.add(
            AgendaItem(
                agenda_draft_id=draft.id,
                section_no=item.section_no,
                item_no=item.item_no,
                title=item.title,
                body=item.body,
                resolution_id=item.resolution_id,
                sort_order=i,
            )
        )
    await db.commit()
    return await _out(db, draft)


@router.get("/{agenda_id}/export")
async def export_docx(agenda_id: UUID, db: AsyncSession = Depends(get_db)):
    """FR-M5-04 ส่งออกเป็น .docx ตามรูปแบบราชการ"""
    draft = await get_or_404(db, AgendaDraft, agenda_id, "ร่างระเบียบวาระ")
    series = await get_or_404(db, MeetingSeries, draft.series_id, "ชุดการประชุม")

    items = await _items(db, draft.id)
    by_section: dict[int, list[dict]] = {}
    for it in items:
        by_section.setdefault(it.section_no, []).append(
            {
                "item_no": it.item_no,
                "title": it.title,
                "body": it.body,
            }
        )

    content = build_agenda_docx(
        series_name=series.name,
        fiscal_year=series.fiscal_year,
        sequence_no=draft.target_sequence_no,
        meeting_date=draft.target_meeting_date,
        items_by_section=by_section,
        template_path=settings.AGENDA_TEMPLATE_PATH or None,
    )

    filename = f"agenda_{series.id}_{draft.target_sequence_no}.docx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
