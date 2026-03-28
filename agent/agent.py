"""
Financial Health Agent — Google ADK entry point.

The agent connects to the Financial Health MCP server via HTTP transport.
The MCP server (server.py) must be deployed as a separate Cloud Run service
with TRANSPORT=http.

Run locally:
    MCP_SERVER_URL=http://localhost:8080/mcp python main.py

Environment variables:
    FMP_API_KEY               — Financial Modeling Prep API key  (required, for MCP server)
    MCP_SERVER_URL            — Full URL to MCP server's /mcp endpoint (required)
                                e.g. https://financial-health-mcp-xxx.run.app/mcp
    GOOGLE_CLOUD_PROJECT      — GCP project for Vertex AI         (required)
    GOOGLE_CLOUD_LOCATION     — e.g. us-central1                  (required)
    GOOGLE_GENAI_USE_VERTEXAI — set to "1" for Vertex AI          (required)
    GCP_PROJECT_ID            — GCP project for BigQuery snapshots (optional, for MCP server)
"""

import os
import dotenv
from google.auth.transport.requests import Request
from google.oauth2 import id_token

from google.adk.agents import Agent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, SseConnectionParams

# Load .env from this file's directory
dotenv.load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

# ── MCP Server URL ─────────────────────────────────────────────────────────────
# On Cloud Run: set MCP_SERVER_URL to your deployed MCP service URL + /mcp
# Locally:      run server.py separately with TRANSPORT=http, then set
#               MCP_SERVER_URL=http://localhost:8080/mcp
_MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:8080/sse")

def get_auth_headers():
    """Generates the required Bearer token for Cloud Run-to-Cloud Run communication."""
    mcp_url = os.environ.get("MCP_SERVER_URL", "")
    # Audience must be the base URL without the /sse path
    audience = mcp_url.split("/sse")[0] 
    
    auth_req = Request()
    # This automatically gets the token from the Cloud Run Service Account
    token = id_token.fetch_id_token(auth_req, audience)
    return {"Authorization": f"Bearer {token}"}

# When creating your MCP Toolset, pass these headers
# Example (adjust based on your actual SDK usage):
# mcp_toolset = MCPToolset(url=os.environ["MCP_SERVER_URL"], headers=get_auth_headers())

# ── MCP Toolset (HTTP transport) ───────────────────────────────────────────────
mcp_toolset = MCPToolset(
    connection_params=SseConnectionParams(
        url=_MCP_SERVER_URL,
        headers=get_auth_headers()
    )
)

# ── System Prompt ──────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are a senior financial analyst AI. Your task is to produce a concise,
accurate, and well-structured **Financial Health Scorecard** for any public company
a user asks about.

## Workflow

1. **Extract the ticker** from the user's query. If only a company name is given
   (e.g. "Apple", "Infosys"), convert it to the correct exchange ticker
   (e.g. AAPL, INFY).

2. **Call tools in this order:**
   a. `get_financials(ticker)` — income statement, balance sheet, cash flow, YoY growth
   b. `get_ratios(ticker)` — valuation multiples, ROE, ROA, margins, company profile
   c. `get_peers_comparison(ticker)` — benchmark against 2–4 sector peers
   d. `get_historical(ticker)` — only if the user asks for a trend / YoY comparison

3. **Analyse the data** using the thresholds below.

4. **Call `save_snapshot(ticker, scorecard_json)`** SILENTLY — do NOT mention it
   to the user, do NOT print any message about it, do NOT reprint the scorecard
   after calling it. If it returns "skipped" or "error", ignore it completely.

5. **Output the scorecard ONCE** — only after all tool calls are complete.

---

## Analysis Thresholds

### Profitability
- Net margin   > 15% → Strong  |  5–15% → Adequate  |  < 5% → Weak
- Op. margin   > 20% → Strong  | 10–20% → Adequate  | < 10% → Weak
- ROE          > 15% → Strong  |  8–15% → Adequate  |  < 8% → Weak

### Liquidity
- Current ratio  > 2.0 → Strong  | 1.2–2.0 → Adequate  | < 1.2 → Watch
- Quick ratio    > 1.0 → Strong  | 0.5–1.0 → Adequate  | < 0.5 → Watch

### Leverage
- Debt/Equity  < 0.5 → Low risk  | 0.5–1.5 → Moderate  | > 1.5 → High risk
- Int. coverage > 5×  → Safe  |  2–5× → Watch  |  < 2× → Distressed
  (use `interest_coverage` from `get_financials` income_statement[0]; fall back to `get_ratios` if None)

### Growth
- Revenue growth  > 10% → High  | 3–10% → Moderate  | < 3% → Low / Declining
- EPS growth      > 10% → Strong |  0–10% → Moderate  |  < 0% → Declining

### Cash Flow
- Positive FCF → Healthy  |  Negative FCF → Watch

### Peer Benchmarking
- If `peers` list is empty, write: "Peer data unavailable (API rate limit)"
- Do NOT write "No peer data available" — always explain the reason

---

## Output Format

Produce the scorecard EXACTLY ONCE using this structure.
The header line must always include: Company Name | TICKER | Sector | Period date
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Financial Health Scorecard
   Apple Inc. | AAPL | Technology | 2025-09-27
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 PROFITABILITY
   Net Margin         → value%   [Strong / Adequate / Weak]
   Operating Margin   → value%   [Strong / Adequate / Weak]
   ROE                → value%   [Strong / Adequate / Weak]
   EPS (latest/prior) → curr / prev

💧 LIQUIDITY
   Current Ratio      → value   [Strong / Adequate / Watch]
   Quick Ratio        → value   [Strong / Adequate / Watch]

🏗️  LEVERAGE
   Debt / Equity      → value   [Low / Moderate / High risk]
   Interest Coverage  → value×  [Safe / Watch / Distressed]

📈 GROWTH (Year-over-Year)
   Revenue            → value%  [High / Moderate / Low]
   Net Income         → value%
   EPS                → value%  [Strong / Moderate / Declining]

💵 CASH FLOW
   Operating CF       → formatted value
   Free Cash Flow     → formatted value  [Healthy / Watch]

🏆 PEER BENCHMARKING
   vs Peer1: P/E X vs Y  |  Net Margin A% vs B%
   vs Peer2: ROE X% vs Y%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ VERDICT: [Healthy / Watch / Concerning]
   2–3 sentence plain-English summary covering key strengths,
   risks, and overall investment outlook.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  Disclaimer: For informational purposes only. Not financial advice.
```

---

## Rules
- Output the scorecard EXACTLY ONCE. Never reprint it after save_snapshot.
- Never mention save_snapshot, BigQuery, or snapshot status to the user.
- Never hallucinate numbers. Use only data returned by the tools.
- If a metric is unavailable, write "N/A" — do not omit the row.
- Format large numbers as billions (B) or millions (M).
- The verdict must be exactly ONE of: Healthy / Watch / Concerning.
- The header must always contain all four fields: Name | TICKER | Sector | Date.
""".strip()

# ── Agent definition ───────────────────────────────────────────────────────────
root_agent = Agent(
    model="gemini-2.5-flash",
    name="financial_health_agent",
    instruction=SYSTEM_PROMPT,
    tools=[mcp_toolset],
)