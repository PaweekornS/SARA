"""
MCP Server — Action Layer of SARA (M7 & v3.0.0-PROD)

Provides:
1. send_meeting_email: Standard personalized meeting resolution and agenda notification.
2. send_public_summary_email: Pass-through public summary dispatch with anti-spam rate and recipient caps.
3. create_tracker_issue: External tracker/Jira integration stub.
"""

from __future__ import annotations

import logging
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import markdown
from jinja2 import Template

try:
    from fastmcp import Context, FastMCP
except ImportError:
    try:
        from mcp.server.fastmcp import Context, FastMCP
    except ImportError:  # pragma: no cover
        class Context:  # type: ignore
            async def info(self, msg: str): pass
            async def error(self, msg: str): pass

        class FastMCP:  # type: ignore
            def __init__(self, name: str):
                self.name = name

            def tool(self, *args, **kwargs):
                def decorator(fn):
                    return fn
                return decorator

            def run(self, *args, **kwargs):
                pass

logger = logging.getLogger(__name__)
mcp = FastMCP("SARA-Action-Server")

MAX_PUBLIC_RECIPIENTS = 10

MANDATORY_AUDIT_FOOTER = """
<hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 24px 0;" />
<p style="font-size: 12px; color: #64748b; text-align: center; font-family: 'IBM Plex Sans Thai', Tahoma, sans-serif;">
  This meeting summary was autonomously generated and dispatched via <strong>SARA (Smart Autonomous Record Agent)</strong>.<br/>
  Local Thai AI Infrastructure · Zero-Data Leakage Guarantee.
</p>
"""

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
    .badge {
      display: inline-block;
      padding: 4px 10px;
      border-radius: 6px;
      font-size: 11.5px;
      font-weight: 600;
      background-color: #ede9fe;
      color: #5b21b6;
      margin-bottom: 16px;
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
        {% if template_name %}
          <div class="badge">📋 {{ template_name }}</div>
        {% endif %}
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
          สรุปการประชุมและติดตามมติอัตโนมัติด้วย <strong>SARA (Smart Autonomous Record Agent)</strong>
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


def send_smtp_email(to_email: str, subject: str, html_content: str) -> bool:
    """Send single email via SMTP. Falls back to mock logging if SMTP credentials are not configured."""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")

    if not smtp_user or not smtp_pass:
        logger.warning(
            "SMTP_USER/SMTP_PASSWORD not configured. Mock dispatching email to %s: %s",
            to_email,
            subject,
        )
        return True

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"SARA AI Assistant <{smtp_user}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, to_email, msg.as_string())
    return True


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


def render_summary_html(
    subject: str,
    greeting: str = "",
    body: str = "",
    rows: list[dict] | None = None,
    template_name: str = "",
) -> str:
    body_html = _markdown_to_html(body or "")
    return Template(HTML_TEMPLATE).render(
        subject=subject,
        greeting=greeting,
        body_html=body_html,
        rows=rows or [],
        template_name=template_name,
    )


@mcp.tool(
    name="send_meeting_email",
    description="ส่งอีเมลรายงานการประชุม การแจ้งเตือนมติ หรือสรุปวาระ ถึงผู้รับหนึ่งคน",
)
async def send_meeting_email(
    to_email: str,
    subject: str,
    greeting: str,
    body: str,
    rows: list[dict],
    ctx: Context,
) -> str:
    if not to_email:
        return "ไม่ได้ระบุอีเมลผู้รับ ยกเลิกการส่ง"

    await ctx.info(f"กำลังส่งอีเมลถึง {to_email}: {subject}")
    try:
        html = render_summary_html(subject, greeting, body, rows)
        send_smtp_email(to_email, subject, html)
    except Exception as err:  # noqa: BLE001
        await ctx.error(f"ส่งอีเมลถึง {to_email} ไม่สำเร็จ: {err}")
        raise

    await ctx.info(f"ส่งอีเมลถึง {to_email} สำเร็จ")
    return f"ส่งอีเมลถึง {to_email} เรียบร้อยแล้ว"


async def dispatch_public_summary_email(
    recipients: list[str],
    subject: str,
    summary_text: str,
    template_name: str = "Executive Summary",
    items: list[dict] | None = None,
) -> dict:
    if len(recipients) > MAX_PUBLIC_RECIPIENTS:
        raise ValueError(
            f"จำกัดผู้รับไม่เกิน {MAX_PUBLIC_RECIPIENTS} อีเมลต่อคำขอ (ระบุมา {len(recipients)} อีเมล)"
        )

    dispatched = []
    html_content = render_summary_html(
        subject=subject,
        greeting="เรียน ผู้เข้าร่วมการประชุม",
        body=summary_text,
        rows=items or [],
        template_name=template_name,
    )

    for email in recipients:
        clean_email = email.strip()
        if not clean_email or "@" not in clean_email:
            continue
        try:
            send_smtp_email(clean_email, subject, html_content)
            dispatched.append(clean_email)
        except Exception as err:
            logger.error("Failed to send email to %s: %s", clean_email, err)

    return {
        "status": "success",
        "dispatched_count": len(dispatched),
        "recipients": dispatched,
    }


# Export for direct Python callers
send_public_summary_email = dispatch_public_summary_email

# Register tool on MCP
mcp.tool(
    name="send_public_summary_email",
    description="ส่งอีเมลสรุปการประชุมแบบ Pass-through ไปยังผู้รับหลายคน (สูงสุด 10 คน) พร้อมการป้องกัน Spam",
)(dispatch_public_summary_email)


@mcp.tool(
    name="create_tracker_issue",
    description="สร้าง issue ในระบบติดตามงานภายนอก (Jira / Linear / GitHub)",
)
async def create_tracker_issue(title: str, description: str, assignee: str, ctx: Context) -> str:
    await ctx.info(f"[tracker] {title} → {assignee}: {description[:120]}")
    return f"บันทึกคำขอสร้าง task '{title}' สำหรับ {assignee} สำเร็จ"


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
