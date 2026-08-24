"""
บริการส่งออกอีเมลและพากระทำภายนอก (M7) — Direct Direct API

สถาปัตยกรรม MVP: ยกเลิกการแยก FastMCP SSE Server ออกเป็นคอนเทนเนอร์แยก
เพื่อลดความซับซ้อนเกินจำเป็นของ MVP โดยส่งผ่าน FastAPI / Direct API สดตรงถึง SMTP Server
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Template

from app.core.config import settings
from app.core.security import magic_link_url, make_magic_token
from app.db.models import Person, Resolution
from app.services.thai_format import thai_date

# ── Global Variables & Constants ─────────────────────────────────────────────

logger = logging.getLogger(__name__)

ALLOWED_TEST_EMAILS = {"test01@gmail.com", "test02@gmail.com"}

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


# ── Classes & Exceptions ─────────────────────────────────────────────────────

class McpError(RuntimeError):
    """ส่งอีเมลไม่สำเร็จ"""


# ── Functions ────────────────────────────────────────────────────────────────

def _render(subject: str, greeting: str, body: str, rows: list[dict]) -> str:
    blocks = [b.strip() for b in (body or "").split("\n\n") if b.strip()]
    return Template(HTML_TEMPLATE).render(
        subject=subject, greeting=greeting, body_blocks=blocks, rows=rows or []
    )


def build_reminder_body(resolution: Resolution, person: Person, overdue: int = 0) -> str:
    """สร้างเนื้อหาข้อความเตือนสำหรับมติที่เกินกำหนด"""
    due_str = thai_date(resolution.due_date) if resolution.due_date else "-"
    if overdue > 0:
        overdue_text = f"เกินกำหนดแล้ว {overdue} วัน"
    else:
        overdue_text = f"ครบกำหนดวันที่ {due_str}"

    token = make_magic_token(resolution.id, person.id)
    url = f"/api/public/resolutions/{token}"

    return (
        f"เรียน {person.full_name}\n\n"
        f"แจ้งเตือนการติดตามมติที่ประชุม: {resolution.ref_no}\n"
        f"“{resolution.text}”\n"
        f"สถานะ: {overdue_text} (กำหนด: {due_str})\n\n"
        f"กรุณาอัปเดตความคืบหน้าได้ที่: {url}\n"
    )


def send_smtp_email(to_email: str, subject: str, html_content: str) -> None:
    target_email = to_email.strip()
    # หากผู้รับไม่ใช่ test01@gmail.com หรือ test02@gmail.com ให้ map ไปยัง test01@gmail.com หรือ test02@gmail.com
    if target_email not in ALLOWED_TEST_EMAILS:
        target_email = "test01@gmail.com" if "supply" in target_email or "kanjana" in target_email or "thanakrit" in target_email or "preeyanuch" in target_email else "test02@gmail.com"

    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")

    if not smtp_user or not smtp_pass:
        logger.info(
            "ไม่พบ SMTP_USER / SMTP_PASSWORD — จำลองการส่งอีเมลสำเร็จถึง %s (Subject: %s)",
            target_email,
            subject,
        )
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"SARA <{smtp_user}>"
    msg["To"] = target_email
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            logger.info("ส่งอีเมลจริงสำเร็จไปยัง %s (เดิม: %s)", target_email, to_email)
    except Exception as err:
        logger.error("ส่งอีเมลไม่สำเร็จ: %s", err)
        raise McpError(f"ส่งอีเมลไม่สำเร็จ: {err}") from err


async def send_email_via_mcp(
    to_email: str, subject: str, greeting: str, body: str, rows: list[dict] | None = None
) -> None:
    html = _render(subject, greeting, body, rows or [])
    send_smtp_email(to_email, subject, html)


def render_and_send_notification(
    to_email: str,
    to_name: str,
    resolution: Resolution,
    due_date_str: str,
    magic_token: str | None = None,
) -> None:
    subject = f"แจ้งมอบหมายการดำเนินงานตามมติ: {resolution.ref_no}"
    greeting = f"เรียน {to_name}"
    body = (
        f"ที่ประชุมได้มีมติมอบหมายให้ท่านดำเนินงานตามมติ “{resolution.text}” "
        f"โดยมีกำหนดแล้วเสร็จภายในวันที่ {due_date_str}\n\n"
        "ขอความอนุเคราะห์ท่านรายงานความคืบหน้าการดำเนินงานกลับมายังฝ่ายเลขานุการ"
    )
    if magic_token:
        link = magic_link_url(settings.PUBLIC_BASE_URL, magic_token)
        body += f"\n\nท่านสามารถคลิกลิงก์เพื่ออัปเดตสถานะการดำเนินงานได้โดยตรง: {link}"

    html = _render(subject, greeting, body, [])
    send_smtp_email(to_email, subject, html)


def notify_overdue_resolutions(
    to_email: str,
    to_name: str,
    overdue_items: list[tuple[Resolution, int]],
) -> None:
    subject = f"แจ้งเตือนมติการประชุมที่เกินกำหนดดำเนินงาน ({len(overdue_items)} รายการ)"
    greeting = f"เรียน {to_name}"
    body = "ระบบตรวจสอบพบมติการประชุมที่ท่านได้รับมอบหมายและเกินกำหนดระยะเวลาดำเนินงานแล้ว ดังรายการต่อไปนี้:"

    rows = []
    for res, days in overdue_items:
        rows.append(
            {
                "text": res.text,
                "assignees": to_name,
                "due_date": thai_date(res.due_date) if res.due_date else "-",
                "status": "เกินกำหนด",
                "overdue": days,
            }
        )

    html = _render(subject, greeting, body, rows)
    send_smtp_email(to_email, subject, html)
