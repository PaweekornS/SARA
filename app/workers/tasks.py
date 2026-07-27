import json
import os
import asyncio
import uuid
from celery import Celery
from app.services.asr import transcribe_audio
from app.services.llm import summarize_with_qwen
from app.services.mcp_agent import dispatch_mcp_email_tool
from app.db.session import AsyncSessionLocal
from app.db.models import Meeting, MeetingStatus

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("tasks", broker=redis_url, backend=redis_url)

def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


async def update_meeting_db(meeting_id: str, status: MeetingStatus, raw_transcript: str = None, summary_json: dict = None):
    async with AsyncSessionLocal() as session:
        try:
            meeting_uuid = uuid.UUID(meeting_id)
            meeting = await session.get(Meeting, meeting_uuid)
            if meeting:
                meeting.status = status
                if raw_transcript is not None:
                    meeting.raw_transcript = raw_transcript
                if summary_json is not None:
                    meeting.summary_json = summary_json
                await session.commit()
        except Exception as e:
            print(f"Error updating meeting status in DB: {e}")


@celery_app.task(name="process_meeting_task")
def process_meeting_task(meeting_id: str, file_path: str):
    # Set status to PROCESSING
    run_async(update_meeting_db(meeting_id, MeetingStatus.PROCESSING))
    
    try:
        # Step 1: Speech-to-Text via AI4Thai API
        raw_transcript = transcribe_audio(file_path)

        # Step 2: Extract Structured Summary & Action Items via Qwen-3.5-14B
        prompt = f"""
        You are an expert corporate secretary. Summarize the following meeting transcript.
        Output MUST be valid JSON with the following key structure:
        {{
            "executive_summary": ["bullet 1", "bullet 2"],
            "key_decisions": ["decision 1"],
            "action_items": [
                {{"task": "Description", "assignee": "Name", "email": "user@example.com", "due_date": "YYYY-MM-DD"}}
            ]
        }}
        Transcript:
        {raw_transcript}
        """
        
        parsed_result = summarize_with_qwen(prompt)

        # Step 3: Trigger MCP Server Tool to send emails automatically
        if parsed_result.get("action_items"):
            dispatch_mcp_email_tool(
                meeting_title=f"Meeting Summary - {meeting_id}",
                participants=parsed_result.get("participants", []),
                action_items=parsed_result.get("action_items", []),
                summary=parsed_result.get("executive_summary", [])
            )

        # Step 4: Update DB record to COMPLETED
        run_async(update_meeting_db(meeting_id, MeetingStatus.COMPLETED, raw_transcript, parsed_result))
        return {"status": "SUCCESS", "meeting_id": meeting_id}

    except Exception as e:
        # Update DB status to FAILED
        run_async(update_meeting_db(meeting_id, MeetingStatus.FAILED))
        return {"status": "FAILED", "error": str(e)}