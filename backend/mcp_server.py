import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field
try:
    from fastmcp import FastMCP, Context
except ImportError:
    from mcp.server.fastmcp import FastMCP, Context
from jinja2 import Template

# 1. Initialize FastMCP Server
mcp = FastMCP("Corporate-Meeting-Email-Server")

# 2. Define Pydantic Schemas for Strict Input Validation
class ActionItem(BaseModel):
    task: str = Field(..., description="Description of the assigned action item or task")
    assignee: str = Field(..., description="Name of the person responsible")
    email: EmailStr = Field(..., description="Recipient's email address")
    due_date: Optional[str] = Field(None, description="Due date in YYYY-MM-DD format")

class EmailPayload(BaseModel):
    subject: str = Field(..., description="Subject line for the meeting summary email")
    summary_bullets: List[str] = Field(..., description="List of key executive summary points")
    action_items: List[ActionItem] = Field(..., description="List of extracted action items and owners")

# 3. HTML Email Template (Rendered with Jinja2)
HTML_EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; }
        .header { background-color: #2563eb; color: white; padding: 20px; border-radius: 8px 8px 0 0; }
        .section { padding: 20px; border: 1px solid #e5e7eb; border-top: none; }
        .summary-box { background-color: #f8fafc; border-left: 4px solid #2563eb; padding: 12px 16px; margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f1f5f9; }
        .footer { text-align: center; font-size: 12px; color: #6b7280; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="header">
        <h2 style="margin:0;">{{ subject }}</h2>
    </div>
    <div class="section">
        <h3>📋 Executive Summary</h3>
        <div class="summary-box">
            <ul>
            {% for bullet in summary_bullets %}
                <li>{{ bullet }}</li>
            {% endfor %}
            </ul>
        </div>

        <h3>⚡ Your Assigned Action Items</h3>
        <table>
            <thead>
                <tr>
                    <th>Task</th>
                    <th>Assignee</th>
                    <th>Due Date</th>
                </tr>
            </thead>
            <tbody>
            {% for item in action_items %}
                <tr>
                    <td><strong>{{ item.task }}</strong></td>
                    <td>{{ item.assignee }}</td>
                    <td>{{ item.due_date or 'N/A' }}</td>
                </tr>
            {% endfor %}
            </tbody>
        </table>
    </div>
    <div class="footer">
        <p>Sent automatically via AI Thailand Onboarding 2026 Meeting AI Platform</p>
    </div>
</body>
</html>
"""

# Helper function to send email via SMTP
def send_smtp_email(to_email: str, subject: str, html_content: str):
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")

    if not smtp_user or not smtp_pass:
        raise ValueError("SMTP_USER and SMTP_PASSWORD environment variables are required.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Meeting AI Assistant <{smtp_user}>"
    msg["To"] = to_email

    msg.attach(MIMEText(html_content, "html"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, to_email, msg.as_string())


# 4. Expose the MCP Tool
@mcp.tool(
    name="send_meeting_summary_email",
    description="Sends formatted HTML meeting summaries and action items to a list of participant email addresses."
)
async def send_meeting_summary_email(
    subject: str,
    summary_bullets: List[str],
    recipient_emails: List[str],  # <--- List of recipient emails
    action_items: List[dict],
    ctx: Context
) -> str:
    await ctx.info(f"Preparing meeting email dispatch for subject: '{subject}'")

    # Render HTML Body
    template = Template(HTML_EMAIL_TEMPLATE)
    html_body = template.render(
        subject=subject,
        summary_bullets=summary_bullets,
        action_items=action_items
    )

    if not recipient_emails:
        return "No participant emails provided. Delivery skipped."

    sent_count = 0
    failed_emails = []

    # Send to every participant email in the list
    for email in recipient_emails:
        try:
            send_smtp_email(to_email=email, subject=subject, html_content=html_body)
            sent_count += 1
            await ctx.info(f"Successfully sent summary to: {email}")
        except Exception as err:
            await ctx.error(f"Failed to send email to {email}: {err}")
            failed_emails.append(email)

    return f"Email summary delivered to {sent_count}/{len(recipient_emails)} participants."


# 5. Entry Point: SSE / HTTP or Stdio Transport
if __name__ == "__main__":
    # Runs the MCP server with HTTP/SSE transport on port 8001
    os.environ.setdefault("FASTMCP_HOST", "0.0.0.0")
    os.environ.setdefault("FASTMCP_PORT", "8001")
    if hasattr(mcp, "settings"):
        mcp.settings.host = "0.0.0.0"
        mcp.settings.port = 8001
    try:
        mcp.run(transport="sse", host="0.0.0.0", port=8001)
    except TypeError:
        mcp.run(transport="sse")