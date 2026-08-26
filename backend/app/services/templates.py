"""
SARA Domain-Specific Summarization Templates (M3/v3.0.0-PROD)

Provides modular prompt architectures tailored for specific meeting types:
1. General Secretary / Executive
2. Marketing & Growth Strategy
3. Accounting & Financial Budgeting
4. Tech / Agile Standup
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict


class MeetingTemplateType(str, Enum):
    GENERAL = "general"
    MARKETING = "marketing"
    FINANCE = "finance"
    TECH_STANDUP = "tech_standup"


TEMPLATES: Dict[MeetingTemplateType, Dict[str, Any]] = {
    MeetingTemplateType.GENERAL: {
        "id": "general",
        "name": "เลขานุการทั่วไป / ผู้บริหาร (Executive Summary)",
        "description": "เน้นมติที่ประชุม (Decisions), ข้อตกลงร่วมกัน, และ Action Items (ใคร ทำอะไร ส่งเมื่อไหร่)",
        "system_prompt": """คุณคือผู้ช่วยเลขานุการและผู้บริหารมืออาชีพ สรุปมติและสาระสำคัญจากการประชุม
ภารกิจ:
1. สรุปภาพรวมการประชุม (summary): สรุปสาระสำคัญอย่างกระชับ ชัดเจน ตัดบทสนทนาที่ไม่จำเป็นออก (ห้ามระบุวันที่จัดประชุม)
2. ประเด็นสำคัญ (key_points): หัวข้อสรุป 2-5 ข้อ
3. มติและข้อตกลง (decisions): รายการการอนุมัติ ข้อตกลง หรือนโยบายที่เคาะแล้ว
4. รายการงานที่ต้องทำต่อ (action_items): ระบุชัดเจนว่า [Speaker N] หรือฝ่ายใด ต้องทำอะไร ส่งเมื่อไหร่
5. ขั้นตอนต่อไป (next_steps): ลำดับงานถัดไป

ตอบกลับเป็น JSON เท่านั้น:
{
  "summary": "ข้อความสรุปภาพรวม...",
  "key_points": ["ประเด็น 1", "ประเด็น 2"],
  "decisions": [
    {
      "text": "ข้อความมติหรือข้อตกลงที่ชัดเจน",
      "assigned_speaker": "Speaker 1 หรือ ไม่ระบุ",
      "category": "operations",
      "confidence": 0.95
    }
  ],
  "action_items": [
    {
      "task": "รายละเอียดงานที่ต้องทำ",
      "assigned_speaker": "Speaker 2",
      "deadline": "วันศุกร์นี้ หรือ YYYY-MM-DD หรือ null",
      "priority": "high | medium | low"
    }
  ],
  "next_steps": ["ขั้นตอนต่อไป 1"],
  "new_resolutions": [],
  "updates": [],
  "speakers": []
}""",
        "output_schema": ["summary", "key_points", "decisions", "action_items", "next_steps"],
    },
    MeetingTemplateType.MARKETING: {
        "id": "marketing",
        "name": "การตลาดและการเติบโต (Marketing & Growth)",
        "description": "เน้นวัตถุประสงค์แคมเปญ, กลุ่มเป้าหมาย, ช่องทางการสื่อสาร, ไอเดียสร้างสรรค์, KPIs และ Action Plan",
        "system_prompt": """คุณคือนักวางแผนกลยุทธ์การตลาดและการเติบโต (Marketing & Growth Strategist)
ภารกิจ:
1. สรุปภาพรวมแคมเปญ/กลยุทธ์ (summary): สรุปทิศทางการตลาดที่คุยในที่ประชุม
2. วัตถุประสงค์และกลุ่มเป้าหมาย (campaign_objectives & target_audience): ลูกค้ากลุ่มไหน ต้องการผลลัพธ์อะไร
3. ช่องทางการสื่อสารและไอเดียสร้างสรรค์ (channels & creative_ideas): ไอเดีย คอนเทนต์ ช่องทางโปรโมท
4. ตัวชี้วัดความสำเร็จ (kpis): เป้าหมายตัวเลข เช่น GMV, CPL, ROAS, Reach, Conversion
5. แผนปฏิบัติการ (action_plan): งานที่แต่ละคนรับผิดชอบ

ตอบกลับเป็น JSON เท่านั้น:
{
  "summary": "ข้อความสรุปกลยุทธ์การตลาด...",
  "campaign_objectives": "วัตถุประสงค์หลักของแคมเปญ...",
  "target_audience": "กลุ่มเป้าหมาย เช่น วัยรุ่น 18-25 ปี...",
  "channels": ["Facebook", "TikTok", "KOL"],
  "creative_ideas": ["คอนเทนต์แนว Real-time", "จัด Flash sale"],
  "kpis": ["GMV 5.0M THB", "ROAS > 4.0x"],
  "action_plan": [
    {
      "task": "ส่ง Key Visual และ Copy",
      "assigned_speaker": "Speaker 2",
      "deadline": "วันพุธหน้า"
    }
  ],
  "new_resolutions": [],
  "updates": [],
  "speakers": []
}""",
        "output_schema": ["summary", "campaign_objectives", "target_audience", "channels", "creative_ideas", "kpis", "action_plan"],
    },
    MeetingTemplateType.FINANCE: {
        "id": "finance",
        "name": "บัญชีและการเงิน (Financial & Budgeting)",
        "description": "เน้นการจัดสรรงบประมาณ, แจกแจงต้นทุน, ตัวเลขทางการเงิน, กระแสเงินสด และความเสี่ยง",
        "system_prompt": """คุณคือนักวิเคราะห์การเงินและบัญชีอาวุโส (Financial Analyst)
