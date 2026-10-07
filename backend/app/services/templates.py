"""
รูปแบบการสรุปตามประเภทการประชุม

ทุก template ตอบ JSON ที่มีคีย์ร่วมกัน 3 ตัว: summary, key_points, action_items
คีย์อื่นใน `details` เป็นฟิลด์เฉพาะของ template นั้น (เช่น kpis, blockers)
และ `detail_labels` คือชื่อหัวข้อภาษาไทยที่หน้าจอและไฟล์ .docx ใช้แสดง
"""

from __future__ import annotations

from enum import Enum
from typing import Any

ACTION_ITEMS_SPEC = """  "action_items": [
    {
      "task": "งานที่ต้องทำ เขียนให้ชัดว่าทำอะไร",
      "owner": "ชื่อหรือ Speaker N ที่รับงาน หรือ \\"\\" ถ้าไม่ระบุ",
      "deadline": "YYYY-MM-DD หรือ null ถ้าไม่ได้ระบุวันที่ชัดเจน",
      "segment_index": 12
    }
  ]"""

COMMON_RULES = """
กฎ:
- สรุปจากบันทึกที่ให้เท่านั้น ห้ามแต่งตัวเลข ชื่อ หรือวันที่ที่ไม่มีในบทสนทนา
- segment_index คือเลขในวงเล็บเหลี่ยม [n] หน้าท่อนที่พูดถึงงานนั้น
- ตอบกลับเป็น JSON ก้อนเดียวเท่านั้น ไม่ต้องมีคำอธิบายอื่น"""


class MeetingTemplateType(str, Enum):
    GENERAL = "general"
    MARKETING = "marketing"
    FINANCE = "finance"
    TECH_STANDUP = "tech_standup"


