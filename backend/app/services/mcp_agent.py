"""
บริการส่งออกอีเมลและพากระทำภายนอก (M7) — Direct Direct API

สถาปัตยกรรม MVP: ยกเลิกการแยก FastMCP SSE Server ออกเป็นคอนเทนเนอร์แยก
เพื่อลดความซับซ้อนเกินจำเป็นของ MVP โดยส่งผ่าน FastAPI / Direct API สดตรงถึง SMTP Server
"""

import logging
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import markdown
from jinja2 import Template

from app.core.config import settings
from app.core.security import magic_link_url, make_magic_token
from app.db.models import Person, Resolution
from app.services.thai_format import thai_date

# ── Global Variables & Constants ─────────────────────────────────────────────

logger = logging.getLogger(__name__)

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <style>
    body {
      margin: 0;
      padding: 0;
      background-color: #f8fafc;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", "Prompt", "Noto Sans Thai", Arial, sans-serif;
      color: #1e293b;
      -webkit-font-smoothing: antialiased;
      line-height: 1.65;
    }
    .wrapper {
      width: 100%;
      background-color: #f8fafc;
      padding: 32px 16px;
      box-sizing: border-box;
    }
    .main-card {
      max-width: 600px;
      margin: 0 auto;
      background-color: #ffffff;
      border-radius: 16px;
      overflow: hidden;
      border: 1px solid #e2e8f0;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.01);
    }
    .header-banner {
      background: linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #4338ca 100%);
      padding: 24px 28px;
      color: #ffffff;
    }
    .email-title {
      font-size: 19px;
      font-weight: 700;
      margin: 0;
      color: #ffffff;
      line-height: 1.4;
      letter-spacing: -0.01em;
    }
    .content-body {
      padding: 28px;
    }
    .greeting {
      font-size: 15px;
      font-weight: 600;
      color: #0f172a;
      margin: 0 0 16px 0;
    }
    .markdown-body {
      font-size: 14px;
      color: #334155;
      line-height: 1.65;
    }
    .markdown-body h1, .markdown-body h2 {
      font-size: 16px;
      font-weight: 700;
      color: #1e1b4b;
      margin: 18px 0 8px 0;
      border-bottom: 1px solid #f1f5f9;
      padding-bottom: 4px;
    }
    .markdown-body h3, .markdown-body h4 {
      font-size: 14.5px;
      font-weight: 600;
      color: #312e81;
      margin: 16px 0 6px 0;
    }
    .markdown-body p {
      margin: 0 0 10px 0;
    }
    .markdown-body ul, .markdown-body ol {
      margin: 6px 0 14px 0;
      padding-left: 22px;
    }
    .markdown-body li {
      margin-bottom: 5px;
    }
    .markdown-body strong {
      font-weight: 600;
      color: #0f172a;
    }
    .markdown-body em {
      color: #64748b;
    }
    .markdown-body blockquote {
      border-left: 4px solid #6366f1;
      background-color: #f5f3ff;
      padding: 10px 16px;
      margin: 12px 0;
      border-radius: 0 8px 8px 0;
      font-size: 13.5px;
      color: #3730a3;
    }
    .table-container {
      margin: 24px 0;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      overflow: hidden;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13.5px;
    }
    th {
      background-color: #f8fafc;
      color: #475569;
      font-weight: 600;
      text-transform: uppercase;
      font-size: 11px;
      letter-spacing: 0.05em;
      padding: 12px 14px;
      text-align: left;
      border-bottom: 1px solid #e2e8f0;
    }
    td {
      padding: 12px 14px;
      border-bottom: 1px solid #f1f5f9;
      color: #334155;
      vertical-align: top;
    }
    tr:last-child td {
      border-bottom: none;
    }
    .status-pill {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 12px;
      font-size: 11px;
      font-weight: 600;
    }
    .status-done { background: #dcfce7; color: #15803d; }
    .status-progress { background: #e0e7ff; color: #4338ca; }
    .status-blocked { background: #fee2e2; color: #b91c1c; }
    .status-overdue { color: #dc2626; font-weight: 600; font-size: 11px; display: block; margin-top: 2px; }
    .footer {
      padding: 24px 32px;
      background-color: #f8fafc;
      border-top: 1px solid #e2e8f0;
      font-size: 12px;
      color: #64748b;
      text-align: center;
      line-height: 1.6;
    }
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="main-card">
      <div class="header-banner">
        <h1 class="email-title">{{ subject }}</h1>
      </div>
      <div class="content-body">
        {% if greeting %}
          <p class="greeting">{{ greeting }}</p>
        {% endif %}
        <div class="markdown-body">
          {{ body_html | safe }}
        </div>
        {% if rows %}
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>ข้อตกลง / Action Item</th>
                  <th>ผู้รับผิดชอบ</th>
                  <th>กำหนด</th>
                  <th>สถานะ</th>
                </tr>
              </thead>
              <tbody>
                {% for row in rows %}
                  <tr>
                    <td style="font-weight: 500;">{{ row.text }}</td>
                    <td>{{ row.assignees or '-' }}</td>
                    <td>{{ row.due_date or '-' }}</td>
                    <td>
                      <span class="status-pill {% if row.status == 'เสร็จแล้ว' or row.status == 'done' %}status-done{% elif row.status == 'ติดปัญหา' or row.status == 'blocked' %}status-blocked{% else %}status-progress{% endif %}">
                        {{ row.status }}
                      </span>
                      {% if row.overdue %}
                        <span class="status-overdue">⚠ เกิน {{ row.overdue }} วัน</span>
                      {% endif %}
                    </td>
                  </tr>
                {% endfor %}
              </tbody>
            </table>
          </div>
        {% endif %}
      </div>
      <div class="footer">
        <p style="margin: 0 0 6px 0; font-weight: 500; color: #475569;">
          ส่งโดยระบบติดตามมติและการประชุมอัตโนมัติ <strong>SARA (Smart Autonomous Record Agent)</strong>
        </p>
        <p style="margin: 0; font-size: 11px; color: #94a3b8;">
          Thai Speech Recognition & LLM Intelligence Platform · Zero-Data Leakage Guarantee
        </p>
      </div>
    </div>
  </div>
</body>
</html>
"""


# ── Classes & Exceptions ─────────────────────────────────────────────────────

class McpError(RuntimeError):
    """ส่งอีเมลไม่สำเร็จ"""


# ── Functions ────────────────────────────────────────────────────────────────

def _markdown_to_html(text: str) -> str:
    if not text:
        return ""
    html = markdown.markdown(text, extensions=["extra", "nl2br", "sane_lists"])
    html = re.sub(
        r"<li>\[ \]\s*",
        r'<li style="list-style: none; margin-left: -18px;"><span style="display:inline-block; width:13px; height:13px; border:1.5px solid #94a3b8; border-radius:3px; margin-right:8px; vertical-align:middle; background:#ffffff;"></span>',
        html,
    )
    html = re.sub(
        r"<li>\[x\]\s*",
        r'<li style="list-style: none; margin-left: -18px;"><span style="display:inline-block; width:14px; height:14px; background:#4f46e5; border-radius:3px; margin-right:8px; vertical-align:middle; color:#ffffff; font-size:10px; line-height:14px; text-align:center; font-weight:bold;">✓</span>',
        html,
    )
    return html


def _render(subject: str, greeting: str, body: str, rows: list[dict]) -> str:
    body_html = _markdown_to_html(body or "")
    return Template(HTML_TEMPLATE).render(
        subject=subject, greeting=greeting, body_html=body_html, rows=rows or []
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
    if not target_email:
        return

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
    msg["From"] = f"SARA AI Assistant <{smtp_user}>"
    msg["To"] = target_email
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            logger.info("ส่งอีเมลจริงสำเร็จไปยัง %s (Subject: %s)", target_email, subject)
    except Exception as err:
        logger.error("ส่งอีเมลไม่สำเร็จไปยัง %s: %s", target_email, err)
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
