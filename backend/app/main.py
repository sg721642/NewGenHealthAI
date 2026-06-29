"""
NewGenHealthAI Backend — main.py
FastAPI application entry point: app setup, lifespan, and router registration.

Module layout:
  core/               — config, logging, state, workflow
  agents/             — 8 individual LangGraph agent nodes
  tools/              — LLM client, vector store, PDF loader, search tools
  db/                 — SQLAlchemy session factory
  models/             — ORM models
  schemas/            — Pydantic request/response schemas
  services/           — DatabaseService, ClinicalEngine
  api/v1/endpoints/   — health, chat, session route handlers
  api/v1/api.py       — router aggregator
  main.py             — FastAPI app + lifespan
"""

import os
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1.api import api_router
from app.api.image_api import router as image_router
from app.core.config import CHAT_DB_PATH, PDF_PATH, VECTOR_STORE_DIR
from app.core.logging_config import logger
from app.services.chat_service import clinical_engine
from app.services.database_service import db_service
from app.tools.pdf_loader import process_pdf
from app.tools.vector_store import get_or_create_vectorstore


# ─────────────────────────────────────────────────────────────
# Lifespan (Startup + Shutdown)
# ─────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    logger.info("Initializing NewGenHealthAI System...")

    # Initialize database
    db_service.init_db()
    logger.info("Database initialized at %s", CHAT_DB_PATH)

    # Process medical PDF and build vector store
    db_exists = False
    if os.path.exists(VECTOR_STORE_DIR) and os.path.isdir(VECTOR_STORE_DIR):
        try:
            db_exists = any(
                f.endswith(".sqlite3") or f == "chroma.sqlite3" or f.startswith("index")
                for f in os.listdir(VECTOR_STORE_DIR)
            )
        except Exception:
            db_exists = False
    
    if db_exists:
        logger.info("Loading existing vector store from %s...", VECTOR_STORE_DIR)
        get_or_create_vectorstore()
    elif os.path.exists(PDF_PATH):
        logger.info("Processing PDF: %s", PDF_PATH)
        documents = process_pdf(PDF_PATH)
        get_or_create_vectorstore(documents)
        logger.info("Vector store ready at %s", VECTOR_STORE_DIR)
    else:
        logger.warning("PDF not found at %s and no pre-built vector store — vector store skipped", PDF_PATH)

    # Initialize LangGraph workflow
    clinical_engine.initialize_workflow()
    logger.info("NewGenHealthAI System Ready!")

    yield

    logger.info("Shutting down NewGenHealthAI...")


# ─────────────────────────────────────────────────────────────
# FastAPI Application
# ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="NewGenHealthAI API",
    description="Professional AI-powered medical consultation system — Clinical Intelligence Engine",
    version="2.1.0",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=secrets.token_hex(32)
)


# ─────────────────────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────────────────────

# Image analysis API
app.include_router(image_router)

# Main API (chat, sessions, health etc.)
app.include_router(api_router)


# ─────────────────────────────────────────────────────────────
# Static File Serving (React Frontend)
# ─────────────────────────────────────────────────────────────
# Serve the built React app from the static directory
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

if os.path.exists(static_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_react_app(request: Request, full_path: str):
        # If the path looks like an API call, let it 404 naturally
        if full_path.startswith("api/") or full_path.startswith("image/"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not Found")
        
        # Otherwise, serve the React index.html for client-side routing
        index_path = os.path.join(static_dir, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        
        return {"detail": "Frontend not found. Please build the frontend first."}
else:
    logger.warning("Static directory not found at %s. Frontend will not be served.", static_dir)


# ─────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
