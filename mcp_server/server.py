import os
import requests
from fastmcp import FastMCP
from google.cloud import bigquery
from datetime import date

# Initialize FastMCP server
mcp = FastMCP("financial-health-server")

# Correct base URL (NO /api)
FMP_BASE = "https://financialmodelingprep.com/stable"
API_KEY = os.environ["FMP_API_KEY"]

bq_client = bigquery.Client()

@mcp.tool()
def get_historical(ticker: str) -> list:
    """Retrieve past financial snapshots for year-over-year comparison."""
    query = f"""
        SELECT snapshot_date, scorecard 
        FROM `{os.environ['GCP_PROJECT_ID']}.financial_health_agent.company_snapshots`
        WHERE ticker = '{ticker}'
        ORDER BY snapshot_date DESC
        LIMIT 5
    """
    results = bq_client.query(query).result()
    return [dict(row) for row in results]

@mcp.tool()
def get_financials(ticker: str) -> dict:
    """Get income statement and balance sheet for a company ticker."""
    
    income_url = f"{FMP_BASE}/income-statement"
    balance_url = f"{FMP_BASE}/balance-sheet-statement"
    
    params = {
        "symbol": ticker,
        "apikey": API_KEY,
        "limit": 2
    }
    
    income = requests.get(income_url, params=params).json()
    balance = requests.get(balance_url, params=params).json()
    
    return {
        "income_statement": income,
        "balance_sheet": balance
    }

@mcp.tool()
def get_ratios(ticker: str) -> dict:
    """Get key financial ratios: P/E, debt/equity, current ratio."""
    
    url = f"{FMP_BASE}/ratios"
    
    params = {
        "symbol": ticker,
        "apikey": API_KEY,
        "limit": 2
    }
    
    ratios = requests.get(url, params=params).json()
    
    return {
        "ratios": ratios
    }

if __name__ == "__main__":
    mcp.run()