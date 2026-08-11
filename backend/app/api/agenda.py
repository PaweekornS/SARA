"""M5 — ร่างระเบียบวาระ: อ่าน แก้ไขลำดับ และส่งออกเป็น .docx"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import AgendaDraft, AgendaItem, MeetingSeries, Person, Resolution, ResolutionAssignee
from app.db.session import get_db
from app.schemas import AgendaItemsPatch, AgendaOut
from app.services.agenda_builder import SECTION_TITLES, STATUS_LABEL_TH
from app.services.docx_export import build_agenda_docx
from app.services.resolutions import get_or_404, overdue_days

router = APIRouter(prefix="/agenda", tags=["Agenda"])


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
    await db.flush()

    for order, item in enumerate(payload.items):
        db.add(
            AgendaItem(
                agenda_draft_id=draft.id,
                section_no=item.section_no,
                item_no=item.item_no,
                title=item.title,
                body=item.body,
                resolution_id=item.resolution_id,
                sort_order=order,
            )
        )

    await db.commit()
    await db.refresh(draft)
    return await _out(db, draft)


@router.get("/{agenda_id}/export")
async def export_agenda(agenda_id: UUID, format: str = "docx", db: AsyncSession = Depends(get_db)):
    """FR-M5-04 ส่งออกร่างวาระเป็น .docx ที่เปิดแก้ต่อใน Word ได้"""
    if format != "docx":
        raise HTTPException(status_code=400, detail="รองรับเฉพาะ format=docx")

    draft = await get_or_404(db, AgendaDraft, agenda_id, "ร่างระเบียบวาระ")
    series = await get_or_404(db, MeetingSeries, draft.series_id, "ชุดการประชุม")
    items = await _items(db, draft.id)

    sections = []
    for section_no in (1, 2, 3, 4, 5):
        rows = [(i.title, i.body) for i in items if i.section_no == section_no]
        sections.append((section_no, SECTION_TITLES[section_no], rows))

    blob = build_agenda_docx(
        series_name=series.name,
        fiscal_year=series.fiscal_year,
        sequence_no=draft.target_sequence_no,
        meeting_date=draft.target_meeting_date,
        sections=sections,
        template_path=settings.AGENDA_TEMPLATE_PATH or None,
    )

    filename = f"agenda-{draft.target_sequence_no}-{series.fiscal_year}.docx"
    return Response(
        content=blob,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{agenda_id}/summary")
async def agenda_summary(agenda_id: UUID, db: AsyncSession = Depends(get_db)):
    """ตารางสรุปมติค้างที่แนบท้ายวาระ — ใช้ทั้งในเอกสารและในอีเมลแจ้งประธาน"""
    draft = await get_or_404(db, AgendaDraft, agenda_id, "ร่างระเบียบวาระ")
    items = [i for i in await _items(db, draft.id) if i.section_no == 3 and i.resolution_id]

    rows = []
    for item in items:
        resolution = await db.get(Resolution, item.resolution_id)
        if resolution is None:
            continue
        names = (
            await db.execute(
                select(Person)
                .join(ResolutionAssignee, ResolutionAssignee.person_id == Person.id)
                .where(ResolutionAssignee.resolution_id == resolution.id)
            )
        ).scalars().all()
        rows.append(
            {
                "ref_no": resolution.ref_no,
                "text": resolution.text,
                "assignees": ", ".join(p.full_name for p in names),
                "due_date": resolution.due_date,
                "status": STATUS_LABEL_TH.get(resolution.status, resolution.status),
                "overdue": overdue_days(resolution),
            }
        )
    return {"agenda_id": draft.id, "rows": rows}
