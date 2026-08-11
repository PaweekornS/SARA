"""
แปลง ORM → DTO ที่ frontend ใช้

จุดเดียวที่ต้องระวัง: Resolution.assignee_ids เป็น list ที่มาจากตารางเชื่อม
จึงต้องดึงมารวมเองแทนที่จะพึ่ง lazy load (async session ทำ lazy load ไม่ได้)
"""

from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Resolution, ResolutionAssignee
from app.schemas import ResolutionOut


async def assignee_map(db: AsyncSession, resolution_ids: list[UUID]) -> dict[UUID, list[UUID]]:
    if not resolution_ids:
        return {}
    rows = await db.execute(
        select(ResolutionAssignee.resolution_id, ResolutionAssignee.person_id).where(
            ResolutionAssignee.resolution_id.in_(resolution_ids)
        )
    )
    mapping: dict[UUID, list[UUID]] = defaultdict(list)
    for resolution_id, person_id in rows.all():
        mapping[resolution_id].append(person_id)
    return mapping


async def resolution_out(db: AsyncSession, resolution: Resolution) -> ResolutionOut:
    mapping = await assignee_map(db, [resolution.id])
    dto = ResolutionOut.model_validate(resolution)
    dto.assignee_ids = mapping.get(resolution.id, [])
    return dto


async def resolutions_out(db: AsyncSession, resolutions: list[Resolution]) -> list[ResolutionOut]:
    mapping = await assignee_map(db, [r.id for r in resolutions])
    out = []
    for r in resolutions:
        dto = ResolutionOut.model_validate(r)
        dto.assignee_ids = mapping.get(r.id, [])
        out.append(dto)
    return out
