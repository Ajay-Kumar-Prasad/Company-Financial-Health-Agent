import os
from google.adk.agents import Agent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioConnectionParams
from mcp import StdioServerParameters

mcp_toolset = MCPToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="python",
            args=["/home/ajayk10440/financial_health_agent/mcp_server/server.py"],
            env={"FMP_API_KEY": os.environ.get("FMP_API_KEY", "")}
        )
    )
)

root_agent = Agent(
    model="gemini-2.5-flash",
    name="financial_health_agent",
    instruction="""You are a financial analyst. Given raw financial data,
produce a structured health scorecard with:
- Profitability: net margin, operating margin, EPS trend
- Liquidity: current ratio, quick ratio
- Leverage: debt-to-equity ratio
- Growth: YoY revenue and earnings growth
- Verdict: plain-English summary - Healthy / Watch / Concerning

Always extract the company ticker from the user query first.""",
    tools=[mcp_toolset]
)
