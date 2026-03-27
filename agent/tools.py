"""
tools.py — MCP Toolset initialisation for the Financial Health ADK Agent.

Connects to the running FastMCP server (server.py) via StreamableHTTP.
The server must be started before the agent (see README.md).

Pattern sourced from the ADK + MCP tutorial (Location Intelligence Codelab).
"""

import os
import logging

import dotenv

from google.adk.tools.mcp_tool.mcp_toolset import (
    MCPToolset,
    StreamableHTTPConnectionParams,
)

logger = logging.getLogger(__name__)

# URL of the running FastMCP financial-health server
# Override via MCP_SERVER_URL env var for remote deployments
MCP_SERVER_URL = os.environ.get(
    "MCP_SERVER_URL", "http://127.0.0.1:8080/mcp"
)


def get_financial_mcp_toolset() -> MCPToolset:
    """
    Return an MCPToolset connected to the Financial Health MCP server.

    The server (server.py) must already be running and reachable at
    MCP_SERVER_URL before this function is called.

    For authenticated remote deployments, add an Authorization header:
        headers={"Authorization": f"Bearer {os.environ['MCP_API_KEY']}"}
    """
    dotenv.load_dotenv()

    server_url = os.environ.get("MCP_SERVER_URL", MCP_SERVER_URL)
    logger.info(f"Connecting MCP toolset to: {server_url}")

    toolset = MCPToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=server_url,
            # Add auth headers here if your server requires them, e.g.:
            # headers={"Authorization": f"Bearer {os.environ.get('MCP_API_KEY', '')}"},
        )
    )
    logger.info("Financial Health MCP Toolset configured (StreamableHTTP).")
    return toolset