"""
ui_server.py — Custom UI server for the Financial Health Agent.

Serves the custom HTML frontend and proxies chat requests to the ADK
server running on port 8000.

Usage:
    # Terminal 1 — start the ADK agent backend
    cd financial_health_agent
    python main.py          # starts ADK on http://localhost:8000

    # Terminal 2 — start the custom UI server
    python ui_server.py     # starts custom UI on http://localhost:3000

    # Visit http://localhost:3000 in your browser

Environment variables:
    ADK_BASE_URL   — ADK server URL  (default: http://localhost:8000)
    UI_PORT        — port for this server (default: 3000)
    UI_HOST        — bind host          (default: 0.0.0.0)
"""

import os
import json
import logging
import httpx
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Config ──────────────────────────────────────────────────────────────────────
ADK_BASE  = os.environ.get("ADK_BASE_URL", "http://localhost:8000")
UI_PORT   = int(os.environ.get("UI_PORT", 3000))
UI_HOST   = os.environ.get("UI_HOST", "0.0.0.0")
UI_DIR    = Path(__file__).parent  # same directory as this file

app = FastAPI(title="FinSight AI — Financial Health Agent UI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Serve HTML ───────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Serve the custom chat UI."""
    html_path = UI_DIR / "index.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


# ── Health ───────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "adk_url": ADK_BASE}


# ── Proxy: Create Session ─────────────────────────────────────────────────────────
@app.post("/apps/{app_name}/users/{user_id}/sessions")
async def create_session(app_name: str, user_id: str, request: Request):
    """Proxy session creation to ADK."""
    body = await request.body()
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                f"{ADK_BASE}/apps/{app_name}/users/{user_id}/sessions",
                content=body,
                headers={"Content-Type": "application/json"},
            )
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
        except httpx.RequestError as e:
            logger.error(f"ADK session create error: {e}")
            # Return a generated session ID so the UI still works
            import uuid
            session_id = str(uuid.uuid4())
            return JSONResponse({"id": session_id}, status_code=200)


# ── Proxy: Run (main chat endpoint) ──────────────────────────────────────────────
@app.post("/run")
async def run_agent(request: Request):
    """
    Proxy the /run request to ADK and return the response.

    ADK's /run endpoint accepts:
      {
        "app_name": "agent",
        "user_id": "user",
        "session_id": "...",
        "new_message": { "role": "user", "parts": [{ "text": "..." }] }
      }

    And returns a list of event objects.
    """
    body = await request.body()
    logger.info(f"Forwarding /run to ADK: {body[:120]!r}...")

    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            resp = await client.post(
                f"{ADK_BASE}/run",
                content=body,
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code != 200:
                logger.error(f"ADK returned {resp.status_code}: {resp.text[:200]}")
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return JSONResponse(content=resp.json())
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="ADK agent timed out (180s). The financial analysis is taking too long.")
        except httpx.RequestError as e:
            logger.error(f"ADK connection error: {e}")
            raise HTTPException(
                status_code=503,
                detail=f"Cannot reach ADK server at {ADK_BASE}. Make sure 'python main.py' is running."
            )


# ── Proxy: SSE streaming run (for streaming-enabled ADK setups) ──────────────────
@app.post("/run_sse")
async def run_agent_sse(request: Request):
    """Proxy streaming SSE run to ADK."""
    body = await request.body()

    async def event_stream():
        async with httpx.AsyncClient(timeout=180.0) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{ADK_BASE}/run_sse",
                    content=body,
                    headers={"Content-Type": "application/json"},
                ) as resp:
                    async for chunk in resp.aiter_bytes():
                        yield chunk
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n".encode()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Proxy: List sessions ──────────────────────────────────────────────────────────
@app.get("/apps/{app_name}/users/{user_id}/sessions")
async def list_sessions(app_name: str, user_id: str):
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"{ADK_BASE}/apps/{app_name}/users/{user_id}/sessions"
            )
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
        except httpx.RequestError:
            return JSONResponse([], status_code=200)


# ── Entry Point ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════════╗
║         FinSight AI — Custom UI Server               ║
╠══════════════════════════════════════════════════════╣
║  UI:        http://localhost:{UI_PORT:<25}║
║  ADK proxy: {ADK_BASE:<41}║
║                                                      ║
║  Make sure ADK backend is running:                   ║
║    python main.py   (in financial_health_agent/)     ║
╚══════════════════════════════════════════════════════╝
""")
    uvicorn.run(app, host=UI_HOST, port=UI_PORT, log_level="info")