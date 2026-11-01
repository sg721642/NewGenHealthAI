"""
NewGenHealthAI — backend/scripts/run_fullstack_test_backend.py
Authoritative test server entry point for real full-stack browser QA.
Runs the real FastAPI application with:
- Isolated test SQLite database
- Real session, auth, DB ownership, and API routing
- Real static file serving of built React frontend
- External LLM network calls safely mocked to return deterministic clinical responses
- Zero external network dependency
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Configure test environment
os.environ.setdefault("CHAT_DB_PATH", "/tmp/test_fullstack_phase7a.db")
os.environ.setdefault("ALLOW_MODEL_DOWNLOADS", "false")
os.environ.setdefault("ENVIRONMENT", "development")

from app.main import app
from app.services.chat_service import clinical_engine

# Mock external LLM workflow invocation only (retains real auth, SQLite DB, routers)
mock_workflow = MagicMock()
mock_workflow.ainvoke = AsyncMock(
    return_value={
        "generation": "### Clinical Assessment Summary\n\nIntake assessment recorded. For acute symptoms, maintain fluid intake and rest. Seek emergency care immediately if breathing difficulty, chest tightness, or high persistent fever occurs.\n\n*Informational only: consult a qualified physician.*",
        "source": "clinical-guidelines-intake",
        "is_urgent": False,
        "triage_status": "educational",
        "chat_history": [],
    }
)

original_init = clinical_engine.initialize_workflow

def _mock_init():
    clinical_engine.workflow_app = mock_workflow

clinical_engine.initialize_workflow = _mock_init

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8008"))
    host = os.getenv("HOST", "127.0.0.1")
    print(f"Starting NewGenHealthAI Fullstack Test Server on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")
