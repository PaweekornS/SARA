import logging
import asyncio
import requests
from mcp import ClientSession
from mcp.client.sse import sse_client
from app.core.config import settings

logger = logging.getLogger(__name__)

async def _async_dispatch(meeting_title: str, recipient_emails: list, action_items: list, summary: list):
    """
    Asynchronously connects to the FastMCP SSE server and calls the send_meeting_summary_email tool.
    """
    # Determine SSE endpoint URL.
    # FastMCP SSE transport runs on /sse by default.
    mcp_url = settings.MCP_SERVER_URL
    if mcp_url.endswith("/mcp"):
        # If set to http://mcp_server:8001/mcp, map it to http://mcp_server:8001/sse
        mcp_url = mcp_url[:-4] + "/sse"
    elif not mcp_url.endswith("/sse"):
        mcp_url = mcp_url.rstrip("/") + "/sse"

    logger.info(f"Connecting to MCP server at: {mcp_url}")
    
    async with sse_client(mcp_url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            logger.info("MCP session initialized. Invoking send_meeting_summary_email...")
            
            response = await session.call_tool(
                "send_meeting_summary_email",
                arguments={
                    "subject": meeting_title,
                    "summary_bullets": summary,
                    "recipient_emails": recipient_emails,
                    "action_items": action_items
                }
            )
            
            logger.info(f"MCP tool call response: {response}")
            return response

def get_recipients_from_api() -> list:
    """
    Calls the local FastAPI /meetings/recipients endpoint to retrieve recipient emails.
    """
    try:
        # Try connecting via localhost (if running natively)
        url = f"http://localhost:8000{settings.API_V1_STR}/meetings/recipients"
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.warning(f"Could not connect to localhost API, trying backend host: {e}")
        try:
            # Try connecting via container name (if running inside docker compose)
            url_docker = f"http://backend:8000{settings.API_V1_STR}/meetings/recipients"
            response = requests.get(url_docker, timeout=2)
            if response.status_code == 200:
                return response.json()
        except Exception as ex:
            logger.warning(f"Could not connect to backend API: {ex}")
    
    return []

def dispatch_mcp_email_tool(meeting_title: str, participants: list, action_items: list, summary: list):
    """
    Invokes the local MCP Server tool to email all meeting participants.
    """
    # 1. Fetch recipient emails from our local API/mock endpoint
    recipient_emails = get_recipients_from_api()

    # Support merging any other emails dynamically passed in the participants list
    if participants:
        for p in participants:
            if isinstance(p, dict) and "email" in p:
                email = p["email"]
                if email not in recipient_emails:
                    recipient_emails.append(email)

    try:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(
            _async_dispatch(
                meeting_title=meeting_title,
                recipient_emails=recipient_emails,
                action_items=action_items,
                summary=summary
            )
        )
        return result
    except Exception as err:
        logger.error(f"[MCP Error] Failed to trigger email tool: {err}")
        return None