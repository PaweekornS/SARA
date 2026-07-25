from fastapi import APIRouter, UploadFile, File, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from app.db.session import get_db
from app.db.models import Meeting, MeetingStatus
from app.workers.tasks import process_meeting_task

router = APIRouter(prefix="/meetings", tags=["Meetings"])

@router.post("/process", status_code=status.HTTP_202_ACCEPTED)
async def submit_meeting(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Ingest meeting audio/document, persist initial state, and queue processing.
    """
    # 1. Generate unique meeting ID and save raw file (e.g., to local storage or S3)
    meeting_id = uuid.uuid4()
    file_path = f"/tmp/{meeting_id}_{file.filename}"
    
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())

    # 2. Register meeting in Database with PENDING status
    new_meeting = Meeting(
        id=meeting_id,
        title=file.filename,
        status=MeetingStatus.PENDING,
        audio_path=file_path
    )
    db.add(new_meeting)
    await db.commit()

    # 3. Push to Redis/Celery queue asynchronously
    process_meeting_task.delay(str(meeting_id), file_path)

    return {
        "meeting_id": str(meeting_id),
        "status": "QUEUED",
        "message": "Meeting successfully submitted for processing."
    }

@router.get("/{meeting_id}/status")
async def get_meeting_status(meeting_id: str, db: AsyncSession = Depends(get_db)):
    """
    Poll meeting execution status from Next.js UI.
    """
    meeting = await db.get(Meeting, uuid.UUID(meeting_id))
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
        
    return {
        "meeting_id": str(meeting.id),
        "status": meeting.status,
        "summary": meeting.summary_json if meeting.status == MeetingStatus.COMPLETED else None
    }