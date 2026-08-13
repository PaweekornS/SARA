"""
M3 — ทะเบียนบุคคลระดับองค์กร + alias

ความเสี่ยงสูงสุดของโมดูลนี้ (§M3): ชื่อคนไทยในการประชุมจริงปนกันทั้งชื่อเล่น ตำแหน่ง คำนำหน้า
หลักการคือ ให้มนุษย์ยืนยันครั้งแรก แล้วระบบจำ ไม่ใช่ให้ AI แม่น 100% ตั้งแต่แรก
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_actor, current_org
from app.db.models import Organization, Person, PersonAlias
from app.db.session import get_db
from app.schemas import Ack, AliasIn, AliasOut, PersonIn, PersonOut
from app.services.resolutions import audit, get_or_404

router = APIRouter(prefix="/people", tags=["People"])


@router.get("", response_model=list[PersonOut])
async def list_people(db: AsyncSession = Depends(get_db), org: Organization = Depends(current_org)):
    rows = await db.execute(select(Person).where(Person.org_id == org.id).order_by(Person.full_name))
    return list(rows.scalars().all())


@router.post("", response_model=PersonOut, status_code=201)
async def create_person(
    payload: PersonIn,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(current_org),
    actor: str = Depends(current_actor),
):
    person = Person(org_id=org.id, **payload.model_dump())
    db.add(person)
    await db.flush()
    await audit(db, org.id, actor, "create_person", "person", person.id, person.full_name)
    await db.commit()
    await db.refresh(person)
    return person


@router.patch("/{person_id}", response_model=PersonOut)
async def patch_person(person_id: UUID, payload: PersonIn, db: AsyncSession = Depends(get_db)):
    person = await get_or_404(db, Person, person_id, "บุคคล")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(person, key, value)
    await db.commit()
    await db.refresh(person)
    return person


@router.delete("/{person_id}", status_code=204)
async def delete_person(
    person_id: UUID,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(current_org),
    actor: str = Depends(current_actor),
):
    person = await get_or_404(db, Person, person_id, "บุคคล")
    await audit(db, org.id, actor, "delete_person", "person", person.id, person.full_name)
    await db.delete(person)
    await db.commit()


@router.get("/aliases", response_model=list[AliasOut])
async def list_aliases(db: AsyncSession = Depends(get_db), org: Organization = Depends(current_org)):
    rows = await db.execute(
        select(PersonAlias).join(Person, Person.id == PersonAlias.person_id).where(Person.org_id == org.id)
    )
    return list(rows.scalars().all())


@router.post("/aliases", response_model=AliasOut, status_code=201)
async def add_alias(
    payload: AliasIn,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(current_org),
    actor: str = Depends(current_actor),
):
    """FR-M3-02, 04 — เก็บ alias หลายค่าต่อคน ยืนยันครั้งเดียวแล้วจำถาวร"""
    await get_or_404(db, Person, payload.person_id, "บุคคล")
    alias = payload.alias.strip()
    if not alias:
        raise HTTPException(status_code=422, detail="ชื่อเรียกว่างไม่ได้")

    exists = (
        await db.execute(
            select(PersonAlias).where(
                PersonAlias.person_id == payload.person_id, PersonAlias.alias == alias
            )
        )
    ).scalars().first()
    if exists:
        return exists

    row = PersonAlias(
        person_id=payload.person_id,
        alias=alias,
        source=payload.source,
        confidence=payload.confidence,
    )
    db.add(row)
    await audit(db, org.id, actor, "add_alias", "person", payload.person_id, alias)
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/aliases/{alias_id}", response_model=Ack)
async def remove_alias(alias_id: UUID, db: AsyncSession = Depends(get_db)):
    alias = await get_or_404(db, PersonAlias, alias_id, "ชื่อเรียก")
    await db.delete(alias)
    await db.commit()
    return Ack(detail="ลบชื่อเรียกแล้ว")
