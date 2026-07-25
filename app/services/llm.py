import json
import logging
from openai import OpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

# OpenRouter utilizes the standard OpenAI client with a customized base_url
client = OpenAI(
    base_url=settings.OPENROUTER_BASE_URL,
    api_key=settings.OPENROUTER_API_KEY,
)

def summarize_with_qwen(transcript: str) -> dict:
    """
    Sends the meeting transcript to OpenRouter (Qwen 3.5 / 2.5)
    and enforces structured JSON output.
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
          "email": "user@email.com",
          "due_date": "YYYY-MM-DD"
        }
      ]
    }
    Do not output any introductory or concluding text—ONLY raw JSON.
    """

    try:
        response = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://aithailand2026.local",
                "X-Title": "AI Thailand AIaaS",
            },
            model=settings.QWEN_MODEL_NAME,
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
        logger.error(f"Error calling OpenRouter LLM: {e}")
        raise RuntimeError(f"LLM Summarization failed: {e}")