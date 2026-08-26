"""M1 · M6 · M8 — ชุดการประชุม แดชบอร์ด ถาม-ตอบ และก้อนข้อมูลสำหรับ frontend"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_actor, current_org
from app.api.serializers import assignee_map, resolutions_out
from app.db.models import (
    AgendaDraft,
    AgendaItem,
    AuditLog,
    Meeting,
    MeetingSeries,
    Organization,
    OutboundAction,
    Person,
    PersonAlias,
    Proposal,
    QaLog,
    Resolution,
    ResolutionAssignee,
    ResolutionHistory,
    ResolutionLink,
    ResolutionStatus,
    TranscriptSegment,
)
from app.db.session import get_db
from app.schemas import (
    ActionOut,
    AgendaOut,
    AliasOut,
    AssigneeLoad,
    AuditOut,
    Bootstrap,
    DashboardOut,
    HistoryOut,
    LinkOut,
    MeetingOut,
    OrganizationOut,
    PersonOut,
    ProposalOut,
    QaAnswerOut,
    Question,
    SegmentOut,
    SeriesIn,
    SeriesOut,
    SeriesPatch,
    SeriesStats,
)
from app.services import qa as qa_service
from app.services.agenda_builder import generate_agenda
from app.services.resolutions import audit, get_or_404, overdue_days

router = APIRouter(tags=["Series"])


# ── CRUD ────────────────────────────────────────────────────────────────

@router.post("/series", response_model=SeriesOut, status_code=201)
async def create_series(
    payload: SeriesIn,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(current_org),
    actor: str = Depends(current_actor),
):
    series = MeetingSeries(
        org_id=org.id,
        **payload.model_dump(exclude={"member_ids"}),
        member_ids=[str(m) for m in payload.member_ids],
    )
    db.add(series)
    await db.flush()
    await audit(db, org.id, actor, "create_series", "meeting_series", series.id, series.name)
    await db.commit()
    await db.refresh(series)
    return series


@router.get("/series", response_model=list[SeriesOut])
async def list_series(db: AsyncSession = Depends(get_db), org: Organization = Depends(current_org)):
    rows = await db.execute(
        select(MeetingSeries).where(MeetingSeries.org_id == org.id).order_by(MeetingSeries.created_at)
    )
    return list(rows.scalars().all())


@router.get("/series/{series_id}", response_model=SeriesOut)
async def get_series(series_id: UUID, db: AsyncSession = Depends(get_db)):
    return await get_or_404(db, MeetingSeries, series_id, "ชุดการประชุม")


@router.patch("/series/{series_id}", response_model=SeriesOut)
async def patch_series(series_id: UUID, payload: SeriesPatch, db: AsyncSession = Depends(get_db)):
    series = await get_or_404(db, MeetingSeries, series_id, "ชุดการประชุม")
    data = payload.model_dump(exclude_unset=True)
    if "member_ids" in data and data["member_ids"] is not None:
        data["member_ids"] = [str(m) for m in data["member_ids"]]
    for key, value in data.items():
        setattr(series, key, value)
    await db.commit()
    await db.refresh(series)
    return series


@router.delete("/series/{series_id}", status_code=204)
async def delete_series(
    series_id: UUID,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(current_org),
    actor: str = Depends(current_actor),
):
    series = await get_or_404(db, MeetingSeries, series_id, "ชุดการประชุม")
    await audit(db, org.id, actor, "delete_series", "meeting_series", series.id, series.name)
    await db.delete(series)
    await db.commit()


# ── มติของ series (FR-M6-03, 04) ────────────────────────────────────────

@router.get("/series/{series_id}/resolutions")
async def series_resolutions(
    series_id: UUID,
    status: str | None = Query(default=None),
    assignee: UUID | None = Query(default=None),
    overdue: bool | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Resolution).where(Resolution.series_id == series_id)
    if status:
        stmt = stmt.where(Resolution.status == status)
    if assignee:
        stmt = stmt.join(ResolutionAssignee).where(ResolutionAssignee.person_id == assignee)

    rows = list((await db.execute(stmt)).scalars().all())
    if overdue:
        rows = [r for r in rows if overdue_days(r) > 0]
    rows.sort(key=lambda r: overdue_days(r), reverse=True)
    return await resolutions_out(db, rows)


# ── แดชบอร์ด (FR-M6-01, 02, 05) ─────────────────────────────────────────

@router.get("/series/{series_id}/dashboard", response_model=DashboardOut)
async def dashboard(series_id: UUID, db: AsyncSession = Depends(get_db)):
    await get_or_404(db, MeetingSeries, series_id, "ชุดการประชุม")
    rows = list(
        (await db.execute(select(Resolution).where(Resolution.series_id == series_id))).scalars().all()
    )

    done = [r for r in rows if r.status == ResolutionStatus.DONE]
    #  มติที่ยกเลิก/ถูกแทนที่ ไม่ควรเป็นตัวหารของอัตราการปิด เพราะไม่เคยต้องปิด
    closable = [
        r for r in rows if r.status not in (ResolutionStatus.CANCELLED, ResolutionStatus.SUPERSEDED)
    ]
    durations = [
        (r.closed_at.date() - r.created_at.date()).days for r in done if r.closed_at and r.created_at
    ]
    overdue = sorted((r for r in rows if overdue_days(r) > 0), key=overdue_days, reverse=True)
    flagged = [r for r in rows if (r.postpone_count or 0) >= 3 and r.status in ResolutionStatus.OPEN]

    stats = SeriesStats(
        total=len(rows),
        open=len([r for r in rows if r.status in ResolutionStatus.OPEN]),
        done=len(done),
        overdue=len(overdue),
        flagged=len(flagged),
        closure_rate=round(len(done) / len(closable) * 100) if closable else 0,
        avg_days_to_close=round(sum(durations) / len(durations)) if durations else 0,
    )

    status_counts: dict[str, int] = defaultdict(int)
    for r in rows:
        status_counts[r.status] += 1

    #  ภาระต่อคน — ประธานอยากรู้ว่า "ใครค้าง" ไม่ใช่แค่ "ค้างกี่ข้อ"
    open_rows = [r for r in rows if r.status in ResolutionStatus.OPEN]
    mapping = await assignee_map(db, [r.id for r in open_rows])
    load: dict[UUID, dict] = {}
    for r in open_rows:
        for pid in mapping.get(r.id, []):
            entry = load.setdefault(pid, {"open": 0, "overdue": 0})
            entry["open"] += 1
            if overdue_days(r) > 0:
                entry["overdue"] += 1

    people = {
        p.id: p
        for p in (
            await db.execute(select(Person).where(Person.id.in_(load.keys() or [None])))
        ).scalars().all()
    }
    load_out = sorted(
        (
            AssigneeLoad(
                person_id=pid,
                name=people[pid].full_name if pid in people else "-",
                open=entry["open"],
                overdue=entry["overdue"],
            )
            for pid, entry in load.items()
        ),
        key=lambda item: (item.overdue, item.open),
        reverse=True,
    )

    return DashboardOut(
        stats=stats,
        status_counts=dict(status_counts),
        overdue=await resolutions_out(db, overdue),
        flagged=await resolutions_out(db, flagged),
        load=load_out,
    )


# ── ร่างวาระ (FR-M5-01) ─────────────────────────────────────────────────

@router.post("/series/{series_id}/agenda/generate", response_model=AgendaOut, status_code=201)
async def generate(
    series_id: UUID,
    db: AsyncSession = Depends(get_db),
    org: Organization = Depends(current_org),
    actor: str = Depends(current_actor),
):
    series = await get_or_404(db, MeetingSeries, series_id, "ชุดการประชุม")

    #  FR-M9-04 ห้ามสร้างวาระจากการประชุมที่ยังไม่รับรอง
    pending = (
        await db.execute(
            select(Meeting).where(
                Meeting.series_id == series_id,
                Meeting.status.in_(("draft", "reviewed", "processing")),
            )
        )
    ).scalars().all()
    if pending:
        raise HTTPException(
            status_code=409,
            detail=(
                f"มีการประชุม {len(pending)} ครั้งที่ยังไม่ได้รับรองรายงาน "
                "มติจากรายงานที่ยังไม่รับรองยังไม่มีผลผูกพัน จึงยังสร้างวาระไม่ได้"
            ),
        )

    draft = await generate_agenda(db, series)
    await audit(
        db, org.id, actor, "generate_agenda", "agenda_draft", draft.id,
        f"ครั้งที่ {draft.target_sequence_no}/{series.fiscal_year}",
    )
    await db.commit()
    return await _agenda_out(db, draft.id)


async def _agenda_out(db: AsyncSession, draft_id: UUID) -> AgendaOut:
    draft = await db.get(AgendaDraft, draft_id)
    items = (
        await db.execute(
            select(AgendaItem).where(AgendaItem.agenda_draft_id == draft_id).order_by(AgendaItem.sort_order)
        )
    ).scalars().all()
    return AgendaOut.model_validate({**_draft_dict(draft), "items": list(items)})


# ── ถาม-ตอบข้ามการประชุม (M8) ───────────────────────────────────────────

@router.post("/series/{series_id}/ask", response_model=QaAnswerOut)
async def ask(series_id: UUID, payload: Question, db: AsyncSession = Depends(get_db)):
    await get_or_404(db, MeetingSeries, series_id, "ชุดการประชุม")
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="กรุณาระบุคำถาม")

    result = await qa_service.answer_question(db, series_id, question)
    log = QaLog(
        series_id=series_id,
        question=question,
        answer=result.answer,
        source=result.source,
        citations=[_jsonable(c) for c in result.citations],
        timeline=[_jsonable(t) for t in result.timeline],
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


def _jsonable(data: dict) -> dict:
    out = {}
    for key, value in data.items():
        if isinstance(value, UUID):
            out[key] = str(value)
        elif isinstance(value, date):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


@router.post("/reset-demo")
async def reset_demo_database(db: AsyncSession = Depends(get_db)):
    """ล้างฐานข้อมูลแล้วสร้างข้อมูลตั้งต้นใหม่ตาม Mock_Data_Update.md"""
    from app.seed import reset, seed
    await reset(db)
    await seed(db)
    return {"status": "ok", "message": "รีเซตข้อมูลเดโม NovaTech Studio เรียบร้อย"}


@router.get("/bootstrap", response_model=Bootstrap)
async def bootstrap(db: AsyncSession = Depends(get_db), org: Organization = Depends(current_org)):
    """
    ส่งข้อมูลทั้ง org ในรูปเดียวกับ Database ของ frontend
    หน้าจอฝั่ง client เก็บ state ทั้งก้อนอยู่แล้ว การดึงทีเดียวจึงเรียบง่ายกว่าการต่อ endpoint ทีละหน้า
    ถ้าข้อมูลโตกว่าระดับ pilot ค่อยแตกเป็น endpoint ย่อยตาม §6 ซึ่งมีให้ครบแล้ว
    """
    if org.name != "NovaTech Studio (Demo Workspace)":
        from app.seed import reset, seed
        await reset(db)
        await seed(db)
        org = (await db.execute(select(Organization).order_by(Organization.created_at))).scalars().first()
    series = list(
        (await db.execute(select(MeetingSeries).where(MeetingSeries.org_id == org.id))).scalars().all()
    )
    series_ids = [s.id for s in series]

    people = list(
        (await db.execute(select(Person).where(Person.org_id == org.id))).scalars().all()
    )
    aliases = list(
        (
            await db.execute(
                select(PersonAlias).where(PersonAlias.person_id.in_([p.id for p in people] or [None]))
            )
        ).scalars().all()
    )
    meetings = list(
        (
            await db.execute(
                select(Meeting).where(Meeting.series_id.in_(series_ids or [None])).order_by(Meeting.sequence_no)
            )
        ).scalars().all()
    )
    meeting_ids = [m.id for m in meetings]
    segments = list(
        (
            await db.execute(
                select(TranscriptSegment)
                .where(TranscriptSegment.meeting_id.in_(meeting_ids or [None]))
                .order_by(TranscriptSegment.start_ms)
            )
        ).scalars().all()
    )
    resolutions = list(
        (
            await db.execute(select(Resolution).where(Resolution.series_id.in_(series_ids or [None])))
        ).scalars().all()
    )
    resolution_ids = [r.id for r in resolutions]
    links = list(
        (
            await db.execute(
                select(ResolutionLink)
                .where(ResolutionLink.resolution_id.in_(resolution_ids or [None]))
                .order_by(ResolutionLink.created_at)
            )
        ).scalars().all()
    )
    history = list(
        (
            await db.execute(
                select(ResolutionHistory)
                .where(ResolutionHistory.resolution_id.in_(resolution_ids or [None]))
                .order_by(ResolutionHistory.changed_at.desc())
            )
        ).scalars().all()
    )
    proposals = list(
        (
            await db.execute(select(Proposal).where(Proposal.meeting_id.in_(meeting_ids or [None])))
        ).scalars().all()
    )
    drafts = list(
        (
            await db.execute(select(AgendaDraft).where(AgendaDraft.series_id.in_(series_ids or [None])))
        ).scalars().all()
    )
    agenda_items = list(
        (
            await db.execute(
                select(AgendaItem)
                .where(AgendaItem.agenda_draft_id.in_([d.id for d in drafts] or [None]))
                .order_by(AgendaItem.sort_order)
            )
        ).scalars().all()
    )
    actions = list(
        (
            await db.execute(
                select(OutboundAction).order_by(OutboundAction.created_at.desc())
            )
        ).scalars().all()
    )
    audit_rows = list(
        (
            await db.execute(
                select(AuditLog).where(AuditLog.org_id == org.id).order_by(AuditLog.created_at.desc()).limit(200)
            )
        ).scalars().all()
    )
    qa_rows = list(
        (
            await db.execute(
                select(QaLog).where(QaLog.series_id.in_(series_ids or [None])).order_by(QaLog.asked_at)
            )
        ).scalars().all()
    )

    items_by_draft: dict[UUID, list] = defaultdict(list)
    for item in agenda_items:
        items_by_draft[item.agenda_draft_id].append(item)

    qa_by_series: dict[str, list[QaAnswerOut]] = defaultdict(list)
    for row in qa_rows:
        qa_by_series[str(row.series_id)].append(QaAnswerOut.model_validate(row))

    return Bootstrap(
        org=OrganizationOut.model_validate(org),
        people=[PersonOut.model_validate(p) for p in people],
        aliases=[AliasOut.model_validate(a) for a in aliases],
        series=[SeriesOut.model_validate(s) for s in series],
        meetings=[MeetingOut.model_validate(m) for m in meetings],
        segments=[SegmentOut.model_validate(s) for s in segments],
        resolutions=await resolutions_out(db, resolutions),
        links=[LinkOut.model_validate(link) for link in links],
        history=[HistoryOut.model_validate(h) for h in history],
        proposals=[ProposalOut.model_validate(p) for p in proposals],
        agendas=[
            AgendaOut.model_validate({**_draft_dict(d), "items": items_by_draft.get(d.id, [])})
            for d in drafts
        ],
        actions=[ActionOut.model_validate(a) for a in actions],
        audit=[AuditOut.model_validate(a) for a in audit_rows],
        qa=dict(qa_by_series),
    )


def _draft_dict(draft: AgendaDraft) -> dict:
    return {
        "id": draft.id,
        "series_id": draft.series_id,
        "target_meeting_date": draft.target_meeting_date,
        "target_sequence_no": draft.target_sequence_no,
        "status": draft.status,
        "created_at": draft.created_at,
    }
