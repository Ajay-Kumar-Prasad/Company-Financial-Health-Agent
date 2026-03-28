"""
main.py — Unified server: ADK backend + custom UI frontend.

Usage:
    cd financial_health_agent
    python main.py
    # → http://localhost:8000        custom FinSight UI
    # → http://localhost:8000/dev-ui original ADK UI
    # → http://localhost:8000/run    ADK chat API
"""

import os
import logging
from pathlib import Path

import uvicorn
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRoute
from starlette.routing import request_response

from google.adk.cli.fast_api import get_fast_api_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_FILE = Path(AGENT_DIR) / "index.html"

# ── Session storage ───────────────────────────────────────────────────────────
# Use Cloud Spanner / Firestore in production; sqlite is fine for local dev.
# On Cloud Run the filesystem is ephemeral — sessions won't survive restarts,
# but for a stateless scorecard agent this is acceptable.
# To persist: swap URI for "firestore" or a Cloud SQL postgres URI.
SESSION_DB_URI = os.environ.get(
    "SESSION_DB_URI", "sqlite+aiosqlite:///./sessions.db"
)

# ── Startup validation ────────────────────────────────────────────────────────
_MCP_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:8080/mcp")
logger.info(f"MCP_SERVER_URL = {_MCP_URL}")

if "localhost" in _MCP_URL and os.environ.get("K_SERVICE"):
    # K_SERVICE is set by Cloud Run — warn if still pointing at localhost
    logger.warning(
        "WARNING: MCP_SERVER_URL points to localhost but we are running on "
        "Cloud Run. Set MCP_SERVER_URL to the deployed MCP service URL."
    )

# ── Build ADK app ─────────────────────────────────────────────────────────────
app = get_fast_api_app(
    agents_dir=AGENT_DIR,
    session_service_uri=SESSION_DB_URI,
    allow_origins=["*"],
    web=True,
)

# ── Custom UI handler ─────────────────────────────────────────────────────────
async def serve_custom_ui(request: Request) -> HTMLResponse:
    if HTML_FILE.exists():
        return HTMLResponse(content=HTML_FILE.read_text(encoding="utf-8"))
    return HTMLResponse(
        content="""
        <html><body style="font-family:monospace;padding:40px;background:#f4f1eb">
        <h2>FinSight AI</h2>
        <p><code>index.html</code> not found next to <code>main.py</code>.</p>
        <p>ADK is running — <a href="/dev-ui">open dev-ui</a> or
           <a href="/docs">browse API docs</a>.</p>
        </body></html>
        """,
        status_code=200,
    )

# ── Override ADK's root route ─────────────────────────────────────────────────
for route in app.routes:
    if isinstance(route, APIRoute) and route.path == "/" and "GET" in (route.methods or set()):
        route.endpoint = serve_custom_ui
        route.app = request_response(serve_custom_ui)
        logger.info("Root route / → custom FinSight UI")
        break

# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import anyio
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"""
╔══════════════════════════════════════════════════════╗
║        FinSight AI — Financial Health Agent          ║
╠══════════════════════════════════════════════════════╣
║  Custom UI  →  http://localhost:{port}              ║
║  ADK UI     →  http://localhost:{port}/dev-ui       ║
║  API Docs   →  http://localhost:{port}/docs         ║
║  MCP URL    →  {_MCP_URL:<36}║
╚══════════════════════════════════════════════════════╝
""")
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        workers=1,          # ← critical: single worker prevents task group conflicts
        loop="asyncio",     # ← force asyncio loop, not uvloop
    )