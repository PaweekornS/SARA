"""
ตัวเรียก MCP tool (M7)

action layer ทั้งหมดวิ่งผ่าน MCP server เพื่อให้สลับปลายทางได้โดยไม่แตะโค้ดหลัก
(อีเมลวันนี้ · ระบบติดตามงานพรุ่งนี้) ตามเจตนาของ FR-M7-05
"""

from __future__ import annotations

import logging

from mcp import ClientSession
from mcp.client.sse import sse_client

from app.core.config import settings
from app.core.security import magic_link_url
from app.db.models import Person, Resolution
from app.services.thai_format import thai_date

logger = logging.getLogger(__name__)


class McpError(RuntimeError):
    """เรียก MCP tool ไม่สำเร็จ"""


def _sse_url() -> str:
    url = settings.MCP_SERVER_URL
    if url.endswith("/mcp"):
        return url[:-4] + "/sse"
    if not url.endswith("/sse"):
        return url.rstrip("/") + "/sse"
    return url


async def call_tool(name: str, arguments: dict):
    try:
        async with sse_client(_sse_url()) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                logger.info("เรียก MCP tool %s", name)
                return await session.call_tool(name, arguments=arguments)
    except Exception as err:  # noqa: BLE001
        raise McpError(f"เรียก MCP tool {name} ไม่สำเร็จ: {err}") from err


async def send_email_via_mcp(
    to_email: str, subject: str, greeting: str, body: str, rows: list[dict] | None = None
):
    """
    ส่งอีเมล 1 ฉบับถึงผู้รับ 1 คน — personalized ต่อคน ไม่ใช่ส่งเหมือนกันทุกคน (FR-M7-02)
    การส่งเป็นรายคนยังลดความเสี่ยงข้อมูลรั่วข้ามฝ่ายด้วย
    """
    return await call_tool(
        "send_meeting_email",
        {
            "to_email": to_email,
            "subject": subject,
            "greeting": greeting,
            "body": body,
            "rows": rows or [],
        },
    )


def build_reminder_body(resolution: Resolution, person: Person, overdue: int) -> str:
    """
    FR-M7-03 — เตือนพร้อมข้อความมติเดิม "คำต่อคำ" ไม่ใช่สรุปย่อ
    ผู้รับต้องเห็นสิ่งที่ตัวเองรับปากไว้ตรงตามที่บันทึกในรายงานการประชุม
    """
    status_line = (
        f"เกินกำหนดแล้ว {overdue} วัน (กำหนดเดิม {thai_date(resolution.due_date)})"
        if overdue
        else f"ครบกำหนดวันที่ {thai_date(resolution.due_date)}"
    )
    return "\n\n".join(
        [
            "ระบบขอแจ้งเตือนมติที่อยู่ในความรับผิดชอบของท่าน",
            f"“{resolution.text}”",
            f"อ้างถึง: {resolution.ref_no}\nสถานะ: {status_line}",
            "กรุณาแจ้งความคืบหน้ากลับผ่านลิงก์ด้านล่าง โดยไม่ต้องเข้าสู่ระบบ",
            magic_link_url(resolution.id, person.id),
        ]
    )
