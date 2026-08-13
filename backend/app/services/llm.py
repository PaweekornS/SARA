"""
ตัวเชื่อม LLM (AI4Thai Pathumma / ThaiLLM)

ไฟล์นี้รู้แค่ "เรียกโมเดลยังไง" ไม่รู้เรื่องมติหรือการประชุม
ตรรกะการสกัดมติอยู่ใน services/extraction.py
"""

from __future__ import annotations

import json
import logging
import re

from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

client = OpenAI(
    base_url=settings.PATHUMMA_BASE_URL,
    api_key=settings.APP_AI4THAI_API_KEY,
    timeout=settings.LLM_TIMEOUT_SECONDS,
)

# AI4Thai gateway ต้องการ apikey header เพิ่มจาก Authorization ปกติ
_EXTRA_HEADERS = {
    "apikey": settings.APP_AI4THAI_API_KEY,
    "x-api-key": settings.APP_AI4THAI_API_KEY,
}


class LlmError(RuntimeError):
    """เรียกโมเดลไม่สำเร็จ หรือได้คำตอบที่ใช้ต่อไม่ได้"""


def chat(messages: list[dict], temperature: float = 0.2, json_mode: bool = False) -> str:
    kwargs = {
        "model": settings.PATHUMMA_MODEL_NAME,
        "messages": messages,
        "temperature": temperature,
        "extra_headers": _EXTRA_HEADERS,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as err:  # noqa: BLE001
        raise LlmError(f"เรียก {settings.PATHUMMA_MODEL_NAME} ไม่สำเร็จ: {err}") from err

    content = (response.choices[0].message.content or "").strip()
    if not content:
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
    except LlmError:
        raw = chat(messages, temperature=temperature, json_mode=False)

    return _parse_json(raw)


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", raw, re.DOTALL)
    if fenced:
        raw = fenced.group(1).strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    #  หาก้อน {...} ที่ใหญ่ที่สุดในข้อความ
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError as err:
            raise LlmError(f"โมเดลตอบกลับมาไม่ใช่ JSON ที่อ่านได้: {err}") from err
    raise LlmError("โมเดลตอบกลับมาโดยไม่มี JSON")


def answer_from_context(question: str, context: str) -> str:
    """
    ตอบคำถามโดยอิงบริบทที่ส่งให้เท่านั้น
    ถ้าไม่มีข้อมูลต้องบอกว่าไม่มี ห้ามเดา — คำตอบผิดในบริบทเอกสารราชการเสียหายกว่าไม่ตอบ
    """
    system = (
        "คุณคือผู้ช่วยฝ่ายเลขานุการที่ประชุม ตอบคำถามโดยอ้างอิงจากข้อมูลที่ให้ไว้ด้านล่างเท่านั้น\n"
        "ถ้าข้อมูลที่ให้ไม่ครอบคลุมคำถาม ให้ตอบตรง ๆ ว่าไม่พบข้อมูลในบันทึกการประชุม ห้ามเดาหรือเติมเอง\n"
        "ตอบเป็นภาษาไทย กระชับ ไม่เกิน 5 ประโยค\n\n"
        f"--- ข้อมูลการประชุม ---\n{context}\n-----------------------"
    )
    return chat(
        [{"role": "system", "content": system}, {"role": "user", "content": question}],
        temperature=0.2,
    )
