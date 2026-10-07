"""
ตัวเชื่อม LLM (AI4Thai Pathumma / ThaiLLM)

ไฟล์นี้รู้แค่ "เรียกโมเดลยังไง" ไม่รู้เรื่องการประชุม
ตรรกะการสรุปอยู่ใน services/extraction.py
"""

from __future__ import annotations

import json
import logging
import re

from openai import OpenAI

from app.core.config import settings

# ── Global Variables & Constants ─────────────────────────────────────────────

logger = logging.getLogger(__name__)

if settings.use_openrouter:
    MODEL = settings.OPENROUTER_LLM_MODEL
    client = OpenAI(
        base_url=settings.OPENROUTER_BASE_URL,
        api_key=settings.APP_OPENROUTER_API_KEY,
        timeout=settings.LLM_TIMEOUT_SECONDS,
        max_retries=3,
    )
    _EXTRA_HEADERS = {"X-Title": "SARA demo"}
    # qwen3.5 คิดยาวก่อนตอบเป็นค่าเริ่มต้น — ปิดไว้ให้ถูกและเร็ว
    _EXTRA_BODY: dict | None = {"reasoning": {"enabled": False}}
else:
    MODEL = settings.PATHUMMA_MODEL_NAME
    client = OpenAI(
        base_url=settings.PATHUMMA_BASE_URL,
        api_key=settings.APP_AI4THAI_API_KEY,
        timeout=settings.LLM_TIMEOUT_SECONDS,
        max_retries=3,
    )
    # AI4Thai gateway ต้องการ apikey header เพิ่มจาก Authorization ปกติ
    _EXTRA_HEADERS = {
        "apikey": settings.APP_AI4THAI_API_KEY,
        "x-api-key": settings.APP_AI4THAI_API_KEY,
    }
    _EXTRA_BODY = None


# ── Classes & Exceptions ─────────────────────────────────────────────────────

class LlmError(RuntimeError):
    """เรียกโมเดลไม่สำเร็จ หรือได้คำตอบที่ใช้ต่อไม่ได้"""


# ── Functions ────────────────────────────────────────────────────────────────

def chat(
    messages: list[dict],
    temperature: float = 0.2,
    json_mode: bool = False,
    max_tokens: int = 2048,
    model: str | None = None,
) -> str:
    model = model or MODEL
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "extra_headers": _EXTRA_HEADERS,
    }
    if _EXTRA_BODY:
        kwargs["extra_body"] = _EXTRA_BODY
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as err:  # noqa: BLE001
        raise LlmError(f"เรียก {model} ไม่สำเร็จ: {err}") from err

    content = (response.choices[0].message.content or "").strip()
    if "</think>" in content:
        content = content.split("</think>")[-1].strip()

    if not content:
        # Fallback to full raw text if think filter stripped everything
        raw_msg = (response.choices[0].message.content or "").strip()
        if raw_msg:
            content = raw_msg
        else:
            raise LlmError("โมเดลตอบกลับมาเป็นค่าว่าง")
    return content


def chat_json(system: str, user: str, temperature: float = 0.1) -> dict:
    """
    ขอผลลัพธ์เป็น JSON — ลอง json_mode ก่อน ถ้า gateway ไม่รองรับค่อยแกะจากข้อความ
    โมเดลเล็กชอบแนบคำอธิบายมาด้วย จึงต้องดึงเฉพาะก้อน JSON ออกมา
    """
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    try:
        raw = chat(messages, temperature=temperature, json_mode=True)
        return _parse_json(raw)
    except Exception:
        pass

    raw = chat(messages, temperature=temperature, json_mode=False)
    return _parse_json(raw)


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    if "</think>" in raw:
        after_think = raw.split("</think>")[-1].strip()
        if after_think:
            raw = after_think

    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", raw, re.DOTALL)
    if fenced:
        raw = fenced.group(1).strip()

    try:
        return json.loads(raw, strict=False)
    except json.JSONDecodeError:
        pass

    # หาก้อน {...} ที่ใหญ่ที่สุดในข้อความ
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1], strict=False)
        except json.JSONDecodeError as err:
            raise LlmError(f"โมเดลตอบกลับมาไม่ใช่ JSON ที่อ่านได้: {err}") from err

    # หาก้อน [...]
    start_arr, end_arr = raw.find("["), raw.rfind("]")
    if start_arr != -1 and end_arr > start_arr:
        try:
            arr = json.loads(raw[start_arr : end_arr + 1], strict=False)
            return {"items": arr}
        except json.JSONDecodeError as err:
            raise LlmError(f"โมเดลตอบกลับมาไม่ใช่ JSON ที่อ่านได้: {err}") from err

    raise LlmError("โมเดลตอบกลับมาโดยไม่มี JSON")


_THAI_CHAR = re.compile(r"[฀-๿]")
_LATIN_CHAR = re.compile(r"[A-Za-z]")


def detect_language(text: str) -> str:
    """'th' หรือ 'en' — นับอักษรไทยเทียบอักษรละติน (คำอังกฤษปนในประชุมไทยยังนับเป็นไทย)"""
    thai = len(_THAI_CHAR.findall(text))
    latin = len(_LATIN_CHAR.findall(text))
    return "th" if thai * 3 >= latin and thai > 0 else "en" if latin else "th"


def language_rule(lang: str) -> str:
    """ต่อท้าย system prompt เพื่อบังคับภาษาของผลลัพธ์ (คีย์ JSON คงเดิม)"""
    if lang == "en":
        return "\n- The meeting is in English: write every text value in English. Keep the JSON keys exactly as specified."
    return "\n- เขียนทุกข้อความเป็นภาษาไทย"


def answer_from_context(question: str, context: str) -> str:
    """
    ตอบคำถามโดยอิงบริบทที่ส่งให้เท่านั้น
    ถ้าไม่มีข้อมูลต้องบอกว่าไม่มี ห้ามเดา
    """
    system = (
        "คุณคือผู้ช่วยที่ตอบคำถามเกี่ยวกับการประชุมของผู้ใช้ โดยอ้างอิงจากข้อมูลด้านล่างเท่านั้น\n"
        "ถ้าข้อมูลไม่ครอบคลุมคำถาม ให้ตอบตรง ๆ ว่าไม่พบในบันทึกการประชุม ห้ามเดาหรือเติมเอง\n"
        f"{'ตอบเป็นภาษาไทย' if detect_language(question) == 'th' else 'Answer in English'} กระชับ ไม่เกิน 5 ประโยค\n\n"
        f"--- ข้อมูลการประชุม ---\n{context}\n-----------------------"
    )
    raw = chat(
        [{"role": "system", "content": system}, {"role": "user", "content": question}],
        temperature=0.2,
    )
    if "</think>" in raw:
        after = raw.split("</think>")[-1].strip()
        if after:
            raw = after
    return raw
