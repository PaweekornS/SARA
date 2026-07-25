import json
import os
from celery import Celery
from app.services.asr import transcribe_audio
from app.services.llm import summarize_with_qwen
from app.services.mcp_agent import dispatch_mcp_email_tool

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("tasks", broker=redis_url, backend=redis_url)

@celery_app.task(name="process_meeting_task")
def process_meeting_task(meeting_id: str, file_path: str):
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
                action_items=parsed_result["action_items"],
                summary=parsed_result["executive_summary"]
            )

        # Step 4: Update DB record to COMPLETED
        return {"status": "SUCCESS", "meeting_id": meeting_id}

    except Exception as e:
        # Update DB status to FAILED
        return {"status": "FAILED", "error": str(e)}