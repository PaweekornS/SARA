"""
ส่งอีเมลสรุปการประชุม — มีที่เดียวในระบบ

เนื้อหาอีเมลสร้างจากข้อมูลการประชุมใน DB เสมอ ไม่รับข้อความอิสระจากผู้ใช้
เพื่อไม่ให้ endpoint ส่งอีเมลกลายเป็นช่องทางส่งสแปมผ่านบัญชีของเรา
"""

from __future__ import annotations

import logging
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

import markdown
from jinja2 import Environment, select_autoescape

from app.core.config import settings

logger = logging.getLogger(__name__)

_jinja = Environment(autoescape=select_autoescape(default=True, default_for_string=True))


class EmailError(RuntimeError):
    """ส่งอีเมลไม่สำเร็จ"""


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
                  <th>งานที่ต้องทำ</th>
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
          สรุปการประชุมอัตโนมัติด้วย <strong>SARA</strong> · ส่งโดย {{ sender_name }}
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


def _markdown_to_html(text: str) -> str:
    if not text:
        return ""
    #  ตัด HTML ดิบที่ผู้ใช้หรือโมเดลอาจแทรกมา ให้เหลือเฉพาะ markdown
    html = markdown.markdown(re.sub(r"<[^>]+>", "", text), extensions=["extra", "nl2br", "sane_lists"])
    return html


def render_summary_html(
    subject: str,
    summary: str,
    key_points: list[str],
    action_items: list[dict],
    template_name: str,
    sender_name: str,
) -> str:
    body = summary or ""
    if key_points:
        body += "\n\n**ประเด็นสำคัญ**\n\n" + "\n".join(f"- {p}" for p in key_points)
    return _jinja.from_string(HTML_TEMPLATE).render(
        subject=subject,
        greeting="",
        body_html=_markdown_to_html(body),
        rows=action_items,
        template_name=template_name,
        sender_name=sender_name,
    )


def send_html(to_email: str, subject: str, html: str, reply_to: str = "") -> None:
    """ส่งหนึ่งฉบับ ถ้ายังไม่ได้ตั้ง SMTP จะแค่ log ไว้ (โหมดพัฒนา)"""
    if not settings.smtp_configured:
        logger.warning("ยังไม่ได้ตั้ง APP_SMTP_USER/APP_SMTP_PASSWORD — จำลองการส่งถึง %s: %s", to_email, subject)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr(("SARA", settings.APP_SMTP_USER))
    msg["To"] = to_email
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(settings.APP_SMTP_USER, settings.APP_SMTP_PASSWORD)
            server.send_message(msg)
    except (smtplib.SMTPException, OSError) as err:
        raise EmailError(f"ส่งอีเมลถึง {to_email} ไม่สำเร็จ: {err}") from err
