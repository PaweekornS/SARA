import asyncio
import logging
from mcp import ClientSession
from mcp.client.sse import sse_client
from app.core.config import settings

logger = logging.getLogger(__name__)

def dispatch_mcp_email_tool(meeting_title: str, action_items: list, summary: list):
    """
    Synchronous wrapper to run the async MCP client dispatch.
    """
    logger.info(f"Triggering MCP dispatch for: {meeting_title}")
    try:
        asyncio.run(_async_dispatch(meeting_title, action_items, summary))
    except Exception as e:
        logger.error(f"Failed to dispatch MCP email tool: {e}")
        raise e

async def _async_dispatch(meeting_title: str, action_items: list, summary: list):
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
                    "action_items": action_items
                }
            )
            
            logger.info(f"MCP tool call response: {response}")
            return response