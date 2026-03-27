"""
Integration test for the Financial Health MCP server tools.
Run this before deploying to confirm the FMP API key is valid
and all tools return expected data shapes.

Usage:
    export FMP_API_KEY=your_key_here
    python test_api.py [TICKER]          # default: AAPL
"""

import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()

# Add project root to path so we can import the server directly
sys.path.insert(0, os.path.dirname(__file__))
from mcp_server.server import get_financials, get_ratios, get_peers_comparison

TICKER = sys.argv[1].upper() if len(sys.argv) > 1 else "AAPL"
DIVIDER = "─" * 60


def _section(title: str):
    print(f"\n{DIVIDER}")
    print(f"  {title}")
    print(DIVIDER)


def test_financials():
    _section(f"get_financials('{TICKER}')")
    data = get_financials(TICKER)

    latest = data["income_statement"][0]
    bal    = data["balance_sheet"][0]
    yoy    = data["yoy_growth"]

    print(f"  Period        : {latest['period']}")
    print(f"  Revenue       : {latest['revenue_fmt']}")
    print(f"  Net Income    : {latest['net_income_fmt']}")
    print(f"  Net Margin    : {latest['net_margin_pct']:.1f}%" if latest['net_margin_pct'] else "  Net Margin    : N/A")
    print(f"  Op. Margin    : {latest['operating_margin_pct']:.1f}%" if latest['operating_margin_pct'] else "  Op. Margin    : N/A")
    print(f"  Current Ratio : {bal['current_ratio']}")
    print(f"  Quick Ratio   : {bal['quick_ratio']}")
    print(f"  Debt/Equity   : {bal['debt_to_equity']}")
    print(f"  Revenue YoY   : {yoy.get('revenue_growth_pct')}%")
    print(f"  EPS YoY       : {yoy.get('eps_growth_pct')}%")
    print("   get_financials OK")
    return data


def test_ratios():
    _section(f"get_ratios('{TICKER}')")
    data = get_ratios(TICKER)

    info  = data["company_info"]
    ratio = data["ratios"][0] if data["ratios"] else {}

    print(f"  Company   : {info.get('name')}")
    print(f"  Sector    : {info.get('sector')}")
    print(f"  Industry  : {info.get('industry')}")
    print(f"  P/E Ratio : {ratio.get('pe_ratio')}")
    print(f"  ROE       : {ratio.get('roe_pct')}")
    print(f"  ROA       : {ratio.get('roa_pct')}")
    print(f"  Div Yield : {ratio.get('dividend_yield_pct')}")
    print("  get_ratios OK")
    return data


def test_peers():
    _section(f"get_peers_comparison('{TICKER}')")
    data = get_peers_comparison(TICKER)

    peers = data.get("peers", [])
    if peers:
        for p in peers:
            print(f"  {p['ticker']:6s}  P/E={p['pe_ratio']}  ROE={p['roe_pct']}  NetMargin={p['net_margin_pct']}")
    else:
        print("  (no peers found)")
    print("   get_peers_comparison OK")
    return data


if __name__ == "__main__":
    if not os.environ.get("FMP_API_KEY"):
        print("ERROR: FMP_API_KEY environment variable is not set.")
        sys.exit(1)

    print(f"\n  Financial Health MCP — Integration Test  |  ticker={TICKER}\n")

    try:
        fin   = test_financials()
        rat   = test_ratios()
        peers = test_peers()

        print(f"\n{DIVIDER}")
        print("   All tests passed — MCP server is ready for deployment.")
        print(DIVIDER)

    except Exception as e:
        print(f"\n  Test failed: {e}")
        sys.exit(1)