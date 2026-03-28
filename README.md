# 🏦 Company Financial Health Agent

> An AI agent built with **Google ADK** and **Model Context Protocol (MCP)** that retrieves live financial data from the Financial Modeling Prep API and produces a structured, analyst-grade **Financial Health Scorecard** for any public company — complete with peer benchmarking, YoY growth analysis, and BigQuery-backed historical tracking.

---

## 📌 Project Overview

Built for the **GenAI Academy APAC Edition — Track 2: Connect AI agents to real-world data and tools using MCP**.

[Live URL: https://financial-health-agent-867517772734.asia-south1.run.app/](https://financial-health-agent-rnnako34vq-el.a.run.app/)

The agent accepts a natural-language query (e.g. *"Is Apple financially healthy?"* or *"Analyse Infosys vs its peers"*), resolves the ticker, fetches structured financial data through a dedicated MCP server, and returns a **five-dimension scorecard** covering Profitability, Liquidity, Leverage, Growth, and Cash Flow — benchmarked against sector peers.

---

## 🎯 Problem Statement

> Build an AI agent that uses MCP to connect to one external tool or data source, retrieve information, and use that information in its response.

| Requirement | Implementation |
|---|---|
| Implemented using Google ADK | ✅ `agent/agent.py` uses `google-adk` |
| Uses MCP to connect to a data source | ✅ FastMCP server exposing 5 tools |
| Retrieves structured data | ✅ Income statement, balance sheet, cash flow, ratios, peer data |
| Uses retrieved data to generate response | ✅ Gemini 2.5 Flash produces a structured scorecard |

---

## 🏗️ System Architecture

```
User Query (natural language)
        │
        ▼
┌──────────────────────────────┐
│   ADK Agent (Gemini 2.5)    │  Orchestrates tool calls, applies
│   agent/agent.py            │  thresholds, formats scorecard
└──────────────┬───────────────┘
               │ stdio / Cloud Run HTTPS
               ▼
┌──────────────────────────────┐
│   MCP Server (FastMCP)      │  5 tools exposed via MCP protocol
│   mcp_server/server.py      │
└────┬─────────────┬───────────┘
     │             │
     ▼             ▼
┌─────────┐  ┌────────────────┐
│ FMP API │  │   BigQuery     │
│ (live)  │  │ (snapshots +   │
│         │  │  YoY history)  │
└─────────┘  └────────────────┘
```

---

## 📊 Sample Output

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Financial Health Scorecard — Apple Inc. (AAPL)
   Sector: Technology | As of: 2024-09-28
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 PROFITABILITY
   Net Margin         → 23.97%  [Strong]
   Operating Margin   → 31.51%  [Strong]
   ROE                → 160.58% [Strong]
   EPS (latest/prior) → $6.11 / $6.16

💧 LIQUIDITY
   Current Ratio      → 0.87  [Watch]
   Quick Ratio        → 0.83  [Watch]

🏗️  LEVERAGE
   Debt / Equity      → 1.87  [High risk]
   Interest Coverage  → 32.4× [Safe]

📈 GROWTH (Year-over-Year)
   Revenue            → +2.0%  [Low]
   Net Income         → +3.3%
   EPS                → -0.8%  [Declining]

💵 CASH FLOW
   Operating CF       → $118.25B
   Free Cash Flow     → $108.81B  [Healthy]

🏆 PEER BENCHMARKING
   vs MSFT: P/E 35.2 vs 29.1 | Net Margin 35.9% vs 24.0%
   vs GOOGL: ROE 31.4% vs 160.6%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ VERDICT: Healthy
   Apple demonstrates exceptional profitability and cash generation
   with $108B in free cash flow. While liquidity ratios are below
   typical benchmarks, this is by design given Apple's capital
   return programme. Revenue growth is modest, but margins remain
   best-in-class for the sector.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  Disclaimer: For informational purposes only. Not financial advice.
```

---

## 🛠️ MCP Tools

| Tool | Description |
|---|---|
| `get_financials(ticker)` | Income statement, balance sheet, cash flow + computed ratios (margins, current/quick ratio, D/E) for last 3 periods |
| `get_ratios(ticker)` | P/E, P/B, EV/EBITDA, ROE, ROA, interest coverage, dividend yield |
| `get_peers_comparison(ticker)` | Sector peer list with key metrics for benchmarking |
| `save_snapshot(ticker, scorecard)` | Persists scorecard to BigQuery for historical tracking |
| `get_historical(ticker)` | Retrieves past 5 snapshots for YoY trend analysis |

---

## 📁 Project Structure

```
financial-health-agent/
├── agent/
│   ├── __init__.py
│   └── agent.py              # ADK agent: MCP client config + system prompt
├── mcp_server/
│   └── server.py             # FastMCP server: 5 tools, error handling, BQ cache
├── Dockerfile                # Multi-stage build for Cloud Run
├── requirements.txt          # Pinned Python dependencies
├── test_api.py               # Integration test for all MCP tools
└── README.md
```

---

## 🚀 Setup and Installation

### Prerequisites
- Python 3.11+
- Google Cloud project with BigQuery and Cloud Run enabled
- [Financial Modeling Prep](https://financialmodelingprep.com) API key (free tier)
- Google ADK installed

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/financial-health-agent.git
cd financial-health-agent
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Set environment variables

```bash
cp .env.example .env
# Edit .env and fill in:
# FMP_API_KEY=your_fmp_api_key
# GCP_PROJECT_ID=your_gcp_project_id
```

### 4. Run the integration test

```bash
python test_api.py AAPL
```

### 5. Run the agent locally

```bash
adk run agent/
```

---

## ☁️ Cloud Run Deployment

### Create BigQuery table

```bash
bq mk --dataset $GCP_PROJECT_ID:financial_health_agent

bq mk --table \
  $GCP_PROJECT_ID:financial_health_agent.company_snapshots \
  ticker:STRING,snapshot_date:DATE,created_at:TIMESTAMP,scorecard:STRING
```

### Build and deploy the MCP server

```bash
# Build Docker image
gcloud builds submit --tag gcr.io/$GCP_PROJECT_ID/financial-mcp-server

# Deploy to Cloud Run (private — no public access)
gcloud run deploy financial-mcp-server \
  --image gcr.io/$GCP_PROJECT_ID/financial-mcp-server \
  --platform managed \
  --region asia-south1 \
  --no-allow-unauthenticated \
  --set-env-vars FMP_API_KEY=$FMP_API_KEY,GCP_PROJECT_ID=$GCP_PROJECT_ID
```

### Grant the agent's service account invoke permission

```bash
gcloud run services add-iam-policy-binding financial-mcp-server \
  --region asia-south1 \
  --member="serviceAccount:$AGENT_SA@$GCP_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

---

## 🔐 Security

- The MCP server is deployed with `--no-allow-unauthenticated` — only the ADK agent's service account can invoke it via IAM.
- The FMP API key is stored as a Cloud Run secret environment variable, never in source code.
- The Dockerfile uses a non-root user and a minimal slim base image.

---

## 🧠 Agent Reasoning — Analysis Thresholds

The agent's system prompt encodes analyst-grade thresholds so scores are consistently labelled:

| Dimension | Strong | Adequate | Watch/Weak |
|---|---|---|---|
| Net Margin | > 15% | 5–15% | < 5% |
| Operating Margin | > 20% | 10–20% | < 10% |
| ROE | > 15% | 8–15% | < 8% |
| Current Ratio | > 2.0 | 1.2–2.0 | < 1.2 |
| Debt / Equity | < 0.5 | 0.5–1.5 | > 1.5 |
| Revenue Growth | > 10% | 3–10% | < 3% |

---

## 🗂️ Skills Demonstrated

| Category | Skill |
|---|---|
| AI Agent Design | Google ADK, structured system prompting, tool orchestration |
| MCP Protocol | FastMCP server, 5 tool definitions, typed inputs/outputs |
| Data Engineering | FMP REST API, BigQuery insert + parameterised query |
| Cloud Deployment | Cloud Run, Docker multi-stage build, IAM service-to-service auth |
| Financial Analysis | Income statement parsing, ratio computation, peer benchmarking |

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

*Built for GenAI Academy APAC Edition — Track 2 Project Submission*
