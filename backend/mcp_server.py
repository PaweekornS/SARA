"""
MCP server — ชั้น action ของ SARA (M7)

ทุกอย่างที่ระบบ "ส่งออกไปข้างนอก" ต้องผ่านที่นี่ที่เดียว
ทำให้สลับปลายทางได้ (อีเมล → ระบบติดตามงาน) โดยไม่ต้องแตะ pipeline

⚠ server นี้ไม่ตัดสินใจเองว่าจะส่งอะไรถึงใคร
   มันเป็นแค่ปลายทางที่ทำตามคำสั่งซึ่งผ่านการอนุมัติจากคนมาแล้วเท่านั้น (FR-M7-07)
"""

from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Template

try:
    from fastmcp import Context, FastMCP
except ImportError:  # pragma: no cover
    from mcp.server.fastmcp import Context, FastMCP

mcp = FastMCP("SARA-Action-Server")

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="th">
<head><meta charset="utf-8"/>
<style>
  body { font-family: "IBM Plex Sans Thai", "Sarabun", Tahoma, sans-serif; line-height: 1.7;
         color: #131a26; max-width: 640px; margin: 0 auto; padding: 24px; }
  .seal { width: 40px; height: 40px; border-radius: 50%; background: #1e3a6e; color: #fff;
          display: inline-flex; align-items: center; justify-content: center; font-weight: 700; }
  h2 { font-size: 18px; margin: 16px 0 4px; }
  .quote { border-left: 3px solid #9a7517; background: #fbf3df; padding: 12px 16px; margin: 16px 0; }
  table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 14px; }
  th, td { padding: 8px 10px; text-align: left; border-bottom: 1px solid #dfe3ea; vertical-align: top; }
  th { background: #eef0f4; }
  .overdue { color: #b3261e; font-weight: 600; }
  .footer { margin-top: 28px; font-size: 12px; color: #6b7688; border-top: 1px solid #dfe3ea; padding-top: 12px; }
</style></head>
<body>
  <div class="seal">S</div>
  <h2>{{ subject }}</h2>
  <p>{{ greeting }}</p>
  {% for block in body_blocks %}
    {% if block.startswith('“') %}<div class="quote">{{ block }}</div>{% else %}<p>{{ block }}</p>{% endif %}
  {% endfor %}
  {% if rows %}
  <table>
    <tr><th>เรื่อง</th><th>ผู้รับผิดชอบ</th><th>กำหนด</th><th>สถานะ</th></tr>
    {% for row in rows %}
    <tr>
      <td>{{ row.text }}</td>
      <td>{{ row.assignees or '-' }}</td>
      <td>{{ row.due_date or '-' }}</td>
      <td>{{ row.status }}{% if row.overdue %}<br/><span class="overdue">เกิน {{ row.overdue }} วัน</span>{% endif %}</td>
    </tr>
    {% endfor %}
  </table>
  {% endif %}
  <div class="footer">ส่งโดยระบบสารบรรณการประชุมอัตโนมัติ (SARA) · อีเมลฉบับนี้ผ่านการตรวจและอนุมัติจากฝ่ายเลขานุการแล้ว</div>
</body></html>
"""


def send_smtp_email(to_email: str, subject: str, html_content: str) -> None:
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")

    if not smtp_user or not smtp_pass:
        raise ValueError("ต้องตั้งค่า SMTP_USER และ SMTP_PASSWORD ก่อนจึงจะส่งอีเมลได้")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"SARA <{smtp_user}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, to_email, msg.as_string())


def _render(subject: str, greeting: str, body: str, rows: list[dict]) -> str:
    blocks = [b.strip() for b in (body or "").split("\n\n") if b.strip()]
    return Template(HTML_TEMPLATE).render(
        subject=subject, greeting=greeting, body_blocks=blocks, rows=rows or []
    )


@mcp.tool(
    name="send_meeting_email",
    description=(
        "ส่งอีเมลรายงานการประชุม การแจ้งเตือนมติ หรือสรุปวาระ ถึงผู้รับหนึ่งคน "
        "เนื้อหาที่ส่งต้องผ่านการอนุมัติจากฝ่ายเลขานุการมาแล้ว"
    ),
)
async def send_meeting_email(
    to_email: str,
    subject: str,
    greeting: str,
    body: str,
    rows: list[dict],
    ctx: Context,
) -> str:
    """
    ส่งทีละคน ไม่รับ list ของผู้รับ

    เจตนา: อีเมลประชุมมีชั้นความลับ การส่งฉบับเดียวหาหลายคนพร้อมกัน
    ทำให้เนื้อหาที่ควรเห็นเฉพาะบางคนหลุดข้ามฝ่ายได้ (FR-M7-02 personalized ต่อคน)
    """
    if not to_email:
        return "ไม่ได้ระบุอีเมลผู้รับ ยกเลิกการส่ง"

    await ctx.info(f"กำลังส่งอีเมลถึง {to_email}: {subject}")
    try:
        send_smtp_email(to_email, subject, _render(subject, greeting, body, rows))
    except Exception as err:  # noqa: BLE001
        await ctx.error(f"ส่งอีเมลถึง {to_email} ไม่สำเร็จ: {err}")
        raise

    await ctx.info(f"ส่งอีเมลถึง {to_email} สำเร็จ")
    return f"ส่งอีเมลถึง {to_email} เรียบร้อยแล้ว"


@mcp.tool(
    name="create_tracker_issue",
    description="สร้าง issue ในระบบติดตามงานภายนอก — มีไว้เพื่อพิสูจน์ว่า action layer สลับปลายทางได้",
)
async def create_tracker_issue(title: str, description: str, assignee: str, ctx: Context) -> str:
    """
    FR-M7-05 — ตั้งใจให้เป็นหลักฐานเชิงสถาปัตยกรรม ไม่ใช่ฟีเจอร์หลัก
    ยังไม่ได้ต่อกับ Jira จริง จึงบันทึกลง log อย่างเดียวและบอกตามตรงว่ายังไม่ได้สร้าง issue
    """
    await ctx.info(f"[tracker] {title} → {assignee}: {description[:120]}")
    return (
        "บันทึกคำขอสร้าง issue แล้ว แต่ยังไม่ได้เชื่อมต่อกับระบบติดตามงานจริง "
        "(ต้องตั้งค่า endpoint และ credential ของ Jira ก่อน)"
    )


if __name__ == "__main__":
    host = os.getenv("FASTMCP_HOST", "0.0.0.0")
    port = int(os.getenv("FASTMCP_PORT", "8001"))
    if hasattr(mcp, "settings"):
        mcp.settings.host = host
        mcp.settings.port = port
    try:
        mcp.run(transport="sse", host=host, port=port)
    except TypeError:
        mcp.run(transport="sse")