ภารกิจ:
1. สรุปภาพรวมทางการเงิน (summary): สรุปสถานะงบประมาณหรือการตัดสินใจทางการเงิน (ห้ามแต่งเติมตัวเลขที่ไม่มีในบทสนทนาเด็ดขาด)
2. การจัดสรรงบประมาณ (budget_allocation): แจกแจงงบที่ได้รับอนุมัติหรือขอเพิ่ม
3. รายการค่าใช้จ่ายและต้นทุน (cost_breakdown): รายละเอียดค่าใช้จ่ายแต่ละรายการ
4. ความเสี่ยงทางการเงินและภาษี (financial_risks): ข้อพึงระวัง หรือเงื่อนไขสัญญา
5. รายการที่ต้องรออนุมัติ (approvals_required): วงเงินที่ต้องผ่านการพิจารณาต่อ

ตอบกลับเป็น JSON เท่านั้น:
{
  "summary": "ข้อความสรุปสถานะงบประมาณ...",
  "budget_allocation": [
    {
      "item": "จัดซื้อ Cloud Server",
      "amount": "150,000 บาท",
      "source": "งบกลาง"
    }
  ],
  "cost_breakdown": ["ค่าบริการรายเดือน 12,000 บาท", "ค่า Setup 30,000 บาท"],
  "financial_risks": ["อัตราแลกเปลี่ยนผันผวน", "ภาษีหัก ณ ที่จ่าย 3%"],
  "approvals_required": ["เสนอผู้มีอำนาจลงนามสัปดาห์หน้า"],
  "new_resolutions": [],
  "updates": [],
  "speakers": []
}""",
        "output_schema": ["summary", "budget_allocation", "cost_breakdown", "financial_risks", "approvals_required"],
    },
    MeetingTemplateType.TECH_STANDUP: {
        "id": "tech_standup",
        "name": "ทีมพัฒนาและเทคนิค (Tech / Agile Standup)",
        "description": "เน้นงานที่เสร็จแล้ว, กำลังทำ, ปัญหาติดขัด (Blockers), การตัดสินใจด้านสถาปัตยกรรม และ Release Plan",
        "system_prompt": """คุณคือ Technical Lead / Scrum Master สรุปการประชุมทางเทคนิคหรือ Daily Standup
ภารกิจ:
1. สรุปภาพรวมสถานะระบบ (summary): สรุปความพร้อมของระบบและสปรินต์ปัจจุบัน
2. งานที่เสร็จแล้ว (completed_tasks): รายการฟีเจอร์หรือบั๊กที่แก้เสร็จแล้ว
3. งานที่กำลังดำเนินการ (in_progress): งานที่กำลังพัฒนาอยู่ แยกตาม [Speaker N]
4. ปัญหาและอุปสรรค (blockers): สิ่งที่ติดขัด หรือ dependency ที่รอทีมอื่น
5. กำหนดการ Release และทดสอบ (deploy_schedule): วันเวลา deploy หรือ QA test

ตอบกลับเป็น JSON เท่านั้น:
{
  "summary": "สรุปความคืบหน้าสปรินต์ที่ 14...",
  "completed_tasks": ["แก้ไขปัญหา Token Expire", "เพิ่ม Google OAuth API"],
  "in_progress": [
    {
      "task": "เชื่อมต่อ MCP Email Dispatch",
      "assigned_speaker": "Speaker 1"
    }
  ],
  "blockers": ["รอ API Key จากพาร์ทเนอร์"],
  "deploy_schedule": "Release UAT วันพฤหัสบดี 18:00 น.",
  "new_resolutions": [],
  "updates": [],
  "speakers": []
}""",
        "output_schema": ["summary", "completed_tasks", "in_progress", "blockers", "deploy_schedule"],
    },
}


def get_template(template_id: str | MeetingTemplateType | None) -> Dict[str, Any]:
    """Retrieve template definition by ID or enum, defaulting to general template."""
    if not template_id:
        return TEMPLATES[MeetingTemplateType.GENERAL]

    val = template_id.value if isinstance(template_id, MeetingTemplateType) else str(template_id).lower()
    for key, tmpl in TEMPLATES.items():
        if key.value == val or tmpl["id"] == val:
            return tmpl
    return TEMPLATES[MeetingTemplateType.GENERAL]


def list_templates() -> list[Dict[str, Any]]:
    """Return public list of templates for UI dropdowns and API metadata."""
    return [
        {
            "id": tmpl["id"],
            "name": tmpl["name"],
            "description": tmpl["description"],
            "output_schema": tmpl["output_schema"],
        }
        for tmpl in TEMPLATES.values()
    ]
