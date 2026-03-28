"""
Financial Health MCP Server
Exposes structured financial data tools via FastMCP.
Connects to Financial Modeling Prep (FMP) API and caches snapshots in BigQuery.

Supports two transports — selected via the TRANSPORT env var:

  stdio (default)
    Used when ADK spawns this server as a subprocess via StdioConnectionParams.
    The ADK agent.py launches this file directly; no separate server start needed.

        python server.py
        # or set explicitly:
        TRANSPORT=stdio python server.py

  http
    Used for remote / Cloud Run deployments with StreamableHTTPConnectionParams.

        TRANSPORT=http python server.py
        # server starts on http://0.0.0.0:${PORT:-8080}/mcp
"""

import os
import json
import logging
from datetime import date, datetime
from typing import Optional

import time
import requests
from fastmcp import FastMCP
from starlette.responses import JSONResponse


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
_health_app = None

# ── Constants ──────────────────────────────────────────────────────────────────
FMP_BASE        = "https://financialmodelingprep.com/stable"
API_KEY         = os.environ.get("FMP_API_KEY", "")
GCP_PROJECT     = os.environ.get("GCP_PROJECT_ID", "")
BQ_DATASET      = "financial_health_agent"
BQ_TABLE        = "company_snapshots"
REQUEST_TIMEOUT = 25  # seconds

# ── FastMCP server instance ────────────────────────────────────────────────────
mcp = FastMCP(
    name="financial-health-server",
    instructions=(
        "You are a financial analysis assistant. Use the available tools to fetch "
        "income statements, balance sheets, cash flows, valuation ratios, and peer "
        "comparisons for publicly listed companies. Always cite the ticker and period "
        "when presenting data."
    ),
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _fmp_get(endpoint: str, params: dict) -> dict | list:
    """Make a GET request to FMP and raise informative errors."""
    if not API_KEY:
        raise EnvironmentError("FMP_API_KEY environment variable is not set.")
    params["apikey"] = API_KEY
    url = f"{FMP_BASE}/{endpoint}"
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        raise RuntimeError(f"FMP API timed out after {REQUEST_TIMEOUT}s for {endpoint}")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"FMP API HTTP error {resp.status_code}: {e}")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"FMP API request failed: {e}")

    if isinstance(data, dict) and "Error Message" in data:
        raise RuntimeError(f"FMP API error: {data['Error Message']}")
    if isinstance(data, list) and len(data) == 0:
        raise ValueError("No data returned for ticker. Check that the symbol is valid.")
    return data


def _safe_pct(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.2f}%"


def _safe_num(value: Optional[float], decimals: int = 2) -> str:
    if value is None:
        return "N/A"
    return f"{value:,.{decimals}f}"


def _bq_client():
    """Return a BigQuery client, or None if GCP is not configured."""
    if not GCP_PROJECT:
        return None
    try:
        from google.cloud import bigquery
        return bigquery.Client(project=GCP_PROJECT)
    except Exception as e:
        logger.warning(f"BigQuery client init failed: {e}")
        return None


# ── Tools ──────────────────────────────────────────────────────────────────────

