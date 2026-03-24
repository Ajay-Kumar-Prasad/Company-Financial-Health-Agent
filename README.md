# 🏦 Company Financial Health Agent

> An AI agent built with Google ADK and Model Context Protocol (MCP) that retrieves live financial data and generates a structured health scorecard for any public company.

---

## 📌 Project Overview

This project was built as part of the **GenAI Academy APAC Edition — Track 2: Connect AI agents to real-world data and tools using Model Context Protocol (MCP)**.

The agent accepts a company name or ticker (e.g. "Analyse Apple" or "How is Infosys doing?"), fetches structured financial data from the Financial Modeling Prep (FMP) API via an MCP server, optionally caches historical snapshots in BigQuery, and returns a plain-English **Financial Health Scorecard** covering profitability, liquidity, leverage, and growth.

---

## 🎯 Problem Statement

> Build an AI agent that uses the Model Context Protocol (MCP) to connect to one external tool or data source, retrieve information, and use that information in its response.

This agent satisfies all four requirements:
1. ✅ Implemented using **Google ADK**
2. ✅ Uses **MCP** to connect to the FMP financial data API
3. ✅ Retrieves structured financial data (income statement, balance sheet, key ratios)
4. ✅ Uses retrieved data to generate a structured health scorecard response

---

## 🏗️ System Architecture

```
User Query
    │
    ▼
┌─────────────────────────────┐
│      ADK Agent (Python)     │  ← Orchestrates tools, reasons, generates response
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│   MCP Client (ADK built-in) │  ← Translates tool calls to MCP protocol
└─────────────┬───────────────┘
              │  IAM service-to-service auth
              ▼
┌─────────────────────────────┐
│   MCP Server (Cloud Run)    │  ← Exposes tools: get_financials, get_ratios
└──────┬──────────────┬───────┘
       │              │
       ▼              ▼
┌────────────┐  ┌──────────────┐
│  FMP API   │  │   BigQuery   │
│ (free tier)│  │  (cache +    │
│            │  │  snapshots)  │
└────────────┘  └──────────────┘
```

---

## 📊 What the Agent Produces

For any company the user queries, the agent returns a **Financial Health Scorecard**:

| Category | Metrics |
|---|---|
| **Profitability** | Net profit margin, operating margin, EPS trend |
| **Liquidity** | Current ratio, quick ratio |
| **Leverage** | Debt-to-equity ratio |
| **Growth** | YoY revenue and earnings growth |
| **Verdict** | Plain-English summary: Healthy / Watch / Concerning |

**Example query:** *"Is Infosys financially healthy compared to last year?"*

**Example output:**
```
📊 Financial Health Scorecard — Infosys (INFY)

Profitability  : Net margin 17.2% ↑ | Operating margin 21.4%
Liquidity      : Current ratio 2.1 (Healthy)
Leverage       : Debt-to-equity 0.09 (Very low risk)
Growth         : Revenue +6.2% YoY | EPS +8.4% YoY

Verdict: Infosys shows strong financial health with low debt, 
improving margins, and consistent earnings growth. The company 
is well-positioned with minimal leverage risk.
```

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| Agent framework | Google ADK |
| MCP server | FastMCP (Python) |
| Financial data | Financial Modeling Prep API (free tier) |
| Historical storage | Google BigQuery |
| Deployment | Google Cloud Run |
| Auth | IAM service accounts |
| Language | Python 3.11+ |

---

## 📁 Project Structure

```
financial-health-agent/
├── agent/
│   └── agent.py              # ADK agent definition + MCP client config
├── mcp_server/
│   └── server.py             # MCP server with get_financials and get_ratios tools
├── Dockerfile                # Container config for Cloud Run deployment
├── requirements.txt          # Python dependencies
└── README.md
```

---

## 🚀 Build Roadmap

### Phase 1 — Project Setup (~1 hour)
- Create Python project structure
- Install dependencies: `google-adk`, `fastmcp`, `requests`, `google-cloud-bigquery`
- Sign up for a free API key at [financialmodelingprep.com](https://financialmodelingprep.com)

### Phase 2 — MCP Server (~2 hours)
Build two tools in `mcp_server/server.py` using `fastmcp`:
- `get_financials(ticker)` → calls FMP income statement + balance sheet endpoints
- `get_ratios(ticker)` → calls FMP key ratios endpoint (P/E, debt/equity, current ratio)

Both tools return clean JSON the agent can reason over.

### Phase 3 — ADK Agent (~2 hours)
In `agent/agent.py`, define an ADK agent that:
- Connects to the MCP server as an MCP client
- Uses a system prompt: *"You are a financial analyst. Given raw financial data, produce a structured health scorecard with Profitability, Liquidity, Leverage, Growth, and a plain-English Verdict."*
- Handles the full conversation loop

### Phase 4 — BigQuery Cache (~1–2 hours)
- Create a BigQuery dataset and table: `company_snapshots`
- After every FMP API call, write the result to BigQuery with a timestamp
- Add a `get_historical(ticker)` tool to retrieve past snapshots for year-over-year comparisons

### Phase 5 — Deploy to Cloud Run (~2 hours)
- Write a `Dockerfile` for the MCP server
- Deploy the MCP server to Cloud Run
- Configure IAM so only the ADK agent's service account can call it
- Point the agent to the Cloud Run URL

### Phase 6 — Test and Demo (~1 hour)
Test with queries such as:
- *"How is Apple doing financially?"*
- *"Is Infosys a healthy company?"*
- *"Compare TCS revenue growth to last year"*

---

## ⚙️ Setup and Installation

### Prerequisites
- Python 3.11+
- Google Cloud project with BigQuery and Cloud Run enabled
- Financial Modeling Prep API key (free tier)
- Google ADK installed

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/financial-health-agent.git
cd financial-health-agent
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set environment variables

```bash
export FMP_API_KEY=your_fmp_api_key_here
export GCP_PROJECT_ID=your_gcp_project_id
export MCP_SERVER_URL=https://your-cloud-run-url
```

### 4. Run the MCP server locally

```bash
python mcp_server/server.py
```

### 5. Run the ADK agent

```bash
adk run agent/agent.py
```

---

## ☁️ Cloud Run Deployment

```bash
# Build and push Docker image
gcloud builds submit --tag gcr.io/$GCP_PROJECT_ID/financial-mcp-server

# Deploy to Cloud Run
gcloud run deploy financial-mcp-server \
  --image gcr.io/$GCP_PROJECT_ID/financial-mcp-server \
  --platform managed \
  --region asia-south1 \
  --no-allow-unauthenticated
```

---

## 🔐 Authentication

Service-to-service authentication is handled via **IAM roles**. The ADK agent runs with a service account that has the `roles/run.invoker` role on the Cloud Run MCP server. This ensures no public access to the server — only the agent can call it.

---

## 🗂️ Skills Demonstrated

This project directly applies skills from both tracks of the GenAI Academy APAC Edition:

| Track | Skill Applied |
|---|---|
| Track 1 | ADK agent design, tool-using agents, structured prompting |
| Track 2 | MCP server implementation, BigQuery integration, Cloud Run deployment, IAM auth |

---

## 🌐 Live Demo

- **Cloud Run URL:** `https://your-cloud-run-url` *(replace after deployment)*
- **GitHub Repository:** `https://github.com/<your-username>/financial-health-agent`

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

*Built for GenAI Academy APAC Edition — Track 2 Project Submission*