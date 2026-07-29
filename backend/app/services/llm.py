# app/services/llm.py
import json
import logging
from openai import OpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize OpenAI client pointing to the Pathumma Tokenmind API Base
client = OpenAI(
    base_url=settings.PATHUMMA_BASE_URL,
    api_key=settings.APP_AI4THAI_API_KEY,  # Standard Authorization: Bearer
)

def summarize_with_qwen(transcript: str) -> dict:
    """
    Sends the meeting transcript to Pathumma/ThaiLLM model and extracts structured JSON.
    """
    system_prompt = """
    You are an expert executive secretary. Process the following meeting transcript.
    Your response MUST be a valid JSON object matching this schema exactly:
    {
      "executive_summary": ["bullet point 1", "bullet point 2"],
      "key_decisions": ["decision 1"],
      "action_items": [
        {
          "task": "Task description",
          "assignee": "Name",
          "due_date": "YYYY-MM-DD"
        }
      ]
    }
    Do not output any introductory or concluding text—ONLY raw JSON.
    """

    try:
        response = client.chat.completions.create(
            # Pass custom apikey header required by AI4Thai API gateway
            extra_headers={
                "apikey": settings.APP_AI4THAI_API_KEY,
                "x-api-key": settings.APP_AI4THAI_API_KEY,
            },
            model=settings.PATHUMMA_MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Transcript:\n{transcript}"}
            ],
            temperature=0.2,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        return json.loads(content)

    except Exception as e:
        logger.error(f"Error calling Pathumma LLM: {e}")
        raise RuntimeError(f"Pathumma LLM Summarization failed: {e}")


def ask_meeting_question(transcript: str, question: str, conversation_history: list = None) -> str:
    """
    Q&A endpoint leveraging Pathumma LLM for Thai-aware meeting context Q&A.
    """
    if conversation_history is None:
        conversation_history = []

    system_prompt = (
        "You are an AI meeting assistant. Answer the user's question based strictly on the "
        "provided meeting transcript below. If the answer is not mentioned in the transcript, "
        "state politely in Thai that it was not covered in the meeting.\n\n"
        f"--- MEETING TRANSCRIPT ---\n{transcript}\n--------------------------"
    )

    messages = [{"role": "system", "content": system_prompt}]
    for turn in conversation_history:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": question})

    try:
        response = client.chat.completions.create(
            extra_headers={
                "apikey": settings.APP_AI4THAI_API_KEY,
                "x-api-key": settings.APP_AI4THAI_API_KEY,
            },
            model=settings.PATHUMMA_MODEL_NAME,
            messages=messages,
            temperature=0.3,
        )
        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"Failed to answer meeting question with Pathumma: {e}")
        raise RuntimeError(f"Pathumma Q&A service error: {e}")