@mcp.tool(
    description=(
        "Fetch the last three years of income statement, balance sheet, and cash flow "
        "data for a ticker. Returns revenue, net income, operating income, gross profit, "
        "EPS, EBITDA, margins, debt ratios, liquidity ratios, free cash flow, and "
        "year-over-year growth metrics."
    )
)
def get_financials(ticker: str) -> dict:
    """
    Args:
        ticker: Stock ticker symbol, e.g. 'AAPL', 'INFY', 'TCS.NS'
    """
    ticker = ticker.upper().strip()
    logger.info(f"get_financials called for {ticker}")

    income   = _fmp_get("income-statement",        {"symbol": ticker, "limit": 3})
    balance  = _fmp_get("balance-sheet-statement",  {"symbol": ticker, "limit": 3})
    cashflow = _fmp_get("cash-flow-statement",      {"symbol": ticker, "limit": 3})

    def parse_income(rec: dict) -> dict:
        revenue           = rec.get("revenue") or 0
        net_income        = rec.get("netIncome") or 0
        op_income         = rec.get("operatingIncome") or 0
        gross_profit      = rec.get("grossProfit") or 0
        # FMP reports interestExpense as a negative number; use abs()
        interest_expense  = abs(rec.get("interestExpense") or 0)
        interest_coverage = round(op_income / interest_expense, 2) if interest_expense else None
        return {
            "period":               rec.get("date", "N/A"),
            "revenue":              revenue,
            "gross_profit":         gross_profit,
            "operating_income":     op_income,
            "net_income":           net_income,
            "eps":                  rec.get("eps"),
            "ebitda":               rec.get("ebitda"),
            "interest_expense":     interest_expense,
            "interest_coverage":    interest_coverage,
            "gross_margin_pct":     (gross_profit / revenue * 100) if revenue else None,
            "operating_margin_pct": (op_income   / revenue * 100) if revenue else None,
            "net_margin_pct":       (net_income   / revenue * 100) if revenue else None,
            "revenue_fmt":          f"${revenue/1e9:.2f}B"    if abs(revenue)    >= 1e9 else f"${revenue/1e6:.1f}M",
            "net_income_fmt":       f"${net_income/1e9:.2f}B" if abs(net_income) >= 1e9 else f"${net_income/1e6:.1f}M",
        }

    def parse_balance(rec: dict) -> dict:
        current_assets = rec.get("totalCurrentAssets")    or 0
        current_liab   = rec.get("totalCurrentLiabilities") or 0
        inventory      = rec.get("inventory")              or 0
        total_debt     = rec.get("totalDebt")              or 0
        equity         = rec.get("totalStockholdersEquity") or 0
        total_assets   = rec.get("totalAssets")            or 0
        return {
            "period":               rec.get("date", "N/A"),
            "total_assets":         total_assets,
            "total_debt":           total_debt,
            "cash_and_equivalents": rec.get("cashAndCashEquivalents"),
            "current_assets":       current_assets,
            "current_liabilities":  current_liab,
            "inventory":            inventory,
            "shareholders_equity":  equity,
            "current_ratio":        round(current_assets / current_liab, 2) if current_liab else None,
            "quick_ratio":          round((current_assets - inventory) / current_liab, 2) if current_liab else None,
            "debt_to_equity":       round(total_debt / equity, 2)       if equity       else None,
            "debt_to_assets":       round(total_debt / total_assets, 2) if total_assets else None,
        }

    def parse_cashflow(rec: dict) -> dict:
        return {
            "period":              rec.get("date", "N/A"),
            "operating_cash_flow": rec.get("operatingCashFlow"),
            "free_cash_flow":      rec.get("freeCashFlow"),
            "capex":               rec.get("capitalExpenditure"),
            "dividends_paid":      rec.get("dividendsPaid"),
        }

    income_parsed   = [parse_income(r)   for r in income[:3]]
    balance_parsed  = [parse_balance(r)  for r in balance[:3]]
    cashflow_parsed = [parse_cashflow(r) for r in cashflow[:3]]

    # YoY growth
    yoy = {}
    if len(income_parsed) >= 2:
        curr, prev = income_parsed[0], income_parsed[1]
        def _growth(a, b):
            return round((a - b) / abs(b) * 100, 2) if b and b != 0 else None
        yoy = {
            "revenue_growth_pct":    _growth(curr["revenue"],    prev["revenue"]),
            "net_income_growth_pct": _growth(curr["net_income"], prev["net_income"]),
            "eps_growth_pct":        _growth(curr["eps"] or 0,   prev["eps"] or 0),
        }

    return {
        "ticker":           ticker,
        "as_of":            date.today().isoformat(),
        "income_statement": income_parsed,
        "balance_sheet":    balance_parsed,
        "cash_flow":        cashflow_parsed,
        "yoy_growth":       yoy,
    }


@mcp.tool(
    description=(
        "Fetch key valuation and financial health ratios for a ticker. "
        "Returns P/E, P/B, EV/EBITDA, ROE, ROA, interest coverage, dividend yield, "
        "payout ratio, and margin ratios for the last two periods. Also returns "
        "company profile (sector, industry, market cap, currency)."
    )
)
def get_ratios(ticker: str) -> dict:
    """
    Args:
        ticker: Stock ticker symbol, e.g. 'AAPL', 'MSFT'
    """
    ticker = ticker.upper().strip()
    logger.info(f"get_ratios called for {ticker}")

    ratios  = _fmp_get("ratios",  {"symbol": ticker, "limit": 2})
    profile = _fmp_get("profile", {"symbol": ticker})

    def parse_ratio(rec: dict) -> dict:
        # FMP sometimes omits interestCoverage on the ratios endpoint;
        # keep whatever value is present (agent will use income-statement
        # calculated value from get_financials as the primary source).
        interest_cov = rec.get("interestCoverage")
        return {
            "period":                    rec.get("date", "N/A"),
            "pe_ratio":                  rec.get("priceEarningsRatio"),
            "pb_ratio":                  rec.get("priceToBookRatio"),
            "ev_to_ebitda":              rec.get("enterpriseValueMultiple"),
            "price_to_sales":            rec.get("priceToSalesRatio"),
            "roe":                       rec.get("returnOnEquity"),
            "roe_pct":                   _safe_pct(rec.get("returnOnEquity")),
            "roa":                       rec.get("returnOnAssets"),
            "roa_pct":                   _safe_pct(rec.get("returnOnAssets")),
            "interest_coverage":         interest_cov,   # may be None — use get_financials value
            "dividend_yield":            rec.get("dividendYield"),
            "dividend_yield_pct":        _safe_pct(rec.get("dividendYield")),
            "payout_ratio":              rec.get("payoutRatio"),
            "gross_profit_margin":       rec.get("grossProfitMargin"),
            "net_profit_margin":         rec.get("netProfitMargin"),
            "operating_profit_margin":   rec.get("operatingProfitMargin"),
        }

    company_info = {}
    if isinstance(profile, list) and profile:
        p = profile[0]
        company_info = {
            "name":        p.get("companyName"),
            "sector":      p.get("sector"),
            "industry":    p.get("industry"),
            "country":     p.get("country"),
            "exchange":    p.get("exchange"),
            "market_cap":  p.get("mktCap"),
            "currency":    p.get("currency"),
            "description": (p.get("description") or "")[:300],
        }

    return {
        "ticker":       ticker,
        "company_info": company_info,
        "ratios":       [parse_ratio(r) for r in ratios],
    }


