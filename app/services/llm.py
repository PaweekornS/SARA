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
    system_prompt = """
    You are an expert executive secretary. Process the following meeting transcript.
    Your response MUST be a valid JSON object matching this schema exactly:
    {
      "executive_summary": ["bullet point 1", "bullet point 2"],
      "key_decisions": ["decision 1"],
      "participants": [
        {"name": "Somchai", "email": "somchai@example.com"},
        {"name": "Jane", "email": "jane@example.com"}
      ],
      "action_items": [
        {
          "task": "Task description",
          "assignee": "Name",
          "due_date": "YYYY-MM-DD"
        }
      ]
    }
    For the participant emails, you MUST strictly and only use 'punpawee30@gmail.com' and 'somchai@example.com' (do not construct other emails or use their actual emails).
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


def ask_meeting_question(transcript: str, question: str, conversation_history: list = None) -> str:
    """
    Answers user questions based strictly on the provided meeting transcript.
    """
    if conversation_history is None:
        conversation_history = []

    system_prompt = (
        "You are an AI meeting assistant. Answer the user's question based strictly on the "
        "provided meeting transcript below. If the answer is not mentioned in the transcript, "
        "state politely that it was not covered in the meeting.\n\n"
        f"--- MEETING TRANSCRIPT ---\n{transcript}\n--------------------------"
    )

    # Format messages array with System Prompt + Chat History + Current Question
    messages = [{"role": "system", "content": system_prompt}]
    
    # Append past conversation turns if present
    for turn in conversation_history:
        messages.append({"role": turn["role"], "content": turn["content"]})

    # Append current user question
    messages.append({"role": "user", "content": question})

    try:
        response = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://aithailand2026.local",
                "X-Title": "AI Thailand AIaaS",
            },
            model=settings.QWEN_MODEL_NAME,
            messages=messages,
            temperature=0.3,
        )
        return response.choices[0].message.content

    except Exception as e:
        logger.error(f"Failed to answer meeting question: {e}")
        raise RuntimeError(f"Q&A service error: {e}")