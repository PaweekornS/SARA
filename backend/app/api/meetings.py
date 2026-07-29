from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel
from typing import List, Optional
import uuid

from app.services.llm import ask_meeting_question
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
async def get_meeting_status(meeting_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """
    Poll meeting execution status from Next.js UI.
    """
    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
        
    return {
        "meeting_id": str(meeting.id),
        "status": meeting.status,
        "summary": meeting.summary_json if meeting.status == MeetingStatus.COMPLETED else None
    }

# Request Payload Schema
class QuestionRequest(BaseModel):
    question: str
    history: Optional[List[dict]] = []  # e.g. [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]

@router.post("/{meeting_id}/ask")
async def ask_question(
    meeting_id: uuid.UUID,
    payload: QuestionRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Q&A interface scoped to a specific meeting transcript.
    """
    # 1. Fetch meeting record from database
    meeting = await db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    if not meeting.raw_transcript:
        raise HTTPException(
            status_code=400, 
            detail="Transcript is not available yet. Meeting status is still processing or failed."
        )

    # 2. Get answer from Qwen 3.5 via AI4Thai / Pathumma
    answer = ask_meeting_question(
        transcript=meeting.raw_transcript,
        question=payload.question,
        conversation_history=payload.history
    )

    return {
        "meeting_id": str(meeting.id),
        "question": payload.question,
        "answer": answer
    }

@router.get("/recipients", response_model=List[str])
async def get_recipient_emails():
    """
    Mock API that returns the list of recipient emails for the meeting platform integration.
    """
    return ["test01@gmail.com", "test02@gmail.com"]