TEMPLATES: dict[MeetingTemplateType, dict[str, Any]] = {
    MeetingTemplateType.GENERAL: {
        "id": "general",
        "name": "ทั่วไป (Executive Summary)",
        "description": "สรุปภาพรวม ประเด็นสำคัญ ข้อตกลง และงานที่ต้องทำต่อ",
        "detail_labels": {"decisions": "ข้อตกลง", "next_steps": "ขั้นตอนถัดไป"},
        "system_prompt": f"""คุณคือผู้ช่วยสรุปการประชุมมืออาชีพ
ภารกิจ:
1. summary: สรุปภาพรวมอย่างกระชับ ตัดบทสนทนาที่ไม่จำเป็นออก
2. key_points: ประเด็นสำคัญ 2-5 ข้อ
3. decisions: ข้อตกลงหรือการตัดสินใจที่ชัดเจนแล้ว
4. action_items: งานที่ต้องทำต่อ ใครทำ เสร็จเมื่อไร
5. next_steps: ขั้นตอนถัดไป

ตอบกลับเป็น JSON:
{{
  "summary": "...",
  "key_points": ["..."],
  "decisions": ["..."],
{ACTION_ITEMS_SPEC},
  "next_steps": ["..."]
}}
{COMMON_RULES}""",
    },
    MeetingTemplateType.MARKETING: {
        "id": "marketing",
        "name": "การตลาดและการเติบโต (Marketing & Growth)",
        "description": "วัตถุประสงค์แคมเปญ กลุ่มเป้าหมาย ช่องทาง ไอเดีย KPI และแผนงาน",
        "detail_labels": {
            "campaign_objectives": "วัตถุประสงค์แคมเปญ",
            "target_audience": "กลุ่มเป้าหมาย",
            "channels": "ช่องทาง",
            "creative_ideas": "ไอเดียสร้างสรรค์",
            "kpis": "ตัวชี้วัด (KPI)",
        },
        "system_prompt": f"""คุณคือนักวางแผนกลยุทธ์การตลาดและการเติบโต
ภารกิจ:
1. summary: ทิศทางการตลาดที่คุยกัน
2. key_points: ประเด็นสำคัญ 2-5 ข้อ
3. campaign_objectives และ target_audience
4. channels และ creative_ideas
5. kpis: เป้าหมายตัวเลข เช่น GMV, ROAS, Conversion
6. action_items: งานที่แต่ละคนรับผิดชอบ

ตอบกลับเป็น JSON:
{{
  "summary": "...",
  "key_points": ["..."],
  "campaign_objectives": "...",
  "target_audience": "...",
  "channels": ["..."],
  "creative_ideas": ["..."],
  "kpis": ["..."],
{ACTION_ITEMS_SPEC}
}}
{COMMON_RULES}""",
    },
    MeetingTemplateType.FINANCE: {
        "id": "finance",
        "name": "บัญชีและการเงิน (Financial & Budgeting)",
        "description": "งบประมาณ ต้นทุน ความเสี่ยง และรายการที่รออนุมัติ",
        "detail_labels": {
            "budget_allocation": "การจัดสรรงบประมาณ",
            "cost_breakdown": "รายการค่าใช้จ่าย",
            "financial_risks": "ความเสี่ยงทางการเงิน",
            "approvals_required": "รายการที่รออนุมัติ",
        },
        "system_prompt": f"""คุณคือนักวิเคราะห์การเงินและบัญชีอาวุโส
ภารกิจ:
1. summary: สถานะงบประมาณหรือการตัดสินใจทางการเงิน
2. key_points: ประเด็นสำคัญ 2-5 ข้อ
3. budget_allocation: งบที่อนุมัติหรือขอเพิ่ม
4. cost_breakdown, financial_risks, approvals_required
5. action_items: งานที่ต้องทำต่อ

ตอบกลับเป็น JSON:
{{
  "summary": "...",
  "key_points": ["..."],
  "budget_allocation": [{{"item": "...", "amount": "...", "source": "..."}}],
  "cost_breakdown": ["..."],
  "financial_risks": ["..."],
  "approvals_required": ["..."],
{ACTION_ITEMS_SPEC}
}}
{COMMON_RULES}""",
    },
    MeetingTemplateType.TECH_STANDUP: {
        "id": "tech_standup",
        "name": "ทีมพัฒนาและเทคนิค (Tech / Agile Standup)",
        "description": "งานที่เสร็จ งานที่กำลังทำ ปัญหาติดขัด และกำหนดการ release",
        "detail_labels": {
            "completed_tasks": "งานที่เสร็จแล้ว",
            "in_progress": "งานที่กำลังทำ",
            "blockers": "ปัญหาติดขัด",
            "deploy_schedule": "กำหนดการ release",
        },
        "system_prompt": f"""คุณคือ Technical Lead / Scrum Master
ภารกิจ:
1. summary: ความคืบหน้าของสปรินต์และความพร้อมของระบบ
2. key_points: ประเด็นสำคัญ 2-5 ข้อ
3. completed_tasks, in_progress, blockers
4. deploy_schedule: วันเวลา deploy หรือ QA
5. action_items: งานที่ต้องทำต่อ

ตอบกลับเป็น JSON:
{{
  "summary": "...",
  "key_points": ["..."],
  "completed_tasks": ["..."],
  "in_progress": ["..."],
  "blockers": ["..."],
  "deploy_schedule": "...",
{ACTION_ITEMS_SPEC}
}}
{COMMON_RULES}""",
    },
}


def get_template(template_id: str | MeetingTemplateType | None) -> dict[str, Any]:
    """คืน template ตาม id ถ้าไม่รู้จักให้ใช้แบบทั่วไป"""
    value = template_id.value if isinstance(template_id, MeetingTemplateType) else str(template_id or "").lower()
    for tmpl in TEMPLATES.values():
        if tmpl["id"] == value:
            return tmpl
    return TEMPLATES[MeetingTemplateType.GENERAL]


def is_known_template(template_id: str) -> bool:
    return any(tmpl["id"] == template_id for tmpl in TEMPLATES.values())


def list_templates() -> list[dict[str, Any]]:
    return [
        {
            "id": tmpl["id"],
            "name": tmpl["name"],
            "description": tmpl["description"],
            "detail_labels": tmpl["detail_labels"],
        }
        for tmpl in TEMPLATES.values()
    ]