@mcp.tool(
    description=(
        "Fetch a list of industry peers and their basic financial metrics for comparison. "
        "Useful for benchmarking a company's P/E, ROE, net margin, and debt/equity "
        "against sector competitors. Returns up to 4 peers."
    )
)
def get_peers_comparison(ticker: str) -> dict:
    """
    Args:
        ticker: Stock ticker symbol
    """
    ticker = ticker.upper().strip()
    logger.info(f"get_peers_comparison called for {ticker}")

    peers_raw    = _fmp_get("stock-peers", {"symbol": ticker})
    peer_tickers = []
    if isinstance(peers_raw, list) and peers_raw:
        peer_tickers = peers_raw[0].get("peersList", [])[:4]

    peers_data = []
    for peer in peer_tickers:
        time.sleep(1.0)   # 1s gap — FMP free tier rate limit: ~300 req/min
        for attempt in range(2):   # 1 retry on failure
            try:
                r = _fmp_get("ratios",  {"symbol": peer, "limit": 1})
                p = _fmp_get("profile", {"symbol": peer})
                if r and p:
                    ratio   = r[0]
                    profile = p[0] if isinstance(p, list) else p
                    peers_data.append({
                        "ticker":         peer,
                        "name":           profile.get("companyName"),
                        "pe_ratio":       ratio.get("priceEarningsRatio"),
                        "roe_pct":        _safe_pct(ratio.get("returnOnEquity")),
                        "net_margin_pct": _safe_pct(ratio.get("netProfitMargin")),
                        "debt_to_equity": ratio.get("debtEquityRatio"),
                        "market_cap":     profile.get("mktCap"),
                    })
                break   # success — no retry needed
            except Exception as e:
                if attempt == 0:
                    logger.warning(f"Peer {peer} attempt 1 failed ({e}), retrying...")
                    time.sleep(2.0)
                else:
                    logger.warning(f"Peer data fetch failed for {peer}: {e}")

    return {"ticker": ticker, "peers": peers_data}


@mcp.tool(
    description=(
        "Persist a generated financial scorecard to BigQuery for historical tracking. "
        "Requires GCP_PROJECT_ID env var to be set. "
        "Skips silently if BigQuery is not configured."
    )
)
def save_snapshot(ticker: str, scorecard_json: str) -> dict:
    """
    Args:
        ticker:         Stock ticker symbol
        scorecard_json: JSON string of the scorecard produced by the agent
    """
    ticker = ticker.upper().strip()
    client = _bq_client()

    if not client:
        return {"status": "skipped", "reason": "BigQuery not configured (GCP_PROJECT_ID missing)."}

    table_ref = f"{GCP_PROJECT}.{BQ_DATASET}.{BQ_TABLE}"
    row = {
        "ticker":        ticker,
        "snapshot_date": date.today().isoformat(),
        "created_at":    datetime.utcnow().isoformat(),
        "scorecard":     scorecard_json,
    }
    errors = client.insert_rows_json(table_ref, [row])
    if errors:
        return {"status": "error", "errors": errors}

    logger.info(f"Snapshot saved for {ticker}")
    return {"status": "saved", "ticker": ticker, "date": row["snapshot_date"]}


@mcp.tool(
    description=(
        "Retrieve the last 5 stored financial scorecards for a company from BigQuery. "
        "Useful for year-over-year trend analysis. "
        "Requires GCP_PROJECT_ID env var to be set."
    )
)
def get_historical(ticker: str) -> list:
    """
    Args:
        ticker: Stock ticker symbol
    """
    ticker = ticker.upper().strip()
    client = _bq_client()

    if not client:
        return [{"status": "skipped", "reason": "BigQuery not configured."}]

    query = f"""
        SELECT snapshot_date, scorecard
        FROM `{GCP_PROJECT}.{BQ_DATASET}.{BQ_TABLE}`
        WHERE ticker = @ticker
        ORDER BY snapshot_date DESC
        LIMIT 5
    """
    from google.cloud import bigquery as bq
    job_config = bq.QueryJobConfig(
        query_parameters=[bq.ScalarQueryParameter("ticker", "STRING", ticker)]
    )
    try:
        results = client.query(query, job_config=job_config).result()
        return [dict(row) for row in results]
    except Exception as e:
        logger.error(f"BigQuery query failed: {e}")
        return [{"status": "error", "reason": str(e)}]


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    transport = os.environ.get("TRANSPORT", "stdio").lower()

    if transport == "http":
        port = int(os.environ.get("PORT", 8080))
        logger.info(f"Starting MCP Server (SSE) on port {port}")
        # Use SSE transport instead of streamable-http
        mcp.run(transport="sse", host="0.0.0.0", port=port, path="/sse")
    else:
        logging.disable(logging.CRITICAL)
        mcp.run(transport="stdio")