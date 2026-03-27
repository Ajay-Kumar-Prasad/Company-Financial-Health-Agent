import os
import uvicorn
from google.adk.cli.fast_api import get_fast_api_app

AGENT_DIR = os.path.dirname(os.path.abspath(__file__))

app = get_fast_api_app(
    agents_dir=AGENT_DIR,
    session_service_uri="sqlite+aiosqlite:///./sessions.db",
    allow_origins=["*"],   # wildcards Cloud Shell's *.cloudshell.dev origin
    web=True,
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)